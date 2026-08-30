#!/usr/bin/env python3
"""frame_chain.py — a ~90-line teaching toy for the Frame Chains paper.

Real SHA-256, zero dependencies. Shows four things:
  1. mint + append: every frame holds the fingerprint of the one before it
  2. verify: recomputation detects changed content or links in the given chain
  3. tamper: change one byte of history and verification says exactly where
  4. the chain is the clock: two devices with disagreeing clocks still
     produce one true order — because order comes from hand-offs, not clocks

This is a TOY: the production substrate is the rapp/1 protocol
(https://kody-w.github.io/rapp-1/) — eleven-key frames, mint-once identity,
domain-separated hashing. Run:  python3 frame_chain.py
"""
import hashlib
import json


def h(obj) -> str:
    """Canonical-ish JSON -> SHA-256 hex. (rapp/1 uses RFC 8785 + domain tags.)"""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def mint(chain, device, what, claimed_clock):
    """Append one frame. Its identity INCLUDES the previous frame's hash."""
    frame = {
        "seq": len(chain),
        "prev": chain[-1]["hash"] if chain else None,
        "device": device,
        "what": what,
        "claimed_clock": claimed_clock,  # annotation, NEVER the source of order
    }
    frame["hash"] = h({k: v for k, v in frame.items() if k != "hash"})
    chain.append(frame)
    return frame


def verify(chain):
    """Recompute every link. Returns (ok, first_bad_seq_or_None)."""
    for i, f in enumerate(chain):
        body = {k: v for k, v in f.items() if k != "hash"}
        if f["hash"] != h(body):
            return False, i
        if f["prev"] != (chain[i - 1]["hash"] if i else None):
            return False, i
    return True, None


def demo():
    chain = []

    # ── two devices, one story; the deck's clock is 17.6 s WRONG ──────────
    mac, skew = 1000.0, -17.6
    mint(chain, "mac", "backed up photos", mac + 0)
    mint(chain, "deck", "saved the game", mac + 5 + skew)   # claims 987.4!
    mint(chain, "mac", "replied to email", mac + 10)
    mint(chain, "deck", "synced a mod", mac + 15 + skew)

    print("CHAIN ORDER (the truth — each frame holds the previous hash):")
    for f in chain:
        print(f"  #{f['seq']} {f['device']:>4}  {f['what']:<18} "
              f"claims t={f['claimed_clock']:<7} holds {str(f['prev'])[:8]}")

    by_clock = sorted(chain, key=lambda f: f["claimed_clock"])
    print("\nWALL-CLOCK ORDER (the lie a wrong clock tells):")
    for f in by_clock:
        mark = "  <-- out of place!" if f["seq"] != by_clock.index(f) else ""
        print(f"  #{f['seq']} {f['device']:>4}  {f['what']:<18} "
              f"claims t={f['claimed_clock']}{mark}")

    ok, _ = verify(chain)
    print(f"\nverify(chain) -> {ok}   (order needed NO clock agreement)")

    # ── tampering: rewrite history, get caught ────────────────────────────
    print("\nNow an attacker edits frame #1's story...")
    chain[1]["what"] = "deleted the backups"
    ok, bad = verify(chain)
    print(f"verify(chain) -> {ok}, first broken frame: #{bad} "
          "(its bytes no longer match its own fingerprint)")

    # even 'fixing' the hash breaks the NEXT link — history is load-bearing
    body = {k: v for k, v in chain[1].items() if k != "hash"}
    chain[1]["hash"] = h(body)
    ok, bad = verify(chain)
    print(f"attacker re-hashes #1 -> verify says {ok}, broken at #{bad} "
          "(frame #2 still holds the OLD fingerprint — the chain remembers)")


if __name__ == "__main__":
    demo()
