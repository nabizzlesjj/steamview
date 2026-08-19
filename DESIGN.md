# SteamView — V1 design

Status: **awaiting sign-off.** The backend described in §3 is built and
tested. The frontend focus hook in §2 is the part that needs your
approval before I write it.

---

## 0. What I verified, and what I couldn't

Everything below was read from source rather than recalled, because both
Steam's internal UI and the Decky APIs drift.

**Verified by reading the actual code:**

| Claim | Source |
| --- | --- |
| `@decky/ui` is at 4.12.0, `@decky/api` at 1.1.3, `@decky/rollup` at 1.0.2 | npm registry |
| Plugin root needs `plugin.json`, `package.json`, `main.py`, `dist/index.js`, `LICENSE` | `SteamDeckHomebrew/decky-plugin-template` |
| `"type": "module"`, backend imports `decky`, frontend uses `call`/`callable` | same |
| `routerHook.addGlobalComponent(name, component)` exists | `@decky/api@1.1.3/dist/types.d.ts` |
| `findSP()`, `getReactInstance()`, `findInReactTree()`, `afterPatch()`, `createReactTreePatcher()`, `getFocusNavController()`, `getGamepadNavigationTrees()` are real exports | `decky-frontend-lib/src/utils/` |
| `gamepadLibraryClasses.GamepadLibrary` and `focusRingClasses` are real exports | `decky-frontend-lib/src/utils/static-classes.ts` |
| `window.appStore.GetAppOverviewByAppID(appid)` and the `GetCached*ImageURLForApp` family exist | `decky-frontend-lib/src/globals/stores.ts` |
| `EAppType.Shortcut === 1073741824`; overviews expose `BIsShortcut()` | `decky-frontend-lib/src/globals/steam-client/App.ts` |
| `appdetails` returns `{"<appid>": {success, data}}` with `movies[]`/`screenshots[]`; `storesearch` returns `{items: [{id, name, …}]}` | Unifideck's own `steam/appdetails.py` and `steam/library.py`, which consume both in production |

**Could not verify — flagged, not guessed:**

1. **The microtrailer URL.** This sandbox's egress proxy blocks every
   Steam host (`store.steampowered.com`, all three `*.steamstatic.com`
   CDNs), so I could not confirm that
   `…/steam/apps/{movie_id}/microtrailer.webm` resolves. It is treated
   as a *hypothesis the backend tests at runtime* — see §3.3. Nothing
   breaks if it is wrong.
2. **That `focusin` fires for gamepad navigation** in the library grid.
   Steam's `Focusable` components are real focusable DOM elements and the
   focus ring is positioned from them, which strongly implies real DOM
   focus — but I have no Deck to confirm it on. §2.4 carries a fallback
   for exactly this.

**One correction to the brief.** `SDH-GameThemeMusic` lives at
`OMGDuke/SDH-GameThemeMusic`, not under `SteamDeckHomebrew`. More
importantly, it does **not** hook "game highlighted in the grid". It
patches the `/library/app/:appid` **route** and reads the appid from
route params — i.e. it reacts to *opening a game's page*, not to
*scrolling past it*. Its `patchLibraryApp.tsx` is a good model for
route-tree patching, but the focus primitive we need is not in it, and I
have designed one from scratch below.

---

## 1. Architecture at a glance

```
gamepad focus moves in the library grid
        │
        ▼
  focus.ts  ── the ONE risky module, feature-flagged ──┐
        │  reports { appid, name, kind, heroUrl, … }   │  on throw:
        ▼                                              │  log once,
  debounce 250–400 ms, cancel stale                    │  disable overlay
        │                                              │  ONLY
        ▼                                              │
  call('get_media_for', entry)  ──────────────────────►│
        │                                              │
        ▼                                        settings + backend
  Python: cache → resolve → cache                 keep working
        │
        ▼
  PreviewOverlay: trailer → screenshots → hero art
```

The frontend is deliberately dumb. It reports *which entry is focused*
and renders *whatever media object comes back*. Every judgement about
which URL to prefer, which name matches which store entry, and what to
cache lives in Python, where it is unit-testable without a Deck.

---

## 2. Focus detection and UI injection — the risky part

### 2.1 Injection: no Valve component is patched at all

`routerHook.addGlobalComponent('SteamViewOverlay', PreviewOverlay)` —
verified to exist in `@decky/api@1.1.3` — renders our component into
Steam's UI through a **supported Decky API**. We never call `afterPatch`
on a Valve function, never walk into their render output, never push
children into their arrays.

