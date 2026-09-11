// The panel and the overlays: runs, layers, cameras, the run's facts, the
// timeline, the photo bar and the status line. DOM only.

import { colours } from './palette.js';

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') node.className = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined && c !== false));
  return node;
}

const degrees = (x) => (x === null || x === undefined ? null : `${x.toFixed(2)}°`);
const count = (n) => n.toLocaleString('en');
const pad = (n, width) => String(n).padStart(width, '0');

// What a run holds, as three cells: sfmkit's model, COLMAP's, the dense cloud.
const HOLDS = [['sfmkit', 'S'], ['colmap', 'C'], ['dense', 'D']];

export function renderRuns(runs, onSelect) {
  $('runs').replaceChildren(...runs.map((run) => {
    const mean = degrees(run.metrics.mean_rotation_error_deg);
    return el('li', {
      'data-id': run.id, 'aria-selected': 'false', title: run.id, onclick: () => onSelect(run.id),
    },
    el('div', { class: 'what' },
      el('span', { class: 'name' }, run.config,
        run.running && el('span', { class: 'live', title: 'sfmkit is at work on this run' }, 'live')),
      el('span', { class: 'project' }, run.project)),
    el('span', { class: 'has' }, ...HOLDS.map(([layer, key]) => el('span', {
      class: run.layers.includes(layer) ? 'on' : '',
      title: run.layers.includes(layer) ? `has ${layer}` : `no ${layer} yet`,
    }, key))),
    el('span', {
      class: mean ? 'metric' : 'metric none', title: 'mean rotation error against COLMAP',
    }, mean ?? '—'));
  }));
}

export function selectRun(id) {
  for (const li of $('runs').children) li.setAttribute('aria-selected', String(li.dataset.id === id));
}

export function renderLayers(layers, onToggle) {
  $('layers').replaceChildren(...layers.map((layer) => {
    const box = el('input', { type: 'checkbox', onchange: (e) => onToggle(layer.id, e.target.checked) });
    box.checked = layer.visible;
    const swatch = layer.color === 'rgb'
      ? el('span', { class: 'swatch rgb' })
      : el('span', { class: 'swatch', style: `background:${layer.color}` });
    return el('li', {}, el('label', {}, box, swatch, layer.label),
      el('span', { class: 'count' }, count(layer.count)));
  }));
}

// One row a photo, a key for each model that placed it; ``selected`` is lit.
export function renderCameras(cameras, selected, onPick) {
  const byName = new Map();
  for (const c of cameras) {
    if (!byName.has(c.name)) byName.set(c.name, []);
    byName.get(c.name).push(c);
  }
  // A column per model, in a fixed order, so the keys line up down the list.
  const columns = ['sfmkit', 'colmap', 'live'].filter((m) => cameras.some((c) => c.source === m));
  $('cameras').replaceChildren(...[...byName.keys()].sort().map((name) => {
    const shots = byName.get(name);
    return el('li', {},
      el('span', { class: 'cam' }, name),
      shots.some((s) => s.query) && el('span', { class: 'note' }, 'old photo'),
      el('span', { class: 'keys' }, ...columns.map((model) => {
        const s = shots.find((shot) => shot.source === model);
        if (!s) return el('span', { class: 'gap', title: `${colours(model).label} did not place ${name}` });
        return el('button', {
          type: 'button',
          class: s.key === selected ? 'on' : '',
          style: `--c:${colours(s.source).main}`,
          title: `look through ${name} as ${colours(s.source).label} placed it`,
          onclick: () => onPick(s.key),
        }, colours(s.source).key);
      })));
  }));
}

export function renderInfo(run, scene) {
  const rows = [
    ['run', run.id],
    ['stages', run.stages.join(' ')],
    ['reference', scene?.reference ?? '—'],
    ['mean rot err', degrees(run.metrics.mean_rotation_error_deg) ?? '—'],
    ['max rot err', degrees(run.metrics.max_rotation_error_deg) ?? '—'],
    ['old photo err', degrees(run.metrics.query_rotation_error_deg) ?? '—'],
    ['updated', run.updated ? run.updated.slice(0, 16).replace('T', ' ') : '—'],
  ];
  $('info').replaceChildren(...rows.flatMap(([k, v]) => [el('dt', {}, k), el('dd', {}, v)]));
}

// The live run's steps, one cell each: hidden without any; ``index`` is lit.
export function renderTimeline(steps, index, running, onStep) {
  const bar = $('timeline');
  bar.hidden = steps.length === 0;
  if (bar.hidden) return;
  $('live-badge').hidden = !running;
  const width = String(steps.length).length < 2 ? 2 : String(steps.length).length;
  $('step-count').textContent = `${pad(index + 1, width)}/${pad(steps.length, width)}`;
  $('steps').replaceChildren(...steps.map((s, i) => el('button', {
    type: 'button',
    class: i === index ? 'on' : i < index ? 'done' : '',
    title: `step ${i + 1}: ${s.image}`,
    'aria-label': `step ${i + 1}`,
    onclick: () => onStep(i),
  })));
  const s = steps[index];
  const rmse = s.rmse_after === null ? '' : ` · ${s.rmse_after.toFixed(2)} px`;
  $('step-label').textContent = `${s.image} · ${s.n_registered} cam · ${count(s.n_points)} pts${rmse}`;
}

// The camera looked through, if any: its name, the photo's opacity, a way back
// to it once the view has moved, and a way out.
export function renderPhotoBar(looking, { onOpacity, onBack, onClose }) {
  const bar = $('photo-bar');
  bar.hidden = !looking;
  if (!looking) return;
  $('photo-name').textContent = `${looking.name} · ${colours(looking.source).label}`;
  const slider = $('photo-opacity');
  slider.value = String(looking.opacity);
  slider.oninput = () => onOpacity(Number(slider.value));
  $('photo-back').hidden = looking.active;
  $('photo-back').onclick = onBack;
  $('photo-close').onclick = onClose;
}

export function status(text, error = false) {
  const node = $('status');
  node.textContent = text;
  node.classList.toggle('error', error);
}
