/**
 * Every point where this plugin touches Steam's internal UI.
 *
 * ## Read this first after a SteamOS update
 *
 * Steam's Game Mode UI is minified, undocumented, and free to change on
 * any release. Rather than scatter that coupling across components, all
 * of it is collected here: the shapes we look for, the globals we read,
 * and the container classes that scope us to the library. If the preview
 * stops working after an update, this file and `focus.ts` are the only
 * two places that should need changing.
 *
 * Two rules keep the coupling as shallow as possible:
 *
 * 1. **Match on data shape, never on minified names.** Valve's prop
 *    names (`app`, `overview`, `appid`) are semantic and survive
 *    minification; CSS class names are hashed per build. So we walk the
 *    React tree looking for props that *look* like an app, rather than
 *    for an element with a particular class.
 *
 * 2. **Resolve class names at runtime.** The one place we do need class
 *    names -- scoping to the library -- goes through `@decky/ui`'s class
 *    mapper, which finds them by module shape at load time. They are
 *    lookups, not hardcoded strings.
 */

import {
  appDetailsClasses,
  basicAppDetailsSectionStylerClasses,
  gamepadLibraryClasses,
  getReactInstance,
} from "@decky/ui";

import { normaliseLanguage } from "../languages";
import type { EntryKind, LibraryEntry } from "../types";

// ---------------------------------------------------------------------
// Tunables
// ---------------------------------------------------------------------

/**
 * Prop paths that identify a library entry, tried in order. Several are
 * listed because Valve has used different shapes in different parts of
 * the UI, and having spares means a rename breaks one path rather than
 * the feature.
 */
const APP_PROP_PATHS: readonly (readonly string[])[] = [
  ["app", "appid"],
  ["overview", "appid"],
  ["appOverview", "appid"],
  ["item", "appid"],
  ["appid"],
];

/** How far up the fiber tree to look before giving up on one element. */
const FIBER_WALK_MAX_DEPTH = 30;

/** `EAppType.Shortcut`, from Steam's client enums. */
const APP_TYPE_SHORTCUT = 1073741824;

/** Synthetic shortcut appids sit at or above this. */
const SHORTCUT_APPID_MIN = 2 ** 31;

// ---------------------------------------------------------------------
// Scoping
// ---------------------------------------------------------------------

function toSelectors(classNames: (string | undefined)[]): string[] {
  return classNames
    .filter((name): name is string => typeof name === "string" && name.length > 0)
    // Steam class values can be space-separated compound names.
    .map((name) => "." + name.trim().split(/\s+/).join("."));
}

function matchesAny(element: Element, selectors: string[]): boolean {
  return selectors.some((selector) => {
    try {
      return Boolean(element.closest(selector));
    } catch {
      return false;
    }
  });
}

/**
 * The library grid -- the only place the preview belongs.
 *
 * Computed lazily and cached, because `@decky/ui`'s class modules are
 * populated during its own load.
 */
let cachedGridSelectors: string[] | null = null;

export function scopeSelectors(): string[] {
  return (cachedGridSelectors ??= toSelectors([gamepadLibraryClasses?.GamepadLibrary]));
}

/**
 * A game's detail page, where the preview is explicitly *not* wanted:
 * Steam already fills that screen with the game's own hero art, stats
 * and Play button, and the overlay simply covers them.
 */
let cachedDetailSelectors: string[] | null = null;

function detailPageSelectors(): string[] {
  return (cachedDetailSelectors ??= toSelectors([
    basicAppDetailsSectionStylerClasses?.AppDetailsRoot,
    appDetailsClasses?.Container,
  ]));
}

/** The detail page's route, as a second, class-independent signal. */
const DETAIL_ROUTE = "/library/app/";

function onDetailRoute(element: Element): boolean {
  try {
    return Boolean(element.ownerDocument?.defaultView?.location?.pathname?.includes(DETAIL_ROUTE));
  } catch {
    return false;
  }
}

/** Whether `element` is on a game's detail page. */
export function isOnDetailPage(element: Element | null): boolean {
  if (!element) return false;
  // Two independent signals, because either can go stale on its own: the
  // class names are minified per build, and the route only helps if
  // Steam's router writes it to the document location.
  return matchesAny(element, detailPageSelectors()) || onDetailRoute(element);
}

/** Whether `element` sits inside the library grid. */
export function isInScope(element: Element | null): boolean {
  if (!element) return false;
  // The detail page wins: it is excluded even where its markup nests
  // inside something the grid check would otherwise accept.
  if (isOnDetailPage(element)) return false;
  const selectors = scopeSelectors();
  // No selector resolved at all: the class mapper did not find it. Fail
  // open rather than silently never firing -- the fiber walk still has
  // to succeed for anything to happen, and that is the real gate.
  if (selectors.length === 0) return true;
  return matchesAny(element, selectors);
}

