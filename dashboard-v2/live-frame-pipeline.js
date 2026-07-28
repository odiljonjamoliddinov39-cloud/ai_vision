export class LiveFramePipeline {
  constructor({ decodeFrame, renderFrame, now = () => Date.now() }) {
    this.decodeFrame = decodeFrame;
    this.renderFrame = renderFrame;
    this.now = now;
    this.states = new Map();
    this.activeDecodeCounts = new Map();
    this.maximumDecodeCounts = new Map();
  }

  state(slot) {
    if (!this.states.has(slot)) {
      this.states.set(slot, {
        decoding: false,
        pendingFrame: null,
        lifecycleToken: 0,
        receivedFrameCount: 0,
        renderedFrameCount: 0,
        droppedFrameCount: 0,
        decodeErrorCount: 0,
        latestRenderedAt: 0,
        latestLatencyMs: null,
      });
    }
    return this.states.get(slot);
  }

  enqueue(slot, frame, { countReceived = true, metadata = null } = {}) {
    const state = this.state(slot);
    if (countReceived) state.receivedFrameCount += 1;

    if (state.decoding) {
      if (state.pendingFrame !== null) state.droppedFrameCount += 1;
      state.pendingFrame = { frame, metadata };
      return;
    }

    state.pendingFrame = { frame, metadata };
    this.decodeNext(slot);
  }

  decodeNext(slot) {
    const state = this.state(slot);
    if (state.decoding || state.pendingFrame === null) return;

    const { frame, metadata } = state.pendingFrame;
    const lifecycleToken = state.lifecycleToken;
    state.pendingFrame = null;
    state.decoding = true;
    const activeDecodes = (this.activeDecodeCounts.get(slot) || 0) + 1;
    this.activeDecodeCounts.set(slot, activeDecodes);
    this.maximumDecodeCounts.set(
      slot,
      Math.max(this.maximumDecodeCounts.get(slot) || 0, activeDecodes),
    );

    Promise.resolve()
      .then(() => this.decodeFrame(frame, slot))
      .then((bitmap) => {
        if (state.lifecycleToken !== lifecycleToken) {
          bitmap?.close?.();
          return;
        }
        try {
          if (this.renderFrame(slot, bitmap, metadata)) {
            state.renderedFrameCount += 1;
            state.latestRenderedAt = this.now();
            state.latestLatencyMs = metadata?.generatedAtMs
              ? Math.max(0, state.latestRenderedAt - metadata.generatedAtMs)
              : null;
          }
        } finally {
          bitmap?.close?.();
        }
      })
      .catch(() => {
        if (state.lifecycleToken === lifecycleToken) {
          state.decodeErrorCount += 1;
        }
      })
      .finally(() => {
        this.activeDecodeCounts.set(
          slot,
          Math.max(0, (this.activeDecodeCounts.get(slot) || 1) - 1),
        );
        if (state.lifecycleToken !== lifecycleToken) {
          state.decoding = false;
          if (state.pendingFrame !== null) this.decodeNext(slot);
          return;
        }
        state.decoding = false;
        if (state.pendingFrame !== null) this.decodeNext(slot);
      });
  }

  reset(slot) {
    const state = this.state(slot);
    state.lifecycleToken += 1;
    state.pendingFrame = null;
    // An obsolete decode may still be running. Keep the slot single-flight
    // until its finally handler releases it; newly arriving frames coalesce
    // into pendingFrame meanwhile.
    state.decoding = (this.activeDecodeCounts.get(slot) || 0) > 0;
  }

  resetAll() {
    for (const slot of this.states.keys()) this.reset(slot);
  }

  diagnostics(webSocketReadyState = null) {
    const now = this.now();
    return Array.from(this.states.entries()).map(([slot, state]) => ({
      slot,
      receivedFrameCount: state.receivedFrameCount,
      renderedFrameCount: state.renderedFrameCount,
      droppedFrameCount: state.droppedFrameCount,
      decodeErrorCount: state.decodeErrorCount,
      millisecondsSinceLastRenderedFrame:
        state.latestRenderedAt > 0 ? Math.max(0, now - state.latestRenderedAt) : null,
      latestLatencyMs: state.latestLatencyMs,
      decoding: state.decoding,
      pendingFrame: state.pendingFrame !== null,
      activeDecodeCount: this.activeDecodeCounts.get(slot) || 0,
      maximumDecodeCount: this.maximumDecodeCounts.get(slot) || 0,
      webSocketReadyState,
    }));
  }
}
