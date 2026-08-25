# Security

SteamView runs inside Decky Loader on your SteamOS device. This document
states what it can reach, what it deliberately does not do, and the one
place it makes a security trade-off you should know about.

## What it can access

| | |
| --- | --- |
| **Privileges** | Runs as the `deck` user. `plugin.json` declares no flags, so it does **not** request root. |
| **Filesystem writes** | Two, both atomic temp-file writes, both confined to Decky's own directories: `DECKY_PLUGIN_SETTINGS_DIR` (settings) and `DECKY_PLUGIN_RUNTIME_DIR` (media cache). Nothing else on disk is written. |
| **Filesystem reads** | Its own settings and cache. |
| **Process execution** | None. No `subprocess`, no `os.system`, no shell. |
| **Dynamic code** | None. No `eval`, no `exec`, no `pickle`, no `innerHTML`, no `dangerouslySetInnerHTML`. |
| **Steam data read** | Game name, appid and artwork URL of whichever library entry is highlighted, via Steam's in-client `appStore`; the client's UI language, via `SteamClient.Settings.GetCurrentLanguage()`. |
| **Network** | `store.steampowered.com` and `*.steamstatic.com`. Nothing else. |

The backend is Python standard library only — no third-party runtime
dependencies, so there is no Python supply chain to audit. The frontend
bundles four packages, listed with their licences in
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## What it does not do

- **No telemetry, no analytics, no crash reporting.** Nothing about your
  library, account or usage leaves the device.
- **No account access.** It never reads your Steam credentials, session,
  friends list, or anything requiring authentication. The store endpoints
  it calls are public and anonymous.
- **No writes to your Steam library.** It reads which game is
  highlighted; it never modifies games, shortcuts, artwork or collections.
- **No auto-update.** It fetches media only. It never downloads or
  executes code.

## The one trade-off: TLS verification

**SteamOS ships an outdated CA bundle, and certificate verification fails
inside the Decky plugin process.** Without handling this, every media
lookup fails and the plugin silently shows box art for everything. Other
plugins hit the same wall — [Unifideck documents it](https://github.com/mubaraknumann/unifideck)
in its own Steam client.

How SteamView handles it:

1. Full verification is **always attempted first**.
2. The fallback engages **only** after a genuine certificate error —
   never a timeout, DNS failure or HTTP status.
3. The fallback is **restricted to `store.steampowered.com` and
   `*.steamstatic.com`**. Any other host keeps full verification and
   fails closed.
4. It logs a warning **once** when it engages, and remembers the decision
   for that session only.

**What an attacker positioned to intercept your traffic could do:** serve
fake responses from those Steam hosts, causing the overlay to display the
wrong trailer, wrong screenshots or wrong description. That is the whole
blast radius. Nothing is executed, no credentials are involved, no file
is written outside the cache, and nothing is uploaded.

If you would rather not accept that, set **Preview mode → Off** or
uninstall. There is currently no setting to make it fail closed instead;
if that would be useful, it is a reasonable thing to add.

## Data handling

- **Cached on disk:** trailer/screenshot URLs, game titles, genres and
  store descriptions, under `DECKY_PLUGIN_RUNTIME_DIR`. Successes expire
  after 7 days, failures after 1 hour, and the cache is capped at 600
  entries. **Clear cache** in the settings panel deletes all of it, and
  uninstalling removes it.
- **Logged locally:** one line per resolution, including the game's name,
  to `~/homebrew/logs/SteamView/plugin.log`. This is a local file that is
  never transmitted, but it does mean the log reflects which games you
  browsed. Decky rotates it.
- **Sent off-device:** the appid, or the display name of a non-Steam
  shortcut, to Steam's public store API — the same request your browser
  makes visiting a store page. Since 1.2.0 the request also carries a
  **language code** (`l=brazilian`, say), which is either the language
  you picked or the one Steam is already set to. It is one of 29 fixed
  values, it is exactly what your browser sends when you view a store
  page in that language, and no identifiers accompany either.

## Reporting a vulnerability

Open an issue if issues are enabled, or contact the repository owner
through GitHub. This is a hobby project maintained by one person: there
is no SLA, and no bounty. Please describe the impact concretely so it can
be assessed and reproduced.

If a report is credible and I cannot fix it promptly, I will say so in
the README rather than leave it silent.

## Auditing it yourself

The plugin is small and the interesting parts are short:

```
py_modules/steamview/http.py       all network I/O, including the TLS fallback
py_modules/steamview/steamstore.py the only two endpoints called
py_modules/steamview/media.py      URL sanitisation before anything reaches the DOM
main.py                            the entire RPC surface the frontend can call
```

The shipped `dist/index.js` is a build artifact. To confirm it matches
the source, build it yourself with `pnpm install && pnpm run build`;
`make package` reproduces the release ZIP.