/**
 * The library pane, measured from Steam's own containers: its inset from
 * the top and bottom of the viewport and its rendered size, all in CSS
 * pixels.
 *
 * The overlay must sit inside the game grid without covering the search
 * field and collection tabs above it or the button-hint bar below, and
 * -- the reason this exists -- it must be *sized* against the grid it
 * sits in. Game Mode runs on far more than a Deck: a docked Deck, a
 * Bazzite desktop, a plain SteamOS install at 1080p, 1440p or 4K. A card
 * whose width is a fixed pixel count is tuned for exactly one of those.
 *
 * The caller decides how much to trust the insets (see
 * `overlayGeometry.paneInsets`, which treats them as a refinement of a
 * floor rather than an answer). The *width* is used directly, because
 * there is no comparable risk in it: too narrow wastes space, and it
 * cannot cover chrome.
 */
export interface LibraryPane {
  top: number;
  bottom: number;
  /** Distance from the viewport's left edge, for pane-relative maths. */
  left: number;
  width: number;
  height: number;
}

/**
 * A measurement is only trusted if the container plausibly *is* the
 * library: it has to occupy most of the width and a real slice of the
 * height. A collapsed or mis-identified element falls back to the
 * caller's defaults rather than positioning the card somewhere absurd.
 */
const MIN_PANE_WIDTH_FRACTION = 0.5;
const MIN_PANE_HEIGHT_FRACTION = 0.3;

/**
 * Candidates, most specific first. `CollectionContents` is the grid
 * itself, so its top edge already sits below the search field and
 * collection tabs; `GamepadLibrary` is the whole library page and on
 * some layouts contains them. Either is a usable width, and the caller's
 * inset floor covers the difference between them.
 */
let cachedPaneSelectors: string[] | null = null;

function paneSelectors(): string[] {
  return (cachedPaneSelectors ??= toSelectors([
    gamepadLibraryClasses?.CollectionContents,
    gamepadLibraryClasses?.GamepadLibrary,
  ]));
}

export function measureLibraryPane(doc: Document | null | undefined): LibraryPane | null {
  if (!doc?.defaultView) return null;

  const viewportWidth = doc.defaultView.innerWidth;
  const viewportHeight = doc.defaultView.innerHeight;
  if (!(viewportWidth > 0 && viewportHeight > 0)) return null;

  for (const selector of paneSelectors()) {
    let rect: DOMRect | undefined;
    try {
      rect = doc.querySelector(selector)?.getBoundingClientRect();
    } catch {
      continue;
    }
    if (!rect) continue;

    if (
      rect.width < viewportWidth * MIN_PANE_WIDTH_FRACTION ||
      rect.height < viewportHeight * MIN_PANE_HEIGHT_FRACTION
    ) {
      continue;
    }

    const top = Math.max(0, Math.round(rect.top));
    const bottom = Math.max(0, Math.round(viewportHeight - rect.bottom));
    // A pane taller than the viewport means the rect is not what we think
    // it is; refuse rather than produce negative space.
    if (top + bottom >= viewportHeight) continue;

    return {
      top,
      bottom,
      left: Math.round(rect.left),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
    };
  }

  return null;
}

// ---------------------------------------------------------------------
// The fiber walk
// ---------------------------------------------------------------------

function readPath(props: any, path: readonly string[]): unknown {
  let current = props;
  for (const segment of path) {
    if (current === null || typeof current !== "object") return undefined;
    current = current[segment];
  }
  return current;
}

function toAppId(value: unknown): number | null {
  const parsed = typeof value === "string" ? Number.parseInt(value, 10) : value;
  if (typeof parsed !== "number" || !Number.isFinite(parsed)) return null;
  // Shortcut appids read back as a negative int32 in some code paths.
  const normalized = parsed < 0 ? parsed + 2 ** 32 : parsed;
  return normalized > 0 ? normalized : null;
}

/**
 * Walk up from a DOM element through the React tree, looking for the
 * first component whose props carry an app identity.
 *
 * This is the primitive the whole feature rests on. It is used both for
 * grid entries and for detail-page elements, because both render
 * ancestors that hold the app's overview.
 */
export function findAppIdForElement(element: Element | null): number | null {
  if (!element) return null;

  let fiber: any;
  try {
    fiber = getReactInstance(element);
  } catch {
    return null;
  }

  for (let depth = 0; fiber && depth < FIBER_WALK_MAX_DEPTH; depth += 1) {
    const props = fiber.memoizedProps ?? fiber.pendingProps;
    if (props && typeof props === "object") {
      for (const path of APP_PROP_PATHS) {
        const appid = toAppId(readPath(props, path));
        if (appid !== null) return appid;
      }
    }
    fiber = fiber.return;
  }

  return null;
}

// ---------------------------------------------------------------------
// Steam's app store
// ---------------------------------------------------------------------

function appStore(): any {
  return (window as any).appStore;
}

export function getAppOverview(appid: number): any | null {
  try {
    return appStore()?.GetAppOverviewByAppID?.(appid) ?? null;
  } catch {
    return null;
  }
}

/** Ask Steam for an artwork URL, tolerating any of these being absent. */
function artworkUrl(overview: any, method: string): string | null {
  try {
    const url = appStore()?.[method]?.(overview);
    return typeof url === "string" && url.length > 0 ? url : null;
  } catch {
    return null;
  }
}

