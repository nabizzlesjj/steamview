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
 *
 * Beneath the media sits an info panel with the game's title, genres and
 * store blurb. Every row of it is optional -- a non-Steam shortcut with
 * no store match has a title and nothing else -- so the panel collapses
 * to fit rather than reserving empty space.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { findSP } from "@decky/ui";

import { getMediaFor, prefetch as prefetchEntries } from "../api";
import { startFocusTracking } from "../steam/focus";
import { setFocusStatus, usePluginState } from "../store";
import type { LibraryEntry, MediaResult, OverlayPosition, OverlaySize } from "../types";
import { entryKey } from "../types";
import { ScreenshotReel } from "./ScreenshotReel";
import { TrailerPlayer } from "./TrailerPlayer";

/** Extra settle time before warming neighbours, which is never urgent. */
const PREFETCH_DELAY_MS = 1_200;

/** Element id of the portal host, so a reload cannot leave two behind. */
const HOST_ID = "steamview-overlay-root";

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

  // --- portal host ----------------------------------------------------
  //
  // `position: fixed` resolves against the nearest ancestor carrying a
  // transform, and Steam's content area is transformed for its page
  // transitions. A card rendered where Decky mounts the component would
  // therefore be positioned inside -- and clipped by -- that region
  // rather than the screen. Portalling to the SP window's body escapes
  // it, so "fixed" means the viewport.

  const [host, setHost] = useState<HTMLElement | null>(null);

  useEffect(() => {
    let element: HTMLElement | null = null;
    try {
      const doc = findSP()?.document;
      if (!doc?.body) return;
      doc.getElementById(HOST_ID)?.remove();
      element = doc.createElement("div");
      element.id = HOST_ID;
      // The host *is* the library pane: inset past Steam's own chrome so
      // the card is bounded by it rather than by the whole viewport.
      Object.assign(element.style, {
        position: "fixed",
        top: `${LIBRARY_PANE_TOP}px`,
        bottom: `${LIBRARY_PANE_BOTTOM}px`,
        left: "0",
        right: "0",
        pointerEvents: "none",
        zIndex: "7000",
      });
      doc.body.appendChild(element);
      setHost(element);
    } catch (error) {
      // Falling back to in-place rendering keeps the preview working,
      // just subject to whatever container Decky mounted us in.
      console.warn("[SteamView] could not create the overlay host:", error);
    }
    return () => {
      element?.remove();
      setHost(null);
    };
  }, []);

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
    const timer = setTimeout(() => setSettled(entry), settings.preview_delay_ms);
    return () => clearTimeout(timer);
    // Keyed on identity, so re-reporting the same game does not restart
    // the timer and stall the preview during continuous input.
  }, [focusedKey, entry, settings.preview_delay_ms]);

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

  const scale = SIZE_SCALE[settings.size] ?? SIZE_SCALE.m;
  // The title alone is worth a panel; a shortcut with no store match
  // still gets a labelled preview rather than an anonymous video.
  const hasInfo = Boolean(media.title || media.genres.length > 0 || media.short_description);

  const card = (
    <div style={containerStyle(settings.position, settings.size, Boolean(host))} aria-hidden="true">
      <style>{KEYFRAMES}</style>
      <div style={CARD_STYLE}>
        <div style={MEDIA_STYLE}>
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
            <img src={media.hero_url} alt="" style={FILL_STYLE} draggable={false} onError={demote} />
          ) : null}
        </div>

        {hasInfo ? (
          <div style={infoStyle(scale)}>
            {media.title ? <div style={titleStyle(scale)}>{media.title}</div> : null}

            {media.genres.length > 0 ? (
              <div style={genreStyle(scale)}>{media.genres.join(" · ")}</div>
            ) : null}

            {media.short_description ? (
              <div style={descriptionStyle(scale)}>{media.short_description}</div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );

  return host ? createPortal(card, host) : card;
}

// ---------------------------------------------------------------------
// Presentation
// ---------------------------------------------------------------------

/** Overlay widths, in CSS pixels on the Deck's 1280x800 panel. */
const SIZE_WIDTHS: Record<OverlaySize, number> = { s: 280, m: 380, l: 480 };

/** Type and padding scale with the overlay so Small stays readable. */
const SIZE_SCALE: Record<OverlaySize, number> = { s: 0.85, m: 1, l: 1.15 };

const EDGE_MARGIN = 20;

/**
 * Steam's library chrome, in CSS pixels, which bounds the area the
 * overlay is allowed to cover.
 *
 * These are *CSS* pixels, not the panel's. Game Mode renders its UI
 * zoomed: a Deck's 1280x800 screen is roughly an 870x545 CSS viewport.
 * The pane between the two bars is therefore only ~380px tall, against a
 * Large card of 377px -- so the clamp in `containerStyle` is a real
 * constraint, not a safety net.
 */
const LIBRARY_PANE_TOP = 96; // search field + collection tabs
const LIBRARY_PANE_BOTTOM = 72; // button-hint bar

/** Gap between the card and the bar it sits against. */
const PANE_INSET = 8;

/** Only used when the portal host could not be created. */
const VERTICAL_MARGIN = LIBRARY_PANE_BOTTOM + PANE_INSET;

function containerStyle(
  position: OverlayPosition,
  size: OverlaySize,
  portalled: boolean,
): React.CSSProperties {
  const width = SIZE_WIDTHS[size] ?? SIZE_WIDTHS.m;
  const [vertical, horizontal] = position.split("-") as ["top" | "bottom", "left" | "right"];

  return {
    // Inside the portal host (itself fixed and filling the viewport)
    // absolute is enough, and is immune to any transform further up.
    position: portalled ? "absolute" : "fixed",
    // Inside the host the offset is from the pane edge, not the screen.
    [vertical]: portalled ? PANE_INSET : VERTICAL_MARGIN,
    [horizontal]: EDGE_MARGIN,
    width,
    // The pane is barely taller than a Large card, so this is a real
    // constraint rather than insurance: when it binds, the media gives
    // way (see MEDIA_STYLE) and the text stays intact.
    maxHeight: portalled ? `calc(100% - ${PANE_INSET * 2}px)` : `calc(100% - ${VERTICAL_MARGIN * 2}px)`,
    display: "flex",
    flexDirection: "column",
    // Height is left to content: the media keeps its 16:9 ratio and the
    // info panel takes whatever it needs, so a game with no blurb gets a
    // shorter card instead of a gap.
    zIndex: 7000,
    // The overlay is decoration. It must never eat gamepad input.
    pointerEvents: "none",
    animation: "steamview-fade-in 240ms ease-out",
  };
}

const CARD_STYLE: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  minHeight: 0,
  maxHeight: "100%",
  overflow: "hidden",
  borderRadius: 8,
  // A hairline light border reads as a deliberate frame against both
  // Steam's dark chrome and a bright capsule behind it.
  border: "1px solid rgba(255, 255, 255, 0.18)",
  background: "rgba(14, 18, 24, 0.94)",
  boxShadow: "0 8px 28px rgba(0, 0, 0, 0.65)",
};

const MEDIA_STYLE: React.CSSProperties = {
  position: "relative",
  width: "100%",
  // If space ever runs short the picture gives way before the text does.
  minHeight: 0,
  flexShrink: 1,
  // Every Steam trailer, screenshot and header image is already 16:9.
  aspectRatio: "16 / 9",
  overflow: "hidden",
  background: "#000000",
};

const FILL_STYLE: React.CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
  display: "block",
};

