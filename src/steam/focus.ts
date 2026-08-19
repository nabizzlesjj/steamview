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
 * ## How it works
 *
 * A passive, capture-phase `focusin` listener on Steam's UI window.
 * Steam's gamepad navigation moves real DOM focus (that is how its focus
 * ring is positioned), so every time the highlight moves we get an event
 * whose target is the focused element. `bindings.entryForElement` then
 * walks up the React tree from that element to find the app it belongs
 * to.
 *
 * Nothing is patched. We add a listener and read the tree; we never
 * modify a Valve component, so there is no patch to go stale.
 *
 * ## If focus events never arrive
 *
 * Should Steam ever stop moving real DOM focus, no `focusin` would fire
 * and the overlay would sit silently blank. So if nothing has been seen
 * within `FALLBACK_ARM_MS`, a low-frequency poll of
 * `document.activeElement` takes over: same fiber walk, different way of
 * reaching the element, and it costs nothing while the listener works.
 */

import { findSP, getFocusNavController } from "@decky/ui";

import type { LibraryEntry } from "../types";
import { entryKey } from "../types";
import { entryForElement } from "./bindings";

/** Wait this long for a first focus event before arming the poll. */
const FALLBACK_ARM_MS = 5_000;

/** How often the fallback checks, once armed. Deliberately unhurried. */
const FALLBACK_POLL_MS = 250;

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
 */
export function startFocusTracking(onFocus: FocusListener): FocusTracker {
  let spWindow: Window | null | undefined;

  try {
    spWindow = findSP();
  } catch (error) {
    console.warn(`${LOG_PREFIX} could not locate Steam's UI window:`, error);
    return { ok: false, reason: "no-sp-window", stop: noop };
  }

  const doc = spWindow?.document;
  if (!doc) {
    console.warn(`${LOG_PREFIX} Steam's UI window has no document; overlay disabled.`);
    return { ok: false, reason: "no-sp-window", stop: noop };
  }

  let stopped = false;
  let lastKey = " "; // a value entryKey() can never produce
  let consecutiveErrors = 0;
  let sawFocusEvent = false;
  let hasLoggedFailure = false;
  let pollTimer: ReturnType<typeof setInterval> | undefined;
  let armTimer: ReturnType<typeof setTimeout> | undefined;
  let lastPolledElement: Element | null = null;

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

  /** Shared by the listener and the fallback poll. */
  const handleElement = (element: Element | null) => {
    if (stopped) return;
    try {
      emit(entryForElement(element));
      consecutiveErrors = 0;
    } catch (error) {
      consecutiveErrors += 1;
      logOnce("focus handler threw; overlay may be degraded.", error);
      if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
        console.warn(
          `${LOG_PREFIX} ${MAX_CONSECUTIVE_ERRORS} consecutive failures; detaching. ` +
            `The library is unaffected, only the preview is off.`,
        );
        stop();
        onFocus(null);
      }
    }
  };

  const onFocusIn = (event: Event) => {
    sawFocusEvent = true;
    handleElement(event.target instanceof Element ? event.target : null);
  };

  /**
   * Last resort: read the focused element directly. Also consults the
   * gamepad navigation controller, in case Steam is tracking a highlight
   * that never reached `document.activeElement`.
   */
  const poll = () => {
    if (stopped) return;
    let element: Element | null = null;
    try {
      element = doc.activeElement;
      if (!element || element === doc.body) {
        const controller = getFocusNavController();
        const context = controller?.m_ActiveContext ?? controller?.m_LastActiveContext;
        const candidate = context?.m_ActiveNavTree?.m_LastFocusedNode?.Element ?? null;
        if (candidate instanceof Element) element = candidate;
      }
    } catch (error) {
      logOnce("focus fallback poll threw.", error);
      return;
    }
    if (element === lastPolledElement) return;
    lastPolledElement = element;
    handleElement(element);
  };

  const armFallback = () => {
    if (stopped || sawFocusEvent || pollTimer !== undefined) return;
    console.warn(
      `${LOG_PREFIX} no focus events in ${FALLBACK_ARM_MS}ms; ` +
        `falling back to polling the focused element.`,
    );
    pollTimer = setInterval(poll, FALLBACK_POLL_MS);
  };

  function stop(): void {
    if (stopped) return;
    stopped = true;
    if (armTimer !== undefined) clearTimeout(armTimer);
    if (pollTimer !== undefined) clearInterval(pollTimer);
    armTimer = undefined;
    pollTimer = undefined;
    try {
      doc.removeEventListener("focusin", onFocusIn, true);
    } catch (error) {
      console.warn(`${LOG_PREFIX} failed to detach the focus listener:`, error);
    }
  }

  try {
    // Capture phase so we see the event regardless of what Steam does
    // with it; passive because we never call preventDefault.
    doc.addEventListener("focusin", onFocusIn, { capture: true, passive: true });
  } catch (error) {
    console.warn(`${LOG_PREFIX} could not attach the focus listener:`, error);
    return { ok: false, reason: "listener-failed", stop: noop };
  }

  armTimer = setTimeout(armFallback, FALLBACK_ARM_MS);

  // Report whatever is already focused, so the overlay is correct
  // immediately rather than only after the next input.
  try {
    handleElement(doc.activeElement);
  } catch {
    // A failure here is not fatal; the listener still works.
  }

  return { ok: true, stop };
}
