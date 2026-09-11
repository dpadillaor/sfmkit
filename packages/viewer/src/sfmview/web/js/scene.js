// The 3D view: a scene from the API drawn with three.js, as named layers.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js';

import { cameraCentre, frustumDepth, frustumSegments, robustSphere } from './geometry.js';
import { colours, PALETTE, SIGNAL } from './palette.js';
import { PhotoView } from './pov.js';

// sfmkit and COLMAP use OpenCV's axes (x right, y down, z forward); three.js has
// y up and cameras looking down -z. This is the one place that converts.
const OPENCV_TO_THREE = new THREE.Matrix4().makeScale(1, -1, -1);

// The reconstruction as it stood at a step of a live run, and the camera that
// step added, in the signal colour.
const LIVE = { main: PALETTE.live.main, added: SIGNAL };

const IDENTITY = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];

const matrix4 = (rows) => new THREE.Matrix4().set(...rows.flat());

export class SceneView {
  #renderer;
  #scene = new THREE.Scene();
  #camera = new THREE.PerspectiveCamera(50, 1, 0.01, 1000);
  #controls;
  #world = new THREE.Group();
  #layers = new Map(); // id -> { label, color, count, object }
  #generation = 0; // bumped by show(), so a late dense cloud is not drawn into another run
  #frames = new Map(); // model source -> its transform into the shared frame
  #reference = null;
  #live = null; // the group holding a live step, in sfmkit's frame
  #liveDepth = 0;
  #shots = new Map(); // camera key -> { key, name, source, query, camera, frame, depth, layer }
  #photos; // looking through a camera, its photo in front
  #bounds = { centre: new THREE.Vector3(), radius: 1 };
  #onLeave;

