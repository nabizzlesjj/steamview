# Contributing

Short version: **fork it and do whatever you like — but this repository
is a personal project and does not accept pull requests.**

## Pull requests are not accepted

Not because contributions aren't welcome in spirit, but because this is a
one-person project and I want the version living here to stay mine.
Pull requests opened against this repository will be closed unread.

Please don't take that personally — it's a blanket policy, not a
judgement on your patch.

## What you *can* do

SteamView is [BSD-3-Clause](LICENSE), which is deliberately permissive:

- **Fork it.** Your fork is yours. Change anything, rename it, ship it.
- **Clone it, vendor it, borrow chunks of it** for something else.
- **Publish your own version**, including a modified one, commercially or
  not.

The licence asks only three things: keep the copyright notice and licence
text, don't use my name to endorse your version, and accept that it comes
with no warranty. See [LICENSE](LICENSE) for the exact terms.

If you fork and improve it, I'd genuinely enjoy seeing it — but you owe
me nothing beyond the licence.

## Bug reports

Issues may or may not be enabled on this repository. If they are, a bug
report is welcome, especially one that includes:

- Your SteamOS version and the plugin version
- The relevant lines from `~/homebrew/logs/SteamView/plugin.log`
- Anything prefixed `[SteamView` from the CEF console

See [TESTING.md](TESTING.md) for how to get at both.

That said: I make no promise to fix anything, or to respond. If you need
a fix on a timeline, forking is the reliable path.

## A note on how this was built

Most of this codebase was written by an AI assistant (Claude), working
from a specification I wrote and iterating against my own on-device
testing. The commit history records that in its `Co-Authored-By` trailers
rather than hiding it.

I mention it because it's relevant if you're deciding whether to build on
this: judge the code on its merits, and note that it has been exercised
on real hardware but is not battle-tested across many devices.
