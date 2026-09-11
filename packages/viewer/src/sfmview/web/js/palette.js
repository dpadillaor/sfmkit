// The data's colours, one per model, shared by the view and the panel. The
// interface's own signal colour lives in style.css.

export const SIGNAL = '#ff4f00';

export const PALETTE = {
  sfmkit: { main: '#f2a93b', query: '#ff6fae', label: 'sfmkit', key: 'S' },
  colmap: { main: '#56a8f5', query: '#a98bf5', label: 'COLMAP', key: 'C' },
  // A live step is sfmkit's model as it stood, so it takes sfmkit's colour.
  live: { main: '#f2a93b', query: '#ff6fae', label: 'sfmkit step', key: 'S' },
  other: { main: '#bbbbbb', query: '#ffffff', label: 'other', key: '?' },
};

export const colours = (source) => PALETTE[source] ?? PALETTE.other;
