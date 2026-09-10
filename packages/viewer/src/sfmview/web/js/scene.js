// The 3D view: a scene from the API drawn with three.js, as named layers.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js';

import { frustumDepth, frustumSegments, robustSphere } from './geometry.js';

// sfmkit and COLMAP use OpenCV's axes (x right, y down, z forward); three.js has
// y up and cameras looking down -z. This is the one place that converts.
const OPENCV_TO_THREE = new THREE.Matrix4().makeScale(1, -1, -1);

// Each model in its colour; its placement of the old photo in a tint apart.
export const PALETTE = {
  sfmkit: { main: '#ff9a3c', query: '#ff4f8b' },
  colmap: { main: '#4db3ff', query: '#b18cff' },
  other: { main: '#cccccc', query: '#ffffff' },
};

const LABELS = { sfmkit: 'sfmkit', colmap: 'COLMAP' };

const matrix4 = (rows) => new THREE.Matrix4().set(...rows.flat());

export class SceneView {
  #renderer;
  #scene = new THREE.Scene();
  #camera = new THREE.PerspectiveCamera(50, 1, 0.01, 1000);
  #controls;
  #world = new THREE.Group();
  #layers = new Map(); // id -> { label, color, count, object }
  #generation = 0; // bumped by show(), so a late dense cloud is not drawn into another run

  constructor(canvas) {
    this.#renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.#renderer.setPixelRatio(window.devicePixelRatio);
    this.#scene.background = new THREE.Color('#0f1115');
    this.#world.matrixAutoUpdate = false;
    this.#world.matrix.copy(OPENCV_TO_THREE);
    this.#scene.add(this.#world);

    this.#controls = new OrbitControls(this.#camera, canvas);
    this.#controls.enableDamping = true;

    new ResizeObserver(() => this.#resize()).observe(canvas.parentElement);
    this.#resize();
    this.#renderer.setAnimationLoop(() => {
      this.#controls.update();
      this.#renderer.render(this.#scene, this.#camera);
    });
  }

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
    for (const model of scene.models) {
      const frame = this.#frame(model.to_common);
      const { main, query } = PALETTE[model.source] ?? PALETTE.other;
      const label = LABELS[model.source] ?? model.source;
      const reconstructed = model.cameras.filter((c) => !c.query);
      const placed = model.cameras.filter((c) => c.query);
      const depth = frustumDepth(reconstructed);
      this.#add(`${model.source}-points`, `${label} points`, main, model.points.length / 3,
        frame, points(model.points, main));
      this.#add(`${model.source}-cameras`, `${label} cameras`, main, reconstructed.length,
        frame, outlines(reconstructed, depth, main));
      if (placed.length) {
        this.#add(`${model.source}-query`, `${label} old photo`, query, placed.length,
          frame, outlines(placed, depth, query));
      }
    }
    this.#fit(scene);
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
    this.#world.traverse((o) => {
      o.geometry?.dispose();
      o.material?.dispose();
    });
    this.#world.clear();
    this.#layers.clear();
  }

  // Look at the bulk of the sparse points from just behind the reference
  // camera, which sits at the origin of the shared frame: the view the photo had.
  #fit(scene) {
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
    const eye = scene.reference ? new THREE.Vector3(0, 0, 0) : target.clone().add(new THREE.Vector3(0, 0, 2 * radius));
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
