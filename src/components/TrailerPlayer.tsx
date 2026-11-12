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
 *
 * Playback is started with an explicit `play()` rather than the
 * `autoplay` attribute, so that a refusal can be handled. Chromium may
 * refuse to start a video *with sound* that no click or tap asked for.
 * Steam's browser has been
 * seen allowing it -- the AudioLoader plugin starts menu music with a
 * plain `play()` -- but if a refusal ever comes, the trailer plays
 * silently rather than not at all, and `onSound("blocked")` lets the
 * settings panel say why there is no audio.
 */

import { useEffect, useRef, useState } from "react";

import { startPlayback } from "../playback";

interface TrailerPlayerProps {
  url: string;
  poster?: string | null;
  muted: boolean;
  loop: boolean;
  /** How long to wait after focus settles before starting. */
  delayMs: number;
  /** Called when this trailer cannot be played, for any reason. */
  onUnplayable: () => void;
  /** Whether a trailer meant to have sound got to play with it. */
  onSound?: (outcome: "ok" | "blocked") => void;
}


export function TrailerPlayer({
  url,
  poster,
  muted,
  loop,
  delayMs,
  onUnplayable,
  onSound,
}: TrailerPlayerProps) {
  const [armed, setArmed] = useState(delayMs <= 0);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  /**
   * True once sound was refused and the trailer fell back to silence.
   * Read by `onPlaying`, which otherwise re-applies the user's setting
   * and would undo the fallback it just made.
   */
  const forcedMute = useRef(false);

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

  // Start playback, and re-apply the setting when it changes mid-play.
  useEffect(() => {
    const video = videoRef.current;
    if (!armed || !video) return;
    let cancelled = false;
    forcedMute.current = false;
    void startPlayback(video, muted, () => cancelled, {
      onSound,
      onUnplayable,
      onForcedMute: () => {
        forcedMute.current = true;
      },
    });
    return () => {
      cancelled = true;
    };
  }, [armed, url, muted, onSound, onUnplayable]);

  if (!armed) {
    return poster ? (
      <img src={poster} alt="" style={STILL_STYLE} draggable={false} />
    ) : null;
  }

  return (
    <video
      // A fresh element per source: the teardown above clears the element
      // it was given, and reusing one across sources let it clear the
      // *new* source when a clip changed in place (Muted toggled mid-play,
      // or a game changed with no autoplay delay).
      key={url}
      ref={videoRef}
      src={url}
      poster={poster ?? undefined}
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
        // Steam can un-mute media it did not create; hold the setting --
        // unless sound was refused, when silence is the fallback to keep.
        const video = videoRef.current;
        const want = muted || forcedMute.current;
        if (video && video.muted !== want) video.muted = want;
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
