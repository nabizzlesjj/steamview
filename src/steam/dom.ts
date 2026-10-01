/**
 * DOM checks that work across windows.
 *
 * Decky plugins run in Steam's `SharedJSContext`; the library is rendered
 * in the separate SP window. Every window has its own `Element`,
 * `HTMLElement` and so on, so `node instanceof Element` here is false for
 * every node in the library -- the check fails *silently*, as if nothing
 * were focused. Kept free of imports so it can be unit tested off-device.
 */

/** Whether `value` is a DOM element, from any window. */
export function isElement(value: unknown): value is Element {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as { nodeType?: unknown }).nodeType === 1 &&
    typeof (value as { closest?: unknown }).closest === "function"
  );
}
