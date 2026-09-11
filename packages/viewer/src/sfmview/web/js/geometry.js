// Camera geometry on plain arrays, in OpenCV's axes (x right, y down, z forward).
// No three.js here: what a camera outline is does not depend on who draws it.

const median = (values) => {
  const s = [...values].sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : 0;
};

// The camera's K and image size. Without them, a 4:3 image and a 53° field of view.
export function intrinsics(camera) {
  const [w, h] = camera.size ?? [4, 3];
  const K = camera.K ?? [[w, 0, w / 2], [0, w, h / 2], [0, 0, 1]];
  return { K, w, h };
}

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

// Where a camera looks, in the world: its optical axis and its image's up.
// The rows of R are the camera's axes in the world.
export function cameraAxes(camera) {
  const R = camera.R;
  return { centre: cameraCentre(camera), forward: [...R[2]], up: R[1].map((v) => -v) };
}

// The image as a rectangle at depth d in front of the camera: its corners,
// top left first, clockwise.
export function imageCorners(camera, depth) {
  const { K, w, h } = intrinsics(camera);
  return [[0, 0], [w, 0], [w, h], [0, h]].map(([u, v]) => unproject(camera, K, u, v, depth));
}

// Line segments, as point pairs, outlining a camera: the apex joined to the
// image's corners, the image, and a tick above its top edge to show which way
// is up.
export function frustumSegments(camera, depth) {
  const { K, w, h } = intrinsics(camera);
  const C = cameraCentre(camera);
  const [a, b, c, d] = imageCorners(camera, depth);
  const up = unproject(camera, K, w / 2, -0.3 * h, depth); // image v grows downwards
  return [C, a, C, b, C, c, C, d, a, b, b, c, c, d, d, a, a, up, up, b];
}

// How deep the scene lies before a camera: the ``q`` quantile of the depths of
// the points, flat [x0, y0, z0, x1, ...], that fall inside its image; null if
// fewer than ``least`` do. A high quantile, so a view drawn to it reaches the
// far side of what the photo takes in, and not past a few stray points.
export function viewDepth(camera, flat, { q = 0.9, least = 10 } = {}) {
  const { K, w, h } = intrinsics(camera);
  const { R, t } = camera;
  const depths = [];
  for (let i = 0; i + 2 < flat.length; i += 3) {
    const c = [0, 1, 2].map((r) => R[r][0] * flat[i] + R[r][1] * flat[i + 1] + R[r][2] * flat[i + 2] + t[r]);
    if (c[2] <= 0) continue;
    const u = (K[0][0] * c[0] + K[0][1] * c[1]) / c[2] + K[0][2];
    const v = K[1][1] * c[1] / c[2] + K[1][2];
    if (u >= 0 && u <= w && v >= 0 && v <= h) depths.push(c[2]);
  }
  if (depths.length < least) return null;
  depths.sort((a, b) => a - b);
  return depths[Math.floor(q * (depths.length - 1))];
}

// Distance from point (x, y) to the segment from (ax, ay) to (bx, by), in the
// units they are given in.
export function segmentDistance(x, y, ax, ay, bx, by) {
  const [dx, dy] = [bx - ax, by - ay];
  const length2 = dx * dx + dy * dy;
  const s = length2 ? Math.min(Math.max(((x - ax) * dx + (y - ay) * dy) / length2, 0), 1) : 0;
  return Math.hypot(ax + s * dx - x, ay + s * dy - y);
}

// The camera as it would be had it taken the photo upright, for an EXIF
// orientation of 3, 6 or 8: the same centre and the same view, its axes and
// its K turned with the pixels. Anything else is left as it is.
export function turnUpright(camera, orientation) {
  const turn = { 3: [[-1, 0, 0], [0, -1, 0]], 6: [[0, -1, 0], [1, 0, 0]], 8: [[0, 1, 0], [-1, 0, 0]] };
  if (!turn[orientation]) return camera;
  const M = [...turn[orientation], [0, 0, 1]];
  const { K, w, h } = intrinsics(camera);
  const [fx, fy, cx, cy] = [K[0][0], K[1][1], K[0][2], K[1][2]];
  const turned = {
    3: { K: [[fx, 0, w - 1 - cx], [0, fy, h - 1 - cy], [0, 0, 1]], size: [w, h] },
    6: { K: [[fy, 0, h - 1 - cy], [0, fx, cx], [0, 0, 1]], size: [h, w] },
    8: { K: [[fy, 0, cy], [0, fx, w - 1 - cx], [0, 0, 1]], size: [h, w] },
  }[orientation];
  return {
    ...camera,
    R: M.map((m) => [0, 1, 2].map((j) => m[0] * camera.R[0][j] + m[1] * camera.R[1][j]
      + m[2] * camera.R[2][j])),
    t: M.map((m) => m[0] * camera.t[0] + m[1] * camera.t[1] + m[2] * camera.t[2]),
    ...turned,
  };
}

// The view frustum at distance ``near`` that shows the camera's whole image as
// its K sees it, principal point and all, in a viewport of ``aspect``: the
// image fills the viewport one way, and the scene shows past its edges the
// other. In a y-up camera, as three.js's: top is the image's first row.
export function imageFrustum(camera, near, aspect) {
  const { K, w, h } = intrinsics(camera);
  const [fx, fy, cx, cy] = [K[0][0], K[1][1], K[0][2], K[1][2]];
  let [left, right] = [-cx / fx * near, (w - cx) / fx * near];
  let [top, bottom] = [cy / fy * near, -(h - cy) / fy * near];
  const width = right - left;
  const height = top - bottom;
  if (aspect > width / height) {
    const extra = (aspect * height - width) / 2;
    left -= extra;
    right += extra;
  } else {
    const extra = (width / aspect - height) / 2;
    top += extra;
    bottom -= extra;
  }
  return { left, right, top, bottom };
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
