/**
 * Plays a trailer, or tells its parent to fall back.
 *
 * Video is the most expensive thing this plugin does, so the component
 * is careful about when it exists at all:
 *
 * - It mounts nothing until `delayMs` has elapsed since focus settled,
 *   so scrolling past a game never starts a decode.
 * - `preload="none"` means the delay actually saves bandwidth, not just
 *   playback.
 * - On unmount the element is paused, its source cleared and reloaded,
 *   which is what actually releases the decoder. Simply unmounting a
 *   `<video>` is not always enough.
 * - Any playback or network error calls `onUnplayable`, which drops the
 *   overlay to screenshots rather than showing a black box.
 */

import { useEffect, useRef, useState } from "react";

interface TrailerPlayerProps {
  url: string;
  poster?: string | null;
  muted: boolean;
  loop: boolean;
  /** How long to wait after focus settles before starting. */
  delayMs: number;
  /** Called when this trailer cannot be played, for any reason. */
  onUnplayable: () => void;
}

export function TrailerPlayer({
  url,
  poster,
  muted,
  loop,
  delayMs,
  onUnplayable,
}: TrailerPlayerProps) {
  const [armed, setArmed] = useState(delayMs <= 0);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Re-arm from scratch whenever the trailer changes.
  useEffect(() => {
    if (delayMs <= 0) {
      setArmed(true);
      return;
    }
    setArmed(false);
    const timer = setTimeout(() => setArmed(true), delayMs);
    return () => clearTimeout(timer);
  }, [url, delayMs]);

  // Tear the decoder down properly on unmount or source change.
  useEffect(() => {
    const video = videoRef.current;
    return () => {
      if (!video) return;
      try {
        video.pause();
        video.removeAttribute("src");
        video.load();
      } catch {
        // Nothing useful to do if the element is already gone.
      }
    };
  }, [url, armed]);

  if (!armed) {
    return poster ? (
      <img src={poster} alt="" style={STILL_STYLE} draggable={false} />
    ) : null;
  }

  return (
    <video
      ref={videoRef}
      src={url}
      poster={poster ?? undefined}
      autoPlay
      muted={muted}
      loop={loop}
      playsInline
      preload="none"
      disablePictureInPicture
      controls={false}
      style={STILL_STYLE}
      onError={onUnplayable}
      onStalled={onUnplayable}
      onPlaying={() => {
        // Steam can un-mute media it did not create; hold the setting.
        const video = videoRef.current;
        if (video && video.muted !== muted) video.muted = muted;
      }}
    />
  );
}

const STILL_STYLE: React.CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
  display: "block",
  border: "none",
  background: "transparent",
};
