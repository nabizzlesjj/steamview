/**
 * Overlay sizing, as pure functions of the measured library pane.
 *
 * The card was originally tuned on a Steam Deck, whose Game Mode UI is
 * roughly an 870x545 CSS viewport. Game Mode also runs on desktop
 * hardware — Bazzite, a docked Deck, a plain SteamOS install — where the
 * CSS viewport is a different size entirely. Fixed pixel widths that look
 * right on a Deck are wrong everywhere else.
 *
 * So the card is sized as a fraction of the pane it sits in, clamped so
 * it can be neither unreadably small on a large display nor overbearing
 * on a small one. Typography scales with the card, which keeps the
 * proportions that were tuned by eye rather than re-tuning them per
 * resolution.
 *
 * Kept separate from the component so the arithmetic is testable without
 * a DOM.
 */

import type { OverlayPosition, OverlaySize } from "./types";

/** The pane width the sizes below were originally chosen against. */
export const BASELINE_PANE_WIDTH = 870;

/** Card width on a Deck, per size setting. The anchor for everything. */
export const BASELINE_WIDTHS: Record<OverlaySize, number> = { s: 280, m: 380, l: 480 };

/**
 * Fraction of pane width each size takes. Derived from the baseline, so
 * a Deck reproduces its tuned widths exactly and other displays keep the
 * same proportion.
 */
export const WIDTH_FRACTIONS: Record<OverlaySize, number> = {
  s: BASELINE_WIDTHS.s / BASELINE_PANE_WIDTH,
  m: BASELINE_WIDTHS.m / BASELINE_PANE_WIDTH,
  l: BASELINE_WIDTHS.l / BASELINE_PANE_WIDTH,
};

/**
 * Absolute bounds in CSS pixels. The lower bound keeps the info panel
 * legible; the upper stops the card dominating a large screen, where the
 * same fraction would be enormous.
 */
export const MIN_WIDTHS: Record<OverlaySize, number> = { s: 220, m: 260, l: 300 };
export const MAX_WIDTHS: Record<OverlaySize, number> = { s: 420, m: 560, l: 700 };

/** How far typography may scale from the Deck-tuned baseline. */
export const MIN_SCALE = 0.8;
export const MAX_SCALE = 1.6;

/** Inset from the left/right edge of the pane, scaled with the card. */
export const BASELINE_EDGE_MARGIN = 20;

/** Gap between the card and the pane edge it sits against. */
export const BASELINE_PANE_INSET = 8;

/**
 * Minimum pane insets: the top and bottom chrome, in CSS pixels.
 *
 * These are CSS pixels, which Game Mode's zoom does not change -- zoom
 * scales the whole coordinate space, so Steam's stylesheet keeps its
 * numbers and only the *viewport* grows or shrinks. They are therefore a
 * usable floor everywhere, not just on a Deck.
 *
 * They are a floor rather than an answer because Steam has responsive
 * breakpoints (narrow, short, wide, ultrawide) that genuinely change the
 * chrome, and because the element we can measure is the library page
 * rather than the grid inside it. See `paneInsets`.
 */
export const FALLBACK_PANE_TOP = 96;
export const FALLBACK_PANE_BOTTOM = 72;

export function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

/**
 * Card width for a size setting within a pane of `paneWidth` CSS pixels.
 * Falls back to the baseline when the pane has not been measured.
 */
export function cardWidth(size: OverlaySize, paneWidth: number | null): number {
  const baseline = BASELINE_WIDTHS[size] ?? BASELINE_WIDTHS.m;
  if (!paneWidth || !Number.isFinite(paneWidth) || paneWidth <= 0) return baseline;

  const fraction = WIDTH_FRACTIONS[size] ?? WIDTH_FRACTIONS.m;
  const min = MIN_WIDTHS[size] ?? MIN_WIDTHS.m;
  const max = MAX_WIDTHS[size] ?? MAX_WIDTHS.m;

  // Never wider than the pane itself, however generous the clamp is.
  // On a pane narrower than the minimum -- which no real Game Mode
  // layout produces, but a mis-measurement could -- the pane wins and
  // the minimum gives way. Overhanging the grid is the worse failure.
  const available = paneWidth - BASELINE_EDGE_MARGIN * 2;
  const ceiling = Math.min(max, available > 0 ? available : paneWidth);
  const floor = Math.min(min, ceiling);
  return Math.round(clamp(paneWidth * fraction, floor, ceiling));
}

