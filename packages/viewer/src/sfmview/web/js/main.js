// Wires the page: the API's runs into the sidebar, the chosen run into the view,
// and its live progress, if the server has a broker, into the timeline.
// The URL's hash names the run (#valencia/cpu), so a view can be linked.

import { getScene, health, listRuns, liveUrl } from './api.js';
import { LiveFeed, writtenAt } from './live.js';
import { colours } from './palette.js';
import { SceneView } from './scene.js';
import * as ui from './ui.js';

const canvas = document.getElementById('view');
const view = new SceneView(canvas, { onLeave: () => showPhotoBar() });
let runs = [];
let liveOn = false;

// The open run: its finished scene, and the steps of its live stream. Every
// open() takes a new token; work begun for an older one drops its results.
const session = {
  token: 0, id: null, feed: null, scene: null, updated: null, connectedAt: Infinity,
  K: null, stage: null, steps: [], index: -1, running: false, fitted: false,
};

const showLayers = () => ui.renderLayers(view.layers(), (id, on) => {
  view.setVisible(id, on);
  showCameras(); // a hidden layer's cameras leave the list
});
const showCameras = () => ui.renderCameras(view.cameras(), view.looking()?.key, lookThrough,
  session.steps[session.index]?.step ?? null);
const showPhotoBar = () => ui.renderPhotoBar(view.looking(), view.cone(), {
  onOpacity: (opacity) => view.setPhotoOpacity(opacity),
  onCone: (settings) => view.setCone(settings),
  onBack: () => { view.lookAgain(); showPhotoBar(); },
  onClose: closePhoto,
});
const runOf = (id) => runs.find((r) => r.id === id);
const say = (token, text, error = false) => {
  if (token === session.token) ui.status(text, error);
};

function open(id) {
  if (!runOf(id)) return;
  const token = ++session.token;
  session.feed?.stop();
  Object.assign(session, {
    id, feed: null, scene: null, updated: runOf(id).updated, connectedAt: Infinity,
    K: null, stage: null, steps: [], index: -1, running: false,
  });
  ui.selectRun(id);
  ui.renderTimeline([], -1);
  // The feed starts at once: the timeline need not wait for a dense cloud.
  if (liveOn) {
    session.feed = new LiveFeed(liveUrl(id), (event) => onLive(token, event),
      (now) => { if (token === session.token) session.connectedAt = now; }).start();
  }
  showScene(token);
}

// The run's finished results, if it has any yet, with its current step on top.
async function showScene(token) {
  const id = session.id;
  say(token, `Loading ${id}…`);
  let scene = null;
  try {
    scene = await getScene(id);
  } catch (error) {
    if (error.status !== 404) {
      say(token, `Could not load ${id}: ${error.message}`, true);
      return;
    }
  }
  if (token !== session.token) return;
  Object.assign(session, { scene, fitted: false });
  view.show(scene ?? { models: [], reference: null });
  drawStep();
  showLayers();
  showCameras();
  showPhotoBar();
  ui.renderInfo(runOf(id), scene);
  if (session.stage) say(token, `${session.stage.name}…`);
  else say(token, scene ? '' : 'No results yet: waiting for the run.');

  if (scene?.dense) {
    try {
      const n = await view.loadDense(scene.dense,
        (f) => say(token, `Loading the dense cloud… ${Math.round(100 * f)}%`));
      if (n === null || token !== session.token) return;
      showLayers();
      say(token, '');
    } catch (error) {
      say(token, `Could not load the dense cloud: ${error.message}`, true);
    }
  }
}

function onLive(token, { id: entry, message }) {
  if (token !== session.token) return;
  // Written after the page connected: news, not history.
  const news = writtenAt(entry) >= session.connectedAt;
  if (message.kind === 'start') {
    // Replayed, a start is at work only if its heartbeat said so; new, it is.
    const running = news || runOf(session.id)?.running !== false;
    Object.assign(session, {
      K: message.K, steps: [], index: -1, running, startSeen: Date.now(),
    });
  } else if (message.kind === 'step') {
    if (!session.scene) say(token, ''); // no results yet, but the run is being drawn
    if (news) markLive(true); // at work, whatever the list last said
    const following = session.index === session.steps.length - 1;
    session.steps.push(message);
    if (following) session.index = session.steps.length - 1;
  } else if (message.kind === 'stage') {
    // The stages that draw nothing still say where the run is: `match` alone
    // is minutes in which the page would otherwise look like a dead run.
    if (news) markLive(message.state === 'start' || session.running);
    session.stage = message.state === 'start'
      ? { name: message.stage, since: Date.now() }
      : null;
    if (news) say(token, stageLine(message));
  } else if (message.kind === 'end') {
    markLive(false);
    if (news) refresh(); // its files are newer than those drawn
  } else if (message.kind === 'failed') {
    markLive(false);
    if (news) say(token, `The run stopped: ${message.error}`, true);
  }
  scheduleDraw();
}

// What a stage message reads as in the status line.
function stageLine({ stage, state, seconds, note }) {
  const minutes = `${Math.round(seconds / 60)} min`;
  const took = seconds ? ` in ${seconds < 60 ? `${seconds}s` : minutes}` : '';
  const said = note ? ` (${note})` : '';
  if (state === 'start') return `${stage}…`;
  if (state === 'failed') return `${stage} stopped${said}`;
  return `${stage} done${took}${said}`;
}

// At work, or no longer: the open run's own stream says so before the list,
// which is asked every few seconds, catches up.
function markLive(running) {
  session.running = running;
  const run = runOf(session.id);
  if (!run || run.running === running || run.running === null) return;
  run.running = running;
  ui.renderRuns(runs, (id) => { location.hash = id; });
  ui.selectRun(session.id);
}

