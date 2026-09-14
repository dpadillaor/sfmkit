"""Incremental Structure-from-Motion: build a reconstruction one camera at a time."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from sfmkit.core.bundle import solve_bundle
from sfmkit.core.bundle_schur import solve_bundle_schur
from sfmkit.core.geometry import (
    fundamental_to_essential,
    project,
    recover_pose,
    triangulate_multi_view,
    triangulate_two_view,
)
from sfmkit.core.robust import ransac_fundamental, ransac_pnp
from sfmkit.core.types import Matches, Pose, Reconstruction, Track

__all__ = ["BUNDLE_SOLVERS", "ReconstructionConfig", "StageReport", "reconstruct"]

# The same bundle adjustment, two solvers: our Levenberg-Marquardt with an
# analytic Jacobian and the Schur complement, or scipy's generic least squares,
# 58x slower on Valencia and stopped short of the minimum: see the site's Results.
BUNDLE_SOLVERS = {"scipy": solve_bundle, "schur": solve_bundle_schur}


@dataclass
class ReconstructionConfig:
    """Thresholds and limits for ``reconstruct``.

    The three that matter most were chosen by grid search against COLMAP rather
    than by intuition, and two behave counter-intuitively: a tighter
    ``max_reprojection_error`` registers fewer cameras, and raising
    ``min_triangulation_angle_deg`` from 0.5 to 2 degrees registers more.
    """

    reference: str | None = None
    seed: int = 0
    ransac_threshold: float = 4.0
    ransac_iterations: int = 1000
    # These three were chosen by a grid search over 64 combinations, scored
    # against COLMAP, not by intuition. A tighter reprojection threshold sounds
    # safer and is not: it discards points that a later bundle adjustment would
    # have pulled into line, leaving new cameras too few correspondences to
    # register. A larger triangulation angle likewise *increases* the number of
    # cameras registered, by refusing badly conditioned points that would
    # otherwise corrupt the PnP that depends on them.
    pnp_threshold: float = 6.0
    min_track_length: int = 2
    min_triangulation_angle_deg: float = 2.0
    max_reprojection_error: float = 12.0
    observation_filter_factor: float = 4.0
    min_pnp_correspondences: int = 30
    min_pnp_inliers: int = 20
    bundle_every_camera: bool = True
    bundle_solver: str = "schur"
    final_refinements: int = 3
    max_cameras: int | None = None

    def __post_init__(self) -> None:
        if self.bundle_solver not in BUNDLE_SOLVERS:
            raise ValueError(f"bundle_solver must be one of {tuple(BUNDLE_SOLVERS)}, "
                             f"not {self.bundle_solver!r}")


@dataclass
class StageReport:
    """One row of the reconstruction log: what happened when a camera was added.

    ``n_pnp_correspondences`` is the inlier count from the PnP that registered
    it, and is the clearest signal of how well supported that camera is.
    """

    step: int
    image: str
    n_registered: int
    n_points: int
    n_pnp_correspondences: int
    rmse_before: float = float("nan")
    rmse_after: float = float("nan")
    bundle_seconds: float = 0.0
    bundle_iterations: int = 0
    n_filtered: int = 0


@dataclass(frozen=True, eq=False)
class Snapshot:
    """The reconstruction as it stood when a step was done, copied for a caller
    to show while the next step runs."""

    report: StageReport
    poses: dict[str, Pose]
    points: np.ndarray  # (N, 3), the triangulated points only


@dataclass
class ReconstructionResult:
    """A finished reconstruction, plus how it got there.

    ``before_refinement`` is the state saved immediately before the final global
    refinement, so the two can be compared directly.
    """

    reconstruction: Reconstruction
    reports: list[StageReport] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    # State just before the final global refinement, so "before and after
    # bundle adjustment" figures compare two real reconstructions rather than
    # one reconstruction and a guess.
    before_refinement: Reconstruction | None = None

    @property
    def rmse(self) -> float:
        return self.reports[-1].rmse_after if self.reports else float("nan")


def _keypoints_by_image(matches: list[Matches]) -> dict[str, np.ndarray]:
    kp: dict[str, np.ndarray] = {}
    for m in matches:
        kp.setdefault(m.image0, m.keypoints0)
        kp.setdefault(m.image1, m.keypoints1)
    return kp


def _pair_index(matches: list[Matches]) -> dict[tuple[str, str], Matches]:
    return {(m.image0, m.image1): m for m in matches}


def _triangulation_angle(centres: list[np.ndarray], X: np.ndarray) -> float:
    """Largest angle subtended at ``X`` by any pair of camera centres, in degrees."""
    if len(centres) < 2:
        return 0.0
    rays = [c - X for c in centres]
    rays = [r / n for r, n in ((r, np.linalg.norm(r)) for r in rays) if n > 1e-9]
    best = 0.0
    for i in range(len(rays)):
        for j in range(i + 1, len(rays)):
            best = max(best, float(np.degrees(np.arccos(np.clip(rays[i] @ rays[j], -1, 1)))))
    return best


def _triangulate_tracks(rec: Reconstruction, keypoints, cfg: ReconstructionConfig) -> int:
    """(Re)triangulate every track visible in >= 2 registered cameras."""
    n_new = 0
    for i, track in enumerate(rec.tracks):
        views = [(img, kp) for img, kp in track.observations.items() if img in rec.poses]
        if len(views) < 2:
            rec.points[i] = np.nan
            continue
        obs = [(keypoints[img][kp], rec.poses[img].projection_matrix(rec.K)) for img, kp in views]
        X = triangulate_multi_view(obs)
        if not np.isfinite(X).all():
            rec.points[i] = np.nan
            continue
        # Cheirality: the point must be in front of every camera that sees it.
        if any(rec.poses[img].transform(X[None])[0, 2] <= 0 for img, _ in views):
            rec.points[i] = np.nan
            continue
        centres = [rec.poses[img].center for img, _ in views]
        if _triangulation_angle(centres, X) < cfg.min_triangulation_angle_deg:
            rec.points[i] = np.nan
            continue
        errs = np.array([
            np.linalg.norm(project(X[None], rec.K, rec.poses[img])[0] - keypoints[img][kp])
            for img, kp in views
        ])
        # Median, not max: a single bad view in a nine-view track should not
        # discard the point, which is exactly what long tracks are for.
        if not np.all(np.isfinite(errs)) or float(np.median(errs)) > cfg.max_reprojection_error:
            rec.points[i] = np.nan
            continue
        was_new = not np.isfinite(rec.points[i]).all()
        rec.points[i] = X
        n_new += was_new
    return n_new


def _filter_observations(rec: Reconstruction, keypoints, cfg: ReconstructionConfig) -> int:
    """Drop observations that grossly disagree with the current estimate.

    Deletion is permanent, so the threshold here is deliberately loose
    (``observation_filter_factor`` times the triangulation threshold): the
    bundle adjustment's robust loss already handles moderate outliers, and this
    only removes correspondences that are plainly wrong. Filtering at the
    triangulation threshold instead throws away good matches that merely look
    bad while a pose is still being refined.
    """
    removed = 0
    ok = rec.triangulated_mask()
    for i, track in enumerate(rec.tracks):
        if not ok[i]:
            continue
        X = rec.points[i][None]
        bad = []
        for img, kp in track.observations.items():
            if img not in rec.poses:
                continue
            uv = project(X, rec.K, rec.poses[img])[0]
            err = np.inf if not np.isfinite(uv).all() else np.linalg.norm(uv - keypoints[img][kp])
            if err > cfg.observation_filter_factor * cfg.max_reprojection_error:
                bad.append(img)
        for img in bad:
            del track.observations[img]
            removed += 1
        if sum(1 for im in track.observations if im in rec.poses) < 2:
            rec.points[i] = np.nan  # no longer supported by the registered cameras
    return removed


def _observations_array(rec: Reconstruction, keypoints, images: list[str]) -> np.ndarray:
    """``(M, 4)`` rows of track index, camera index, u, v -- the bundle's input."""
    cam_of = {name: i for i, name in enumerate(images)}
    ok = rec.triangulated_mask()
    rows = []
    for t, track in enumerate(rec.tracks):
        if not ok[t]:
            continue
        for img, kp in track.observations.items():
            if img in cam_of:
                u, v = keypoints[img][kp]
                rows.append((t, cam_of[img], u, v))
    return np.asarray(rows, dtype=float) if rows else np.zeros((0, 4))