  // ``onLeave()`` is called when the user moves the view away from a camera.
  constructor(canvas, { onLeave = () => {} } = {}) {
    this.#onLeave = onLeave;
    this.#renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.#renderer.setPixelRatio(window.devicePixelRatio);
    this.#scene.background = new THREE.Color('#161616');
    this.#world.matrixAutoUpdate = false;
    this.#world.matrix.copy(OPENCV_TO_THREE);
    this.#scene.add(this.#world);

    this.#controls = new OrbitControls(this.#camera, canvas);
    this.#controls.enableDamping = true;
    this.#photos = new PhotoView(this.#camera, this.#controls);
    // Captured, so the controls see the press that leaves a camera's view and
    // the drag starts at once.
    for (const type of ['pointerdown', 'wheel']) {
      canvas.addEventListener(type, () => this.#leaveOnTouch(), { capture: true });
    }

    new ResizeObserver(() => this.#resize()).observe(canvas.parentElement);
    this.#resize();
    this.#renderer.setAnimationLoop(() => {
      if (!this.#photos.active) this.#controls.update();
      this.#renderer.render(this.#scene, this.#camera);
    });
  }

  // Every camera that can be looked through: { key, name, source, query }.
  // The cameras of the visible layers, as pick() sees them: a hidden model's
  // cameras are not offered, as the finished one while a new run is drawn.
  cameras() {
    return [...this.#shots.values()]
      .filter((shot) => this.#layers.get(shot.layer)?.object.visible)
      .map(({ key, name, source, query }) => ({ key, name, source, query }));
  }

  // The camera drawn nearest to (x, y), in the page's pixels, within a few
  // pixels of it; null if none. Hidden cameras are not picked.
  pick(x, y, within = 14) {
    const rect = this.#renderer.domElement.getBoundingClientRect();
    this.#world.updateMatrixWorld(true);
    let best = null;
    let bestDistance = within;
    for (const shot of this.#shots.values()) {
      if (!this.#layers.get(shot.layer)?.object.visible) continue;
      const p = new THREE.Vector3(...cameraCentre(shot.camera))
        .applyMatrix4(shot.frame.matrixWorld).project(this.#camera);
      if (p.z < -1 || p.z > 1) continue; // behind the view, or beyond it
      const d = Math.hypot(rect.left + (p.x + 1) / 2 * rect.width - x,
        rect.top + (1 - p.y) / 2 * rect.height - y);
      if (d < bestDistance) [best, bestDistance] = [shot.key, d];
    }
    return best;
  }

  // Look through a camera, with its photo from ``url`` in front. Resolves to
  // whether the photo loaded.
  lookThrough(key, url) {
    const shot = this.#shots.get(key);
    return shot ? this.#photos.show(shot, url) : Promise.resolve(false);
  }

  // Back to the camera being looked through, after the view moved away.
  lookAgain() { this.#photos.enter(); }

  // The camera looked through and whether the view is still its: or null.
  looking() {
    const shot = this.#photos.shot;
    return shot ? { key: shot.key, name: shot.name, source: shot.source,
      active: this.#photos.active, opacity: this.#photos.opacity } : null;
  }

  setPhotoOpacity(opacity) { this.#photos.setOpacity(opacity); }

  closePhoto() { this.#photos.clear(); }

  // Layers in drawing order, for a legend: { id, label, color, count, visible }.
  layers() {
    return [...this.#layers].map(([id, l]) => ({
      id, label: l.label, color: l.color, count: l.count, visible: l.object.visible,
    }));
  }

  setVisible(id, visible) {
    const layer = this.#layers.get(id);
    if (layer) layer.object.visible = visible;
  }

  // Draw a scene from the API, replacing whatever was drawn.
  show(scene) {
    this.#generation += 1;
    this.#clear();
    this.#reference = scene.reference;
    for (const model of scene.models) {
      this.#frames.set(model.source, model.to_common);
      const frame = this.#frame(model.to_common);
      const { main, query, label } = colours(model.source);
      const reconstructed = model.cameras.filter((c) => !c.query);
      const placed = model.cameras.filter((c) => c.query);
      const depth = frustumDepth(reconstructed);
      for (const camera of model.cameras) {
        this.#addShot(model.source, camera, frame, depth,
          `${model.source}-${camera.query ? 'query' : 'cameras'}`);
      }
      this.#add(`${model.source}-points`, `${label} points`, main, model.points.length / 3,
        frame, points(model.points, main));
      this.#add(`${model.source}-cameras`, `${label} cameras`, main, reconstructed.length,
        frame, outlines(reconstructed, depth, main));
      if (placed.length) {
        this.#add(`${model.source}-query`, `${label} old photo`, query, placed.length,
          frame, outlines(placed, depth, query));
      }
    }
    this.fit();
  }

  // Draw the reconstruction as a live step left it, replacing the last step
  // drawn. Its coordinates are sfmkit's, so it takes sfmkit's transform when
  // the run's finished model is shown. ``K`` is the run's, from its start.
  showStep(step, K) {
    this.#live ??= this.#frame(this.#frames.get('sfmkit') ?? IDENTITY);
    const visible = (id) => this.#layers.get(id)?.object.visible ?? true;
    const shown = { points: visible('live-points'), cameras: visible('live-cameras') };
    for (const id of ['live-points', 'live-cameras']) { // the last step's, not a photo
      this.#layers.get(id)?.object.traverse((o) => { o.geometry?.dispose(); o.material?.dispose(); });
      this.#layers.get(id)?.object.removeFromParent();
    }

    const size = K ? [Math.round(2 * K[0][2]), Math.round(2 * K[1][2])] : null;
    const cameras = step.cameras.map((c) => ({ ...c, K, size }));
    this.#liveDepth = Math.max(this.#liveDepth, frustumDepth(cameras));
    for (const key of [...this.#shots.keys()].filter((k) => k.startsWith('live:'))) {
      this.#shots.delete(key);
    }
    for (const camera of cameras) {
      this.#addShot('live', camera, this.#live, this.#liveDepth, 'live-cameras');
    }
    const outline = new THREE.Group();
    outline.add(outlines(cameras.filter((c) => c.name !== step.image), this.#liveDepth, LIVE.main));
    outline.add(outlines(cameras.filter((c) => c.name === step.image), this.#liveDepth, LIVE.added));

    const cloud = points(step.points, LIVE.main);
    this.#add('live-points', `step ${step.step + 1} points`, LIVE.main, step.points.length / 3,
      this.#live, cloud);
    this.#add('live-cameras', `step ${step.step + 1} cameras`, LIVE.main, cameras.length,
      this.#live, outline);
    cloud.visible = shown.points;
    outline.visible = shown.cameras;
  }

  // Frame the bulk of the points, from behind the reference camera if known.
  fit() {
    this.#fit(this.#reference);
  }

  // Load and draw the dense cloud; resolves to its point count, or null if
  // another scene was shown meanwhile.
  async loadDense(dense, onProgress) {
    const generation = this.#generation;
    const geometry = await new PLYLoader().loadAsync(dense.url, (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded / e.total);
    });
    if (generation !== this.#generation) {
      geometry.dispose();
      return null;
    }
    const cloud = new THREE.Points(geometry, new THREE.PointsMaterial({
      size: 1.5, sizeAttenuation: false, vertexColors: geometry.hasAttribute('color'),
    }));
    const count = geometry.getAttribute('position').count;
    this.#add('dense', 'COLMAP dense', 'rgb', count, this.#frame(dense.to_common), cloud);
    return count;
  }

  #addShot(source, camera, frame, depth, layer) {
    const key = `${source}:${camera.name}`;
    this.#shots.set(key, {
      key, name: camera.name, source, query: Boolean(camera.query), camera, frame, depth, layer,
    });
  }

  #leaveOnTouch() {
    if (!this.#photos.active) return;
    const ahead = Math.max(this.#camera.position.distanceTo(this.#bounds.centre), 0.1);
    this.#photos.leave(ahead);
    this.#onLeave();
  }

  #add(id, label, color, count, parent, object) {
    parent.add(object);
    this.#layers.set(id, { label, color, count, object });
  }

  #frame(rows) {
    const group = new THREE.Group();
    group.matrixAutoUpdate = false;
    group.matrix.copy(matrix4(rows));
    this.#world.add(group);
    return group;
  }

  #clear() {
    this.#photos.clear();
    this.#shots.clear();
    this.#world.traverse((o) => {
      o.geometry?.dispose();
      o.material?.dispose();
    });
    this.#world.clear();
    this.#layers.clear();
    this.#frames.clear();
    this.#live = null;
    this.#liveDepth = 0;
  }

