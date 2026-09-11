// The sidebar: runs, layers, the run's facts, and a status line. DOM only.

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') node.className = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined));
  return node;
}

const degrees = (x) => (x === null || x === undefined ? null : `${x.toFixed(2)}°`);
const count = (n) => n.toLocaleString('en');

export function renderRuns(runs, onSelect) {
  $('runs').replaceChildren(...runs.map((run) => {
    const mean = degrees(run.metrics.mean_rotation_error_deg);
    return el('li', { 'data-id': run.id, 'aria-selected': 'false', title: run.id, onclick: () => onSelect(run.id) },
      el('div', { class: 'name' }, run.config),
      el('div', { class: 'meta' },
        run.project,
        ...(run.layers.length ? run.layers.map((l) => el('span', { class: 'badge' }, l))
          : [el('span', { class: 'badge' }, 'no results yet')]),
        mean && el('span', { class: 'metric', title: 'mean rotation error against COLMAP' }, mean)));
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

export function renderInfo(run, scene) {
  const rows = [
    ['run', run.id],
    ['stages', run.stages.join(', ')],
    ['reference', scene?.reference ?? '—'],
    ['mean rot. err', degrees(run.metrics.mean_rotation_error_deg) ?? '—'],
    ['max rot. err', degrees(run.metrics.max_rotation_error_deg) ?? '—'],
    ['query rot. err', degrees(run.metrics.query_rotation_error_deg) ?? '—'],
    ['updated', run.updated ? new Date(run.updated).toLocaleString() : '—'],
  ];
  $('info').replaceChildren(...rows.flatMap(([k, v]) => [el('dt', {}, k), el('dd', {}, v)]));
}

export function status(text, error = false) {
  const node = $('status');
  node.hidden = !text;
  node.textContent = text;
  node.classList.toggle('error', error);
}

// The live run's steps: hidden without any; ``index`` is the one drawn.
export function renderTimeline(steps, index, running, onScrub) {
  const bar = $('timeline');
  bar.hidden = steps.length === 0;
  if (bar.hidden) return;
  const scrub = $('scrub');
  scrub.max = String(steps.length - 1);
  scrub.value = String(index);
  scrub.oninput = () => onScrub(Number(scrub.value));
  $('live-badge').hidden = !running;
  const s = steps[index];
  const rmse = s.rmse_after === null ? '' : ` · rmse ${s.rmse_after.toFixed(2)} px`;
  $('step-label').textContent = `step ${index + 1}/${steps.length} · ${s.image} · `
    + `${s.n_registered} cameras · ${count(s.n_points)} points${rmse}`;
}

const SOURCE = {
  sfmkit: { label: 'sfmkit', color: '#ff9a3c' },
  colmap: { label: 'COLMAP', color: '#4db3ff' },
  live: { label: 'step', color: '#ffd166' },
};
const source = (s) => SOURCE[s] ?? { label: s, color: '#cccccc' };

// One row per photo, a chip per model that placed it; ``selected`` is lit.
export function renderCameras(cameras, selected, onPick) {
  const byName = new Map();
  for (const c of cameras) {
    if (!byName.has(c.name)) byName.set(c.name, []);
    byName.get(c.name).push(c);
  }
  $('cameras').replaceChildren(...[...byName.keys()].sort().map((name) => {
    const shots = byName.get(name);
    return el('li', {},
      el('span', { class: 'cam-name' }, name,
        shots.some((s) => s.query) ? el('span', { class: 'muted' }, ' · old photo') : null),
      el('span', { class: 'chips' }, ...shots.map((s) => el('button', {
        type: 'button',
        class: s.key === selected ? 'chip on' : 'chip',
        style: `--c:${source(s.source).color}`,
        title: `look through ${name} as ${source(s.source).label} placed it`,
        onclick: () => onPick(s.key),
      }, source(s.source).label))));
  }));
}

// The camera looked through, if any: its name, the photo's opacity, a way back
// to it once the view has moved, and a way out.
export function renderPhotoBar(looking, { onOpacity, onBack, onClose }) {
  const bar = $('photo-bar');
  bar.hidden = !looking;
  if (!looking) return;
  $('photo-name').textContent = `${looking.name} · ${source(looking.source).label}`;
  const slider = $('photo-opacity');
  slider.value = String(looking.opacity);
  slider.oninput = () => onOpacity(Number(slider.value));
  $('photo-back').hidden = looking.active;
  $('photo-back').onclick = onBack;
  $('photo-close').onclick = onClose;
}
