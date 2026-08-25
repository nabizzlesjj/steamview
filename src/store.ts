/**
 * A minimal observable store shared by the overlay and the settings
 * panel, so both see one source of truth without prop-drilling through
 * components that Decky mounts independently.
 *
 * Deliberately tiny -- this needs about twenty lines, not a state
 * library.
 */

import { useEffect, useState } from "react";

import { getSettings, setSettings } from "./api";
import { effectiveLanguage } from "./languages";
import { readClientLanguage } from "./steam/bindings";
import type { FocusStatus, Settings } from "./types";
import { DEFAULT_SETTINGS } from "./types";

export interface PluginState {
  settings: Settings;
  /** False once the focus hook has reported it could not start. */
  focus: FocusStatus;
  /** True until the first backend settings load resolves. */
  loading: boolean;
  /**
   * The language Steam itself is set to, once asked. Null means Steam
   * would not say, or has not been asked yet -- either way the effective
   * language falls back to English.
   */
  clientLanguage: string | null;
}

type Listener = (state: PluginState) => void;

let state: PluginState = {
  settings: { ...DEFAULT_SETTINGS },
  focus: { ok: true },
  loading: true,
  clientLanguage: null,
};

const listeners = new Set<Listener>();

function publish(next: Partial<PluginState>): void {
  state = { ...state, ...next };
  for (const listener of listeners) {
    try {
      listener(state);
    } catch (error) {
      console.warn("[SteamView] a state listener threw:", error);
    }
  }
}

export function getState(): PluginState {
  return state;
}

export function setFocusStatus(focus: FocusStatus): void {
  publish({ focus });
}

/** Load persisted settings from the backend. Safe to call more than once. */
export async function loadSettings(): Promise<void> {
  const settings = await getSettings();
  publish({ settings, loading: false });
}

/**
 * Ask Steam what language it is in, once.
 *
 * Only the frontend can answer this -- the backend cannot see the
 * client -- so the resolved code travels with each lookup rather than
 * being persisted. A failure is not worth retrying or reporting: the
 * effective language simply stays English.
 */
export async function detectClientLanguage(): Promise<void> {
  const clientLanguage = await readClientLanguage();
  if (clientLanguage !== state.clientLanguage) publish({ clientLanguage });
}

/** The store language to send with a lookup, given current state. */
export function currentLanguage(): string {
  return effectiveLanguage(state.settings.language, state.clientLanguage);
}

/**
 * Apply a settings change optimistically, then reconcile with whatever
 * the backend actually persisted (it clamps and validates, so the two
 * can legitimately differ).
 */
export async function updateSettings(patch: Partial<Settings>): Promise<void> {
  publish({ settings: { ...state.settings, ...patch } });
  const persisted = await setSettings(patch);
  publish({ settings: persisted });
}

/** Subscribe a React component to the store. */
export function usePluginState(): PluginState {
  const [snapshot, setSnapshot] = useState<PluginState>(state);

  useEffect(() => {
    listeners.add(setSnapshot);
    // Re-sync in case the store changed between render and effect.
    setSnapshot(state);
    return () => {
      listeners.delete(setSnapshot);
    };
  }, []);

  return snapshot;
}
