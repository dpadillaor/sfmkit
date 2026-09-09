"""Feature tracks: turning pairwise matches into multi-view correspondences.

A track is a connected component of the match graph, whose nodes are
``(image, keypoint index)`` and whose edges are verified matches. The value is
transitivity: if keypoint *a* in image A matches *b* in B, and *b* matches *c*
in C, then *a*, *b* and *c* are one 3D point seen from three cameras -- even
though A and C were never matched directly.

The original pipeline only ever consumed pairs involving the reference image, so
its match graph was a star. Transitivity still applies to a star -- two
non-reference cameras do get linked, through a shared reference keypoint acting
as the hub -- so the defect is narrower than "no cross-camera constraints", and
worth stating precisely:

* a point the reference never sees has no hub, so its observations never meet
  and it cannot be reconstructed at all;
* every match not involving the reference is discarded, removing constraints
  between the cameras that do share it.

Measured on a 5-camera synthetic scene: a star graph yields 236 tracks and 1007
observations against 296 and 1202 for the complete graph, and 20% of the points
visible in two or more cameras are unreachable. See ``tests/test_tracks.py``.
"""

from __future__ import annotations

from collections import defaultdict

from sfmkit.core.types import Matches, Track

__all__ = ["UnionFind", "build_tracks", "track_statistics"]


class UnionFind:
    """Disjoint-set forest with path compression and union by size."""

    def __init__(self) -> None:
        self._parent: dict[tuple[str, int], tuple[str, int]] = {}
        self._size: dict[tuple[str, int], int] = {}

    def find(self, x):
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

    def union(self, a, b) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._size[ra] < self._size[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        self._size[ra] += self._size[rb]

    def groups(self) -> dict:
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

    Tracks that observe the same image twice are dropped: one 3D point cannot
    project to two places in one photo, so such a component is the result of a
    mismatch somewhere along the chain. This is the standard filter and it
    catches real matching errors -- discarding the whole component is
    deliberately conservative, since we cannot tell which link is the bad one.

    ``max_length`` guards against a degenerate component swallowing most of the
    graph; ``None`` means "at most one observation per image", the natural cap.
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
