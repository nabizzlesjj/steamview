# Changelog

All notable changes to this project are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/).

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

[Unreleased]: https://github.com/nabizzlesjj/steamview/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/nabizzlesjj/steamview/releases/tag/v0.1.2
[0.1.1]: https://github.com/nabizzlesjj/steamview/releases/tag/v0.1.1
[0.1.0]: https://github.com/nabizzlesjj/steamview/releases/tag/v0.1.0
