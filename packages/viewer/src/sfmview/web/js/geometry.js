// Camera geometry on plain arrays, in OpenCV's axes (x right, y down, z forward).
// No three.js here: what a camera outline is does not depend on who draws it.

const median = (values) => {
  const s = [...values].sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : 0;
};

// World point of pixel (u, v) at depth d: X = Rᵀ(d·K⁻¹[u v 1] − t).
function unproject(camera, K, u, v, d) {
  const p = [(u - K[0][2]) / K[0][0] * d - camera.t[0],
             (v - K[1][2]) / K[1][1] * d - camera.t[1],
             d - camera.t[2]];
  const R = camera.R;
  return [0, 1, 2].map((j) => R[0][j] * p[0] + R[1][j] * p[1] + R[2][j] * p[2]);
}

export function cameraCentre(camera) {
  return unproject(camera, [[1, 0, 0], [0, 1, 0], [0, 0, 1]], 0, 0, 0);
}

// Line segments, as point pairs, outlining a camera: the apex joined to the
// image's corners, the image, and a tick above its top edge to show which way
// is up. Without K or size, a 4:3 image and a 53° field of view.
export function frustumSegments(camera, depth) {
  const [w, h] = camera.size ?? [4, 3];
  const K = camera.K ?? [[w, 0, w / 2], [0, w, h / 2], [0, 0, 1]];
  const C = cameraCentre(camera);
  const [a, b, c, d] = [[0, 0], [w, 0], [w, h], [0, h]]
    .map(([u, v]) => unproject(camera, K, u, v, depth));
  const up = unproject(camera, K, w / 2, -0.3 * h, depth); // image v grows downwards
  return [C, a, C, b, C, c, C, d, a, b, b, c, c, d, d, a, a, up, up, b];
}

// A camera outline sized to the model: a tenth of how far apart its cameras are.
export function frustumDepth(cameras) {
  const centres = cameras.map(cameraCentre);
  if (centres.length < 2) return 0.1;
  const mid = [0, 1, 2].map((i) => median(centres.map((c) => c[i])));
  const spread = median(centres.map((c) => Math.hypot(c[0] - mid[0], c[1] - mid[1], c[2] - mid[2])));
  return spread > 0 ? 0.12 * spread : 0.1;
}

// Centre and radius of the bulk of some points, flat [x0, y0, z0, x1, ...]:
// the median, and the distance within which 80% of them lie. Stray points,
// which every reconstruction has, do not move the view.
export function robustSphere(flat) {
  const n = flat.length / 3;
  if (!n) return { centre: [0, 0, 0], radius: 1 };
  const axis = (i) => median(Array.from({ length: n }, (_, k) => flat[3 * k + i]));
  const centre = [axis(0), axis(1), axis(2)];
  const d = Array.from({ length: n }, (_, k) => Math.hypot(
    flat[3 * k] - centre[0], flat[3 * k + 1] - centre[1], flat[3 * k + 2] - centre[2]));
  d.sort((a, b) => a - b);
  return { centre, radius: d[Math.floor(0.8 * (n - 1))] || 1 };
}
