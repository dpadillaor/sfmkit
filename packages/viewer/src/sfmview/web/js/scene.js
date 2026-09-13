// The 3D view: a scene from the API drawn with three.js, as named layers.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js';

import {
  cameraCentre, frustumDepth, frustumSegments, imageCorners, referenceFrame, robustSphere,
  segmentDistance, viewDepth,
} from './geometry.js';
import { colours, PALETTE, SIGNAL } from './palette.js';
import { PhotoView } from './pov.js';

// sfmkit and COLMAP use OpenCV's axes (x right, y down, z forward); three.js has
// y up and cameras looking down -z. This is the one place that converts.
const OPENCV_TO_THREE = new THREE.Matrix4().makeScale(1, -1, -1);

// The reconstruction as it stood at a step of a live run, and the camera that
// step added, in the signal colour.
const LIVE = { main: PALETTE.live.main, added: SIGNAL };

const IDENTITY = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];

// A camera under the pointer, drawn over everything else.
const HOVER = '#ffffff';

// A live step stands in for sfmkit's finished model, under its layers' names:
// while a step is drawn, the finished points and cameras are not.
const STEP_OF = { 'sfmkit-points': 'live-points', 'sfmkit-cameras': 'live-cameras' };
const LAYER_OF = Object.fromEntries(Object.entries(STEP_OF).map(([a, b]) => [b, a]));
const GROUPS = ['sfmkit', 'COLMAP'];

const matrix4 = (rows) => new THREE.Matrix4().set(...rows.flat());

export class SceneView {
  #renderer;
  #scene = new THREE.Scene();
  #camera = new THREE.PerspectiveCamera(50, 1, 0.01, 1000);
  #controls;
  #world = new THREE.Group();
  #layers = new Map(); // id -> { group, label, color, count, object }
  #wanted = new Map(); // layer id, as the panel names it -> whether it should show
  #generation = 0; // bumped by show(), so a late dense cloud is not drawn into another run
  #frames = new Map(); // model source -> its transform into the shared frame
  #reference = null;
  #live = null; // the group holding a live step, in sfmkit's frame
  #shots = new Map(); // camera key -> { key, name, source, query, camera, frame, depth, layer }
  #photos; // looking through a camera, its photo in front
  #hovered = null; // { key, object }: the camera under the pointer, outlined
  #reach = new Map(); // camera key -> its view drawn out to the scene
  #cone = { show: 0.5, far: 1 }; // how strongly a view is drawn, and how far out
  #pointsOf = new Map(); // model source -> its sparse points, flat, in its own frame
  // The dense cloud, kept across scenes: when a watched run ends, only sfmkit's
  // files have changed, and fetching and parsing several MB of COLMAP's again
  // to draw the same points is the most expensive thing the page can do.
  #dense = { url: null, geometry: null };
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

