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
        ...run.layers.map((l) => el('span', { class: 'badge' }, l)),
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
    ['reference', scene.reference ?? '—'],
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
