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

It measures the library pane rather than assuming one, so it sits
correctly on a Steam Deck, on a docked Deck, and on desktop Game Mode —
Bazzite or plain SteamOS — at 1080p, 1440p or 4K. The card grows with the
grid, and its text grows with the card.

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

You need [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader)
already installed. SteamView is not on the Decky store, so it's a manual
ZIP install — which means getting the file onto the Deck first.

### 1. Download the ZIP (Desktop Mode)

Game Mode has no practical way to download a file, so switch over:

1. Press **STEAM** → **Power** → **Switch to Desktop**.
2. Open a browser and go to
   [Releases](https://github.com/nabizzlesjj/steamview/releases).
3. Download **`SteamView-vX.Y.Z.zip`** — the attached asset under
   **Assets**, *not* the "Source code (zip)" link beneath it. It lands in
   `/home/deck/Downloads`.
4. Double-click **Return to Gaming Mode** on the desktop.

> The "Source code" links will **not** work. They contain the source but
> not the compiled `dist/index.js`, so Decky will list the plugin and
> then fail to load it. Only the `SteamView-vX.Y.Z.zip` asset is
> installable.

### 2. Install it (Game Mode)

1. Press the **···** (Quick Access) button.
2. Open the **plug** icon — that's Decky.
3. Press the **gear** icon at the top of the Decky panel.
4. Under **General**, turn on **Developer mode**.
5. A **Developer** tab appears in the left-hand list. Open it.
6. Under **Third-Party Plugins** → **Install Plugin from ZIP File**,
   press **Browse**.
7. Navigate to `/home/deck/Downloads`, select the ZIP, then press
   **Install**.

### 3. Use it

Press **···** → the **plug** icon. **SteamView** is now in the plugin
list; open it to reach the settings.

The preview is on by default — go to your library, highlight a game, and
it should appear within a second.

> **Shortcut worth trying:** the same Developer tab has an **Install
> Plugin from URL** field. Pasting a release asset's direct download URL
> there should skip the Desktop Mode trip entirely. I haven't verified
> it, so the route above is the one I know works.

**Requirements:** any device running SteamOS Game Mode — a Steam Deck,
docked or handheld, or a desktop running SteamOS or Bazzite at any
resolution — plus Decky Loader and an internet connection the first time
each game is previewed. After that its media is cached on disk.

### Updating

Same steps — installing a newer ZIP over the top replaces the old
version. Your settings are kept.

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

It requests **no root privileges**, executes no processes, and writes
only to its own settings and cache directories.

One caveat worth stating plainly: SteamOS ships an outdated certificate
bundle, and TLS verification fails inside the Decky plugin process.
SteamView attempts verification first and falls back to an unverified
connection **only** after a genuine certificate error, and **only for
Steam's own hosts** — anything else keeps full verification and fails
closed. [SECURITY.md](SECURITY.md) explains the trade-off, what an
attacker could and couldn't do with it, and exactly what is cached and
logged.

---

## Development

**Prerequisites:** Node 20+ and pnpm 9
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
| `pnpm run test:fe` | Overlay sizing tests, across Deck / 1080p / 1440p / 4K |
| `pytest` | Backend test suite (392 tests) |
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
  overlayGeometry.ts    display-independent card sizing, pure and testable
  components/           overlay and settings UI
tests/                pytest suite
  frontend/             overlay sizing tests (node's own runner, no framework)
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
installed folder is missing `dist/index.js`, which almost always means
the "Source code (zip)" link was installed instead of the release asset.
Check with `ls ~/homebrew/plugins/SteamView/dist/index.js`; if it's
absent, reinstall using the `SteamView-vX.Y.Z.zip` asset.

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
