/**
 * The preview overlay itself.
 *
 * Rendered through `routerHook.addGlobalComponent`, so it is a sibling
 * of Steam's UI rather than something spliced into it. It is
 * `pointer-events: none` and never focusable, so it cannot intercept
 * gamepad navigation no matter what state it is in.
 *
 * Its job is a fallback ladder: trailer, then screenshots, then hero
 * art, then nothing. Each stage can demote itself (a video that will not
 * play, images that will not load), so the overlay is never a blank box
 * and never a broken one.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getMediaFor, prefetch as prefetchEntries } from "../api";
import { startFocusTracking } from "../steam/focus";
import { setFocusStatus, usePluginState } from "../store";
import type { LibraryEntry, MediaResult, OverlayPosition, OverlaySize } from "../types";
import { entryKey } from "../types";
import { ScreenshotReel } from "./ScreenshotReel";
import { TrailerPlayer } from "./TrailerPlayer";

/**
 * How long focus must settle before we ask the backend for anything.
 * Inside the 250-400ms band that keeps a fast scroll from firing a
 * request per frame.
 */
const FOCUS_DEBOUNCE_MS = 300;

/** Extra settle time before warming neighbours, which is never urgent. */
const PREFETCH_DELAY_MS = 1_200;

type Stage = "trailer" | "screenshots" | "hero";

export function PreviewOverlay() {
  const { settings, focus } = usePluginState();
  const [entry, setEntry] = useState<LibraryEntry | null>(null);
  const [settled, setSettled] = useState<LibraryEntry | null>(null);
  const [media, setMedia] = useState<MediaResult | null>(null);
  const [stageIndex, setStageIndex] = useState(0);

  /**
   * Monotonic token identifying the newest in-flight request. A response
   * carrying a stale token is dropped, so a fast scroll can never land
   * an earlier game's trailer on a later game's overlay.
   */
  const requestToken = useRef(0);

  const active = settings.enabled && settings.preview_mode !== "off" && focus.ok;

  // --- focus tracking -------------------------------------------------

  useEffect(() => {
    if (!active) {
      setEntry(null);
      return;
    }
    const tracker = startFocusTracking(setEntry);
    if (!tracker.ok) {
      setFocusStatus({ ok: false, reason: tracker.reason });
    }
    return () => tracker.stop();
  }, [active]);

  // --- debounce -------------------------------------------------------

  const focusedKey = entryKey(entry);

  useEffect(() => {
    if (!entry) {
      setSettled(null);
      return;
    }
    const timer = setTimeout(() => setSettled(entry), FOCUS_DEBOUNCE_MS);
    return () => clearTimeout(timer);
    // Keyed on identity, so re-reporting the same game does not restart
    // the timer and stall the preview during continuous input.
  }, [focusedKey, entry]);

  // --- media resolution ----------------------------------------------

  const settledKey = entryKey(settled);

  useEffect(() => {
    if (!settled || !active) {
      setMedia(null);
      return;
    }

    const token = ++requestToken.current;
    let cancelled = false;

    setStageIndex(0);
    getMediaFor(settled)
      .then((result) => {
        // Two guards: this effect being torn down, and a newer request
        // having started while we were waiting.
        if (cancelled || token !== requestToken.current) return;
        setMedia(result);
      })
      .catch((error) => {
        if (cancelled || token !== requestToken.current) return;
        console.warn("[SteamView] media lookup failed:", error);
        setMedia(null);
      });

    return () => {
      cancelled = true;
    };
  }, [settledKey, settled, active]);

  // --- neighbour prefetch ---------------------------------------------

  useEffect(() => {
    if (!settled || !active) return;
    // Only once focus has been stable well past the debounce, so this
    // never competes with the request the user is actually waiting on.
    const timer = setTimeout(() => {
      void prefetchEntries([settled]);
    }, PREFETCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [settledKey, settled, active]);

  // --- the fallback ladder --------------------------------------------

  const stages = useMemo<Stage[]>(() => {
    if (!media) return [];
    const ladder: Stage[] = [];
    const wantsVideo = settings.preview_mode === "trailer" && !settings.data_saver;
    if (wantsVideo && media.trailer_url) ladder.push("trailer");
    if (media.screenshot_urls.length > 0) ladder.push("screenshots");
    if (media.hero_url) ladder.push("hero");
    return ladder;
  }, [media, settings.preview_mode, settings.data_saver]);

  const demote = useCallback(() => setStageIndex((index) => index + 1), []);

  const stage = stages[stageIndex];

  if (!active || !media || !stage) return null;

  return (
    <div style={containerStyle(settings.position, settings.size)} aria-hidden="true">
      <style>{KEYFRAMES}</style>
      <div style={FRAME_STYLE}>
        {stage === "trailer" && media.trailer_url ? (
          <TrailerPlayer
            url={media.trailer_url}
            poster={media.trailer_thumbnail ?? media.hero_url}
            muted={settings.muted}
            loop={settings.loop}
            delayMs={settings.autoplay_delay_ms}
            onUnplayable={demote}
          />
        ) : null}

        {stage === "screenshots" ? (
          <ScreenshotReel urls={media.screenshot_urls} onUnusable={demote} />
        ) : null}

        {stage === "hero" && media.hero_url ? (
          <img src={media.hero_url} alt="" style={HERO_STYLE} draggable={false} onError={demote} />
        ) : null}

        {media.title ? <div style={CAPTION_STYLE}>{media.title}</div> : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------
// Presentation
// ---------------------------------------------------------------------

/** Overlay widths, in CSS pixels on the Deck's 1280x800 panel. */
const SIZE_WIDTHS: Record<OverlaySize, number> = { s: 280, m: 380, l: 480 };

const EDGE_MARGIN = 20;

function containerStyle(position: OverlayPosition, size: OverlaySize): React.CSSProperties {
  const width = SIZE_WIDTHS[size] ?? SIZE_WIDTHS.m;
  const [vertical, horizontal] = position.split("-") as ["top" | "bottom", "left" | "right"];

  return {
    position: "fixed",
    [vertical]: EDGE_MARGIN,
    [horizontal]: EDGE_MARGIN,
    width,
    // 16:9, which every Steam trailer and screenshot already is.
    height: Math.round((width * 9) / 16),
    // Above Steam's library chrome, below its modals and the QAM.
    zIndex: 7000,
    // The overlay is decoration. It must never eat gamepad input.
    pointerEvents: "none",
    animation: "steamview-fade-in 240ms ease-out",
  };
}

const FRAME_STYLE: React.CSSProperties = {
  position: "relative",
  width: "100%",
  height: "100%",
  overflow: "hidden",
  borderRadius: 6,
  background: "rgba(0, 0, 0, 0.85)",
  boxShadow: "0 6px 24px rgba(0, 0, 0, 0.6)",
};

const HERO_STYLE: React.CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
  display: "block",
};

const CAPTION_STYLE: React.CSSProperties = {
  position: "absolute",
  left: 0,
  right: 0,
  bottom: 0,
  padding: "14px 10px 6px",
  background: "linear-gradient(to top, rgba(0, 0, 0, 0.85), transparent)",
  color: "#ffffff",
  fontSize: 13,
  fontWeight: 500,
  lineHeight: 1.2,
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const KEYFRAMES = `
@keyframes steamview-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
`;
