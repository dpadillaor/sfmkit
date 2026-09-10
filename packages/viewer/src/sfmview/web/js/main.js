// Wires the page: the API's runs into the sidebar, the chosen run into the view,
// and its live progress, if the server has a broker, into the timeline.
// The URL's hash names the run (#valencia/9cameras), so a view can be linked.

import { getScene, health, listRuns, liveUrl } from './api.js';
import { LiveFeed, writtenAt } from './live.js';
import { SceneView } from './scene.js';
import * as ui from './ui.js';

const view = new SceneView(document.getElementById('view'));
let runs = [];
let liveOn = false;

// The open run: its finished scene, and the steps of its live stream.
const session = {
  id: null, feed: null, scene: null, loadedAt: 0,
  K: null, steps: [], index: -1, running: false, hidFinished: false, fitted: false,
};

const showLayers = () => ui.renderLayers(view.layers(), (id, on) => view.setVisible(id, on));
const runOf = (id) => runs.find((r) => r.id === id);

async function open(id) {
  if (!runOf(id)) return;
  session.feed?.stop();
  Object.assign(session, {
    id, feed: null, scene: null, K: null, steps: [], index: -1, running: false,
  });
  ui.selectRun(id);
  ui.renderTimeline([], -1);
  await showScene(id);
  if (liveOn && session.id === id) {
    session.feed = new LiveFeed(liveUrl(id), (event) => onLive(id, event)).start();
  }
}

// The run's finished results, if it has any yet, with its current step on top.
async function showScene(id) {
  ui.status(`Loading ${id}…`);
  let scene = null;
  try {
    scene = await getScene(id);
  } catch (error) {
    if (error.status !== 404) {
      ui.status(`Could not load ${id}: ${error.message}`, true);
      return;
    }
  }
  if (session.id !== id) return; // another run was opened meanwhile
  Object.assign(session, { scene, loadedAt: Date.now(), hidFinished: false, fitted: false });
  view.show(scene ?? { models: [], reference: null });
  drawStep();
  showLayers();
  ui.renderInfo(runOf(id), scene);
  ui.status(scene ? '' : 'No results yet: waiting for the run.');

  if (scene?.dense) {
    try {
      const n = await view.loadDense(scene.dense,
        (f) => ui.status(`Loading the dense cloud… ${Math.round(100 * f)}%`));
      if (n === null || session.id !== id) return;
      showLayers();
      ui.status('');
    } catch (error) {
      ui.status(`Could not load the dense cloud: ${error.message}`, true);
    }
  }
}

function onLive(id, { id: entry, message }) {
  if (session.id !== id) return;
  if (message.kind === 'start') {
    Object.assign(session, { K: message.K, steps: [], index: -1, running: true });
  } else if (message.kind === 'step') {
    const following = session.index === session.steps.length - 1;
    session.steps.push(message);
    if (following) session.index = session.steps.length - 1;
  } else if (message.kind === 'end') {
    session.running = false;
    // Finished while the page watched: its files are newer than those drawn.
    if (writtenAt(entry) > session.loadedAt) refresh();
  }
  scheduleDraw();
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
  if (!session.hidFinished) {
    // The growing model says it all; the finished one stays a click away.
    view.setVisible('sfmkit-points', false);
    view.setVisible('sfmkit-cameras', false);
    session.hidFinished = true;
  }
  view.showStep(steps[index], session.K);
  if (!session.scene && !session.fitted) {
    view.fit();
    session.fitted = true;
  }
  showLayers();
}

async function refresh() {
  try {
    runs = await listRuns();
  } catch {
    return; // keep the list there is
  }
  ui.renderRuns(runs, (id) => { location.hash = id; });
  ui.selectRun(session.id);
  if (session.id) await showScene(session.id);
}

// The run in the hash, or else the one with the most to draw.
function initial() {
  const wanted = decodeURIComponent(location.hash.slice(1));
  if (runOf(wanted)) return wanted;
  const most = Math.max(...runs.map((r) => r.layers.length));
  return runs.find((r) => r.layers.length === most)?.id;
}

async function start() {
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
  window.addEventListener('hashchange', () => open(decodeURIComponent(location.hash.slice(1))));
  // New runs appear in the list without a reload.
  setInterval(async () => {
    try {
      runs = await listRuns();
      ui.renderRuns(runs, (id) => { location.hash = id; });
      ui.selectRun(session.id);
    } catch { /* the server may be restarting */ }
  }, 15000);
  const id = initial();
  if (location.hash.slice(1) === id) open(id);
  else location.hash = id;
}

start();