def _run_bundle(rec: Reconstruction, keypoints, images: list[str], report: StageReport,
                cfg: ReconstructionConfig) -> None:
    """Optimise every registered camera and every triangulated point together."""
    obs = _observations_array(rec, keypoints, images)
    if len(obs) < 20 or len(images) < 2:
        return
    used = np.unique(obs[:, 0].astype(int))
    remap = {t: k for k, t in enumerate(used)}
    obs_local = obs.copy()
    obs_local[:, 0] = [remap[int(t)] for t in obs[:, 0]]

    solve = BUNDLE_SOLVERS[cfg.bundle_solver]
    result = solve(rec.K, images, rec.poses, rec.points[used], obs_local)
    rec.poses.update(result.poses)
    rec.points[used] = result.points
    report.rmse_before = result.rmse_before
    report.rmse_after = result.rmse_after
    report.bundle_seconds = result.seconds
    report.bundle_iterations = result.n_iterations


def _initial_pair_score(m: Matches, K: np.ndarray, seed: int, cfg: ReconstructionConfig) -> float:
    """Rank a candidate seed pair by inliers *and* parallax.

    Inlier count alone picks the pair whose images are most alike, which is
    usually the pair with the shortest baseline -- and a short baseline gives
    badly conditioned depth, so the initial points are poor and every camera
    registered against them by PnP inherits the error. COLMAP scores candidate
    initial pairs the same way, on inliers and triangulation angle together.

    Returns the number of inliers whose triangulation angle is usable, which
    combines both criteria in one number.
    """
    x0, x1 = m.points()
    if len(x0) < 30:
        return 0.0
    res = ransac_fundamental(x0, x1, threshold=cfg.ransac_threshold,
                             max_iterations=200, seed=seed)
    if res.model is None:
        return 0.0
    E = fundamental_to_essential(res.model, K, K)
    try:
        rel = recover_pose(E, K, x0[res.inliers], x1[res.inliers])
    except np.linalg.LinAlgError:
        return 0.0
    rel = Pose(rel.R, rel.t / (np.linalg.norm(rel.t) or 1.0))

    X = triangulate_two_view(x0[res.inliers], x1[res.inliers], K, Pose.identity(), K, rel)
    ok = np.isfinite(X).all(axis=1) & (X[:, 2] > 0)
    if ok.sum() < 30:
        return 0.0
    centres = [np.zeros(3), rel.center]
    angles = np.array([_triangulation_angle(centres, x) for x in X[ok]])
    return float((angles > cfg.min_triangulation_angle_deg).sum())


