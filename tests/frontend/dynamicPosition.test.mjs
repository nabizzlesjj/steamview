/**
 * Dynamic overlay positioning.
 *
 * The card moves to the opposite side of the pane from the highlighted
 * game. Two things matter and neither is obvious from the code alone:
 * it must genuinely move away from the highlight, and it must not
 * *flicker* when the highlight sits near the middle -- which is what the
 * dead band exists for.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  SIDE_DEAD_ZONE,
  nextSide,
  resolvePosition,
} from "../../.tsbuild/src/overlayGeometry.js";

test("the side follows the highlight once it is clearly past the middle", () => {
  assert.equal(nextSide(null, 0.0), "left");
  assert.equal(nextSide(null, 0.2), "left");
  assert.equal(nextSide(null, 0.8), "right");
  assert.equal(nextSide(null, 1.0), "right");
});

test("the dead band holds the previous side, so the card cannot flicker", () => {
  // Anywhere inside the band, whatever we last decided stands.
  for (let centre = 0.5 - SIDE_DEAD_ZONE; centre <= 0.5 + SIDE_DEAD_ZONE; centre += 0.005) {
    assert.equal(nextSide("left", centre), "left", `left lost at ${centre.toFixed(3)}`);
    assert.equal(nextSide("right", centre), "right", `right lost at ${centre.toFixed(3)}`);
  }
});

test("a walk across the middle flips exactly once in each direction", () => {
  let side = "left";
  let flips = 0;
  for (let centre = 0; centre <= 1.0001; centre += 0.01) {
    const resolved = nextSide(side, centre);
    if (resolved !== side) flips += 1;
    side = resolved;
  }
  assert.equal(side, "right");
  assert.equal(flips, 1, "crossing the pane once should move the card once");

  flips = 0;
  for (let centre = 1; centre >= -0.0001; centre -= 0.01) {
    const resolved = nextSide(side, centre);
    if (resolved !== side) flips += 1;
    side = resolved;
  }
  assert.equal(side, "left");
  assert.equal(flips, 1, "coming back should also move the card exactly once");
});

test("nonsense input keeps the card where it is", () => {
  assert.equal(nextSide("right", Number.NaN), "right");
  assert.equal(nextSide("left", Number.POSITIVE_INFINITY), "left");
  // With no history at all it still has to answer something.
  assert.equal(nextSide(null, Number.NaN), "left");
});

test("the card is placed opposite the highlight", () => {
  assert.equal(resolvePosition("bottom-right", "left", true), "bottom-right");
  assert.equal(resolvePosition("bottom-right", "right", true), "bottom-left");
  assert.equal(resolvePosition("top-left", "right", true), "top-left");
  assert.equal(resolvePosition("top-left", "left", true), "top-right");
});

test("the vertical half is the user's, and is never overridden", () => {
  for (const side of ["left", "right"]) {
    for (const position of ["top-left", "top-right"]) {
      assert.ok(resolvePosition(position, side, true).startsWith("top"));
    }
    for (const position of ["bottom-left", "bottom-right"]) {
      assert.ok(resolvePosition(position, side, true).startsWith("bottom"));
    }
  }
});

test("with the toggle off, or nothing measured, the chosen corner stands", () => {
  for (const position of ["top-left", "top-right", "bottom-left", "bottom-right"]) {
    assert.equal(resolvePosition(position, "left", false), position);
    assert.equal(resolvePosition(position, "right", false), position);
    assert.equal(resolvePosition(position, null, true), position);
  }
});
