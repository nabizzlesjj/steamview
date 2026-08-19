/**
 * Types shared between the focus hook, the overlay and the backend RPC
 * surface. These mirror the Python side's contracts exactly.
 */

/** Which resolution path an entry takes. Mirrors `steamview.entries`. */
export type EntryKind = "steam" | "shortcut";

/** A library item the focus hook has identified. */
export interface LibraryEntry {
  appid: number;
  name: string;
  kind: EntryKind;
  hero_url?: string | null;
  capsule_url?: string | null;
  extra_art?: string[];
}

/**
 * Stable identity for an entry, used to decide whether focus actually
 * moved and to key React effects.
 *
 * Shortcuts key by name rather than appid for the same reason the
 * backend cache does: their appids are machine-local and regenerate.
 */
export function entryKey(entry: LibraryEntry | null): string {
  if (!entry) return "";
  return entry.kind === "steam"
    ? `steam:${entry.appid}`
    : `shortcut:${entry.name.trim().toLowerCase()}`;
}

/** Where a media object's contents came from. Mirrors `steamview.media`. */
export type MediaSource = "appdetails" | "name-match" | "fallback-art" | "empty";

/** The resolved media the overlay renders. Mirrors `MediaResult.to_dict()`. */
export interface MediaResult {
  key: string;
  kind: string;
  title: string;
  source: MediaSource;
  resolved_appid: number | null;
  trailer_url: string | null;
  trailer_kind: "microtrailer" | "webm" | "mp4" | null;
  trailer_thumbnail: string | null;
  screenshot_urls: string[];
  hero_url: string | null;
  note: string | null;
}

export type PreviewMode = "trailer" | "screenshots" | "off";
export type OverlayPosition = "top-left" | "top-right" | "bottom-left" | "bottom-right";
export type OverlaySize = "s" | "m" | "l";

/** Mirrors `steamview.settings.DEFAULTS`. */
export interface Settings {
  enabled: boolean;
  preview_mode: PreviewMode;
  autoplay_delay_ms: number;
  muted: boolean;
  loop: boolean;
  position: OverlayPosition;
  size: OverlaySize;
  data_saver: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  enabled: true,
  preview_mode: "trailer",
  autoplay_delay_ms: 600,
  muted: true,
  loop: true,
  position: "bottom-right",
  size: "m",
  data_saver: false,
};

export interface CacheStats {
  directory: string;
  entries: number;
  memory_entries: number;
  bytes: number;
}

/** Whether the Steam-coupled focus hook came up. */
export interface FocusStatus {
  ok: boolean;
  reason?: string;
}
