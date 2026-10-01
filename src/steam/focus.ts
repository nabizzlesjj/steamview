/**
 * Focus tracking: which library entry is the user currently highlighting?
 *
 * This module and `bindings.ts` are the only Steam-coupled code in the
 * plugin, and this is the one with moving parts. Everything it does is
 * wrapped so that a failure here disables *only* the preview overlay.
 * The settings panel, the backend and -- most importantly -- Steam's own
 * library keep working exactly as they would without the plugin
 * installed.
 *
 * ## Two sources, one answer
 *
 * The highlighted element is read from two places, and both feed the
 * same handler:
 *
 * - a passive, capture-phase `focusin` listener on Steam's UI window, for
 *   an instant response when focus events arrive; and
 * - a light poll of `document.activeElement`, which is what guarantees a
 *   correct answer when they do not.
 *
 * Both are needed because whether Steam's SP window *delivers* focus
 * events depends on which window holds system focus -- it varies by
 * device, and changes the moment the Quick Access Menu opens or closes.
 * `activeElement` is updated either way. An earlier version ran the poll
 * only if no focus event arrived in the first five seconds, which made
 * the plugin's behaviour depend on how quickly the user closed the QAM
 * after enabling it.
 *
 * The poll costs one property read and one identity comparison per tick;
 * the fiber walk only runs when the focused element actually changed.
 *
 * ## Realms
 *
 * Decky plugins run in Steam's `SharedJSContext`, but the library lives
 * in the separate SP window. Elements from another window fail
 * `instanceof Element` here, because each window has its own `Element`.
 * So nothing here uses `instanceof` on a DOM node -- see `dom.ts`, and
 * the lint rule that enforces it.
 *
 * Nothing is patched. We add a listener and read the tree; we never
 * modify a Valve component, so there is no patch to go stale.
 */

import { getFocusNavController } from "@decky/ui";

import type { LibraryEntry } from "../types";
import { entryKey } from "../types";
import { entryForElement, spWindow } from "./bindings";
import { isElement } from "./dom";

/** How often the `activeElement` poll checks. Deliberately unhurried. */
const POLL_MS = 250;

/** Detach after this many consecutive handler failures. */
const MAX_CONSECUTIVE_ERRORS = 5;

const LOG_PREFIX = "[SteamView:focus]";

export interface FocusTracker {
  /** False means the overlay must stay off; everything else still works. */
  ok: boolean;
  reason?: string;
  stop(): void;
}

export type FocusListener = (entry: LibraryEntry | null) => void;

/** Told when tracking gives up after starting, so the UI can say so. */
export type FailureListener = (reason: string) => void;

function noop(): void {
  /* nothing to tear down */
}

/**
 * Begin reporting the highlighted library entry.
 *
 * `onFocus` receives the entry when one is highlighted, and `null` when
 * focus moves somewhere the overlay should not appear. It is only called
 * when the entry actually changes, so a repeated focus event on the same
 * game does not churn React state.
 *
 * `onFailure` is called if tracking has to give up after a successful
 * start, so the settings panel can say why rather than going quiet.
 */
export function startFocusTracking(onFocus: FocusListener, onFailure?: FailureListener): FocusTracker {
  let win: Window | null;

  try {
    win = spWindow();
  } catch (error) {
    console.warn(`${LOG_PREFIX} could not locate Steam's UI window:`, error);
    return { ok: false, reason: "no-sp-window", stop: noop };
  }

  const doc = win?.document;
  if (!doc) {
    console.warn(`${LOG_PREFIX} Steam's UI window has no document; overlay disabled.`);
    return { ok: false, reason: "no-sp-window", stop: noop };
  }

  let stopped = false;
  let lastKey = " "; // a value entryKey() can never produce
  let consecutiveErrors = 0;
  let hasLoggedFailure = false;
  let pollTimer: ReturnType<typeof setInterval> | undefined;

  /**
   * The last element either source handed over. Shared, so the poll
   * does not repeat a fiber walk a focus event already did -- and so the
   * two sources can never disagree about what is current.
   */
  let lastElement: Element | null | undefined;

  /** Log the first failure in full, then stay quiet. */
  const logOnce = (message: string, error?: unknown) => {
    if (hasLoggedFailure) return;
    hasLoggedFailure = true;
    console.warn(`${LOG_PREFIX} ${message}`, error ?? "");
    console.warn(`${LOG_PREFIX} further errors from this session are suppressed.`);
  };

  const emit = (entry: LibraryEntry | null) => {
    const key = entryKey(entry);
    if (key === lastKey) return;
    lastKey = key;
    onFocus(entry);
  };

  /** Shared by the listener and the poll. */
  const handleElement = (element: Element | null) => {
    if (stopped || element === lastElement) return;
    lastElement = element;
    try {
      emit(entryForElement(element));
      consecutiveErrors = 0;
    } catch (error) {
      consecutiveErrors += 1;
      // Forget the element, so the next tick retries it rather than
      // treating a failed walk as a settled answer.
      lastElement = undefined;
      logOnce("focus handler threw; overlay may be degraded.", error);
      if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
        console.warn(
          `${LOG_PREFIX} ${MAX_CONSECUTIVE_ERRORS} consecutive failures; detaching. ` +
            `The library is unaffected, only the preview is off.`,
        );
        stop();
        onFocus(null);
        onFailure?.("handler-errors");
      }
    }
  };

  const onFocusIn = (event: Event) => {
    handleElement(isElement(event.target) ? event.target : null);
  };

  /**
   * Read the focused element directly. Also consults the gamepad
   * navigation controller, in case Steam is tracking a highlight that
   * never reached `document.activeElement`.
   */
  const poll = () => {
    if (stopped) return;
    let element: Element | null = null;
    try {
      // Nothing on screen to follow; a hidden window cannot be browsed.
      if (doc.visibilityState === "hidden") return;
      const active = doc.activeElement;
      element = isElement(active) ? active : null;
      if (!element || element === doc.body) {
        const controller = getFocusNavController();
        const context = controller?.m_ActiveContext ?? controller?.m_LastActiveContext;
        const candidate = context?.m_ActiveNavTree?.m_LastFocusedNode?.Element;
        element = isElement(candidate) ? candidate : element;
      }
    } catch (error) {
      logOnce("focus poll threw.", error);
      return;
    }
    handleElement(element);
  };

  function stop(): void {
    if (stopped) return;
    stopped = true;
    if (pollTimer !== undefined) clearInterval(pollTimer);
    pollTimer = undefined;
    try {
      doc?.removeEventListener("focusin", onFocusIn, true);
    } catch (error) {
      console.warn(`${LOG_PREFIX} failed to detach the focus listener:`, error);
    }
  }

  try {
    // Capture phase so we see the event regardless of what Steam does
    // with it; passive because we never call preventDefault.
    doc.addEventListener("focusin", onFocusIn, { capture: true, passive: true });
  } catch (error) {
    // Not fatal on its own: the poll alone gives a correct answer.
    console.warn(`${LOG_PREFIX} could not attach the focus listener; polling only:`, error);
  }

  try {
    pollTimer = setInterval(poll, POLL_MS);
  } catch (error) {
    console.warn(`${LOG_PREFIX} could not start the focus poll:`, error);
    stop();
    return { ok: false, reason: "poll-failed", stop: noop };
  }

  // Report whatever is already focused, so the overlay is correct
  // immediately rather than only after the next input.
  poll();

  return { ok: true, stop };
}
