# SteamView

A [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader)
plugin for SteamOS Game Mode that shows a **live media preview of the
game you're currently highlighting** in your Steam library — an
auto-playing trailer, falling back to a screenshot reel, falling back to
hero art. Scroll your library and see what each game actually looks like
without opening its store page.

It works for **native Steam games** and for **non-Steam shortcuts**,
including libraries imported by [Unifideck](https://github.com/mubaraknumann/unifideck)
(Epic, GOG, Amazon, Ubisoft, Xbox Cloud).

> **This plugin reads Steam's internal UI to know which game you are
> highlighting.** That interface is undocumented and changes without
> notice, so a SteamOS update can break the preview and require a plugin
> update. It is built so that when that happens, **only the preview
> switches off** — the plugin's settings keep working and your Steam
> library is never modified or blocked. See
> [DESIGN.md](DESIGN.md#25-the-feature-flag-and-kill-safety).

---

## What it does

As focus moves between games in the library grid, SteamView resolves
media for the highlighted entry and plays it in a small fixed overlay:

1. **Trailer** — Steam's ~6 second silent microtrailer where available,
   otherwise the game's 480p trailer, muted and looping.
2. **Screenshots** — a slow carousel, when there is no usable video.
3. **Hero art** — the capsule or hero image the client already has.

The preview appears only over the library grid. Opening a game's page
hides it, since Steam already fills that screen with the game's own
artwork and details.

Under the media sits an info panel with the game's **title**, its
**genres**, and the first two lines of the **store description**. Each
row is optional and the panel collapses to fit, so a shortcut with no
store match still gets a labelled preview instead of an anonymous video.

It never shows a blank box, and a failure at any step falls through to
the next.

### Native Steam games

Media comes straight from Steam's public store API for the game's appid.

### Non-Steam shortcuts

A shortcut has no store appid, only a display name. SteamView searches
the Steam store for that name — stripping launcher decorations like
`(Epic)` and edition suffixes like `Deluxe Edition` along the way — and
uses the match's trailer if, and only if, it is confident the two are the
same game. Most multi-store titles are also on Steam, so this recovers a
real trailer for the majority of an imported library. When nothing
matches confidently it falls back to the artwork already applied to the
shortcut (SteamGridDB hero art, for a Unifideck library).

The match threshold is deliberately strict: showing the wrong game's
trailer is worse than showing none.

---

## Install

> ### ⚠️ Do not install a source download
>
> **Cloning this repo, or using GitHub's green "Code → Download ZIP"
> button, will NOT give you an installable plugin.** Those contain the
> source but not `dist/index.js`, which is compiled output and is
> deliberately not committed.
>
> Decky will happily accept such a folder, list "SteamView" in the plugin
> menu, and then fail with:
>
> ```
> TypeError: Failed to fetch dynamically imported module:
> http://127.0.0.1:1337/plugins/SteamView/dist/index.js
> ```
>
> Install a **release ZIP** or one you built yourself (both below).

### From a release ZIP

1. Download the latest `SteamView-vX.Y.Z.zip` from
   [Releases](https://github.com/nabizzlesjj/steamview/releases) — the
   file attached to the release, *not* the "Source code" links.
2. On your Deck, open the Decky menu (the plug icon in the Quick Access
   Menu) → the **gear** icon → **Settings**.
3. Turn on **Developer Mode**.
4. Go to the **Developer** tab → **Install Plugin from ZIP File**.
5. Point it at the ZIP and confirm.

The overlay is on by default. Scroll your library and it should appear.

### Building the ZIP yourself

If there is no release yet, build one:

```bash
pnpm install
pnpm run build          # produces dist/index.js
python3 scripts/package.py --out-dir out
```

That writes `out/SteamView-vX.Y.Z.zip`, ready to install. The packaging
script refuses to run when `dist/index.js` is missing, so a ZIP it
produces is always complete.

`make deploy DECK_HOST=<your-deck-ip>` does the same over SSH, and also
builds first, so it cannot deploy an incomplete plugin.

### Requirements

- A Steam Deck (or SteamOS device) running Game Mode
- Decky Loader installed
- An internet connection the first time each game is previewed; after
  that its media is cached on disk

---

## Troubleshooting

### `TypeError: Failed to fetch dynamically imported module`

The installed plugin folder is missing `dist/index.js`. This almost
always means a source clone or GitHub "Download ZIP" was installed
instead of a built plugin. Decky still reads `plugin.json`, so the plugin
appears in the menu by name and only fails when its frontend is loaded.

Check on the Deck:

```bash
ls ~/homebrew/plugins/SteamView/dist/index.js
```

If that file is absent, uninstall the plugin and install a release ZIP,
or one built with the steps above.

### The plugin loads but no preview ever appears

Open the QAM panel. If it shows a **"Preview unavailable"** block, the
focus hook could not attach -- note the reason it gives and open an
issue. If there is no such block, check that **Enabled** is on and
**Preview mode** is not *Off*, then work through
[TESTING.md](TESTING.md).

---

## Settings

All settings live in the Quick Access Menu under **SteamView**, and
persist across restarts.

| Setting | Default | What it does |
| --- | --- | --- |
| **Enabled** | On | Master switch. Off removes the overlay entirely. |
| **Preview mode** | Trailer + screenshots | `Trailer + screenshots`, `Screenshots only`, or `Off`. |
| **Preview delay** | 300 ms | How long a game must stay highlighted before the preview appears. Applies in every mode. Lower values fetch more while scrolling. |
| **Autoplay delay** | 600 ms | Extra wait before the trailer starts, once the preview is showing. Trailer mode only. |
| **Muted** | On | Trailer audio. Leaving this on is strongly recommended — Steam's own UI sounds keep playing underneath. |
| **Loop** | On | Repeat the trailer while the game stays highlighted. |
| **Overlay position** | Bottom right | Which corner the preview sits in. |
| **Overlay size** | Medium | Small / Medium / Large. |
| **Data saver** | Off | Skip video entirely and show screenshots only. Saves bandwidth and battery. |
| **Clear cache** | — | Delete all cached media metadata. Use this if a game's preview looks wrong or stale. |

---

## Privacy and network use

SteamView contacts exactly two things, and only for the game you are
currently highlighting:

- `store.steampowered.com` — the public store API, for trailer and
  screenshot metadata
- `*.steamstatic.com` — Valve's CDNs, to play the media itself

**There is no telemetry and no analytics of any kind**, and none will be
added. Nothing about your library, your account, or your usage is sent
anywhere. All lookups are cached on-disk for seven days and debounced, so
scrolling quickly through a large library does not generate a request per
frame.

---

## Development

### Prerequisites

- Node 18+ and **pnpm 9** (`corepack enable && corepack prepare pnpm@9.15.9 --activate`)
- Python 3.11+ and `pytest` (the plugin backend itself has **no**
  dependencies — standard library only)

### Setup

```bash
pnpm install
```

### Everyday commands

| Command | What it does |
| --- | --- |
| `pnpm run build` | Build `dist/index.js` |
| `pnpm run watch` | Rebuild on change |
| `pnpm run typecheck` | `tsc --noEmit` |
| `pnpm run lint` | ESLint over `src/` |
| `pytest` | Backend test suite |
| `make check` | Everything CI runs |
| `make package` | Build the installable ZIP into `out/` |

### Deploying to a Deck

`make deploy` rsyncs the built plugin over SSH and restarts the loader.
Nothing about your device is committed — it is all environment
variables:

```bash
make deploy DECK_HOST=192.168.1.42
```

| Variable | Default | |
| --- | --- | --- |
| `DECK_HOST` | `steamdeck` | Hostname or IP |
| `DECK_USER` | `deck` | SSH user |
| `DECK_PORT` | `22` | SSH port |
| `DECK_PLUGIN_DIR` | `/home/$(DECK_USER)/homebrew/plugins` | Where Decky keeps plugins |

This needs `sshd` running on the Deck and a password set (`passwd` in
Desktop Mode). `make logs` tails the plugin log; `make restart` restarts
the loader on its own.

### Testing

The backend resolver — entry classification, appdetails parsing, trailer
URL derivation, name-to-appid ranking, cache TTL and eviction, and every
failure path — is covered by `pytest` with all network mocked, so it is
verifiable without a Deck. For everything that genuinely needs hardware,
[TESTING.md](TESTING.md) is a step-by-step on-device plan.

### Project layout

```
main.py               decky lifecycle + RPC surface (thin)
py_modules/steamview/ all backend logic, unit tested
  entries.py            native vs shortcut classification
  matching.py           name normalisation and match ranking
  steamstore.py         the two store endpoints
  media.py              appdetails -> media object
  cache.py              memory + disk TTL cache
  resolver.py           Path A / Path B orchestration
src/                  frontend
  steam/focus.ts        THE Steam-coupled module -- start here after a SteamOS update
  components/           overlay and settings UI
tests/                pytest suite
scripts/              packaging and CI guards
```

[DESIGN.md](DESIGN.md) documents the focus-detection approach, what was
verified against live sources versus assumed, and the risk register.

---

## Not in scope

Deliberately left out of V1: restyling the library grid, emulation / ROM
/ ES-DE local media integration, per-game manual media overrides, and
custom themes or animations.

---

## Cutting a release

Releases are built by CI and attached to a GitHub Release, so the ZIP
users download is always a clean, verified build.

**Before tagging**, bump the version and record the change:

1. Set `"version"` in `package.json` (this names the ZIP).
2. Add a dated section to [CHANGELOG.md](CHANGELOG.md).
3. Commit and push to `main`.

Then publish, either way:

**From the Actions tab** (no local clone needed)

1. Go to **Actions → Release → Run workflow**.
2. Enter the tag, e.g. `v0.1.0`.
3. Run it. The workflow creates the tag, builds, and publishes the
   release with the ZIP attached.

**From a terminal**

```bash
git checkout main && git pull
git tag -a v0.1.0 -m "SteamView v0.1.0"
git push origin v0.1.0
```

Either path runs the same checks (typecheck, lint, pytest) before
building, and refuses to publish if the tag does not match
`package.json`'s version — so a release can never ship a ZIP whose
filename disagrees with its tag.

The published asset is `SteamView-vX.Y.Z.zip`, which is the file to
install on a Deck.

---

## Contributing

**This repository does not accept pull requests** — it is a personal
project. You are entirely welcome to fork it and do whatever you like;
the licence is permissive and your fork is yours. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

BSD-3-Clause. See [LICENSE](LICENSE).

The plugin ships one bundled JavaScript file which inlines a few
dependencies; their notices are reproduced in
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md), generated from the
installed packages by `make licenses`.

Built on the
[Decky plugin template](https://github.com/SteamDeckHomebrew/decky-plugin-template),
whose original copyright notice is retained in `LICENSE`.
