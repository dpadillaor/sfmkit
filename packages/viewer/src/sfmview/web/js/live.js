// A run's live progress over a WebSocket: the stream's history, then each new
// message. It reconnects when the connection drops, resuming after the last
// message it saw, so nothing is missed and nothing repeated.

const FINAL = new Set([4404, 4503]); // not a run; live progress off

export class LiveFeed {
  #url;
  #onEvent;
  #socket = null;
  #after = '0';
  #retry = 1000;
  #stopped = false;

  constructor(url, onEvent) {
    this.#url = url;
    this.#onEvent = onEvent;
  }

  start() {
    this.#connect();
    return this;
  }

  stop() {
    this.#stopped = true;
    this.#socket?.close();
  }

  #connect() {
    const socket = new WebSocket(`${this.#url}?after=${encodeURIComponent(this.#after)}`);
    socket.onmessage = (e) => {
      const event = JSON.parse(e.data);
      this.#after = event.id;
      this.#retry = 1000;
      this.#onEvent(event);
    };
    socket.onclose = (e) => {
      if (this.#stopped || FINAL.has(e.code)) return;
      setTimeout(() => this.#connect(), this.#retry);
      this.#retry = Math.min(2 * this.#retry, 15000);
    };
    this.#socket = socket;
  }
}

// When a stream entry was written, from its id ("<milliseconds>-<n>").
export const writtenAt = (id) => Number(id.split('-')[0]);
