# On-device test plan

Everything that can be verified without hardware already is: the backend
resolver has 439 `pytest` cases with all network mocked, the overlay's
sizing and placement are tested across Deck, 1080p, 1440p and 4K
viewports,
and the frontend typechecks, lints and builds clean in CI. What none of
that can prove is whether the focus hook actually fires on a real Deck,
whether the microtrailer URL exists, and whether the pane Steam actually
renders matches the one the plugin measures.

That is what this document is for. It should take about 30 minutes, or a
little longer if you have a display other than the Deck's to try.

**Two things are genuinely unverified** and deserve your attention first,
because everything else degrades gracefully around them:

| | What to watch |
| --- | --- |
| **Does the focus hook fire at all?** | [Test 2](#test-2-native-steam-game). If it does not, nothing else in this document will pass. |
| **Does the microtrailer URL resolve?** | [Test 3](#test-3-confirm-or-refute-the-microtrailer-url). This is the one URL in the codebase that is a hypothesis rather than a fact. |

---

## Setup

### Install

> **Do not install a git clone or a GitHub "Download ZIP".** Neither
> contains `dist/index.js` (it is compiled output and is not committed),
> and Decky will list the plugin and then fail with `TypeError: Failed to
> fetch dynamically imported module`. Always install a *built* ZIP.

```
make package
```

Get the resulting `out/SteamView-vX.Y.Z.zip` onto the Deck (Desktop Mode
download, `scp`, or a USB stick — it needs to land somewhere the file
picker can reach, e.g. `/home/deck/Downloads`). Then in Game Mode:

1. **···** → the **plug** icon (Decky) → the **gear** icon
2. **General** → turn on **Developer mode**
3. The **Developer** tab → **Third-Party Plugins** → **Install Plugin
   from ZIP File** → **Browse** → pick the ZIP → **Install**

Or, if you have SSH set up:

```
make deploy DECK_HOST=<your-deck-ip>
```

### Get at the logs

**Backend** (Python — resolution, caching, HTTP):

```
make logs DECK_HOST=<your-deck-ip>
# or, on the Deck itself:
tail -f ~/homebrew/logs/SteamView/plugin.log
```

**Frontend** (the focus hook and the overlay): open
`http://<deck-ip>:8080` in a desktop browser with CEF remote debugging
enabled, pick the **SharedJSContext** target, and open its Console. Every
message from the focus hook is prefixed `[SteamView:focus]`; everything
else is `[SteamView]`.

Keep both open for the first run. Most failures announce themselves.

---

## Test 1: the plugin loads

1. Open the Quick Access Menu → the plug icon.
2. **SteamView** is in the plugin list with a photo/video icon.
3. Open it. You see a **Preview** section with eight controls and a
   **Cache** section with a Clear cache button.

**Backend log should contain:** `SteamView backend ready (cache: …)`

> ❗ **If a red "Preview unavailable" block appears at the top of the
> panel**, the focus hook did not start. That is the headline failure —
> note the reason it gives and the frontend console output, and stop
> here. Everything below depends on it.

---

## Test 2: native Steam game

Pick an installed, popular game with a trailer — Hades, Cyberpunk 2077,
Elden Ring.

1. Go to **Library** → **Great on Deck** or **All Games**.
2. Highlight the game with the D-pad or stick. **Do not press A.**
3. Wait about a second.

**Expect:** a preview appears in the bottom-right corner. It shows the
game's trailer, muted and looping, with the game's name captioned along
the bottom.

**Backend log:** a `store.steampowered.com` fetch for that appid on the
first view, and nothing on subsequent views (it is cached).

| If instead you see… | It means |
| --- | --- |
| Nothing at all | The focus hook is not firing. Check the frontend console for `[SteamView:focus]`. |
| Screenshots, not video | No usable trailer was found, or Data saver is on. Check `trailer_url` in the log. |
| A single static image | Neither video nor screenshots resolved; this is hero art. Check the `note` field in the log. |
| The wrong game | The fiber walk found the wrong ancestor. Note the game and the log line. |

### Now check the detail page

Press **A** to open the game's page. **Expect:** the preview
**disappears** — Steam already fills that screen with the game's own
artwork, playtime and Play button. Press **B** to go back and it returns,
following the highlight again.

---

## Test 3: confirm or refute the microtrailer URL

This is the one thing the code guesses at. Valve does not publish the
microtrailer URL, so the backend *probes* for it and falls back to the
trailer the API does publish.

With the backend log open, highlight a native game you have not viewed
before and look for a line mentioning `microtrailer`.

- **`trailer_kind: "microtrailer"`** — the hypothesis holds. Previews
  are ~6 second silent loops, which is the ideal behaviour.
- **`trailer_kind: "webm"`** — the probe failed and the fallback took
  over. **This is a working outcome, not a bug**: you get the full
  trailer instead of the short loop. If this happens on most games the
  probe is not earning its request and can be dropped.

Either way the preview plays. There is no failure mode here, only a
better and a worse one.

---

## Test 4: Unifideck / non-Steam shortcut

This is Path B, and it has two correct outcomes.

### 4a — a game that also exists on Steam

Highlight an imported title that is also sold on Steam (Cyberpunk 2077
from Epic, Control from Ubisoft, most GOG catalogue titles).

**Expect:** a real trailer, exactly as for a native game. The backend
searched the Steam store for the shortcut's name and found it.

**Backend log:** `'Cyberpunk 2077 (Epic)' -> 1091500 ('Cyberpunk 2077', score 1.000)`

### 4b — a game with no Steam presence

Highlight something Steam-exclusive-to-elsewhere, or with an unusual
name.

**Expect:** the shortcut's own artwork — the SteamGridDB hero Unifideck
applied. **This is the correct result, not a failure.**

**Backend log:** `no confident store match for 'Whatever The Name Is'`

> ⚠️ **The failure to watch for here is the *wrong* trailer.** The
> matcher is tuned to refuse anything below 0.82 similarity precisely to
> avoid this. If you ever see a preview for a different game than the one
> highlighted, that is the most important failure in this document. Note
> the shortcut's exact display name; the threshold in `matching.py` is
> the dial to turn.

Worth spot-checking a franchise: highlight a shortcut for *Portal* or
*Grand Theft Auto V* if you have one, and confirm you do not get *Portal
2* or *GTA IV*.

---

## Test 5: the fallback ladder

Verify each rung is reachable.

| Rung | How to force it | Expect |
| --- | --- | --- |
| Trailer | Preview mode = *Trailer + screenshots*, Data saver off | Video plays |
| Screenshots | Preview mode = **Screenshots only** | Crossfading stills, ~3.5s each |
| Hero art | Highlight a shortcut with no Steam match (Test 4b) | One static image |
| Nothing | Preview mode = **Off** | No overlay at all |

Then force a demotion: turn **Airplane mode** on, use **Clear cache**,
and highlight a game you have not viewed. **Expect** no overlay and no
error — not a black box, not a spinner, not a crash. Turn networking back
on and the preview returns.

---

## Test 6: scroll spam

The one that matters for battery and network.

1. Go to a library view with many games.
2. Hold the D-pad and scroll **hard** through 30-40 games without pausing.
3. Watch the backend log while you do.

**Expect:**

- **No video starts** while you are moving. Decoding should only begin
  once you stop.
- The log shows **far fewer** fetches than games scrolled past — focus
  has to settle for 300 ms before anything is requested.
- No more than **3** concurrent requests at any moment.
- When you stop, the preview shows **the game you stopped on** — never a
  game you scrolled past. This is the stale-response guard; if you ever
  see the wrong game after a fast scroll, that is a real bug.
- The UI never stutters. The library must feel exactly as it does with
  the plugin disabled.

Now scroll fast **back and forth** over the same few games. The log
should show no new fetches at all — they are cached, and duplicate
in-flight requests are coalesced.

---

## Test 7: every setting works and persists

Change each one, confirm the effect, then **fully restart Steam**
(Steam menu → Restart Steam) and confirm the setting survived.

| Setting | What to check |
| --- | --- |
| **Enabled** → off | Overlay disappears immediately. Library still perfect. |
| **Preview mode** | All three modes behave as in Test 5 |
| **Autoplay delay** → 3000 ms | Highlight a game: art first, video only after ~3s |
| **Autoplay delay** → 0 ms | Video starts as soon as the debounce settles |
| **Muted** → off | Audio plays *over* Steam's UI sounds. Turn it back on. |
| **Loop** → off | Trailer plays once and stops on its last frame |
| **Position** | Preview moves to each of the four corners |
| **Size** | Small / Medium / Large visibly differ |
| **Data saver** → on | No video in any mode; screenshots only. Autoplay/Muted/Loop grey out. |
| **Dynamic positioning** | See Test 9 |
| **Metadata language** | See Test 9 |
| **Clear cache** | Button reports how many entries went; next highlight re-fetches |

Also confirm: with **Preview mode = Off** or **Data saver = on**, the
video-only controls are greyed out rather than silently ignored.

---

## Test 8: displays other than a Deck's

Only relevant if you have one. Game Mode runs on a docked Deck and on
desktop SteamOS or Bazzite, and the overlay measures the library pane
rather than assuming a handheld's.

Run this on each display you have, and at each of the three **Overlay
size** settings:

- [ ] The card sits **inside the game grid** — clear of the search field
      and collection tabs above it, and of the button-hint bar below
- [ ] It is **proportionate**: not a postage stamp on a 4K TV, not half
      the screen on a 1080p monitor
- [ ] The **title, genres and description are readable** from wherever
      you actually sit
- [ ] All four corner positions still land in their corners

Then, with a Deck: highlight a game, **dock or undock** without leaving
the library, and confirm the card **re-places itself** to the new pane
within a second or so. It should not need a restart, and it should not
be left stranded over the chrome.

> If the card covers the search field or the button bar on some display,
> that is the measurement disagreeing with Steam's real layout. Note the
> resolution, and grab `[SteamView]` lines from the frontend console —
> `overlayGeometry.paneInsets` is the one place to change.

---

## Test 9: dynamic positioning and language

Both are off/automatic by default, so this only matters if you turn them
on — but both are new in 1.2.0 and neither has been on hardware.

### Dynamic positioning

Turn **Dynamic positioning** on, then scroll along a row of games.

- [ ] Highlighting a game on the **left** puts the card on the **right**,
      and vice versa
- [ ] The card never covers the game you are actually highlighting
- [ ] Your chosen **top/bottom** half is kept — only the side changes
- [ ] Scrolling slowly across the middle of the grid moves the card
      **once**, cleanly. It must not flick back and forth between two
      adjacent games.

> The flicker case is the one worth being fussy about: there is a
> deliberate dead band around the centre to prevent it, and if you can
> still provoke it, `SIDE_DEAD_ZONE` in `overlayGeometry.ts` is the dial.

### Language

With **Metadata language** on its default of **Match Steam**, the
description under the preview should already be in whatever language
Steam's UI is in. The panel says which language it detected.

- [ ] Pick a language explicitly (say **Portuguese (Brazil)**). Highlight
      a game you have not viewed since changing it — the title,
      description and genres come back in that language.
- [ ] Switch back to **English** and highlight the same game: it changes
      back **immediately**, not minutes later. Entries are cached per
      language, so both are already on disk.
- [ ] A game with no translation shows English rather than nothing.
      Steam falls back on its own; the preview should look normal.
- [ ] A non-Steam shortcut still matches. Matching deliberately stays in
      English — if turning on a language *loses* previews for imported
      games that is a real bug, and the log line names the language.

**Backend log:** each resolution line now carries the language, e.g.
`Cyberpunk 2077 (steam, brazilian) -> source=appdetails …`

---

## Test 10: battery and thermals

Worth a single longer pass, since previews decode video continuously.

1. Note battery percentage.
2. Browse the library for 10 minutes with previews on, pausing on games.
3. Note battery again, and whether the fans spun up.
4. Turn **Data saver** on and repeat for 10 minutes.

**Expect:** data saver is measurably gentler. If normal mode is
*dramatically* worse — fans running constantly, several percent of
battery in ten minutes — the autoplay delay and the 480p cap are the
levers to reach for.

---

## Test 11: it never breaks the library

The non-negotiable. Confirm all of these hold:

- [ ] Every game in the library still launches normally
- [ ] Scrolling, filtering, searching and collections all behave
- [ ] Game detail pages render fully, with the preview alongside rather
      than on top of anything you need
- [ ] The preview never steals focus — you can never "land on" it with
      the D-pad
- [ ] Disabling the plugin in Decky returns everything to exactly stock
- [ ] Uninstalling it leaves nothing behind

### Simulating a SteamOS update breaking the hook

Worth doing once, because it is the failure mode most likely to reach
you for real. In the frontend console:

```js
// Force the focus hook to fail on next start
document.addEventListener = () => { throw new Error("simulated breakage"); };
```

Then toggle **Enabled** off and on. **Expect:** the overlay stays gone,
the QAM panel shows the "Preview unavailable" block, **and the library
keeps working completely normally.** Reload Steam to undo.

---

## Recording a failure

1. Which test number, and what you saw versus what it says to expect
2. The game's exact display name, and whether it is native or a shortcut
3. The relevant lines from `~/homebrew/logs/SteamView/plugin.log`
4. Anything prefixed `[SteamView` from the frontend console
5. Your SteamOS version (Settings → System) and the plugin version

The most significant failure is **the wrong game's trailer showing**: it
means the matcher needs tightening, and no amount of off-device testing
will surface it.
