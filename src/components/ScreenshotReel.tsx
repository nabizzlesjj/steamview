/**
 * A slow crossfading carousel, used when there is no playable trailer.
 *
 * Only two images are ever in the DOM (the current one and the one
 * fading in), so a game with a dozen screenshots does not hold a dozen
 * decoded bitmaps. A single image renders statically, with no timer at
 * all.
 */

import { useEffect, useState } from "react";

/** Long enough to actually look at, short enough to feel alive. */
const SLIDE_DURATION_MS = 3_500;
const CROSSFADE_MS = 600;

interface ScreenshotReelProps {
  urls: string[];
  /** Called if every image fails to load, so the parent can fall back. */
  onUnusable?: () => void;
}

export function ScreenshotReel({ urls, onUnusable }: ScreenshotReelProps) {
  const [index, setIndex] = useState(0);
  const [failed, setFailed] = useState<Set<string>>(() => new Set());

  const usable = urls.filter((url) => !failed.has(url));

  // Restart the reel when the game changes.
  useEffect(() => {
    setIndex(0);
    setFailed(new Set());
  }, [urls]);

  useEffect(() => {
    if (usable.length < 2) return;
    const timer = setInterval(() => {
      setIndex((current) => (current + 1) % usable.length);
    }, SLIDE_DURATION_MS);
    return () => clearInterval(timer);
  }, [usable.length]);

  useEffect(() => {
    if (urls.length > 0 && usable.length === 0) onUnusable?.();
  }, [urls.length, usable.length, onUnusable]);

  if (usable.length === 0) return null;

  const current = usable[index % usable.length];
  const previous = usable[(index - 1 + usable.length) % usable.length];

  const markFailed = (url: string) =>
    setFailed((existing) => {
      if (existing.has(url)) return existing;
      const next = new Set(existing);
      next.add(url);
      return next;
    });

  return (
    <div style={CONTAINER_STYLE}>
      {usable.length > 1 && previous !== current ? (
        <img key={previous} src={previous} alt="" style={LAYER_STYLE} draggable={false} />
      ) : null}
      <img
        key={current}
        src={current}
        alt=""
        style={{ ...LAYER_STYLE, animation: `steamview-fade-in ${CROSSFADE_MS}ms ease-out` }}
        draggable={false}
        onError={() => markFailed(current)}
      />
    </div>
  );
}

const CONTAINER_STYLE: React.CSSProperties = {
  position: "relative",
  width: "100%",
  height: "100%",
  overflow: "hidden",
};

const LAYER_STYLE: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  width: "100%",
  height: "100%",
  objectFit: "cover",
  display: "block",
};
