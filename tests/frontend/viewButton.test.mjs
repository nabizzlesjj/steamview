/**
 * The View-button preview: reading Steam's controller callback, and the
 * per-game peek it drives.
 *
 * The callback's shape changed between Steam builds -- an array of
 * { nA, bS } on older ones, positional (controller, button, pressed) on
 * newer -- and a plugin handling only one goes silently dead on the
 * other. Both shapes are exercised here.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  CAPTURE_GRACE_MS,
  VIEW_BUTTON,
  buttonLabel,
  createCapture,
  parseControllerInput,
  pressDetector,
  toUnsubscribe,
} from "../../.tsbuild/src/steam/controllerInput.js";
import { peekAfterFocus, peekAfterPress } from "../../.tsbuild/src/peek.js";

test("View is EGamepadButton 9", () => {
  assert.equal(VIEW_BUTTON, 9);
});

test("the newer positional callback shape is parsed", () => {
  assert.deepEqual(parseControllerInput([0, 9, true]), [{ button: 9, pressed: true }]);
  assert.deepEqual(parseControllerInput([2, 9, false, "extra"]), [{ button: 9, pressed: false }]);
});

test("the older array-of-events callback shape is parsed", () => {
  assert.deepEqual(
    parseControllerInput([[{ nA: 0, bS: true }, { nA: 9, bS: true }, { nA: 9, bS: false }]]),
    [
      { button: 0, pressed: true },
      { button: 9, pressed: true },
      { button: 9, pressed: false },
    ],
  );
});

test("malformed input yields nothing rather than throwing", () => {
  for (const args of [[], [null], [undefined, undefined], [0, "9", true], [[null, { nA: "9" }, {}]], [{}]]) {
    assert.deepEqual(parseControllerInput(args), [], JSON.stringify(args));
  }
});

test("a press fires once, on the way down, for either shape", () => {
  let presses = 0;
  const detect = pressDetector(VIEW_BUTTON, () => presses++);
  detect(0, 9, true);
  detect(0, 9, true); // still held: Steam reporting it again is not a new press
  detect(0, 9, false);
  assert.equal(presses, 1);
  detect([{ nA: 9, bS: true }]);
  detect([{ nA: 9, bS: false }]);
  assert.equal(presses, 2);
});

test("other buttons never fire", () => {
  let presses = 0;
  const detect = pressDetector(VIEW_BUTTON, () => presses++);
  for (const button of [0, 1, 2, 3, 8, 10, 35]) {
    detect(0, button, true);
    detect(0, button, false);
  }
  assert.equal(presses, 0);
});

test("either unregister handle form is undone, and a bad one is harmless", () => {
  let calls = 0;
  toUnsubscribe(() => calls++)();
  toUnsubscribe({ unregister() { calls++; } })();
  assert.equal(calls, 2);
  for (const handle of [null, undefined, 3, {}, { unregister: 1 }]) toUnsubscribe(handle)();
  toUnsubscribe(() => { throw new Error("stale"); })();
});

test("press shows the highlighted game, a second press hides it", () => {
  let peek = null;
  peek = peekAfterPress(peek, "steam:1145360");
  assert.equal(peek, "steam:1145360");
  peek = peekAfterPress(peek, "steam:1145360");
  assert.equal(peek, null);
});

test("moving to another game closes the preview", () => {
  let peek = peekAfterPress(null, "steam:1145360");
  peek = peekAfterFocus(peek, "steam:504230");
  assert.equal(peek, null);
  // ...and coming back does not reopen it: nothing appears unasked.
  peek = peekAfterFocus(peek, "steam:1145360");
  assert.equal(peek, null);
});

test("re-reporting the same game keeps the preview open", () => {
  const peek = peekAfterPress(null, "steam:1145360");
  assert.equal(peekAfterFocus(peek, "steam:1145360"), "steam:1145360");
});

test("a press with nothing highlighted shows nothing and closes anything open", () => {
  assert.equal(peekAfterPress(null, ""), null);
  assert.equal(peekAfterPress("steam:1145360", ""), null);
});

test("pressing on a new game while one is open switches to it", () => {
  // Only reachable if focus moved without a focus report in between;
  // the new game wins either way.
  assert.equal(peekAfterPress("steam:1145360", "steam:504230"), "steam:504230");
});

// --- capturing the button --------------------------------------------

test("a capture returns the next button pressed, whatever its ID", () => {
  const capture = createCapture(0);
  // 35 is not the published View ID -- which is the point: current Steam
  // builds do not always send the published values.
  assert.equal(capture.feed([0, 35, true], 1000), 35);
});

test("the A press that started the capture cannot capture itself", () => {
  const capture = createCapture(0);
  // Steam re-reports A as still held just after "Change" was pressed...
  assert.equal(capture.feed([0, 0, true], 50), null);
  // ...and even reported again after the grace period, it is still the
  // same press until it has been released.
  assert.equal(capture.feed([0, 0, true], CAPTURE_GRACE_MS + 100), null);
  assert.equal(capture.feed([0, 0, false], CAPTURE_GRACE_MS + 200), null);
  // The user then presses View.
  assert.equal(capture.feed([0, 9, true], CAPTURE_GRACE_MS + 900), 9);
});

test("a deliberate press of the button that started it still counts once released", () => {
  const capture = createCapture(0);
  capture.feed([0, 0, true], 10);
  capture.feed([0, 0, false], 200);
  assert.equal(capture.feed([0, 0, true], CAPTURE_GRACE_MS + 50), 0);
});

test("releases never capture", () => {
  const capture = createCapture(0);
  assert.equal(capture.feed([0, 9, false], 2000), null);
});

test("the older callback shape is captured too", () => {
  const capture = createCapture(0);
  assert.equal(capture.feed([[{ nA: 35, bS: true }]], 1000), 35);
});

test("a capture can tell silence from an unreadable message", () => {
  const silent = createCapture(0);
  assert.equal(silent.callbacks, 0);

  const unreadable = createCapture(0);
  unreadable.feed([{ some: "new shape" }], 1000);
  unreadable.feed(["also new"], 1100);
  assert.equal(unreadable.callbacks, 2);
  assert.equal(unreadable.events, 0);

  const readable = createCapture(0);
  readable.feed([0, 9, false], 1000);
  assert.equal(readable.events, 1);
});

test("button labels name what they can and number everything", () => {
  assert.equal(buttonLabel(9), "View (9)");
  assert.equal(buttonLabel(0), "A (0)");
  assert.equal(buttonLabel(35), "Button 35");
});