// The history arrives in a burst: draw once per frame, not once per message.
let drawing = false;
function scheduleDraw() {
  if (drawing) return;
  drawing = true;
  requestAnimationFrame(() => {
    drawing = false;
    drawStep();
  });
}

function drawStep() {
  const { steps, index } = session;
  ui.renderTimeline(steps, index, session.running, (i) => {
    session.index = i;
    drawStep();
  });
  if (index < 0) return;
  // sfmkit's points and cameras become the step's; the old photo stays.
  view.showStep(steps[index], session.K);
  if (!session.scene && !session.fitted) {
    view.fit();
    session.fitted = true;
  }
  showLayers();
  showCameras();
}

// Look through a camera, its photo in front of it.
async function lookThrough(key) {
  const shot = view.cameras().find((c) => c.key === key);
  if (!shot) return;
  const token = session.token;
  const base = session.scene?.images;
  const loaded = view.lookThrough(key, base && `${base}/${encodeURIComponent(shot.name)}`);
  showCameras();
  showPhotoBar();
  if (!(await loaded)) say(token, `No photo of ${shot.name} to show`);
}

function closePhoto() {
  view.closePhoto();
  showCameras();
  showPhotoBar();
}

// A click, not a drag, on a camera looks through it.
let press = null;
canvas.addEventListener('pointerdown', (e) => {
  press = { x: e.clientX, y: e.clientY, at: performance.now() };
});
canvas.addEventListener('pointerup', (e) => {
  const click = press && Math.hypot(e.clientX - press.x, e.clientY - press.y) < 5
    && performance.now() - press.at < 500;
  press = null;
  const key = click && view.pick(e.clientX, e.clientY);
  if (key) lookThrough(key);
  queueHover(key ? null : { x: e.clientX, y: e.clientY }); // the view may have moved under it
});

// The camera under the pointer, outlined and named, so a click takes what it
// shows. Once a frame at most; not while dragging.
const hoverLabel = document.getElementById('hover-label');
let pointer = null;
let hoverQueued = false;
function queueHover(next) {
  pointer = next;
  if (hoverQueued) return;
  hoverQueued = true;
  requestAnimationFrame(() => {
    hoverQueued = false;
    const key = pointer ? view.hover(pointer.x, pointer.y) : view.hover();
    const shot = key && view.cameras().find((c) => c.key === key);
    canvas.style.cursor = shot ? 'pointer' : '';
    hoverLabel.hidden = !shot;
    if (!shot) return;
    const source = document.createElement('span');
    source.className = 'source';
    source.textContent = `${colours(shot.source).label}${shot.query ? ' old photo' : ''}`;
    hoverLabel.replaceChildren(shot.name, source);
    const stage = canvas.getBoundingClientRect();
    hoverLabel.style.left = `${pointer.x - stage.left + 14}px`;
    hoverLabel.style.top = `${pointer.y - stage.top + 14}px`;
  });
}
canvas.addEventListener('pointermove', (e) => queueHover(e.buttons ? null : { x: e.clientX, y: e.clientY }));
canvas.addEventListener('wheel', (e) => queueHover({ x: e.clientX, y: e.clientY }), { passive: true });
canvas.addEventListener('pointerleave', () => queueHover(null));
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && view.looking()) closePhoto();
  // Step through the timeline, as a sequencer's arrows do.
  const move = { ArrowLeft: -1, ArrowRight: 1 }[e.key];
  if (move && session.steps.length && !(e.target instanceof HTMLInputElement)) {
    session.index = Math.min(Math.max(session.index + move, 0), session.steps.length - 1);
    drawStep();
    e.preventDefault();
  }
});

// The run list again, and the open run's results if its files changed.
async function refresh() {
  const asked = Date.now();
  try {
    runs = await listRuns();
  } catch {
    return; // the server may be restarting; keep what there is
  }
  ui.renderRuns(runs, (id) => { location.hash = id; });
  ui.selectRun(session.id);
  const run = runOf(session.id);
  // A start with no end: sfmkit's heartbeat says whether it is still at work.
  // Only an answer asked for after the start counts, or a run just begun would
  // be taken for a dead one.
  if (session.running && run?.running === false && session.startSeen < asked) {
    markLive(false);
    say(session.token, 'The run stopped without a word: sfmkit is no longer at work.', true);
    scheduleDraw();
  }
  if (!session.id && runs.length) {
    // The page came up before any run, or before the server: start now.
    ui.status('');
    liveOn = await health().then((h) => h.live, () => liveOn);
    go(initial());
  } else if (run && run.updated !== session.updated) {
    session.updated = run.updated;
    showScene(session.token);
  }
}

// The run in the hash, or else the one with the most to draw.
function initial() {
  const wanted = decodeURIComponent(location.hash.slice(1));
  if (runOf(wanted)) return wanted;
  const most = Math.max(...runs.map((r) => r.layers.length));
  return runs.find((r) => r.layers.length === most)?.id;
}

async function start() {
  window.addEventListener('hashchange', () => open(decodeURIComponent(location.hash.slice(1))));
  setInterval(refresh, 5000); // new runs, and new results, without a reload
  try {
    [runs, { live: liveOn }] = await Promise.all([listRuns(), health()]);
  } catch (error) {
    ui.status(`Could not reach the server: ${error.message}`, true);
    return;
  }
  if (!runs.length) {
    ui.status('No runs yet: run sfmkit first.');
    return;
  }
  ui.renderRuns(runs, (id) => { location.hash = id; });
  go(initial());
}

// Open a run through the hash, so the address names it.
function go(id) {
  if (location.hash.slice(1) === id) open(id);
  else location.hash = id;
}

start();
