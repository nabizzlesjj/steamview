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