/**
 * Typography multiplier for a rendered card width. 1.0 reproduces the
 * Deck-tuned look exactly; a wider card scales type with it.
 */
export function typeScale(size: OverlaySize, width: number): number {
  const baseline = BASELINE_WIDTHS[size] ?? BASELINE_WIDTHS.m;
  if (!width || !Number.isFinite(width) || baseline <= 0) return 1;
  return Number(clamp(width / baseline, MIN_SCALE, MAX_SCALE).toFixed(3));
}

/** Edge inset, scaled so margins keep their proportion on large displays. */
export function edgeMargin(scale: number): number {
  return Math.round(BASELINE_EDGE_MARGIN * clamp(scale, MIN_SCALE, MAX_SCALE));
}

export function paneInset(scale: number): number {
  return Math.round(BASELINE_PANE_INSET * clamp(scale, MIN_SCALE, MAX_SCALE));
}

/**
 * How far the overlay host is inset from the top and bottom of the
 * viewport, given whatever measurement we managed to take.
 *
 * Measurement is preferred but never trusted downwards. The element
 * available to measure is Steam's library *page*, which on some layouts
 * contains the search field and collection tabs -- so its top edge can
 * sit above the grid, and using it raw would put the card over chrome
 * the hardcoded constants already clear.
 *
 * Taking the larger of the two can only ever move the pane inward from
 * the behaviour that was verified on a Deck: a measured inset is used
 * exactly when it is the more cautious of the pair. The cost is some
 * wasted space on a layout whose chrome is genuinely shorter than the
 * floor; the alternative cost is covering the search field, which is a
 * bug and this is not.
 */
export function paneInsets(pane: { top: number; bottom: number } | null): {
  top: number;
  bottom: number;
} {
  return {
    top: Math.max(pane?.top ?? 0, FALLBACK_PANE_TOP),
    bottom: Math.max(pane?.bottom ?? 0, FALLBACK_PANE_BOTTOM),
  };
}

// ---------------------------------------------------------------------
// Dynamic positioning
// ---------------------------------------------------------------------

/** Which half of the pane something is in. */
export type PaneSide = "left" | "right";

/**
 * How far past the middle the highlight must travel before the card
 * moves, as a fraction of pane width either side of centre.
 *
 * Without a dead band, scrolling along a row that straddles the middle
 * would flip the card on every step -- far more distracting than the
 * overlap it exists to avoid. Roughly a capsule and a half on a Deck.
 */
export const SIDE_DEAD_ZONE = 0.08;

/**
 * Which side of the pane the highlight is on, given where it was.
 *
 * Inside the dead band the previous answer stands, which is what makes
 * this stable; `current` is null only before anything has been
 * highlighted, and then the midpoint decides.
 */
export function nextSide(current: PaneSide | null, centreFraction: number): PaneSide {
  if (!Number.isFinite(centreFraction)) return current ?? "left";
  if (centreFraction < 0.5 - SIDE_DEAD_ZONE) return "left";
  if (centreFraction > 0.5 + SIDE_DEAD_ZONE) return "right";
  return current ?? (centreFraction <= 0.5 ? "left" : "right");
}

/**
 * The corner the card should actually use.
 *
 * Dynamic positioning moves the card *away* from the highlighted game,
 * so it never covers what you are looking at. Only the horizontal half
 * is decided for you: the vertical half stays wherever the user put it,
 * because that is a taste preference rather than an occlusion problem.
 */
export function resolvePosition(
  position: OverlayPosition,
  side: PaneSide | null,
  dynamic: boolean,
): OverlayPosition {
  if (!dynamic || side === null) return position;
  const vertical = position.startsWith("top") ? "top" : "bottom";
  return `${vertical}-${side === "left" ? "right" : "left"}` as OverlayPosition;
}
