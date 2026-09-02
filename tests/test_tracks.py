"""Track construction: the fix for the star-shaped pose graph.

The synthetic scene makes these testable at all -- we know by construction which
keypoints across which images belong to the same 3D point.
"""

import numpy as np

from sfmkit.tracks import UnionFind, build_tracks, track_statistics
from sfmkit.types import Matches


class TestUnionFind:
    def test_merges_transitively(self):
        uf = UnionFind()
        uf.union(("a", 0), ("b", 1))
        uf.union(("b", 1), ("c", 2))
        assert uf.find(("a", 0)) == uf.find(("c", 2))

    def test_keeps_disjoint_sets_apart(self):
        uf = UnionFind()
        uf.union(("a", 0), ("b", 1))
        uf.union(("c", 2), ("d", 3))
        assert uf.find(("a", 0)) != uf.find(("c", 2))
        assert len(uf.groups()) == 2

    def test_is_idempotent(self):
        uf = UnionFind()
        for _ in range(5):
            uf.union(("a", 0), ("b", 1))
        assert len(uf.groups()) == 1


def _matches(a, b, pairs, n=10):
    kp = np.zeros((n, 2))
    return Matches(a, b, kp, kp, np.asarray(pairs, dtype=np.intp))


class TestBuildTracks:
    def test_transitivity_links_unmatched_images(self):
        """A-B and B-C matches must produce one A-B-C track, with no A-C match."""
        tracks = build_tracks([_matches("A", "B", [[0, 0]]), _matches("B", "C", [[0, 0]])])
        assert len(tracks) == 1
        assert tracks[0].images() == {"A", "B", "C"}

    def test_rejects_tracks_seeing_one_image_twice(self):
        """A point cannot project to two places in the same photo."""
        tracks = build_tracks([
            _matches("A", "B", [[0, 0]]),
            _matches("B", "C", [[0, 0]]),
            _matches("C", "A", [[0, 1]]),  # closes a loop onto a different keypoint in A
        ])
        assert tracks == []

    def test_respects_min_length(self):
        m = [_matches("A", "B", [[0, 0]]), _matches("B", "C", [[0, 0]])]
        assert len(build_tracks(m, min_length=2)) == 1
        assert len(build_tracks(m, min_length=4)) == 0

    def test_no_matches_gives_no_tracks(self):
        assert build_tracks([]) == []

    def test_recovers_ground_truth_tracks(self, scene):
        """On noiseless synthetic data, tracks must match the generator exactly."""
        matches = []
        for i, a in enumerate(scene.images):
            for b in scene.images[i + 1:]:
                matches.append(scene.matches_for(a, b))
        tracks = build_tracks(matches)

        # Every track must correspond to exactly one true 3D point.
        for tr in tracks:
            point_ids = {int(scene.visible[img][kp]) for img, kp in tr.observations.items()}
            assert len(point_ids) == 1, "a track mixed two different 3D points"

        # And every point seen by >= 2 cameras must produce a track.
        seen = {}
        for img in scene.images:
            for pid in scene.visible[img]:
                seen[int(pid)] = seen.get(int(pid), 0) + 1
        expected = sum(1 for c in seen.values() if c >= 2)
        assert len(tracks) == expected

    def test_track_lengths_exceed_two_on_a_full_graph(self, scene):
        """The whole point: a complete match graph yields multi-view tracks."""
        matches = []
        for i, a in enumerate(scene.images):
            for b in scene.images[i + 1:]:
                matches.append(scene.matches_for(a, b))
        stats = track_statistics(build_tracks(matches))
        assert stats["mean_length"] > 2.5
        assert stats["max_length"] == len(scene.images)

    def test_star_graph_cannot_reach_points_the_reference_misses(self, scene):
        """The original topology's actual defect, expressed as a test.

        A star graph still chains transitively -- two non-reference cameras are
        linked through a shared reference keypoint, so tracks do span many views.
        What it cannot do is reconstruct a point the reference never sees: with
        no reference keypoint to act as the hub, those observations never meet.
        """
        ref = scene.images[0]
        star = build_tracks([scene.matches_for(ref, b) for b in scene.images[1:]])
        full = build_tracks([
            scene.matches_for(a, b)
            for i, a in enumerate(scene.images)
            for b in scene.images[i + 1:]
        ])

        # Chaining happens in both: the star is not limited to pairwise tracks.
        assert track_statistics(star)["max_length"] > 2

        # But the star reconstructs strictly fewer points and constraints.
        assert len(full) > len(star)
        assert sum(t.length for t in full) > sum(t.length for t in star)

        # Every star track must involve the reference; that is the limitation.
        assert all(ref in t.images() for t in star)

        # And the points the reference misses are exactly what the star loses.
        seen_by_ref = set(scene.visible[ref].tolist())
        counts: dict[int, int] = {}
        for img in scene.images:
            for pid in scene.visible[img]:
                counts[int(pid)] = counts.get(int(pid), 0) + 1
        orphans = [p for p, c in counts.items() if c >= 2 and p not in seen_by_ref]
        assert len(orphans) > 0
        assert len(full) - len(star) == len(orphans)


class TestStatistics:
    def test_empty(self):
        assert track_statistics([])["n_tracks"] == 0

    def test_histogram_sums_to_track_count(self, scene):
        matches = [scene.matches_for(scene.images[0], b) for b in scene.images[1:]]
        stats = track_statistics(build_tracks(matches))
        assert sum(stats["length_histogram"].values()) == stats["n_tracks"]
