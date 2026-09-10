// Wires the page: the API's runs into the sidebar, the chosen run into the view.
// The URL's hash names the run (#valencia/9cameras), so a view can be linked.

import { getScene, listRuns } from './api.js';
import { SceneView } from './scene.js';
import * as ui from './ui.js';

const view = new SceneView(document.getElementById('view'));
let runs = [];

const showLayers = () => ui.renderLayers(view.layers(), (id, on) => view.setVisible(id, on));

async function open(id) {
  const run = runs.find((r) => r.id === id);
  if (!run) return;
  ui.selectRun(id);
  ui.status(`Loading ${id}…`);
  try {
    const scene = await getScene(id);
    view.show(scene);
    showLayers();
    ui.renderInfo(run, scene);
    ui.status('');
    if (scene.dense) {
      ui.status('Loading the dense cloud…');
      const n = await view.loadDense(scene.dense,
        (f) => ui.status(`Loading the dense cloud… ${Math.round(100 * f)}%`));
      if (n === null) return; // another run was opened meanwhile
      showLayers();
      ui.status('');
    }
  } catch (error) {
    ui.status(`Could not load ${id}: ${error.message}`, true);
  }
}

// The run in the hash, or else the one with the most to draw.
function initial() {
  const wanted = decodeURIComponent(location.hash.slice(1));
  if (runs.some((r) => r.id === wanted)) return wanted;
  const most = Math.max(...runs.map((r) => r.layers.length));
  return runs.find((r) => r.layers.length === most)?.id;
}

async function start() {
  try {
    runs = (await listRuns()).filter((r) => r.layers.length > 0);
  } catch (error) {
    ui.status(`Could not list the runs: ${error.message}`, true);
    return;
  }
  if (!runs.length) {
    ui.status('No runs to show yet: run sfmkit first.');
    return;
  }
  ui.renderRuns(runs, (id) => { location.hash = id; });
  window.addEventListener('hashchange', () => open(decodeURIComponent(location.hash.slice(1))));
  const id = initial();
  if (location.hash.slice(1) === id) open(id);
  else location.hash = id;
}

start();
