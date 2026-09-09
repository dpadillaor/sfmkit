"""Feature tracks: group pairwise matches into multi-view correspondences.

A track is one 3D point together with every image observation of it."""

from __future__ import annotations

from collections import defaultdict

from sfmkit.core.types import Matches, Track

__all__ = ["ImageName", "KeypointIndex", "Node", "UnionFind", "build_tracks",
           "track_statistics"]

ImageName = str
KeypointIndex = int
Node = tuple[ImageName, KeypointIndex]


class UnionFind:
    """Groups keypoints that are the same 3D point.

    One :meth:`union` per verified match; :meth:`groups` returns what formed.
    Disjoint-set forest with path compression and union by size.
    """

    def __init__(self) -> None:
        self._parent: dict[Node, Node] = {}
        self._size: dict[Node, int] = {}

    def find(self, x: Node) -> Node:
        """The root of ``x``'s group, creating the group if ``x`` is new."""
        parent = self._parent
        if x not in parent:
            parent[x] = x
            self._size[x] = 1
            return x
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:  # path compression
            parent[x], x = root, parent[x]
        return root

    def union(self, a: Node, b: Node) -> None:
        """Put ``a`` and ``b`` in the same group, merging transitively."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._size[ra] < self._size[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        self._size[ra] += self._size[rb]

    def groups(self) -> dict[Node, list[Node]]:
        """Every group so far, as ``{label: [keypoints]}``. One group, one 3D point."""
        out = defaultdict(list)
        for node in self._parent:
            out[self.find(node)].append(node)
        return out


def build_tracks(
    matches: list[Matches],
    *,
    min_length: int = 2,
    max_length: int | None = None,
) -> list[Track]:
    """Group verified matches into tracks.

    Tracks observing the same image twice are discarded: a single 3D point
    cannot project to two places in one photograph, so such a component contains
    a mismatch somewhere along its chain. Dropping the whole component is
    conservative, since which link is wrong cannot be determined locally.

    ``max_length`` bounds a degenerate component; ``None`` caps it at one
    observation per image.
    """
    uf = UnionFind()
    for m in matches:
        for i, j in m.verified_pairs():
            uf.union((m.image0, int(i)), (m.image1, int(j)))

    cap = max_length if max_length is not None else len({m.image0 for m in matches} |
                                                        {m.image1 for m in matches})

    tracks: list[Track] = []
    for nodes in uf.groups().values():
        if len(nodes) < min_length or len(nodes) > cap:
            continue
        obs: dict[str, int] = {}
        conflict = False
        for image, kp in nodes:
            if image in obs:
                conflict = True
                break
            obs[image] = kp
        if not conflict and len(obs) >= min_length:
            tracks.append(Track(observations=obs))
    return tracks


def track_statistics(tracks: list[Track]) -> dict:
    """Summary used for reporting and for regression tests."""
    if not tracks:
        return {"n_tracks": 0, "mean_length": 0.0, "max_length": 0, "length_histogram": {}}
    lengths = [t.length for t in tracks]
    hist: dict[int, int] = {}
    for n in lengths:
        hist[n] = hist.get(n, 0) + 1
    return {
        "n_tracks": len(tracks),
        "mean_length": float(sum(lengths) / len(lengths)),
        "max_length": max(lengths),
        "length_histogram": dict(sorted(hist.items())),
    }
