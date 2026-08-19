/**
 * Typed wrappers around the Python backend's RPC surface.
 *
 * Each backend method is guaranteed to return a well-formed result
 * rather than raise, but the transport itself can still fail (the plugin
 * unloading mid-call, for instance), so every call is also guarded here.
 * A failed lookup yields an empty media object, never an exception.
 */

import { call } from "@decky/api";

import type { CacheStats, LibraryEntry, MediaResult, Settings } from "./types";
import { DEFAULT_SETTINGS } from "./types";

export function emptyMedia(key = "", note: string | null = null): MediaResult {
  return {
    key,
    kind: "",
    title: "",
    source: "empty",
    resolved_appid: null,
    trailer_url: null,
    trailer_kind: null,
    trailer_thumbnail: null,
    screenshot_urls: [],
    hero_url: null,
    note,
  };
}

export async function getMediaFor(entry: LibraryEntry): Promise<MediaResult> {
  try {
    const result = await call<[entry: LibraryEntry], MediaResult>("get_media_for", entry);
    return result ?? emptyMedia("", "no-response");
  } catch (error) {
    console.warn("[SteamView] get_media_for failed:", error);
    return emptyMedia("", "transport-error");
  }
}

export async function prefetch(entries: LibraryEntry[]): Promise<number> {
  try {
    return (await call<[entries: LibraryEntry[]], number>("prefetch", entries)) ?? 0;
  } catch {
    // Prefetching is an optimisation; a failure is not worth reporting.
    return 0;
  }
}

export async function clearCache(): Promise<number> {
  try {
    const result = await call<[], { ok: boolean; removed: number }>("clear_cache");
    return result?.removed ?? 0;
  } catch (error) {
    console.warn("[SteamView] clear_cache failed:", error);
    return 0;
  }
}

export async function cacheStats(): Promise<CacheStats> {
  try {
    const result = await call<[], CacheStats>("cache_stats");
    return result ?? { directory: "", entries: 0, memory_entries: 0, bytes: 0 };
  } catch {
    return { directory: "", entries: 0, memory_entries: 0, bytes: 0 };
  }
}

export async function getSettings(): Promise<Settings> {
  try {
    const result = await call<[], Settings>("get_settings");
    return { ...DEFAULT_SETTINGS, ...(result ?? {}) };
  } catch (error) {
    console.warn("[SteamView] get_settings failed, using defaults:", error);
    return { ...DEFAULT_SETTINGS };
  }
}

export async function setSettings(patch: Partial<Settings>): Promise<Settings> {
  try {
    const result = await call<[patch: Partial<Settings>], Settings>("set_settings", patch);
    return { ...DEFAULT_SETTINGS, ...(result ?? {}) };
  } catch (error) {
    console.warn("[SteamView] set_settings failed:", error);
    return { ...DEFAULT_SETTINGS };
  }
}