function classifyKind(overview: any, appid: number): EntryKind {
  try {
    if (typeof overview?.BIsShortcut === "function" && overview.BIsShortcut()) {
      return "shortcut";
    }
  } catch {
    // Fall through to the flag checks.
  }
  if (overview?.app_type === APP_TYPE_SHORTCUT) return "shortcut";
  return appid >= SHORTCUT_APPID_MIN ? "shortcut" : "steam";
}

/**
 * Turn an appid into the entry the backend resolves.
 *
 * The artwork URLs are what make Path B's fallback work: for a
 * Unifideck shortcut with no Steam store match, this is the SteamGridDB
 * hero the overlay ends up showing.
 */
export function buildEntry(appid: number): LibraryEntry | null {
  const overview = getAppOverview(appid);
  if (!overview) return null;

  const name = String(overview.display_name ?? overview.sort_as ?? "").trim();
  const kind = classifyKind(overview, appid);

  // A shortcut with no name cannot be resolved by name, and that is the
  // only path it has.
  if (kind === "shortcut" && !name) return null;

  const hero =
    artworkUrl(overview, "GetCachedLandscapeImageURLForApp") ??
    artworkUrl(overview, "GetLandscapeImageURLForApp");
  const capsule =
    artworkUrl(overview, "GetCachedVerticalImageURLForApp") ??
    artworkUrl(overview, "GetVerticalCapsuleURLForApp");

  const extra: string[] = [];
  for (const method of ["GetCustomHeroImageURLs", "GetCustomLandcapeImageURLs"]) {
    try {
      const urls = appStore()?.[method]?.(overview);
      if (Array.isArray(urls)) {
        extra.push(...urls.filter((url): url is string => typeof url === "string" && url.length > 0));
      }
    } catch {
      // Custom artwork is a bonus, never a requirement.
    }
  }

  return {
    appid,
    name,
    kind,
    hero_url: hero,
    capsule_url: capsule,
    extra_art: extra.slice(0, 6),
  };
}

/** The full lookup: a focused DOM element to a resolvable entry. */
export function entryForElement(element: Element | null): LibraryEntry | null {
  if (!isInScope(element)) return null;
  const appid = findAppIdForElement(element);
  return appid === null ? null : buildEntry(appid);
}

// ---------------------------------------------------------------------
// The highlighted item's position
// ---------------------------------------------------------------------

/**
 * Where the focused capsule sits across the pane, as a 0..1 fraction --
 * 0 is the left edge, 1 the right.
 *
 * This is what lets the overlay move out of the way of the game you are
 * actually looking at. It reads `document.activeElement` rather than
 * anything of Steam's, because by the time this is called focus has been
 * still long enough to settle, and the focused element *is* the capsule.
 * The overlay itself is `pointer-events: none` and never focusable, so
 * it can never be what we measure.
 *
 * Returns null when there is nothing sensible to measure, which the
 * caller treats as "leave the overlay where the user put it".
 */
export function measureFocusCentre(
  doc: Document | null | undefined,
  pane: LibraryPane | null,
): number | null {
  if (!doc?.defaultView) return null;

  let rect: DOMRect | undefined;
  try {
    const element = doc.activeElement;
    // `body` means nothing is really focused -- a fallback-poll state,
    // not a highlighted game.
    if (!element || element === doc.body) return null;
    rect = element.getBoundingClientRect();
  } catch {
    return null;
  }
  if (!rect || rect.width <= 0) return null;

  // Measured against the pane, not the viewport: a pane that is inset
  // from the left edge would otherwise push every fraction rightwards
  // and bias which side the card picks.
  const paneLeft = pane?.left ?? 0;
  const paneWidth = pane?.width ?? doc.defaultView.innerWidth;
  if (!(paneWidth > 0)) return null;

  const centre = (rect.left + rect.right) / 2 - paneLeft;
  if (!Number.isFinite(centre)) return null;

  return Math.min(1, Math.max(0, centre / paneWidth));
}

// ---------------------------------------------------------------------
// The client's language
// ---------------------------------------------------------------------

interface SteamSettingsLanguageApi {
  Settings?: { GetCurrentLanguage?: () => Promise<string> };
}

/**
 * The language Steam's own UI is set to, as a store API language code.
 *
 * Steam answers in its own vocabulary -- "brazilian", "koreana",
 * "schinese" -- which is exactly the vocabulary the store API's `l=`
 * parameter takes, so nothing needs translating between the two. The
 * answer is still validated before use: it ends up in a URL.
 *
 * Returns null if Steam will not say, in which case the caller keeps
 * English rather than guessing.
 */
export async function readClientLanguage(): Promise<string | null> {
  try {
    const client = (globalThis as { SteamClient?: SteamSettingsLanguageApi }).SteamClient;
    const settings = client?.Settings;
    const get = settings?.GetCurrentLanguage;
    if (typeof get !== "function") return null;
    return normaliseLanguage(await get.call(settings));
  } catch (error) {
    console.warn("[SteamView] could not read Steam's language:", error);
    return null;
  }
}