  // The camera whose outline, any of its lines, passes nearest to (x, y) in
  // the page's pixels, within a few pixels of it; null if none. Hidden cameras
  // are not picked.
  pick(x, y, within = 8) {
    const rect = this.#renderer.domElement.getBoundingClientRect();
    this.#world.updateMatrixWorld(true);
    const v = new THREE.Vector3();
    const toPage = (point, frame) => {
      v.set(...point).applyMatrix4(frame.matrixWorld).project(this.#camera);
      // Behind the view, or beyond it: not on the page.
      return v.z < -1 || v.z > 1 ? null
        : [rect.left + (v.x + 1) / 2 * rect.width, rect.top + (1 - v.y) / 2 * rect.height];
    };
    let best = null;
    let bestDistance = within;
    for (const shot of this.#shots.values()) {
      if (!this.#layers.get(shot.layer)?.object.visible) continue;
      const ends = frustumSegments(shot.camera, shot.depth).map((p) => toPage(p, shot.frame));
      for (let i = 0; i < ends.length; i += 2) {
        if (!ends[i] || !ends[i + 1]) continue;
        const d = segmentDistance(x, y, ...ends[i], ...ends[i + 1]);
        if (d < bestDistance) [best, bestDistance] = [shot.key, d];
      }
    }
    return best;
  }

  // Outline the camera under (x, y) over everything else, and return its key;
  // or clear the outline, given no point or finding no camera.
  hover(x = null, y = null) {
    const key = x === null ? null : this.pick(x, y);
    if (key === (this.#hovered?.key ?? null)) return key;
    this.#unhover();
    const shot = key && this.#shots.get(key);
    if (shot) {
      const object = outlines([shot.camera], shot.depth, HOVER);
      object.material.depthTest = false;
      object.renderOrder = 10;
      shot.frame.add(object);
      this.#hovered = { key, object };
    }
    this.#updateReach();
    return key;
  }

  // Look through a camera, with its photo from ``url`` in front. Resolves to
  // whether the photo loaded.
  lookThrough(key, url) {
    const shot = this.#shots.get(key);
    const loaded = shot ? this.#photos.show(shot, url) : Promise.resolve(false);
    this.#updateReach();
    return loaded;
  }

  // Back to the camera being looked through, after the view moved away.
  lookAgain() {
    this.#photos.enter();
    this.#updateReach();
  }

  // The camera looked through and whether the view is still its: or null.
  looking() {
    const shot = this.#photos.shot;
    return shot ? { key: shot.key, name: shot.name, source: shot.source,
      active: this.#photos.active, opacity: this.#photos.opacity } : null;
  }

  setPhotoOpacity(opacity) { this.#photos.setOpacity(opacity); }

  closePhoto() {
    this.#photos.clear();
    this.#updateReach();
  }

  // How a camera's view is drawn: ``show`` 0 to 1, its strength, and ``far``,
  // what the depth of what it sees is multiplied by.
  cone() { return { ...this.#cone }; }

  setCone(settings) {
    Object.assign(this.#cone, settings);
    for (const [key, object] of this.#reach) {  // the drawn ones, again
      dispose(object);
      this.#reach.delete(key);
    }
    this.#updateReach();
  }

  // Layers for the panel, grouped by model: { id, group, label, color, count,
  // visible }. sfmkit's points and cameras are the step's while one is drawn.
  layers() {
    const ids = [...new Set([...this.#layers.keys()].map((id) => LAYER_OF[id] ?? id))];
    return ids.map((id) => {
      const l = this.#drawn(id);
      return { id, group: l.group, label: l.label, color: l.color, count: l.count,
        visible: this.#wanted.get(id) ?? true };
    }).sort((a, b) => GROUPS.indexOf(a.group) - GROUPS.indexOf(b.group));
  }

  setVisible(id, visible) {
    this.#unhover();
    this.#wanted.set(id, visible);
    this.#apply(id);
    this.#updateReach();
  }

  // Draw a scene from the API, replacing whatever was drawn.
  show(scene) {
    this.#generation += 1;
    this.#clear();
    this.#reference = scene.reference;
    for (const model of scene.models) {
      this.#frames.set(model.source, model.to_common);
      this.#pointsOf.set(model.source, model.points);
      const frame = this.#frame(model.to_common);
      const { main, query, label } = colours(model.source);
      const reconstructed = model.cameras.filter((c) => !c.query);
      const placed = model.cameras.filter((c) => c.query);
      const depth = frustumDepth(reconstructed);
      for (const camera of model.cameras) {
        this.#addShot(model.source, camera, frame, depth,
          `${model.source}-${camera.query ? 'query' : 'cameras'}`);
      }
      this.#add(`${model.source}-points`, label, 'points', main, model.points.length / 3,
        frame, points(model.points, main));
      this.#add(`${model.source}-cameras`, label, 'cameras', main, reconstructed.length,
        frame, outlines(reconstructed, depth, main));
      if (placed.length) {
        this.#add(`${model.source}-query`, label, 'old photo', query, placed.length,
          frame, outlines(placed, depth, query));
      }
    }
    this.fit();
  }

  // Draw the reconstruction as a live step left it, replacing the last step
  // drawn. Its coordinates are sfmkit's, so it takes sfmkit's transform when
  // the run's finished model is shown. ``K`` is the run's, from its start, and
  // ``reference`` the camera it will be anchored to: until there is a finished
  // model to take the transform from, the step is placed by its own reference
  // camera, so it does not sit in the seed pair's frame and jump later.
  showStep(step, K, reference = null) {
    const rows = this.#frames.get('sfmkit')
      ?? referenceFrame(step.cameras, reference) ?? IDENTITY;
    if (this.#live) this.#live.matrix.copy(matrix4(rows));
    else this.#live = this.#frame(rows);
    for (const id of ['live-points', 'live-cameras']) { // the last step's, not a photo
      this.#layers.get(id)?.object.traverse((o) => { o.geometry?.dispose(); o.material?.dispose(); });
      this.#layers.get(id)?.object.removeFromParent();
    }

    this.#unhover(); // its camera may be the last step's
    for (const key of [...this.#reach.keys()].filter((k) => k.startsWith('live:'))) {
      dispose(this.#reach.get(key));
      this.#reach.delete(key);
    }
    this.#pointsOf.set('live', step.points);
    const size = K ? [Math.round(2 * K[0][2]), Math.round(2 * K[1][2])] : null;
    const cameras = step.cameras.map((c) => ({ ...c, K, size }));
    // Sized to this step's cameras, so a step replayed looks as it did live.
    const depth = frustumDepth(cameras);
    for (const key of [...this.#shots.keys()].filter((k) => k.startsWith('live:'))) {
      this.#shots.delete(key);
    }
    for (const camera of cameras) {
      this.#addShot('live', camera, this.#live, depth, 'live-cameras');
    }
    const outline = new THREE.Group();
    outline.add(outlines(cameras.filter((c) => c.name !== step.image), depth, LIVE.main));
    outline.add(outlines(cameras.filter((c) => c.name === step.image), depth, LIVE.added));

    const cloud = points(step.points, LIVE.main);
    this.#add('live-points', 'sfmkit', 'points', LIVE.main, step.points.length / 3,
      this.#live, cloud);
    this.#add('live-cameras', 'sfmkit', 'cameras', LIVE.main, cameras.length, this.#live, outline);
    this.#apply('sfmkit-points');
    this.#apply('sfmkit-cameras');
    this.#updateReach();
  }

  // Frame the bulk of the points, from behind the reference camera if known.
  fit() {
    this.#fit(this.#reference);
  }

  // Load and draw the dense cloud; resolves to its point count, or null if
  // another scene was shown meanwhile.
  async loadDense(dense, onProgress) {
    const generation = this.#generation;
    let geometry = this.#dense.url === dense.url ? this.#dense.geometry : null;
    if (!geometry) {
      geometry = await new PLYLoader().loadAsync(dense.url, (e) => {
        if (e.lengthComputable) onProgress?.(e.loaded / e.total);
      });
      if (generation !== this.#generation) {
        geometry.dispose();
        return null;
      }
      this.#dense.geometry?.dispose(); // a different cloud: the old one goes
      this.#dense = { url: dense.url, geometry };
    } else if (generation !== this.#generation) {
      return null;
    }
    const cloud = new THREE.Points(geometry, new THREE.PointsMaterial({
      size: 1.5, sizeAttenuation: false, vertexColors: geometry.hasAttribute('color'),
    }));
    const count = geometry.getAttribute('position').count;
    this.#add('dense', 'COLMAP', 'dense', 'rgb', count, this.#frame(dense.to_common), cloud);
    this.#apply('dense');
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
    this.#updateReach();
    this.#onLeave();
  }

  #add(id, group, label, color, count, parent, object) {
    parent.add(object);
    this.#layers.set(id, { group, label, color, count, object });
  }

  // What a panel layer draws now: the step's, if one is drawn, else its own.
  #drawn(id) {
    return this.#layers.get(STEP_OF[id]) ?? this.#layers.get(id);
  }

  // Show a panel layer as wanted, and whatever it stands in for not at all.
  #apply(id) {
    const on = this.#wanted.get(id) ?? true;
    const drawn = this.#drawn(id);
    for (const layer of [this.#layers.get(id), this.#layers.get(STEP_OF[id])]) {
      if (layer) layer.object.visible = on && layer === drawn;
    }
  }

  #frame(rows) {
    const group = new THREE.Group();
    group.matrixAutoUpdate = false;
    group.matrix.copy(matrix4(rows));
    this.#world.add(group);
    return group;
  }

  // The hovered camera's view, and the chosen one's once the view has left it,
  // drawn out to the scene: what part of it each photo takes in. From inside
  // a camera its view is the screen, so the chosen one's waits.
  #updateReach() {
    const chosen = this.#photos.shot && !this.#photos.active ? this.#photos.shot.key : null;
    const keys = new Set([this.#hovered?.key, chosen].filter(Boolean));
    for (const [key, object] of this.#reach) {
      if (keys.has(key)) continue;
      dispose(object);
      this.#reach.delete(key);
    }
    for (const key of keys) {
      const shot = this.#shots.get(key);
      if (this.#reach.has(key) || !shot || !this.#layers.get(shot.layer)?.object.visible) continue;
      shot.reach ??= viewDepth(shot.camera, this.#pointsOf.get(shot.source) ?? []);
      if (!shot.reach) continue;
      const object = cone(shot.camera, shot.reach * this.#cone.far, HOVER, this.#cone.show);
      shot.frame.add(object);
      this.#reach.set(key, object);
    }
  }

  #unhover() {
    if (!this.#hovered) return;
    this.#hovered.object.removeFromParent();
    this.#hovered.object.geometry.dispose();
    this.#hovered.object.material.dispose();
    this.#hovered = null;
  }

  #clear() {
    this.#unhover();
    this.#wanted.clear();
    this.#reach.clear(); // disposed with the world below
    this.#pointsOf.clear();
    this.#photos.clear();
    this.#shots.clear();
    this.#world.traverse((o) => {
      if (o.geometry !== this.#dense.geometry) o.geometry?.dispose(); // kept for the next scene
      o.material?.dispose();
    });
    this.#world.clear();
    this.#layers.clear();
    this.#frames.clear();
    this.#live = null;
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

// A camera's view out to ``depth``: its four edges and its sides, faint, drawn
// over the scene.
function cone(camera, depth, color, show) {
  const C = cameraCentre(camera);
  const corners = imageCorners(camera, depth);
  const next = (i) => corners[(i + 1) % 4];
  const geometry = (flat) => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(flat, 3));
    return g;
  };
  const sides = new THREE.Mesh(geometry(corners.flatMap((a, i) => [C, a, next(i)]).flat()),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.14 * show,
      side: THREE.DoubleSide, depthWrite: false }));
  const edges = new THREE.LineSegments(geometry(corners.flatMap((a, i) => [C, a, a, next(i)]).flat()),
    new THREE.LineBasicMaterial({ color, transparent: true, opacity: show, depthWrite: false }));
  const group = new THREE.Group();
  group.add(sides, edges);
  return group;
}

function dispose(object) {
  object.removeFromParent();
  object.traverse((o) => { o.geometry?.dispose(); o.material?.dispose(); });
}

// Cameras as one set of line segments, all of one size and colour.
function outlines(cameras, depth, color) {
  const positions = cameras.flatMap((c) => frustumSegments(c, depth).flat());
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color }));
}
