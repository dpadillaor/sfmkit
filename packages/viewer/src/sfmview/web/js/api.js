// The server's JSON API. Nothing else in the page knows the URLs.

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
  return `/api/runs/${encodeURIComponent(project)}/${encodeURIComponent(config)}`;
}

export const health = () => json('/api/health');
export const listRuns = () => json('/api/runs');
export const getScene = (id) => json(`${runPath(id)}/scene`);

export function liveUrl(id) {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${location.host}${runPath(id)}/live`;
}
