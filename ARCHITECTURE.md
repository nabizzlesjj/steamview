# Architecture

How SteamView is put together, and why the awkward parts are the way they
are. Read this before changing the focus hook or the resolver.

---

## Overview

```
gamepad focus moves in the library grid
        │
        ▼
  src/steam/focus.ts  ── the Steam-coupled module, feature-flagged ──┐
        │  reports { appid, name, kind, heroUrl, … }                 │  on failure:
        ▼                                                            │  log once,
  debounce (preview_delay_ms), cancel stale requests                 │  disable the
        │                                                            │  overlay only
        ▼                                                            │
  call('get_media_for', entry)  ─────────────────────────────────────┤
        │                                                            │
        ▼                                                     settings + backend
  Python: cache → resolve → cache                              keep working
        │
        ▼
  PreviewOverlay: trailer → screenshots → hero art
```

The frontend is deliberately thin. It reports *which entry is focused*
and renders *whatever media object comes back*. Every judgement about
which URL to prefer, which name matches which store entry, and what to
cache lives in Python, where it is unit-testable without a Deck.

---

## Focus detection and UI injection

This is the part most likely to break on a SteamOS update. It is confined
to two files: `src/steam/bindings.ts` (everything Steam-specific) and
`src/steam/focus.ts` (the listener and the failure policy).

### No Valve component is patched

`routerHook.addGlobalComponent()` renders the overlay through a supported
Decky API. Nothing patches, wraps or mutates a Steam component, so there
is no patch to go stale. The overlay is a sibling of Steam's UI, not a
graft onto it.

It is also `pointer-events: none` and never focusable, so it cannot
intercept gamepad navigation in any state.

### Detection

1. `findSP()` locates Steam's UI window.
2. A passive, capture-phase `focusin` listener is attached to its
   document. Steam's gamepad navigation moves real DOM focus — that is
   how its focus ring is positioned — so the highlight moving produces an
   event whose target is the focused element.
3. Scope check, in `bindings.isInScope`:
   - on a game's **detail page** → ignore. Steam already fills that
     screen with the game's own artwork and Play button.
   - inside `gamepadLibraryClasses.GamepadLibrary` → continue.
   - anything else (the store, the QAM, a context menu) → ignore.
4. `bindings.findAppIdForElement` walks up the React fiber tree from the
   focused element, at most 30 levels, for the first component whose
   props carry an app identity.
5. `appStore.GetAppOverviewByAppID()` turns that id into a full overview,
   which is classified native or shortcut and handed to the backend.

### Why a fiber walk instead of class names

Valve's prop names (`app`, `overview`, `appid`) are semantic and survive
minification. CSS class names are hashed per build. Matching on data
shape is therefore substantially more durable than matching on markup.

The one place class names are unavoidable — scoping to the library — goes
through `@decky/ui`'s class mapper, which resolves them at load time by
module shape. They are lookups, not hardcoded strings.

The detail-page exclusion carries two independent signals, the container
classes *and* the `/library/app/` route, because either can go stale
alone: class names are minified per build, and the route only helps if
Steam's router writes it to the document location.

### If focus events never arrive

Should Steam stop moving real DOM focus, no `focusin` would fire and the
overlay would sit blank. If nothing has been seen within 5 seconds,
`focus.ts` arms a 250 ms poll: `document.activeElement` first (plain DOM,
coupled to nothing), then `getFocusNavController()` for a highlight Steam
is tracking that never reached the document. Either way the element goes
through the same fiber walk. The poll is never armed while the listener
is working.

### Failure policy

`startFocusTracking` returns `{ ok, reason, stop }`. Every callback body
is wrapped; the initial wiring is wrapped; five consecutive handler
exceptions detach the listener entirely. Failures log **once**, not per
event, so a broken build cannot spam the console at gamepad-input
frequency.

On failure the plugin stays loaded: the QAM panel appears, states the
reason inline, and every setting still works. Only the overlay is gone,
and the library is untouched either way.

### Overlay geometry

The overlay renders into a portal host appended to the SP window's body.
This matters: `position: fixed` resolves against the nearest ancestor
carrying a transform, and Steam's content region is transformed for its
page transitions, so a card rendered in place is positioned and clipped
by that region rather than the screen.

The host spans the *library pane* — inset past the search field and
collection tabs above, and the button-hint bar below — so the overlay can
only ever cover the game grid.

Note that Game Mode renders its UI zoomed: a Deck's 1280x800 panel is
roughly an 870x545 CSS viewport, leaving a pane only ~380px tall against
a 377px Large card. The card is clamped to the pane, and when that clamp
binds the media shrinks while the info panel does not.

#### Sizing across displays

Game Mode runs on far more than a Deck — a docked Deck, a Bazzite
desktop, a plain SteamOS install at 1080p, 1440p or 4K — and a card
whose width is a fixed pixel count is right on exactly one of them.

`bindings.measureLibraryPane` reads the rect of Steam's own container,
preferring `CollectionContents` (the grid) and falling back to
`GamepadLibrary` (the whole library page). A rect is only believed if it
plausibly *is* the library: most of the viewport's width, a real slice of
its height, and insets that leave positive space.

`overlayGeometry` then turns that into a card, as pure arithmetic with no
DOM, which is what makes it testable:

- **Width** is a fraction of the pane, the fraction being whatever the
  Deck's tuned width was over the Deck's pane. A Deck therefore
  reproduces 280 / 380 / 480 exactly, and a larger display keeps the
  proportion. It is then clamped to per-size minima and maxima, and to
  the pane itself — the last of which wins outright, since overhanging
  the grid is worse than being narrower than intended.
