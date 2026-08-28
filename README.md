# Frame Chains

**Self-Healing, Leader-Redundant Orchestration of a Distributed AI Estate via
Signed Content-Addressed Frame Chains**

Kody Wildfeuer · RapterBox LLC · first public disclosure 2026-08-27

**Site: https://kody-w.github.io/frame-chains/ · Paper: https://kody-w.github.io/frame-chains/paper.html**

AI agents accumulate on devices the way services once accumulated on servers —
organically, unwatched, drifting. Frame chains keep a fleet of AI agents and
devices healthy as *verifiable state* on an append-only content-addressed
substrate: no central server, no elections, no clock agreement. One signed scan
tile fans an observation across the estate; the report's data exhaust drives
O(delta) follow-up; a homeostatic loop heals the estate to a stable floor and
goes quiet; leases and rosters make leader failover structural; disconnected
dimensions resume by appending to their own head. Proven on a real
eight-device estate — including ordering that survived a 17.6-second clock
disagreement, because the chain is the clock.

## Play with the ideas (no coding required)

| Exercise | What it teaches |
|---|---|
| [⏱ The Chain Is the Clock](https://kody-w.github.io/frame-chains/play/chain-is-the-clock.html) | Order comes from hand-offs, not timestamps — drag a clock 2 minutes wrong and the story stays true |
| [🛰 Scan Tiles & the Healing Loop](https://kody-w.github.io/frame-chains/play/scan-tile.html) | One frame asks the whole fleet; only the delta pays; the estate converges and goes quiet |
| [👑 Succession Without Elections](https://kody-w.github.io/frame-chains/play/succession.html) | Knock out the leader — staggered leases hand over power; lag can never cause a coup |

Every page is a single self-contained HTML file using real SHA-256 in your
browser. They are teaching toys; the paper is the source of truth.

## Run a sample

```
python3 samples/frame_chain.py
```

~120 lines, stdlib only: mint, append, verify, catch tampering (twice — the
chain remembers even if the attacker re-hashes), and watch two skewed-clock
devices produce one true order.

## Repo layout

```
paper.html      the paper (also at /paper.html on the site)
index.html      the landing page
play/           three interactive exercises (self-contained HTML)
samples/        frame_chain.py — the runnable toy
```

Substrate: the [rapp/1 protocol](https://kody-w.github.io/rapp-1/) (published
separately; not claimed here — this paper discloses the orchestration methods
built on it).

© 2026 RapterBox LLC. Paper text all rights reserved; the `play/` exercises and
`samples/` code may be used freely for teaching.
