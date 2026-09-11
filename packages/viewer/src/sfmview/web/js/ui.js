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

// Where a run's GPU-capable stages ran: one word if they agree, else each.
function device(devices = {}) {
  const word = { cuda: 'GPU', cpu: 'CPU' };
  const all = Object.entries(devices);
  if (!all.length) return null;
  const seen = new Set(all.map(([, d]) => d));
  return seen.size === 1 ? word[[...seen][0]] ?? [...seen][0]
    : all.map(([stage, d]) => `${stage} ${word[d] ?? d}`).join(' · ');
}
const count = (n) => n.toLocaleString('en');
const pad = (n, width) => String(n).padStart(width, '0');

// What a run holds, as three cells: sfmkit's model, COLMAP's, the dense cloud.
const HOLDS = [['sfmkit', 'S', 'sfmkit model'], ['colmap', 'C', 'COLMAP model'],
  ['dense', 'D', 'dense cloud']];

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
    el('span', { class: 'has' }, ...HOLDS.map(([layer, key, what]) => el('span', {
      class: run.layers.includes(layer) ? 'on' : '',
      'data-tip': run.layers.includes(layer) ? what : `no ${what}`,
    }, key))),
    el('span', {
      class: mean ? 'metric' : 'metric none', title: 'mean rotation error against COLMAP',
    }, mean ?? '—'));
  }));
}

export function selectRun(id) {
  for (const li of $('runs').children) li.setAttribute('aria-selected', String(li.dataset.id === id));
}

// Layers under their model's name, in the order given.
export function renderLayers(layers, onToggle) {
  const rows = [];
  layers.forEach((layer, i) => {
    if (layer.group !== layers[i - 1]?.group) rows.push(el('li', { class: 'group' }, layer.group));
    const box = el('input', { type: 'checkbox', onchange: (e) => onToggle(layer.id, e.target.checked) });
    box.checked = layer.visible;
    const swatch = layer.color === 'rgb'
      ? el('span', { class: 'swatch rgb' })
      : el('span', { class: 'swatch', style: `background:${layer.color}` });
    rows.push(el('li', {}, el('label', {}, box, swatch, layer.label),
      el('span', { class: 'count' }, count(layer.count))));
  });
  $('layers').replaceChildren(...rows);
}

// One row a photo, a key for each model that placed it; ``selected`` is lit.
// ``step``, the timeline's step drawn, if any: its cameras are sfmkit's.
export function renderCameras(cameras, selected, onPick, step = null) {
  // A live step is sfmkit's model as it stood: it takes sfmkit's column, before
  // the finished model's camera.
  const column = (c) => (c.source === 'live' ? 'sfmkit' : c.source);
  const byName = new Map();
  for (const c of cameras) {
    if (!byName.has(c.name)) byName.set(c.name, []);
    byName.get(c.name).push(c);
  }
  // A column per model, in a fixed order, so the keys line up down the list.
  const columns = ['sfmkit', 'colmap'].filter((m) => cameras.some((c) => column(c) === m));
  const live = cameras.some((c) => c.source === 'live');
  const as = (s) => (s.source === 'live' ? `sfmkit, step ${step + 1}`
    : `${colours(s.source).label}${s.query ? ' old photo' : ''}`);
  $('cameras').replaceChildren(...[...byName.keys()].sort().map((name) => {
    const shots = byName.get(name);
    return el('li', {},
      el('span', { class: 'cam' }, name),
      shots.some((s) => s.query) && el('span', { class: 'note' }, 'old photo'),
      el('span', { class: 'keys' }, ...columns.map((model) => {
        const s = shots.filter((shot) => column(shot) === model)
          .sort((a, b) => (b.source === 'live') - (a.source === 'live'))[0];
        if (!s) {
          const why = model === 'sfmkit' && live ? `not yet, step ${step + 1}` : 'not placed';
          return el('span', { class: 'gap', 'data-tip': `${colours(model).label}: ${why}` });
        }
        return el('button', {
          type: 'button',
          class: s.key === selected ? 'on' : '',
          style: `--c:${colours(model).main}`,
          'data-tip': as(s),
          'aria-label': `look through ${name} as ${as(s)} placed it`,
          onclick: () => onPick(s.key),
        }, colours(model).key);
      })));
  }));
}

export function renderInfo(run, scene) {
  const rows = [
    ['run', run.id],
    ['device', device(run.devices) ?? '—'],
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