function infoStyle(scale: number): React.CSSProperties {
  return {
    // Never squeezed: the title and blurb are the point of the panel.
    flexShrink: 0,
    padding: `${Math.round(9 * scale)}px ${Math.round(11 * scale)}px ${Math.round(10 * scale)}px`,
    borderTop: "1px solid rgba(255, 255, 255, 0.10)",
    display: "flex",
    flexDirection: "column",
    gap: Math.round(3 * scale),
  };
}

function titleStyle(scale: number): React.CSSProperties {
  return {
    color: "#ffffff",
    fontSize: Math.round(15 * scale),
    fontWeight: 700,
    lineHeight: 1.25,
    // One line: a long title should not push the blurb off the card.
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  };
}

function genreStyle(scale: number): React.CSSProperties {
  return {
    color: "#8ba6c1",
    fontSize: Math.round(11 * scale),
    fontWeight: 600,
    letterSpacing: 0.3,
    lineHeight: 1.3,
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  };
}

function descriptionStyle(scale: number): React.CSSProperties {
  return {
    color: "rgba(255, 255, 255, 0.72)",
    fontSize: Math.round(12 * scale),
    lineHeight: 1.4,
    // Two lines, clamped. The backend caps the payload; this decides
    // what is actually shown, so it adapts to the chosen overlay size.
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
  };
}

const KEYFRAMES = `
@keyframes steamview-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
`;
