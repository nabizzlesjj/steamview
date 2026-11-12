/**
 * Starting a trailer, with or without sound.
 *
 * Node has no media elements, so these drive `startPlayback` with a fake
 * that resolves or rejects `play()` the way Chromium does. The behaviour
 * against a real <video> under both autoplay policies was checked
 * separately in a browser; these pin the decisions so they cannot drift.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { startPlayback } from "../../.tsbuild/src/playback.js";

/** A media element whose play() answers from a script, one entry per call. */
function fakeMedia(answers) {
  const calls = [];
  return {
    muted: false,
    calls,
    play() {
      calls.push({ muted: this.muted });
      const answer = answers.shift() ?? "ok";
      if (answer === "ok") return Promise.resolve();
      const error = new Error(answer);
      error.name = answer;
      return Promise.reject(error);
    },
  };
}

function hooks() {
  const seen = { sound: [], forced: 0, unplayable: 0 };
  return {
    seen,
    onSound: (outcome) => seen.sound.push(outcome),
    onForcedMute: () => seen.forced++,
    onUnplayable: () => seen.unplayable++,
  };
}

const notCancelled = () => false;

test("sound requested and allowed: plays audibly and says so", async () => {
  const media = fakeMedia(["ok"]);
  const h = hooks();
  await startPlayback(media, false, notCancelled, h);
  assert.equal(media.muted, false);
  assert.deepEqual(h.seen, { sound: ["ok"], forced: 0, unplayable: 0 });
});

test("muted: plays silently and reports nothing about sound", async () => {
  const media = fakeMedia(["ok"]);
  const h = hooks();
  await startPlayback(media, true, notCancelled, h);
  assert.equal(media.muted, true);
  assert.deepEqual(h.seen, { sound: [], forced: 0, unplayable: 0 });
});

test("sound refused: retries silently, keeps the trailer, reports blocked", async () => {
  const media = fakeMedia(["NotAllowedError", "ok"]);
  const h = hooks();
  await startPlayback(media, false, notCancelled, h);
  assert.deepEqual(media.calls, [{ muted: false }, { muted: true }]);
  assert.deepEqual(h.seen, { sound: ["blocked"], forced: 1, unplayable: 0 });
});

test("refused even silently: falls back to screenshots", async () => {
  const media = fakeMedia(["NotAllowedError", "NotAllowedError"]);
  const h = hooks();
  await startPlayback(media, false, notCancelled, h);
  assert.equal(h.seen.unplayable, 1);
});

test("a muted refusal is not mistaken for a sound problem", async () => {
  const media = fakeMedia(["NotAllowedError"]);
  const h = hooks();
  await startPlayback(media, true, notCancelled, h);
  assert.deepEqual(h.seen, { sound: [], forced: 0, unplayable: 1 });
});

test("a broken source falls back without a silent retry", async () => {
  const media = fakeMedia(["NotSupportedError"]);
  const h = hooks();
  await startPlayback(media, false, notCancelled, h);
  assert.equal(media.calls.length, 1);
  assert.deepEqual(h.seen, { sound: [], forced: 0, unplayable: 1 });
});

test("an aborted start (source changed) does nothing", async () => {
  const media = fakeMedia(["AbortError"]);
  const h = hooks();
  await startPlayback(media, false, notCancelled, h);
  assert.deepEqual(h.seen, { sound: [], forced: 0, unplayable: 0 });
});

test("a superseded start never reports or falls back", async () => {
  const media = fakeMedia(["NotAllowedError"]);
  const h = hooks();
  await startPlayback(media, false, () => true, h);
  assert.deepEqual(h.seen, { sound: [], forced: 0, unplayable: 0 });
});