  // Look at the bulk of the sparse points from just behind the reference
  // camera, which sits at the origin of the shared frame: the view the photo had.
  #fit(reference) {
    this.#world.updateMatrixWorld(true);
    const flat = [];
    const v = new THREE.Vector3();
    for (const { object } of this.#layers.values()) {
      if (!(object instanceof THREE.Points)) continue;
      const p = object.geometry.getAttribute('position');
      for (let i = 0; i < p.count; i += 1) {
        v.fromBufferAttribute(p, i).applyMatrix4(object.matrixWorld);
        flat.push(v.x, v.y, v.z);
      }
    }
    const { centre, radius } = robustSphere(flat);
    const target = new THREE.Vector3(...centre);
    this.#bounds = { centre: target.clone(), radius };
    const eye = reference ? new THREE.Vector3(0, 0, 0)
      : target.clone().add(new THREE.Vector3(0, 0, 2 * radius));
    const back = eye.clone().sub(target).normalize().multiplyScalar(0.5 * radius);
    this.#camera.position.copy(eye).add(back).add(new THREE.Vector3(0, 0.25 * radius, 0));
    this.#camera.near = radius / 1000;
    this.#camera.far = radius * 100;
    this.#camera.updateProjectionMatrix();
    this.#controls.target.copy(target);
    this.#controls.update();
  }

  #resize() {
    const { clientWidth: w, clientHeight: h } = this.#renderer.domElement.parentElement;
    this.#renderer.setSize(w, h, false);
    this.#camera.aspect = w / Math.max(h, 1);
    this.#camera.updateProjectionMatrix();
    this.#photos.resize();
  }
}

// Sparse points in their model's colour: the point of drawing two models is
// telling them apart.
function points(flat, color) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(flat, 3));
  return new THREE.Points(geometry, new THREE.PointsMaterial({ size: 3, sizeAttenuation: false, color }));
}

// Cameras as one set of line segments, all of one size and colour.
function outlines(cameras, depth, color) {
  const positions = cameras.flatMap((c) => frustumSegments(c, depth).flat());
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color }));
}