- **Type, padding and margins** scale with the rendered width, clamped
  to 0.8–1.6, so the proportions tuned by eye survive rather than being
  re-tuned per resolution.
- **Insets** are the *larger* of the measurement and the Deck-verified
  floor (96 top, 72 bottom). Those are CSS pixels, which zoom does not
  change — zoom scales the coordinate space, so Steam's stylesheet keeps
  its numbers and only the viewport grows. Taking the larger can only
  move the pane inward from behaviour already verified on hardware,
  which matters because the element available to measure is sometimes
  the library page rather than the grid, and its top edge then sits
  *above* the search field. Wasted space is a cost; covering the search
  field is a bug.

The pane is re-measured on window resize (docking, undocking, a
resolution change) and once per settled focus, which is the cheapest
moment at which the container is certainly mounted.

`tests/frontend/overlayGeometry.test.mjs` runs the arithmetic across
Deck, 1080p, 1440p and 4K viewports and asserts the card never outgrows
its pane, never shrinks as the pane grows, and never inverts the size
ordering.

---

## Media resolution

### Entry classification

Two signals, in order of trust: `app_type === EAppType.Shortcut`
(authoritative, from Steam), then the appid falling at or above `2^31`
(Steam's synthetic shortcut range). Real store appids are in the low
millions, so the ranges do not overlap.

### Path A — native Steam app

`appdetails?appids={appid}&l=english&cc=us`, then read `movies[]`,
`screenshots[]`, `short_description` and `genres[]`.

### Path B — non-Steam shortcut

No store appid exists, only a display name. Search `storesearch` with
progressively stripped variants of that name — raw, minus the store
suffix (`(Epic)`, `[GOG]`, `- Ubisoft Connect`), minus the edition suffix
(`Deluxe Edition`, `GOTY`) — score the candidates, and run Path A on the
winner. Failing that, fall back to whatever artwork the client already
holds for the shortcut.

**Ranking is deliberately conservative.** A missed match costs a trailer;
a wrong match shows a different game entirely. A candidate must clear
**0.82** similarity, combining a character ratio with a token-set ratio,
and any disagreement on a numeric token **halves** the score. Roman
numerals are folded to digits first, which is what separates `Grand Theft
Auto V` from `Grand Theft Auto IV` (0.40) while `Cyberpunk 2077 (Epic)`
still matches `Cyberpunk 2077` (1.00). Single-letter numerals are left
alone, because `I`, `V` and `X` are ordinary title words often enough
(`I Am Bread`, `Mega Man X`) that rewriting them would invent matches.

### Trailer selection

In order:

1. **Microtrailer** — `{cdn}/steam/apps/{movie_id}/microtrailer.webm`
   across the Cloudflare, Akamai and Fastly hosts. Valve does not publish
   this path, so it is **probed with a HEAD request** and used only on a
   2xx. The result is cached with the media object, costing one request
   per game ever.
2. **The movie's own 480p `webm`**, which *is* in the API payload and so
   is always correct when present. This is the safety net.
3. **The movie's 480p `mp4`**, for entries with no webm variant.

If Valve moves or removes microtrailers, step 1 stops matching and step 2
takes over with no code change.

### Networking

SteamOS ships an outdated CA bundle, and certificate verification fails
inside the Decky plugin process. `http._open` attempts verification
first and falls back to an unverified connection **only** after a genuine
certificate error — never a timeout, DNS failure or HTTP status — logging
once and remembering the decision for the session. What travels over it
is public game metadata; the plugin sends no credentials and nothing
user-identifying.

The only hosts contacted are `store.steampowered.com` and the
`*.steamstatic.com` CDNs. There is no telemetry of any kind.

### Caching

Two layers, memory over disk. Successes live **7 days**; failures live
**1 hour**, so an offline moment does not poison the cache but a
genuinely storeless game is not re-fetched on every pass. Disk is capped
at 600 entries, pruned oldest-first.

Native games key by `app:{appid}`. Shortcuts key by a hash of their
normalised **name**, because synthetic shortcut appids are machine-local
and change if the shortcut is recreated, while the name is what was
actually resolved against.

Duplicate in-flight requests for the same entry are coalesced.

### Failure contract

Every backend method returns a well-formed media object regardless of
input — unparseable entry, upstream failure, read-only filesystem. No
input makes it raise. The `note` field carries why
(`no-confident-match`, `no-store-entry`, `resolve-error`), and one
info-level log line per resolution records the source, resolved appid,
trailer kind and screenshot count.

---

## Risks

| # | Risk | Mitigation |
| --- | --- | --- |
| 1 | Microtrailer path changes or disappears | Probed, never assumed; falls back to the API's own webm |
| 2 | `focusin` stops firing for gamepad nav | `activeElement` poll, then nav-controller, then clean self-disable |
| 3 | Valve renames the props the fiber walk looks for | Four candidate paths; all constants in one block in `bindings.ts` |
| 4 | Steam rate-limits `storesearch` on a large library | 3 concurrent max, 7-day cache, backoff honouring `Retry-After` |
| 5 | Video decode costs battery | 480p cap, muted, autoplay delay, teardown on blur, data-saver mode |
| 6 | A SteamOS update breaks the hook entirely | Feature flag: overlay off, library and settings untouched |

---

## Not in scope

Restyling the library grid; emulation / ROM / ES-DE local media
integration; per-game manual media overrides; custom themes and
animations. And no telemetry or analytics, ever.
