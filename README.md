# Frame Chains

**Self-Healing, Leader-Redundant Orchestration of a Distributed AI Estate via
Signed Content-Addressed Frame Chains**

Kody Wildfeuer · RapterBox LLC · first public disclosure 2026-08-27

**Site: https://kody-w.github.io/frame-chains/ · Guide: https://kody-w.github.io/frame-chains/guide.html · Paper: https://kody-w.github.io/frame-chains/paper.html**

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

## Start with the guided evidence path

The [newcomer guide](https://kody-w.github.io/frame-chains/guide.html)
walks through six claims in a deliberate order. Every step tells the reader
what the page models, what to do, what to watch for, and what the observed
result does—and does not—demonstrate.

## Play with the ideas (no coding required)

| Exercise | What it teaches |
|---|---|
| [⏱ The Chain Is the Clock](https://kody-w.github.io/frame-chains/play/chain-is-the-clock.html) | Order comes from hand-offs, not timestamps — drag a clock 2 minutes wrong and the story stays true |
| [🛰 Scan Tiles & the Healing Loop](https://kody-w.github.io/frame-chains/play/scan-tile.html) | One frame asks the whole fleet; only the delta pays; the estate converges and goes quiet |
| [👑 Succession Without Elections](https://kody-w.github.io/frame-chains/play/succession.html) | Knock out the leader — staggered leases hand over power; lag can never cause a coup |
| [Membrane](https://kody-w.github.io/frame-chains/play/membrane.html) | Verified public facts may enrich a private estate, while private frames have no outward path |
| [Deterministic Reattach](https://kody-w.github.io/frame-chains/play/reattach.html) | A stranded frame finds the first contradiction-free base by exact set comparison |
| [Merge Fidelity](https://kody-w.github.io/frame-chains/play/merge-fidelity.html) | Independent histories merge agreement while preserving genuine contradictions |

Every page is a single self-contained HTML file. Where hashing is part of the
claim, the page uses the browser's real SHA-256 implementation. Each exercise
includes a normal path, a deliberate failure or mutation path, visible
assertions, reset/replay controls, and a copyable prompt for asking any LLM to
build an independent runnable proof. These are explanatory models; the paper is
the source of truth for the reported estate runs and limitations.

## Run a sample

```
python3 samples/frame_chain.py
```

~90 lines, stdlib only: mint, append, verify, catch tampering (twice — the
chain remembers even if the attacker re-hashes), and watch two skewed-clock
devices produce one true order.

## Verify the publication

```sh
npm ci
npm run check
```

The full gate boots the landing page, guide, paper, and all six exercises at
responsive sizes; validates every paper embed and prompt-copy path; exercises
the positive and deliberate-failure paths in Chromium; and runs the Python
sample. Cross-browser smoke commands use
`npm run papercheck -- firefox smoke` or `webkit smoke`.

## Repo layout

```
paper.html      the paper (also at /paper.html on the site)
index.html      the landing page
guide.html      the newcomer-first guided evidence path
play/           six interactive exercises (self-contained HTML)
samples/        frame_chain.py — the runnable toy
papercheck.mjs  structural and browser verification for the publication
```

Substrate: the [rapp/1 protocol](https://kody-w.github.io/rapp-1/) (published
separately; not claimed here — this paper discloses the orchestration methods
built on it).

© 2026 RapterBox LLC. Paper text all rights reserved; the `play/` exercises and
`samples/` code may be used freely for teaching.
