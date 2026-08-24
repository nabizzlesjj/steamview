# SteamView

**See what a game actually looks like, without opening its store page.**

A [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin
for SteamOS Game Mode. As you scroll your library, SteamView plays a
muted trailer for whatever game is highlighted, in a small card in the
corner — with the game's genres and a couple of lines of its description
underneath.

It works for native Steam games and for non-Steam shortcuts, including
libraries imported by [Unifideck](https://github.com/mubaraknumann/unifideck)
(Epic, GOG, Amazon, Ubisoft, Xbox Cloud).

---

## What it does

Highlight a game. After a moment, a preview appears:

1. **Trailer** — Steam's ~6 second silent microtrailer where one exists,
   otherwise the game's 480p trailer. Muted and looping.
2. **Screenshots** — a slow crossfading reel, when there's no usable
   video.
3. **Hero art** — the capsule the client already has.

Each step falls through to the next, so the card is never blank and never
broken. Beneath the media sits the game's **title**, **genres** and the
first two lines of its **store description** — each row optional, so a
shortcut with no store match still gets a labelled preview rather than an
anonymous video.

The preview covers only the library grid. Opening a game's page hides it,
since Steam already fills that screen with the game's own artwork.

### Non-Steam shortcuts

A shortcut has no store appid, only a name. SteamView searches the Steam
store for it — stripping launcher decorations like `(Epic)` and edition
suffixes like `Deluxe Edition` along the way — and uses the match only if
it's confident the two are the same game. Most multi-store titles are
also on Steam, so this recovers a real trailer for the majority of an
imported library.

The threshold is deliberately strict. Showing the wrong game's trailer is
worse than showing none, so a near-miss falls back to the artwork already
on the shortcut.

---

## Install

1. Download **`SteamView-vX.Y.Z.zip`** from
   [Releases](https://github.com/nabizzlesjj/steamview/releases) — the
   attached asset, not the "Source code" links.
2. On your Deck: Quick Access Menu → the **plug** icon → **gear** →
   **Settings** → turn on **Developer Mode**.
3. **Developer** tab → **Install Plugin from ZIP File** → pick the ZIP.

The preview is on by default. Scroll your library and it should appear.

> A git clone or GitHub's "Download ZIP" will **not** work — neither
> contains the compiled `dist/index.js`. Use a release asset, or build
> one yourself (see [Development](#development)).

**Requirements:** a Steam Deck or SteamOS device in Game Mode, Decky
Loader, and an internet connection the first time each game is previewed.
After that its media is cached on disk.

---

## Settings

All settings live in the Quick Access Menu under **SteamView**, and
persist across restarts.

| Setting | Default | What it does |
| --- | --- | --- |
| **Enabled** | On | Master switch. |
| **Preview mode** | Trailer + screenshots | `Trailer + screenshots`, `Screenshots only`, or `Off`. |
| **Preview delay** | 300 ms | How long a game must stay highlighted before the preview appears. Applies in every mode. Lower values fetch more while scrolling. |
| **Autoplay delay** | 600 ms | Extra wait before the trailer starts, once the preview is showing. Trailer mode only. |
| **Muted** | On | Recommended — Steam's own UI sounds keep playing underneath. |
| **Loop** | On | Repeat the trailer while the game stays highlighted. |
| **Overlay position** | Bottom right | Which corner the card sits in. |
| **Overlay size** | Medium | Small / Medium / Large. |
| **Data saver** | Off | Skip video entirely; screenshots only. |
| **Clear cache** | — | Delete cached media metadata. Use if a preview looks wrong or stale. |

---

## Privacy

SteamView contacts exactly two things, and only for the game you're
currently highlighting:

- `store.steampowered.com` — the public store API, for trailer and
  screenshot metadata
- `*.steamstatic.com` — Valve's CDNs, to play the media

**There is no telemetry and no analytics**, and none will be added.
Nothing about your library, your account or your usage is sent anywhere.
Lookups are cached on disk for seven days and debounced, so scrolling a
large library doesn't generate a request per frame.

One caveat worth stating plainly: SteamOS ships an outdated certificate
bundle, and TLS verification fails inside the Decky plugin process.
SteamView tries verification first and falls back to an unverified
connection **only** after a genuine certificate error. What travels over
it is public game metadata — no credentials, nothing user-identifying.

---

## Development

**Prerequisites:** Node 18+ and pnpm 9
(`corepack enable && corepack prepare pnpm@9.15.9 --activate`); Python
3.11+ and `pytest`. The plugin backend itself has **no** dependencies —
standard library only.

```bash
pnpm install
```

| Command | What it does |
| --- | --- |
| `pnpm run build` | Build `dist/index.js` |
| `pnpm run watch` | Rebuild on change |
| `pnpm run typecheck` | `tsc --noEmit` |
| `pnpm run lint` | ESLint over `src/` |
| `pytest` | Backend test suite (362 tests) |
| `make check` | Everything CI runs |
| `make package` | Build the installable ZIP into `out/` |
| `make licenses` | Regenerate `THIRD_PARTY_LICENSES.md` |

### Deploying to a Deck

`make deploy` builds, rsyncs over SSH and restarts the loader. Nothing
device-specific is committed — it's all environment variables:

```bash
make deploy DECK_HOST=192.168.1.42
```

| Variable | Default |
| --- | --- |
| `DECK_HOST` | `steamdeck` |
| `DECK_USER` | `deck` |
| `DECK_PORT` | `22` |
| `DECK_PLUGIN_DIR` | `/home/$(DECK_USER)/homebrew/plugins` |

Needs `sshd` running on the Deck and a password set (`passwd` in Desktop
Mode). `make logs` tails the plugin log; `make restart` restarts the
loader alone.

### Layout

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
  steam/bindings.ts     everything Steam-specific -- start here after a SteamOS update
  steam/focus.ts        the focus listener and its failure policy
  components/           overlay and settings UI
tests/                pytest suite
```

[ARCHITECTURE.md](ARCHITECTURE.md) explains the focus hook, the media
resolver and the risk register. [TESTING.md](TESTING.md) is a manual
on-device test plan, for the parts no unit test can reach.

### Releasing

Bump `"version"` in `package.json`, add a `CHANGELOG.md` entry, push to
`main`, then **Actions → Release → Run workflow** with the tag (e.g.
`v1.1.0`). The workflow refuses to publish if the tag and `package.json`
disagree.

---

## A note on stability

This plugin reads Steam's internal UI to know which game you're
highlighting. That interface is undocumented and changes without notice,
so a SteamOS update can break the preview and require a plugin update.

It's built so that when that happens, **only the preview switches off**.
The settings panel keeps working, says what went wrong, and your Steam
library is never modified or blocked.

---

## Not in scope

Restyling the library grid, emulation / ROM / ES-DE local media
integration, per-game manual media overrides, and custom themes or
animations.

---

## Troubleshooting

**`TypeError: Failed to fetch dynamically imported module`** — the
installed folder is missing `dist/index.js`, which almost always means a
source clone was installed instead of a built plugin. Check with
`ls ~/homebrew/plugins/SteamView/dist/index.js`; if it's absent,
reinstall from a release asset.

**The plugin loads but no preview appears** — open the QAM panel. A
**"Preview unavailable"** block means the focus hook couldn't attach,
most likely because a SteamOS update changed the library UI. Otherwise
check that **Enabled** is on and **Preview mode** isn't *Off*.

**A preview looks wrong or stale** — use **Clear cache**. Media is cached
for seven days.

Logs live at `~/homebrew/logs/SteamView/plugin.log`, one line per
resolution.

---

## Contributing

**This repository does not accept pull requests** — it's a personal
project. You're entirely welcome to fork it and do whatever you like; the
licence is permissive and your fork is yours. See
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

BSD-3-Clause. See [LICENSE](LICENSE).

The plugin ships one bundled JavaScript file which inlines a few
dependencies; their notices are in
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

Built on the
[Decky plugin template](https://github.com/SteamDeckHomebrew/decky-plugin-template),
whose original copyright notice is retained in `LICENSE`.