This is the single biggest safety decision in the design. The reference
plugin's `createReactTreePatcher` approach mutates Steam's component
tree, which is precisely what breaks on SteamOS updates. Our overlay is a
sibling, positioned `fixed`, that Steam does not know about. If it fails
to render, Steam's tree is byte-for-byte what it would have been.

The overlay is visually inert too: `pointer-events: none`, never
focusable, so it cannot intercept gamepad navigation.

### 2.2 Detection: a passive listener plus a fiber walk

All of this lives in **`src/steam/focus.ts`** — the one file to open
after a SteamOS update.

```
1. const sp = findSP()                            // @decky/ui, verified
2. sp.document.addEventListener('focusin', handler,
                                { capture: true, passive: true })
3. handler(e):
     a. scope check — is e.target inside
        `.${gamepadLibraryClasses.GamepadLibrary}`?   // verified export
        no  → ignore (we are not in the library)
     b. fiber = getReactInstance(e.target)            // verified export
     c. walk fiber.return upward, at most 30 levels, for the first
        node whose memoizedProps carries an app identity:
            props.app?.appid
            props.overview?.appid
            props.appid
            props.item?.appid
     d. overview = appStore.GetAppOverviewByAppID(appid)   // verified
     e. kind = overview.BIsShortcut?.() || overview.app_type === 1073741824
              ? 'shortcut' : 'steam'
     f. emit { appid, name: overview.display_name, kind, heroUrl, … }
```

**Why a fiber walk rather than class names.** The prop *names* Valve
uses (`app`, `overview`) are semantic and survive minification; the CSS
class names are hashed per build. So the walk keys on data shape, not on
strings that change every release. The only minified value we touch is
`gamepadLibraryClasses.GamepadLibrary`, and that is resolved at runtime
by `@decky/ui`'s class mapper — it is a lookup, not a hardcoded string.

**Everything Steam-specific is a named constant** at the top of
`focus.ts`: the prop paths, the walk depth, the container class. One
file, one block, to fix after an update.

### 2.3 Debounce and cancellation

- Focus change starts a timer (default **300 ms**, inside the 250–400 ms
  band you specified). Only after it settles do we call the backend.
- Each request carries a monotonically increasing token. A response whose
  token is not the newest is discarded, so a fast scroll cannot make an
  old game's trailer land on a new game's overlay.
- Trailer autoplay is a *second* delay on top (`autoplay_delay_ms`,
  default 600 ms), so we never start decoding video mid-scroll.
- On focus leaving the library, the video element is paused, its `src`
  cleared, and the element unmounted — no background decode.
- Neighbour prefetch fires only once focus has been stable, and is capped
  backend-side at 8 entries and 3 concurrent requests.

### 2.4 Fallback if `focusin` never fires

If no focus event has been seen within 5 seconds of the user being in the
library, `focus.ts` switches to a **200 ms polling fallback** that reads
`getFocusNavController()` (verified export) → active context → the
focused node's element, and runs the *same* fiber walk from step (b).
Same primitive, different way of reaching the DOM node. If that also
yields nothing, the module reports failure and the overlay disables
itself.

### 2.5 The feature flag and kill-safety

`focus.ts` exposes exactly one interface:

```ts
startFocusTracking(onFocus: (entry: LibraryEntry | null) => void)
  : { ok: boolean; reason?: string; stop(): void }
```

- Every callback body is wrapped in `try/catch`.
- The initial wiring is wrapped in `try/catch`; a throw returns
  `{ ok: false, reason }` rather than propagating.
- After **5 consecutive** handler exceptions the module detaches itself
  and reports `overlayDisabled`.
- Failure logs **once**, not per event, so a broken build cannot spam
  the console at gamepad-input frequency.
- On `{ ok: false }` the plugin still loads: the QAM panel appears, shows
  the reason inline, and every setting still works. Only the overlay is
  gone. The library is never touched either way.

---

## 3. Media resolution (built)

### 3.1 Entry classification

