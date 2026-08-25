/**
 * Overlay sizing across the displays Game Mode actually runs on.
 *
 * The card was tuned by eye on a Steam Deck. These tests pin the two
 * things that tuning must survive: a Deck still gets exactly the widths
 * it was tuned with, and every other display gets something bounded,
 * proportionate and never wider than the pane it sits in.
 *
 * Plain JavaScript against the compiled module, so the suite needs no
 * test framework and no type packages -- `pnpm run test:fe` compiles
 * `src/overlayGeometry.ts` first. See tsconfig.test.json.
 *
 * The script passes a shell-expanded glob rather than one node expands
 * itself: node only learned to glob `--test` arguments in v21, and CI
 * runs 20.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  BASELINE_PANE_WIDTH,
  BASELINE_WIDTHS,
  FALLBACK_PANE_BOTTOM,
  FALLBACK_PANE_TOP,
  MAX_SCALE,
  MAX_WIDTHS,
  MIN_SCALE,
  MIN_WIDTHS,
  cardWidth,
  clamp,
  edgeMargin,
  paneInset,
  paneInsets,
  typeScale,
} from "../../.tsbuild/src/overlayGeometry.js";

const SIZES = ["s", "m", "l"];

/**
 * Representative CSS viewport widths. Game Mode zooms its UI, so these
 * are not the panel's pixels: a Deck's 1280x800 screen presents as
 * roughly 870x545 CSS. The larger figures stand in for a docked Deck and
 * for desktop Game Mode at 1080p, 1440p and 4K, whose zoom levels vary
 * by hardware -- which is exactly why the code measures rather than
 * assumes.
 */
const PANES = {
  deck: 870,
  p1080: 1280,
  p1440: 1600,
  p4k: 2560,
};

test("a Deck reproduces the widths the card was tuned with", () => {
  for (const size of SIZES) {
    assert.equal(cardWidth(size, BASELINE_PANE_WIDTH), BASELINE_WIDTHS[size]);
    assert.equal(typeScale(size, cardWidth(size, BASELINE_PANE_WIDTH)), 1);
  }
});

test("an unmeasured pane falls back to the Deck-tuned widths", () => {
  for (const size of SIZES) {
    for (const paneWidth of [null, 0, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
      assert.equal(cardWidth(size, paneWidth), BASELINE_WIDTHS[size]);
    }
  }
});

test("width stays within its bounds on every display", () => {
  for (const size of SIZES) {
    for (const paneWidth of Object.values(PANES)) {
      const width = cardWidth(size, paneWidth);
      assert.ok(width >= MIN_WIDTHS[size], `${size} at ${paneWidth}: ${width} below minimum`);
      assert.ok(width <= MAX_WIDTHS[size], `${size} at ${paneWidth}: ${width} above maximum`);
    }
  }
});

test("the card never outgrows the pane, however narrow", () => {
  for (const size of SIZES) {
    // 240 is narrower than any real Game Mode pane; the point is that
    // the clamp binds before the card can overhang.
    for (let paneWidth = 240; paneWidth <= 3840; paneWidth += 37) {
      const width = cardWidth(size, paneWidth);
      assert.ok(width <= paneWidth, `${size} at ${paneWidth}: card ${width} exceeds the pane`);
    }
  }
});

test("width grows with the pane, and never shrinks", () => {
  for (const size of SIZES) {
    let previous = 0;
    for (let paneWidth = 400; paneWidth <= 3840; paneWidth += 17) {
      const width = cardWidth(size, paneWidth);
      assert.ok(width >= previous, `${size} at ${paneWidth}: ${width} < ${previous}`);
      previous = width;
    }
  }
});

test("the three sizes stay ordered on every display", () => {
  for (const paneWidth of Object.values(PANES)) {
    const [small, medium, large] = SIZES.map((size) => cardWidth(size, paneWidth));
    // On a very large pane the per-size maxima can coincide, so this is
    // "never inverted" rather than "strictly increasing".
    assert.ok(small <= medium, `at ${paneWidth}: s ${small} > m ${medium}`);
    assert.ok(medium <= large, `at ${paneWidth}: m ${medium} > l ${large}`);
  }
});

test("a 4K pane makes the card larger than a Deck's, but not unboundedly", () => {
  for (const size of SIZES) {
    const deck = cardWidth(size, PANES.deck);
    const uhd = cardWidth(size, PANES.p4k);
    assert.ok(uhd > deck, `${size}: 4K ${uhd} is not larger than a Deck's ${deck}`);
    assert.ok(uhd <= deck * MAX_SCALE + 1, `${size}: 4K ${uhd} outgrew the scale ceiling`);
  }
});

test("type scale is clamped, and tracks the rendered width", () => {
  for (const size of SIZES) {
    assert.equal(typeScale(size, 0), 1, "an unrendered card must not scale to nothing");
    assert.ok(typeScale(size, 10) >= MIN_SCALE);
    assert.ok(typeScale(size, 100_000) <= MAX_SCALE);

    const deck = typeScale(size, cardWidth(size, PANES.deck));
    const uhd = typeScale(size, cardWidth(size, PANES.p4k));
    assert.ok(uhd >= deck, `${size}: type shrank on the larger display`);
  }
});

test("margins scale with the card and stay positive", () => {
  for (const scale of [MIN_SCALE, 1, 1.25, MAX_SCALE]) {
    assert.ok(edgeMargin(scale) > 0);
    assert.ok(paneInset(scale) > 0);
  }
  assert.ok(edgeMargin(MAX_SCALE) > edgeMargin(1));
  assert.ok(paneInset(MAX_SCALE) > paneInset(1));
  // Out-of-range input is clamped rather than trusted.
  assert.equal(edgeMargin(50), edgeMargin(MAX_SCALE));
  assert.equal(edgeMargin(-5), edgeMargin(MIN_SCALE));
});

test("pane insets never fall below the chrome floor", () => {
  assert.deepEqual(paneInsets(null), { top: FALLBACK_PANE_TOP, bottom: FALLBACK_PANE_BOTTOM });
  // A measured pane that clears more chrome than the floor is trusted.
  assert.deepEqual(paneInsets({ top: 210, bottom: 160 }), { top: 210, bottom: 160 });
  // One that clears less is not: it would put the card over the search
  // field, which is the bug this floor exists to prevent.
  assert.deepEqual(paneInsets({ top: 0, bottom: 0 }), {
    top: FALLBACK_PANE_TOP,
    bottom: FALLBACK_PANE_BOTTOM,
  });
  assert.deepEqual(paneInsets({ top: 300, bottom: 4 }), {
    top: 300,
    bottom: FALLBACK_PANE_BOTTOM,
  });
});

test("clamp is inclusive at both ends", () => {
  assert.equal(clamp(5, 1, 10), 5);
  assert.equal(clamp(0, 1, 10), 1);
  assert.equal(clamp(99, 1, 10), 10);
  assert.equal(clamp(1, 1, 10), 1);
  assert.equal(clamp(10, 1, 10), 10);
});
