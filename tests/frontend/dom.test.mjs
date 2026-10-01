/**
 * Realm-independent DOM checks.
 *
 * The library lives in Steam's SP window, a different realm from the
 * plugin, so `instanceof Element` was false for every focused capsule and
 * the preview blanked on the first focus event (1.0-1.2). `isElement`
 * must therefore recognise an element by what it is, never by which
 * window's constructor made it. Node has no DOM, so these use the same
 * duck-typed shapes a foreign-realm element presents.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { isElement } from "../../.tsbuild/src/steam/dom.js";

/** What an element from *any* window looks like to code in another. */
function foreignElement() {
  return Object.create(null, {
    nodeType: { value: 1 },
    closest: { value: () => null },
  });
}

test("an element from another realm is still an element", () => {
  // No shared prototype, no shared constructor: exactly the SP case.
  assert.equal(isElement(foreignElement()), true);
});

test("other node types are not elements", () => {
  for (const nodeType of [3 /* text */, 8 /* comment */, 9 /* document */, 11 /* fragment */]) {
    assert.equal(isElement({ nodeType, closest: () => null }), false, `nodeType ${nodeType}`);
  }
});

test("the window and other focus-event targets are not elements", () => {
  assert.equal(isElement({ document: {}, closed: false }), false);
  assert.equal(isElement({ addEventListener() {} }), false);
});

test("junk is rejected without throwing", () => {
  for (const value of [null, undefined, 0, 1, "", "div", true, [], () => {}, Symbol("x")]) {
    assert.equal(isElement(value), false);
  }
});

test("an element-shaped object without closest() is rejected", () => {
  // The scope check calls closest(); something that cannot answer it is
  // no use to us even if it claims to be an element.
  assert.equal(isElement({ nodeType: 1 }), false);
});
