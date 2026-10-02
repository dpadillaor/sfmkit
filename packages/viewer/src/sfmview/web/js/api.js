// The server's JSON API. Nothing else in the page knows the URLs.
//
// A static copy of the page (`sfmview-export`) names where its saved answers
// are in a <meta name="sfmview-data">, relative to the page: then every answer
// is a file, the photos are JPEGs, and live progress is a recorded stream.

const DATA = document.querySelector('meta[name="sfmview-data"]')?.content ?? null;

// Whether the page is a static copy, with no server behind it.
export const isStatic = DATA !== null;

async function json(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(body.detail ?? `${response.status} ${response.statusText}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function runPath(id) {
  const [project, config] = id.split('/');
  return `${DATA ?? '/api/'}runs/${encodeURIComponent(project)}/${encodeURIComponent(config)}`;
}

// A static copy replays what it recorded, so it is always "live".
export const health = () => (isStatic ? Promise.resolve({ status: 'ok', live: true })
  : json('/api/health'));
export const listRuns = () => json(isStatic ? `${DATA}runs.json` : '/api/runs');
export const getScene = (id) => json(`${runPath(id)}/scene${isStatic ? '.json' : ''}`);

// A photo, from the scene's ``images``.
export const photoUrl = (base, name) => `${base}/${encodeURIComponent(name)}${isStatic ? '.jpg' : ''}`;

// Where a run's live progress comes from: a WebSocket, or a static copy's
// recording of the stream.
export function liveUrl(id) {
  if (isStatic) return `${runPath(id)}/steps.json`;
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${location.host}${runPath(id)}/live`;
}
