import assert from "node:assert/strict";
import { LiveFramePipeline } from "../dashboard-v2/live-frame-pipeline.js";

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
};

const flush = () => new Promise((resolve) => setImmediate(resolve));

async function slowAndFastFrames() {
  const decodes = [];
  const rendered = [];
  const pipeline = new LiveFramePipeline({
    decodeFrame(frame) {
      const operation = deferred();
      decodes.push({ frame, operation });
      return operation.promise;
    },
    renderFrame(slot, bitmap) {
      rendered.push([slot, bitmap.frame]);
      return true;
    },
  });

  pipeline.enqueue(1, "frame-1");
  await flush();
  pipeline.enqueue(1, "frame-2");
  pipeline.enqueue(1, "frame-3");
  assert.equal(decodes.length, 1, "only one decode may run per slot");
  decodes[0].operation.resolve({ frame: "frame-1", close() {} });
  await flush();
  assert.equal(decodes.length, 2);
  assert.equal(decodes[1].frame, "frame-3", "only newest pending frame survives");
  decodes[1].operation.resolve({ frame: "frame-3", close() {} });
  await flush();

  const stats = pipeline.diagnostics(1)[0];
  assert.deepEqual(rendered, [[1, "frame-1"], [1, "frame-3"]]);
  assert.equal(stats.receivedFrameCount, 3);
  assert.equal(stats.renderedFrameCount, 2);
  assert.equal(stats.droppedFrameCount, 1);
  assert.equal(stats.maximumDecodeCount, 1);
  return stats;
}

async function offscreenAndHiddenRecovery() {
  let visible = false;
  let rendered = 0;
  const pipeline = new LiveFramePipeline({
    decodeFrame: async (frame) => ({ frame, close() {} }),
    renderFrame() {
      if (!visible) return false;
      rendered += 1;
      return true;
    },
  });

  for (let second = 0; second < 10; second += 1) {
    pipeline.enqueue(2, `offscreen-${second}`);
    await flush();
  }
  visible = true;
  pipeline.enqueue(2, "visible-again");
  await flush();
  assert.equal(rendered, 1, "rendering resumes after an off-screen/hidden interval");
  const stats = pipeline.diagnostics(1)[0];
  assert.equal(stats.maximumDecodeCount, 1);
  return stats;
}

async function removedCanvasAndLifecycleReset() {
  const operations = [];
  const rendered = [];
  const pipeline = new LiveFramePipeline({
    decodeFrame(frame) {
      const operation = deferred();
      operations.push({ frame, operation });
      return operation.promise;
    },
    renderFrame(slot, bitmap) {
      rendered.push(bitmap.frame);
      return true;
    },
  });

  pipeline.enqueue(3, "old-page");
  await flush();
  pipeline.reset(3);
  pipeline.enqueue(3, "new-page");
  assert.equal(operations.length, 1, "restart must wait for obsolete decode to settle");
  operations[0].operation.resolve({ frame: "old-page", close() {} });
  await flush();
  assert.equal(operations.length, 2);
  operations[1].operation.resolve({ frame: "new-page", close() {} });
  await flush();
  assert.deepEqual(rendered, ["new-page"], "obsolete decode must not draw after navigation");
  const stats = pipeline.diagnostics(1)[0];
  assert.equal(stats.maximumDecodeCount, 1);
  return stats;
}

async function reconnectAndMultipleSlots() {
  const rendered = [];
  const pipeline = new LiveFramePipeline({
    decodeFrame: async (frame) => ({ frame, close() {} }),
    renderFrame(slot, bitmap) {
      rendered.push([slot, bitmap.frame]);
      return true;
    },
  });

  pipeline.enqueue(4, "a");
  pipeline.enqueue(5, "b");
  await flush();
  pipeline.resetAll();
  pipeline.enqueue(4, "a-reconnected");
  pipeline.enqueue(5, "b-reconnected");
  await flush();
  assert(rendered.some(([slot, frame]) => slot === 4 && frame === "a-reconnected"));
  assert(rendered.some(([slot, frame]) => slot === 5 && frame === "b-reconnected"));
  assert(pipeline.diagnostics(1).every((row) => row.maximumDecodeCount === 1));
  return pipeline.diagnostics(1);
}

async function fiveMinuteEquivalentSustainedStream() {
  let rendered = 0;
  const pipeline = new LiveFramePipeline({
    decodeFrame: async (frame) => ({ frame, close() {} }),
    renderFrame() {
      rendered += 1;
      return true;
    },
  });

  // 10 FPS × 300 seconds. Run without wall-clock waiting.
  for (let frame = 0; frame < 3000; frame += 1) {
    pipeline.enqueue(6, frame);
    if (frame % 5 === 0) await flush();
  }
  for (let attempt = 0; attempt < 10; attempt += 1) await flush();
  const stats = pipeline.diagnostics(1)[0];
  assert.equal(stats.receivedFrameCount, 3000);
  assert(stats.renderedFrameCount > 0);
  assert(rendered > 0);
  assert.equal(stats.maximumDecodeCount, 1);
  assert.equal(stats.decodeErrorCount, 0);
  return stats;
}

const evidence = {
  coalescing: await slowAndFastFrames(),
  offscreenRecovery: await offscreenAndHiddenRecovery(),
  lifecycleReset: await removedCanvasAndLifecycleReset(),
  multipleSlots: await reconnectAndMultipleSlots(),
  sustainedFiveMinuteEquivalent: await fiveMinuteEquivalentSustainedStream(),
};
console.log("live-frame pipeline harness: PASS");
console.log(JSON.stringify(evidence, null, 2));
