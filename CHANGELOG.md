# Changelog

All notable changes to this project are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/).

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

[1.0.0]: https://github.com/nabizzlesjj/steamview/releases/tag/v1.0.0
