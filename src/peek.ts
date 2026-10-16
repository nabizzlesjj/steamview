/**
 * The View-button preview, as a pure state machine.
 *
 * In this mode nothing appears on its own. Pressing View shows the
 * preview for the highlighted game; pressing it again hides it; moving
 * the highlight to another game hides it too, so scrolling is always
 * quiet unless you ask about a specific game.
 *
 * The state is just which game the preview was summoned for -- its
 * `entryKey` -- or null for none.
 */

/** After View is pressed with `focusedKey` highlighted. */
export function peekAfterPress(current: string | null, focusedKey: string): string | null {
  // Nothing highlighted (the press came from the store, a menu, a game's
  // page): nothing to show, and nothing should stay open.
  if (!focusedKey) return null;
  // Second press on the same game closes it.
  if (current === focusedKey) return null;
  return focusedKey;
}

/** After the highlight moves to `focusedKey`. */
export function peekAfterFocus(current: string | null, focusedKey: string): string | null {
  // The preview belongs to the game it was opened on.
  return current !== null && current === focusedKey ? current : null;
}
