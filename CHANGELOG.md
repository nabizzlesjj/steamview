# Changelog

All notable changes to this project are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/).

## [1.2.0] - 2026-08-25

Two features suggested by players after the 1.1.0 release.

### Added

- **Dynamic positioning** (off by default). The preview moves to the
  opposite side of the screen from the highlighted game, so it never
  covers what you are looking at. The vertical half stays wherever you
  put it -- that is taste, not occlusion. A dead band around the middle
  of the grid stops the card flicking side to side while you scroll
  along a row that straddles the centre.
- **Metadata language.** The title, description and genres under the
  preview can be shown in any of the 29 languages Steam's store
  supports. The default, **Match Steam**, asks the client what language
  it is set to and uses that, so it is correct without being configured;
  any language can also be picked explicitly.

### Changed

- Cached entries are keyed by language, so switching language takes
  effect on the next preview rather than when the old entry expires.
  English keys are unchanged, so upgrading does not invalidate a cache
  that is already warm.

## [1.1.0] - 2026-08-25

Game Mode is not only a Steam Deck. This release makes the overlay sit
correctly on a docked Deck and on desktop SteamOS or Bazzite at 1080p,
1440p and 4K, where it was previously sized for exactly one panel.

### Added

- The overlay now measures Steam's own library container and sizes
  itself against the pane it sits in, rather than against a fixed pixel
  count tuned on a 1280x800 handheld. On a Deck the card is unchanged to
  the pixel; on larger displays it grows with the grid, and its
  typography, padding and margins grow with it.
- Re-measurement on window resize, so docking and undocking a Deck --
  and any resolution change -- are picked up without a restart.
- A frontend test suite (`pnpm run test:fe`, `make test-fe`) covering the
  sizing arithmetic across Deck, 1080p, 1440p and 4K viewports. It uses
  node's own test runner over the compiled module, so it adds no
  dependency of any kind. This raises the development-time Node floor to
  20; the plugin itself is unaffected.

### Fixed

- On a pane narrower than the card's own minimum width, the card could
  overhang the grid. The pane now wins.

## [1.0.1] - 2026-08-24

### Security

- Artwork URLs from the Steam client are now restricted to http, https
  and client-local paths. `javascript:`, `data:`, `file:` and similar
  previously passed through to the `<img>` and `<video>` elements. A
  non-Steam shortcut's artwork is user-supplied data, so this is a real
  boundary rather than a formality.
- The unverified-TLS fallback is now scoped to `store.steampowered.com`
  and `*.steamstatic.com`. It was reachable for any host once armed;
  nothing else was ever fetched, but the downgrade should not travel
  with a URL some later change introduces. Lookalike hosts such as
  `steampowered.com.evil.net` are correctly refused.

### Added

- `SECURITY.md`: what the plugin can access, what it deliberately does
  not do, the TLS trade-off and its blast radius, and what is cached and
  logged locally.

### Fixed

- Install instructions covered Decky's side but not how the ZIP reaches
  the Deck, which is the step that actually blocks people.

## [1.0.0] - 2026-08-23

First stable release.

### Added

- Live media preview of the highlighted game in the SteamOS library:
  an auto-playing muted trailer, falling back to a screenshot reel and
  then to hero art, so the overlay is never blank and never broken.
- An info panel under the media carrying the game's title, genres and
  the first two lines of its store description. Each row is optional and
  the panel collapses to fit.
- Support for non-Steam shortcuts, including libraries imported by
  Unifideck. A shortcut's display name is resolved against the Steam
  store, with a deliberately strict confidence threshold so a near-miss
  shows the shortcut's own artwork rather than the wrong game's trailer.
- Python backend resolver with a two-layer cache (memory over disk),
  separate TTLs for successes and failures, size-capped and pruned
  oldest-first. Standard library only — no third-party dependencies.
- Quick Access Menu panel: master enable, preview mode, preview delay,
  autoplay delay, muted, loop, overlay position and size, data saver,
  and clear cache. All persisted and validated on load.
- Focus detection via a passive `focusin` listener and a React fiber
  walk, injected with `routerHook.addGlobalComponent` so no Steam
  component is patched. It disables only itself on failure, leaving the
  library and the rest of the plugin untouched.
- i18next scaffolding with an English base locale.
- GitHub Actions CI (typecheck, lint, build, pytest on 3.11 and 3.12)
  and a release workflow that publishes the installable plugin ZIP.
- `THIRD_PARTY_LICENSES.md`, generated from the installed packages and
  shipped inside the plugin ZIP.

[1.0.1]: https://github.com/nabizzlesjj/steamview/releases/tag/v1.0.1
[1.0.0]: https://github.com/nabizzlesjj/steamview/releases/tag/v1.0.0