Two signals, in order of trust: `app_type === EAppType.Shortcut`
(authoritative, straight from Steam), then the appid falling at or above
`2^31` (Steam's synthetic shortcut range). Real store appids are in the
low millions, so the ranges do not overlap.

### 3.2 The two paths

**Path A — native.** `appdetails?appids={appid}&l=english&cc=us`, then
read `movies[]` and `screenshots[]`.

**Path B — non-Steam shortcut.** No store appid exists, only a display
name. So: search `storesearch?term={name}` with progressively stripped
variants of the name — raw, minus the store suffix (`(Epic)`, `[GOG]`,
`- Ubisoft Connect`), minus the edition suffix (`Deluxe Edition`,
`GOTY`) — score the candidates, and run Path A on the winner. Failing
that, fall back to the SteamGridDB hero/art Unifideck already applied.

**The ranking is deliberately conservative.** A missed match costs a
trailer; a wrong match shows a different game entirely. So a candidate
must clear **0.82** similarity, combining a character ratio with a
token-set ratio, and any disagreement on a numeric token **halves** the
score. Roman numerals are folded to digits first, which is what makes
`Grand Theft Auto V` vs `Grand Theft Auto IV` fail (0.40) while
`Cyberpunk 2077 (Epic)` vs `Cyberpunk 2077` passes (1.00). Single-letter
numerals are left alone, because `I`, `V` and `X` are ordinary title
words often enough (`I Am Bread`, `Mega Man X`) that rewriting them would
invent matches.

### 3.3 Trailer selection, and the microtrailer hypothesis

In order:

1. **Microtrailer** — `{cdn}/steam/apps/{movie_id}/microtrailer.webm`,
   across the Cloudflare, Akamai and Fastly CDN hosts. This URL is
   *derived*, not published by the API, and I could not test it from
   here. So it is **probed with a HEAD request**, and only used if the
   probe returns 2xx. The probe result is cached with the media object,
   so it costs one request per game, ever.
2. **The movie's own 480p `webm`** — this URL *is* in the API payload, so
   it is always correct when present. This is the safety net.
3. **The movie's 480p `mp4`**, for entries with no webm variant.

If Valve moves or removes microtrailers, step 1 simply stops matching and
step 2 takes over. No code change, no broken preview. That is the whole
reason it is a probe and not an assumption.

### 3.4 Caching

Two layers, memory over disk. Successes live **7 days** (a game's trailer
does not change); failures live **1 hour**, so an offline moment does not
poison the cache but a genuinely storeless game is not re-fetched on
every pass. Disk is capped at 600 entries, pruned oldest-first.

Native games key by `app:{appid}`. Shortcuts key by a hash of their
normalised **name**, not their appid — Unifideck's synthetic appids are
machine-local and change if a shortcut is recreated, but the name is what
we actually resolved against.

Duplicate in-flight requests for the same entry are coalesced, so
scrolling back onto a game mid-fetch does not fetch twice.

### 3.5 Failure contract

Every backend method returns a well-formed media object no matter what —
unparseable entry, upstream on fire, read-only filesystem. There is no
input that makes it raise. The `note` field carries why
(`no-confident-match`, `no-store-entry`, `resolve-error`), which the QAM
panel can surface for debugging. 306 tests cover this, at 94% coverage.

---

## 4. Risk register

| # | Risk | Likelihood | Mitigation |
| --- | --- | --- | --- |
| 1 | Microtrailer URL pattern is wrong or gone | Medium | Probed, never assumed; falls back to the API's own webm (§3.3) |
| 2 | `focusin` does not fire for gamepad nav | Medium | Nav-controller polling fallback (§2.4), then clean self-disable |
| 3 | Valve renames the props the fiber walk looks for | Low–Medium | Four candidate paths tried; all constants in one block in `focus.ts` |
| 4 | `addGlobalComponent` renders in the wrong window / wrong z-index | Low | `findSP()` anchors the window; z-index and position are ours |
| 5 | Steam rate-limits `storesearch` on a large shortcut library | Low | 3 concurrent max, 7-day cache, backoff honouring `Retry-After` |
| 6 | Video decode hurts battery | Medium | 480p max, muted, autoplay delay, teardown on blur, data-saver mode |
| 7 | Overlay covers UI the user needs | Low | Configurable corner + size, `pointer-events: none`, master toggle |
| 8 | A SteamOS update breaks the whole hook | Medium | Feature flag: overlay off, library and settings untouched (§2.5) |

---

## 5. Explicitly out of scope for V1

Noted as future work, not built: restyling the library grid; emulation /
ROM / ES-DE local media; per-game manual media overrides; custom themes
and animations. **No telemetry or analytics, ever** — the only hosts the
plugin contacts are `store.steampowered.com` and the `*.steamstatic.com`
CDNs, and only for the focused game's media.

---

## 6. Decisions I need from you

1. **The focus hook (§2).** Passive `focusin` + fiber walk, injected via
   `addGlobalComponent` with zero Valve patching. This is the one thing
   the brief asked me to get sign-off on.
2. **Match threshold 0.82.** Tuned to reject `Portal` → `Portal 2` and
   `GTA V` → `GTA IV`. Lowering it recovers more shortcuts but starts
   showing wrong trailers.
3. **Detail page too?** V1 as specified shows the overlay only while a
   *grid* entry is focused. Opening a game's page hides it. Say the word
   if you want it to persist there.
