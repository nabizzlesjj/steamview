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
 * `EGamepadButton` value of the View button -- the one left of the left
 * stick on a Deck, "Back"/"Select" on most other pads. Matches
 * `ControllerInputGamepadButton.GAMEPAD_BUTTON_VIEW` in `@decky/ui`.
 */
export const VIEW_BUTTON = 9;

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
