// A run's live progress over a WebSocket: the stream's history, then each new
// message. It reconnects when the connection drops, resuming after the last
// message it saw, so nothing is missed and nothing repeated.

const FINAL = new Set([4404, 4503]); // not a run; live progress off

export class LiveFeed {
  #url;
  #onEvent;
  #onClock;
  #socket = null;
  #timer = null;
  #after = '0';
  #retry = 1000;
  #stopped = false;

  // ``onEvent({id, message})`` for each message; ``onClock(ms)`` with the
  // server's clock each time the connection opens.
  constructor(url, onEvent, onClock = () => {}) {
    this.#url = url;
    this.#onEvent = onEvent;
    this.#onClock = onClock;
  }

  start() {
    this.#connect();
    return this;
  }

  stop() {
    this.#stopped = true;
    clearTimeout(this.#timer);
    this.#socket?.close();
  }

  #connect() {
    if (this.#stopped) return;
    const socket = new WebSocket(`${this.#url}?after=${encodeURIComponent(this.#after)}`);
    socket.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if ('now' in data) {
        this.#onClock(data.now);
        return;
      }
      this.#after = data.id;
      this.#retry = 1000;
      this.#onEvent(data);
    };
    socket.onclose = (e) => {
      if (this.#stopped || FINAL.has(e.code)) return;
      this.#timer = setTimeout(() => this.#connect(), this.#retry);
      this.#retry = Math.min(2 * this.#retry, 15000);
    };
    this.#socket = socket;
  }
}

// A stream recorded to a file, as a static copy of the page keeps it: the same
// entries, all history, handed over at once.
export class RecordedFeed {
  #url;
  #onEvent;
  #stopped = false;

  constructor(url, onEvent) {
    this.#url = url;
    this.#onEvent = onEvent;
  }

  start() {
    this.#load();
    return this;
  }

  stop() {
    this.#stopped = true;
  }

  async #load() {
    const response = await fetch(this.#url).catch(() => null);
    if (!response?.ok) return; // a run with no recording has no timeline
    for (const event of await response.json()) {
      if (this.#stopped) return;
      this.#onEvent(event);
    }
  }
}

// When a stream entry was written, on the server's clock: its id is
// "<milliseconds>-<n>".
export const writtenAt = (id) => Number(id.split('-')[0]);