def _best_initial_pair(matches, K, cfg: ReconstructionConfig) -> Matches:
    """The pair with the most well-conditioned inliers, preferring the reference."""
    candidates = [m for m in matches if m.n_inliers >= 30] or list(matches)
    if cfg.reference is not None:
        with_ref = [m for m in candidates if cfg.reference in (m.image0, m.image1)]
        candidates = with_ref or candidates
    scored = [(_initial_pair_score(m, K, cfg.seed, cfg), m) for m in candidates]
    best = max(scored, key=lambda s: s[0])
    if best[0] <= 0:
        return max(candidates, key=lambda m: m.n_inliers)
    return best[1]


def reconstruct(
    matches: list[Matches],
    K: np.ndarray,
    tracks: list[Track],
    cfg: ReconstructionConfig | None = None,
    on_step: Callable[[Snapshot], None] | None = None,
) -> ReconstructionResult:
    """Build a reconstruction from verified matches and precomputed tracks.

    ``on_step`` is handed a snapshot as soon as each step is done, so a caller
    can show progress, or the model growing; the reports are also returned
    together.
    """
    cfg = cfg or ReconstructionConfig()
    keypoints = _keypoints_by_image(matches)
    pairs = _pair_index(matches)

    rec = Reconstruction(K=np.asarray(K, dtype=float), tracks=list(tracks))
    rec.points = np.full((len(rec.tracks), 3), np.nan)
    reports: list[StageReport] = []

    def done(report: StageReport) -> None:
        reports.append(report)
        if on_step is not None:
            triangulated = np.isfinite(rec.points).all(axis=1)
            on_step(Snapshot(report, dict(rec.poses), rec.points[triangulated].copy()))

    # ---- seed the reconstruction from one pair ----------------------------
    seed_pair = _best_initial_pair(matches, rec.K, cfg)
    x0, x1 = seed_pair.points()
    F = ransac_fundamental(
        x0, x1, threshold=cfg.ransac_threshold,
        max_iterations=cfg.ransac_iterations, seed=cfg.seed,
    ).model
    if F is None:
        raise RuntimeError(
            f"could not estimate F for the seed pair "
            f"{seed_pair.image0}/{seed_pair.image1}"
        )

    E = fundamental_to_essential(F, rec.K, rec.K)
    rel = recover_pose(E, rec.K, x0, x1)
    # Gauge: reference at the identity, first baseline unit length.
    rec.poses[seed_pair.image0] = Pose.identity()
    rec.poses[seed_pair.image1] = Pose(rel.R, rel.t / (np.linalg.norm(rel.t) or 1.0))

    images = [seed_pair.image0, seed_pair.image1]
    _triangulate_tracks(rec, keypoints, cfg)
    r = StageReport(0, seed_pair.image1, 2, rec.n_points, len(x0))
    _run_bundle(rec, keypoints, images, r, cfg)
    r.n_filtered = _filter_observations(rec, keypoints, cfg)
    _triangulate_tracks(rec, keypoints, cfg)
    r.n_points = rec.n_points
    done(r)

    # ---- register the remaining cameras -----------------------------------
    all_images = sorted({m.image0 for m in matches} | {m.image1 for m in matches})
    step = 1
    while True:
        if cfg.max_cameras is not None and len(rec.poses) >= cfg.max_cameras:
            break
        remaining = [i for i in all_images if i not in rec.poses]
        if not remaining:
            break

        # Next camera = the one already seeing the most triangulated tracks.
        scored = []
        for name in remaining:
            tid, kid = rec.observations_of(name)
            scored.append((len(tid), name, tid, kid))
        scored.sort(key=lambda s: -s[0])
        n_corr, name, tid, kid = scored[0]
        if n_corr < cfg.min_pnp_correspondences:
            break

        pnp = ransac_pnp(
            rec.points[tid], keypoints[name][kid], rec.K,
            threshold=cfg.pnp_threshold, max_iterations=cfg.ransac_iterations, seed=cfg.seed + step,
        )
        if pnp.model is None or pnp.n_inliers < cfg.min_pnp_inliers:
            # A camera fixed by a handful of points drags everything registered
            # after it; better to leave it out than to poison the map.
            all_images = [i for i in all_images if i != name]
            continue

        rec.poses[name] = pnp.model
        images.append(name)
        _triangulate_tracks(rec, keypoints, cfg)
        rep = StageReport(step, name, len(rec.poses), rec.n_points, int(pnp.n_inliers))
        if cfg.bundle_every_camera:
            _run_bundle(rec, keypoints, images, rep, cfg)
            rep.n_filtered = _filter_observations(rec, keypoints, cfg)
            _triangulate_tracks(rec, keypoints, cfg)
            rep.n_points = rec.n_points
        done(rep)
        step += 1

    before_refinement = Reconstruction(
        K=rec.K, poses=dict(rec.poses), points=rec.points.copy(),
        tracks=[Track(observations=dict(t.observations)) for t in rec.tracks],
    )

    # ---- final global refinement ------------------------------------------
    # Registering incrementally means the earliest cameras were optimised
    # against a fraction of the eventual observations. Alternating
    # retriangulation and bundle adjustment once every camera is in lets the
    # whole graph settle -- COLMAP's global refinement loop does the same, and
    # it is cheap compared with the incremental passes.
    for i in range(cfg.final_refinements):
        before = rec.n_points
        _triangulate_tracks(rec, keypoints, cfg)
        rep = StageReport(step + i, "global refinement", len(rec.poses), rec.n_points, 0)
        _run_bundle(rec, keypoints, images, rep, cfg)
        rep.n_filtered = _filter_observations(rec, keypoints, cfg)
        _triangulate_tracks(rec, keypoints, cfg)
        rep.n_points = rec.n_points
        done(rep)
        if abs(rec.n_points - before) < 0.005 * max(before, 1):
            break

    _ = pairs  # kept for future two-view refinement; unused today
    return ReconstructionResult(reconstruction=rec, reports=reports, tracks=list(tracks),
                                before_refinement=before_refinement)
