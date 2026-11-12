/**
 * Starting a trailer, with sound when asked for and allowed.
 *
 * Kept free of imports and React so it can run in a real browser under
 * each of Chromium's autoplay policies; see TrailerPlayer for why it is
 * an explicit `play()` at all.
 */

export interface PlaybackHooks {
  /** Whether a trailer meant to have sound got to play with it. */
  onSound?: (outcome: "ok" | "blocked") => void;
  /** Sound was refused and the trailer fell back to playing silently. */
  onForcedMute?: () => void;
  /** It could not be played at all. */
  onUnplayable: () => void;
}

function errorName(error: unknown): string {
  return typeof error === "object" && error !== null ? String((error as { name?: unknown }).name) : "";
}

/**
 * Play `media` muted or not, as asked. If sound is refused, play it
 * silently rather than not at all. `isCancelled` is checked after every
 * await, so a superseded start never reports or falls back.
 */
export async function startPlayback(
  media: HTMLMediaElement,
  muted: boolean,
  isCancelled: () => boolean,
  hooks: PlaybackHooks,
): Promise<void> {
  media.muted = muted;
  try {
    await media.play();
    if (!muted && !isCancelled()) hooks.onSound?.("ok");
  } catch (error) {
    // AbortError: the source changed or the element went away first.
    if (isCancelled() || errorName(error) === "AbortError") return;
    if (!muted && errorName(error) === "NotAllowedError") {
      // A muted <video> may always start, so retrying silently succeeds
      // at once. (Verified in Chromium under
      // --autoplay-policy=document-user-activation-required; an <audio>
      // element is stricter, but trailers are always <video>.)
      media.muted = true;
      hooks.onForcedMute?.();
      hooks.onSound?.("blocked");
      console.warn("[SteamView] Steam refused trailer sound; playing it silently.");
      try {
        await media.play();
      } catch (retry) {
        if (!isCancelled() && errorName(retry) !== "AbortError") hooks.onUnplayable();
      }
      return;
    }
    hooks.onUnplayable();
  }
}
