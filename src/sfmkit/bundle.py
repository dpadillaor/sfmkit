"""Bundle adjustment over an arbitrary set of cameras and tracks.

Two things matter for speed, and they were established by measurement rather
than by reading the code (see docs/optimizations.md):

* Supply ``jac_sparsity``. The Jacobian is ~99.7% structural zeros, so colouring
  the columns turns one finite-difference evaluation per parameter into about
  ten, and -- more importantly -- switches SciPy to ``tr_solver='lsmr'``, which
  never forms the dense SVD that dominated the original runtime.
* Precompute the observation index arrays. The original rebuilt them by
  iterating a dict inside the residual on every call, although they do not
  depend on the parameters.

The gauge is fixed by holding the reference camera at the identity and the first
camera's baseline at unit length (parameterised by two polar angles), which is
what the original did and what makes scale comparisons against COLMAP meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import coo_matrix

from sfmkit.geometry import log_rotation, rodrigues
from sfmkit.types import Pose

__all__ = ["BundleProblem", "BundleResult", "solve_bundle"]


@dataclass
class BundleResult:
    poses: dict[str, Pose]
    points: np.ndarray
    rmse_before: float
    rmse_after: float
    n_iterations: int
    seconds: float
    n_observations: int


def _polar_to_unit(theta: float, phi: float) -> np.ndarray:
    return np.array([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)])


def _unit_to_polar(t: np.ndarray) -> tuple[float, float]:
    t = np.asarray(t, dtype=float)
    t = t / (np.linalg.norm(t) or 1.0)
    return float(np.arccos(np.clip(t[2], -1.0, 1.0))), float(np.arctan2(t[1], t[0]))


class BundleProblem:
    """Residuals, parameter packing and sparsity for one bundle adjustment.

    ``images[0]`` is the fixed reference; ``images[1]`` keeps a unit-norm
    baseline. Every other camera is free.
    """

    def __init__(self, K, images, poses, points, observations):
        """``observations`` is ``(M, 4)``: track index, camera index, u, v."""
        self.K = np.asarray(K, dtype=float)
        self.images = list(images)
        self.n_cameras = len(self.images)
        self.points = np.asarray(points, dtype=float)
        self.n_points = len(self.points)

        obs = np.asarray(observations, dtype=float)
        order = np.lexsort((obs[:, 0], obs[:, 1]))  # group by camera for cheap slicing
        obs = obs[order]
        self.obs_point = obs[:, 0].astype(np.intp)
        self.obs_cam = obs[:, 1].astype(np.intp)
        self.obs_uv = obs[:, 2:4]

        self.blocks = []
        for c in range(self.n_cameras):
            sel = np.flatnonzero(self.obs_cam == c)
            if sel.size:
                self.blocks.append((c, sel, self.obs_point[sel], self.obs_uv[sel]))

        self.n_residuals = 2 * sum(s.size for _, s, _, _ in self.blocks)
        self.point_offset = 5 + 6 * (self.n_cameras - 2)
        self._initial_poses = dict(poses)

    # ---- parameter packing -------------------------------------------------

    def pack(self, poses: dict[str, Pose], points: np.ndarray) -> np.ndarray:
        first = poses[self.images[1]]
        p = [log_rotation(first.R), np.array(_unit_to_polar(first.t))]
        for name in self.images[2:]:
            p += [log_rotation(poses[name].R), poses[name].t]
        p.append(np.asarray(points, dtype=float).T.ravel())  # X..., Y..., Z...
        return np.concatenate([np.asarray(a, dtype=float).ravel() for a in p])

    def unpack(self, params: np.ndarray) -> tuple[dict[str, Pose], np.ndarray]:
        poses = {self.images[0]: Pose.identity()}
        poses[self.images[1]] = Pose(rodrigues(params[0:3]), _polar_to_unit(params[3], params[4]))
        o = 5
        for name in self.images[2:]:
            poses[name] = Pose(rodrigues(params[o:o + 3]), params[o + 3:o + 6])
            o += 6
        points = params[self.point_offset:].reshape(3, -1).T
        return poses, points

    # ---- residuals and sparsity -------------------------------------------

    def residual(self, params: np.ndarray) -> np.ndarray:
        poses, points = self.unpack(params)
        out = np.empty(self.n_residuals)
        row = 0
        for cam_idx, _, pidx, uv in self.blocks:
            pose = poses[self.images[cam_idx]]
            M = self.K @ pose.R
            c = self.K @ pose.t
            xh = points[pidx] @ M.T + c
            with np.errstate(divide="ignore", invalid="ignore"):
                proj = xh[:, :2] / xh[:, 2:3]
            n = pidx.size
            out[row:row + 2 * n] = (uv - proj).T.ravel()
            row += 2 * n
        return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)

    def sparsity(self) -> coo_matrix:
        n_params = self.point_offset + 3 * self.n_points
        rows, cols = [], []
        row = 0
        for cam_idx, _, pidx, _ in self.blocks:
            n = pidx.size
            if cam_idx == 1:
                cam_cols = np.arange(0, 5)
            elif cam_idx >= 2:
                start = 5 + 6 * (cam_idx - 2)
                cam_cols = np.arange(start, start + 6)
            else:
                cam_cols = np.empty(0, dtype=np.intp)
            if cam_cols.size:
                rr, cc = np.meshgrid(np.arange(row, row + 2 * n), cam_cols, indexing="ij")
                rows.append(rr.ravel())
                cols.append(cc.ravel())
            j = np.arange(n)
            for k in range(3):
                c = self.point_offset + k * self.n_points + pidx
                rows.append(row + j)
                cols.append(c)
                rows.append(row + n + j)
                cols.append(c)
            row += 2 * n
        r = np.concatenate(rows)
        c = np.concatenate(cols)
        return coo_matrix((np.ones(r.size, dtype=np.int8), (r, c)),
                          shape=(self.n_residuals, n_params)).tocsr()


def solve_bundle(
    K, images, poses, points, observations, *, max_iterations: int = 200,
    loss: str = "huber", f_scale: float = 4.0, verbose: int = 0,
) -> BundleResult:
    """Run the bundle adjustment and report RMSE before and after.

    A robust ``loss`` down-weights gross outliers instead of letting a handful of
    bad correspondences dominate a least-squares fit. This is preferable to
    deleting the offending observations: deletion is permanent, so a match
    discarded while the pose was still poor never returns once it improves.
    ``f_scale`` is the residual (in pixels) beyond which down-weighting begins.
    """
    import time

    prob = BundleProblem(K, images, poses, points, observations)
    x0 = prob.pack(poses, points)

    rmse = lambda r: float(np.sqrt(np.mean(r.reshape(-1) ** 2) * 2))  # noqa: E731
    before = rmse(prob.residual(x0))

    t0 = time.perf_counter()
    res = least_squares(
        prob.residual,
        x0,
        method="trf",
        jac_sparsity=prob.sparsity(),
        tr_solver="lsmr",
        loss=loss,
        f_scale=f_scale,
        max_nfev=max_iterations * 10,
        verbose=verbose,
    )
    seconds = time.perf_counter() - t0

    new_poses, new_points = prob.unpack(res.x)
    after = rmse(prob.residual(res.x))  # raw residuals, not the robust-weighted cost
    return BundleResult(
        poses=new_poses,
        points=new_points,
        rmse_before=before,
        rmse_after=after,
        n_iterations=int(res.njev or 0),
        seconds=seconds,
        n_observations=prob.n_residuals // 2,
    )
