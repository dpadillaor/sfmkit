"""Drop-in fast replacement for sfm.resBundleProjection_multicamera.

Same mathematics, three changes:

  * Visibility bookkeeping is hoisted. The original rebuilds a Python list by
    iterating point3D_map on every residual evaluation (sfm.py:727); it does not
    depend on the parameter vector, so it is precomputed once here.
  * Rotations use Rodrigues' closed form instead of scipy's general
    expm(crossMatrix(theta)). crossMatrix also builds its matrix with
    dtype="object" (sfm.py:659), which forces Python-object arithmetic.
  * A Jacobian sparsity pattern is supplied, so least_squares differences
    grouped columns instead of one per parameter.

Parameter layout, matching the original exactly:
    [0:3]   camera 2 rotation (axis-angle)
    [3], [4] camera 2 translation as polar angles (norm fixed to 1)
    then 6 per additional camera: 3 axis-angle + 3 cartesian
    then the 3D points, as reshape(3, -1): all X, then all Y, then all Z

Residual layout, also matching: per camera, the (2, N) residual block
flattened row-major, i.e. all du then all dv.
"""
import time

import numpy as np
from scipy.sparse import coo_matrix

STATS = {"residual_calls": 0, "residual_time": 0.0, "sparsity_time": 0.0}


def reset_stats():
    STATS.update(residual_calls=0, residual_time=0.0, sparsity_time=0.0)


def report(tag, wall):
    """Print where a bundle-adjustment call actually spent its time."""
    r, n = STATS["residual_time"], STATS["residual_calls"]
    print(f"[timer] {tag}: wall {wall:.2f}s")
    print(f"[timer]   residual : {r:8.2f}s  ({100*r/wall:5.1f}%)  "
          f"{n:,} calls, {1000*r/max(n,1):.3f} ms each")
    print(f"[timer]   sparsity : {STATS['sparsity_time']:8.2f}s  "
          f"({100*STATS['sparsity_time']/wall:5.1f}%)")
    print(f"[timer]   solver   : {wall-r-STATS['sparsity_time']:8.2f}s  "
          f"({100*(wall-r-STATS['sparsity_time'])/wall:5.1f}%)  [scipy internals]")


def rodrigues(w):
    """expm(crossMatrix(w)) in closed form."""
    theta = float(np.linalg.norm(w))
    if theta < 1e-12:
        return np.eye(3)
    k = np.asarray(w, dtype=float) / theta
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(theta) * K + (1 - np.cos(theta)) * (K @ K)


class MulticameraBA:
    """Precomputed residual + sparsity for the multi-camera bundle adjustment."""

    def __init__(self, point3D_map, keypoints_2D, K_c, n_cameras):
        self.K = np.asarray(K_c, dtype=float)
        self.n_cameras = n_cameras
        self.offset = 5 + 6 * (n_cameras - 2)  # where the 3D points start

        self.blocks = []  # (cam_idx, point_indices, observed_keypoints)
        for cam_idx in range(1, n_cameras + 1):
            vis = [(p, info[cam_idx]) for p, info in point3D_map.items() if cam_idx in info]
            if not vis:
                continue
            pidx = np.fromiter((p for p, _ in vis), dtype=np.intp, count=len(vis))
            kidx = np.fromiter((k for _, k in vis), dtype=np.intp, count=len(vis))
            self.blocks.append((cam_idx, pidx, np.asarray(keypoints_2D[cam_idx - 1])[:, kidx]))

        self.n_res = sum(2 * len(p) for _, p, _ in self.blocks)

    def _poses(self, Op):
        """Unpack camera rotations/translations; index i is camera i+2."""
        R = [rodrigues(Op[0:3])]
        th, ph = Op[3], Op[4]
        t = [np.array([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)])]
        o = 5
        for _ in range(2, self.n_cameras):
            R.append(rodrigues(Op[o:o + 3]))
            t.append(np.asarray(Op[o + 3:o + 6], dtype=float))
            o += 6
        return R, t

    def residual(self, Op):
        _t0 = time.perf_counter()
        Op = np.asarray(Op, dtype=float)
        R, t = self._poses(Op)
        pts = Op[self.offset:].reshape(3, -1)

        out = np.empty(self.n_res)
        row = 0
        for cam_idx, pidx, kp in self.blocks:
            if cam_idx == 1:
                M, c = self.K, np.zeros(3)
            else:
                M = self.K @ R[cam_idx - 2]
                c = self.K @ t[cam_idx - 2]
            xh = M @ pts[:, pidx] + c[:, None]
            proj = xh[:2] / xh[2]
            n = pidx.size
            out[row:row + 2 * n] = (kp - proj).ravel()
            row += 2 * n
        STATS["residual_calls"] += 1
        STATS["residual_time"] += time.perf_counter() - _t0
        return out

    def sparsity(self, n_params):
        """Boolean pattern: which residual depends on which parameter."""
        _t0 = time.perf_counter()
        n_points = (n_params - self.offset) // 3
        rows, cols = [], []

        def mark(r, c):
            rr, cc = np.meshgrid(np.asarray(r), np.asarray(c), indexing="ij")
            rows.append(rr.ravel()); cols.append(cc.ravel())

        row = 0
        for cam_idx, pidx, _ in self.blocks:
            n = pidx.size
            block = np.arange(row, row + 2 * n)
            if cam_idx >= 2:
                start = 5 + 6 * (cam_idx - 3) if cam_idx >= 3 else 0
                mark(block, np.arange(start, start + (5 if cam_idx == 2 else 6)))
            # Each observation depends on its own point's X, Y and Z.
            j = np.arange(n)
            for k in range(3):
                c = self.offset + k * n_points + pidx
                rows.append(row + j); cols.append(c)          # du rows
                rows.append(row + n + j); cols.append(c)      # dv rows
            row += 2 * n

        r = np.concatenate(rows); c = np.concatenate(cols)
        S = coo_matrix((np.ones(r.size, dtype=np.int8), (r, c)),
                       shape=(self.n_res, n_params)).tocsr()
        STATS["sparsity_time"] += time.perf_counter() - _t0
        return S
