/**
 * Reading controller buttons from `SteamClient.Input`.
 *
 * `RegisterForControllerInputMessages` is how a plugin hears a button
 * press. Two things about it are not in any documentation, and both are
 * handled here rather than discovered on someone's Deck:
 *
 * 1. **Its callback changed shape between Steam builds.** Older builds
 *    pass one argument, an array of `{ nA: button, bS: pressed }`. Newer
 *    builds pass `(controllerIndex, button, pressed, ...)`. The button IDs
 *    are the same `EGamepadButton` values either way. (Found by the
 *    Steamcord plugin, whose controller shortcut silently died across the
 *    change; its fix handles both, and so does this.)
 * 2. **Its unregister handle varies too:** a function on some builds, an
 *    object with `unregister()` on others.
 *
 * Kept free of imports so the parsing can be unit tested off-device.
 */

/**
 * The published `EGamepadButton` value of the View button -- the one
 * left of the left stick on a Deck, "Back"/"Select" on most other pads --
 * as `ControllerInputGamepadButton.GAMEPAD_BUTTON_VIEW` in `@decky/ui`.
 *
 * Only a default. Current Steam builds do not always send the published
 * values through this API: the Steamcord plugin measured the D-pad
 * arriving as 20-23 rather than 4-7 in September 2026, and View did
 * nothing on a Deck with 1.3.0. So the button is *captured* -- the user
 * presses it once and whatever ID Steam actually sends is stored -- and
 * this is only where that starts.
 */
export const VIEW_BUTTON = 9;

/**
 * Names for the IDs worth naming, from `@decky/ui`'s published enum.
 * Since Steam does not always send those values, a name is a hint, not a
 * promise -- the panel shows the number alongside it.
 */
const BUTTON_NAMES: Record<number, string> = {
  0: "A",
  1: "B",
  2: "X",
  3: "Y",
  8: "Menu",
  9: "View",
  28: "Left trigger",
  29: "Right trigger",
  30: "Left bumper",
  31: "Right bumper",
};

/** A short label for a button ID, e.g. "View (9)" or "Button 35". */
export function buttonLabel(button: number): string {
  const name = BUTTON_NAMES[button];
  return name ? `${name} (${button})` : `Button ${button}`;
}

export interface ButtonEvent {
  button: number;
  pressed: boolean;
}

/** Normalise one callback invocation, in either shape, to button events. */
export function parseControllerInput(args: readonly unknown[]): ButtonEvent[] {
  const first = args[0];

  // Older builds: [{ nA: button, bS: pressed }, ...]
  if (Array.isArray(first)) {
    const events: ButtonEvent[] = [];
    for (const item of first) {
      const button = (item as { nA?: unknown } | null)?.nA;
      if (typeof button === "number" && Number.isInteger(button)) {
        events.push({ button, pressed: Boolean((item as { bS?: unknown }).bS) });
      }
    }
    return events;
  }

  // Newer builds: (controllerIndex, button, pressed, ...)
  const button = args[1];
  if (typeof button === "number" && Number.isInteger(button)) {
    return [{ button, pressed: Boolean(args[2]) }];
  }

  return [];
}

/** Turn whichever unregister handle Steam returned into a plain function. */
export function toUnsubscribe(handle: unknown): () => void {
  return () => {
    try {
      if (typeof handle === "function") {
        handle();
      } else {
        const unregister = (handle as { unregister?: unknown } | null)?.unregister;
        if (typeof unregister === "function") unregister.call(handle);
      }
    } catch {
      // Steam is tearing down or the handle is stale; nothing to undo.
    }
  };
}

/**
 * Watch for a button being *pressed*, as an edge.
 *
 * Returns a handler for raw callback arguments. It fires `onPress` once
 * per press, on the transition to pressed: a held button that Steam
 * reports again as still pressed does not fire twice, and a release does
 * not fire at all.
 */
export function pressDetector(button: number, onPress: () => void): (...args: unknown[]) => void {
  let held = false;
  return (...args: unknown[]) => {
    for (const event of parseControllerInput(args)) {
      if (event.button !== button) continue;
      if (event.pressed && !held) onPress();
      held = event.pressed;
    }
  };
}

/** How long after a capture starts to treat already-held buttons as noise. */
export const CAPTURE_GRACE_MS = 400;

/**
 * Learns which button the user presses next.
 *
 * Feed it every raw callback; it returns the button ID once a genuine
 * press arrives. Two things are not genuine presses:
 *
 * - **The press that started the capture.** The user pressed A on
 *   "Change", and Steam can report A as still held just after the capture
 *   begins -- Steamcord's capture validated itself on exactly that. Any
 *   button seen pressed in the first `graceMs` is ignored until it has
 *   been released.
 * - **Releases.** Only a press counts.
 *
 * It also counts what arrived, so a capture that ends empty-handed can
 * say *why*: Steam sent nothing at all, or sent something unrecognisable.
 */
export function createCapture(startMs: number, graceMs = CAPTURE_GRACE_MS) {
  const ignored = new Set<number>();
  let callbacks = 0;
  let events = 0;
  return {
    /** Raw callbacks received, recognised or not. */
    get callbacks(): number {
      return callbacks;
    },
    /** Button events parsed out of them. */
    get events(): number {
      return events;
    },
    feed(args: readonly unknown[], nowMs: number): number | null {
      callbacks += 1;
      for (const { button, pressed } of parseControllerInput(args)) {
        events += 1;
        if (!pressed) {
          ignored.delete(button);
          continue;
        }
        if (nowMs - startMs < graceMs) {
          ignored.add(button);
          continue;
        }
        if (!ignored.has(button)) return button;
      }
      return null;
    },
  };
}
