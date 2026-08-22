# Changelog

All notable changes to this project are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.5] - 2026-08-22

### Fixed

- **The preview stayed on screen after opening a game.** It now hides on
  a game's detail page, where Steam already shows the game's own hero
  art, playtime and Play button and the overlay simply covered them.
  Detected by two independent signals -- the detail-page container
  classes and the `/library/app/` route -- so either going stale still
  leaves the other working.

## [0.1.4] - 2026-08-22

### Fixed

- **The preview covered Steam's own navigation bars.** The overlay is
  now bounded by the library pane itself -- its host is inset past the
  search field and collection tabs at the top and the button-hint bar at
  the bottom -- rather than by the whole screen, so it can only ever
  cover the game grid.
- The card is clamped to the pane height. That is a real constraint, not
  insurance: Game Mode renders its UI zoomed, so a Deck's 1280x800 panel
  is roughly an 870x545 CSS viewport, leaving a library pane only ~380px
  tall against a 377px Large card. When the clamp binds the media gives
  way and the text stays intact.

## [0.1.3] - 2026-08-22

### Fixed

- **The bottom of the info panel was cut off.** `position: fixed`
  resolves against the nearest ancestor carrying a transform, and
  Steam's content region is transformed for its page transitions, so the
  card was being positioned inside -- and clipped by -- that region
  rather than the viewport. The overlay now renders into its own host
  appended to the window body, which puts it back on the viewport. It
  also keeps clear of the collection tabs and the button-hint bar, which
  it would otherwise have covered once it escaped.

### Added

- **Preview delay** setting: how long a game must stay highlighted
  before the preview appears. Applies in every mode, so screenshots-only
  is now adjustable too; previously the only delay control gated video
  and was greyed out unless trailers were on.

### Changed

- Autoplay delay is now explicitly the *extra* wait before the trailer
  starts once the preview is up, rather than the only timing control.

## [0.1.2] - 2026-08-22

### Added

- The preview is now a bordered card with an info panel under the media,
  showing the game's title, its genres, and the first two lines of the
  Steam store description. Every row is optional and the panel collapses
  to fit, so a non-Steam shortcut with no store match gets a labelled
  preview rather than an anonymous video.
- Type and padding scale with the overlay size setting, so Small stays
  legible rather than just smaller.

### Changed

- The title moved out of the gradient strip over the media and into the
  info panel, where it no longer covers the picture.

## [0.1.1] - 2026-08-22

### Fixed

- **Every game showed only box art, never a trailer or screenshots.**
  SteamOS ships an outdated CA bundle, and certificate verification
  fails inside the Decky plugin process, so every request to Steam's
  store API failed and both resolution paths fell through to artwork.
  Verification is still attempted first; the plugin now falls back to an
  unverified connection only after a genuine certificate error, logs
  that once, and remembers it for the session. Only Steam's public store
  and CDN endpoints are involved -- no credentials or personal data are
  ever sent.

### Added

- One info-level log line per resolution recording the source, resolved
  appid, trailer kind and screenshot count, so an unexpected preview can
  be diagnosed from the plugin log alone.

## [0.1.0] - 2026-08-22

First release.

### Added

- Preview overlay showing the highlighted game's trailer, falling back
  to a screenshot reel and then to hero art. Visible on the library grid
  and on a game's detail page.
- Focus detection via a passive `focusin` listener and a React fiber
  walk, injected with `routerHook.addGlobalComponent` so no Steam
  component is patched. It disables only itself on failure, leaving the
  library and the rest of the plugin untouched.
- Quick Access Menu panel: master enable, preview mode, autoplay delay,
  muted, loop, overlay position and size, data saver, and clear cache.
- i18next scaffolding with an English base locale.
- Backend media resolver: `appdetails` for native Steam games, and
  `storesearch` name matching for non-Steam shortcuts, with a
  conservative confidence threshold so a near-miss shows the shortcut's
  own artwork rather than the wrong game's trailer.
- Two-layer media cache (memory over disk) with separate TTLs for
  successes and failures, size-capped and pruned oldest-first.
- Persisted settings with validation, so a hand-edited or older settings
  file can never produce a broken UI.
- GitHub Actions CI (typecheck, lint, build, pytest on 3.11 and 3.12)
  and a tag-triggered release workflow that publishes the plugin ZIP.
- A CI guard asserting the backend imports nothing outside the standard
  library, which is what keeps packaging free of Docker.

[Unreleased]: https://github.com/nabizzlesjj/steamview/compare/v0.1.5...HEAD
[0.1.5]: https://github.com/nabizzlesjj/steamview/releases/tag/v0.1.5
[0.1.4]: https://github.com/nabizzlesjj/steamview/releases/tag/v0.1.4
[0.1.3]: https://github.com/nabizzlesjj/steamview/releases/tag/v0.1.3
[0.1.2]: https://github.com/nabizzlesjj/steamview/releases/tag/v0.1.2
[0.1.1]: https://github.com/nabizzlesjj/steamview/releases/tag/v0.1.1
[0.1.0]: https://github.com/nabizzlesjj/steamview/releases/tag/v0.1.0
