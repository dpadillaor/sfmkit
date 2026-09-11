// Looking through one of the reconstruction's cameras, its photo in front.
//
// The view takes the camera's pose and its K, principal point included, so the
// photo fills the view as it filled the sensor, and each 3D point sits over the
// pixel that saw it, as far as the reconstruction is right. The photo is a
// half-transparent rectangle in the camera's frame, a little in front of it; it
// stays in the scene when the view moves away.

import * as THREE from 'three';

import { cameraAxes, imageCorners, imageFrustum, intrinsics } from './geometry.js';

// The photo's texture coordinates at its corners, top left first, clockwise,
// for each EXIF orientation a browser turns a photo by to show it (a mirrored
// one is drawn as it comes). The camera saw the pixels as stored: these turn
// them back.
const UNTURN = {
  1: [0, 1, 1, 1, 1, 0, 0, 0],
  3: [1, 0, 0, 0, 0, 1, 1, 1],
  6: [1, 1, 1, 0, 0, 0, 0, 1], // held upright: stored turned a quarter anticlockwise
  8: [0, 0, 0, 1, 1, 1, 1, 0],
};

export class PhotoView {
  #camera;
  #controls;
  #photo = null; // the photo's mesh
  #shot = null; // { camera, frame, depth, ... }: whose photo it is
  #active = false; // the view is the camera's
  #opacity = 0.6;
  #loads = 0; // bumped per photo, so a slow one does not replace a later one

  constructor(camera, controls) {
    this.#camera = camera;
    this.#controls = controls;
  }

  get active() { return this.#active; }
  get shot() { return this.#shot; }
  get opacity() { return this.#opacity; }

  // Show ``shot``'s photo from ``url`` and look through its camera. Resolves to
  // false if the photo could not be loaded (the view moves all the same).
  async show(shot, url) {
    this.clear();
    this.#shot = shot;
    this.enter();
    if (!url) return false;
    const load = ++this.#loads;
    let texture;
    let orientation;
    try {
      [texture, orientation] = await Promise.all([
        new THREE.TextureLoader().loadAsync(url), orientationOf(url)]);
    } catch {
      return false;
    }
    if (load !== this.#loads || this.#shot !== shot) {
      texture.dispose();
      return true;
    }
    texture.colorSpace = THREE.SRGBColorSpace;
    // A quarter turn shows in the photo's shape: taken as turned only if it did.
    const { w, h } = intrinsics(shot.camera);
    const { width, height } = texture.image;
    if ((orientation === 6 || orientation === 8) && (width > height) === (w > h)) orientation = 1;
    this.#photo = photoMesh(shot.camera, shot.depth, texture, this.#opacity,
      UNTURN[orientation] ?? UNTURN[1]);
    shot.frame.add(this.#photo);
    return true;
  }

  // Put the view back at the shot's camera.
  enter() {
    if (!this.#shot) return;
    const { position, forward, up, distance } = this.#pose();
    this.#camera.position.copy(position);
    this.#camera.up.copy(up);
    this.#camera.lookAt(position.clone().add(forward));
    this.#camera.near = distance / 20;
    this.#controls.enabled = false;
    this.#active = true;
    this.resize();
  }

  // Hand the view back to the orbit controls, turning about a point ``ahead``
  // along the camera's axis. The photo stays.
  leave(ahead) {
    if (!this.#active) return;
    this.#active = false;
    const { position, forward } = this.#pose();
    this.#camera.up.set(0, 1, 0);
    this.#controls.target.copy(position).addScaledVector(forward, ahead);
    this.#controls.enabled = true;
    this.#camera.updateProjectionMatrix(); // back to a plain perspective
  }

  clear() {
    this.#loads += 1;
    if (this.#photo) {
      this.#photo.removeFromParent();
      this.#photo.material.map?.dispose();
      this.#photo.material.dispose();
      this.#photo.geometry.dispose();
    }
    this.#photo = null;
    if (this.#active) this.leave(1);
    this.#shot = null;
  }

  setOpacity(opacity) {
    this.#opacity = opacity;
    if (this.#photo) this.#photo.material.opacity = opacity;
  }

  // The projection that shows the whole photo in the viewport, as its K does.
  resize() {
    if (!this.#active) return;
    const c = this.#camera;
    const { left, right, top, bottom } = imageFrustum(this.#shot.camera, c.near, c.aspect);
    c.projectionMatrix.makePerspective(left, right, top, bottom, c.near, c.far);
    c.projectionMatrixInverse.copy(c.projectionMatrix).invert();
  }

  // The shot's camera in the world: where it is, its axis, its up, and how far
  // in front the photo hangs.
  #pose() {
    const { camera, frame, depth } = this.#shot;
    frame.updateWorldMatrix(true, false);
    const M = frame.matrixWorld;
    const { centre, forward, up } = cameraAxes(camera);
    const at = (v, k = 0) => new THREE.Vector3(
      centre[0] + k * v[0], centre[1] + k * v[1], centre[2] + k * v[2]).applyMatrix4(M);
    const position = at(forward, 0);
    const ahead = at(forward, depth);
    return {
      position,
      forward: ahead.clone().sub(position).normalize(),
      up: at(up, depth).sub(position).normalize(),
      distance: ahead.distanceTo(position),
    };
  }
}

// The photo stretched over the image's rectangle at ``depth``: seen from the
// camera, it covers the view exactly.
// A JPEG's EXIF orientation, 1 to 8, from the first bytes of the file at
// ``url``; 1 when it has none, or they cannot be read.
async function orientationOf(url) {
  try {
    const response = await fetch(url, { headers: { Range: 'bytes=0-131071' } });
    return exifOrientation(await response.arrayBuffer());
  } catch {
    return 1;
  }
}

// The orientation tag (0x0112) of a JPEG's EXIF, from its bytes; 1 if absent.
export function exifOrientation(buffer) {
  const v = new DataView(buffer);
  if (v.byteLength < 4 || v.getUint16(0) !== 0xffd8) return 1;
  for (let o = 2; o + 10 <= v.byteLength;) {
    const marker = v.getUint16(o);
    if ((marker & 0xff00) !== 0xff00) return 1;
    if (marker === 0xffe1 && v.getUint32(o + 4) === 0x45786966) { // APP1, "Exif"
      const tiff = o + 10;
      const little = v.getUint16(tiff) === 0x4949;
      const ifd = tiff + v.getUint32(tiff + 4, little);
      const n = ifd + 2 <= v.byteLength ? v.getUint16(ifd, little) : 0;
      for (let i = 0; i < n && ifd + 14 + 12 * i <= v.byteLength; i += 1) {
        const entry = ifd + 2 + 12 * i;
        if (v.getUint16(entry, little) === 0x0112) return v.getUint16(entry + 8, little);
      }
      return 1;
    }
    o += 2 + v.getUint16(o + 2);
  }
  return 1;
}

function photoMesh(camera, depth, texture, opacity, uv) {
  const [a, b, c, d] = imageCorners(camera, depth);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute([...a, ...b, ...c, ...d], 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geometry.setIndex([0, 1, 2, 0, 2, 3]);
  const material = new THREE.MeshBasicMaterial({
    map: texture, transparent: true, opacity, side: THREE.DoubleSide, depthWrite: false,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.renderOrder = 1; // over the points behind it
  return mesh;
}
