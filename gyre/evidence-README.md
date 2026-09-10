# Gyre: public evidence boundary and offline replay

This is the synthetic evidence subset of a **completed exploratory pilot**,
with separately labeled post-hoc counterexamples. It is not a new confirmatory
experiment, the entire private journal, or proof of general self-improvement.
No physical quantum mechanism is implemented or established.

From the repository root, using Python 3.11 or newer:

```sh
python3 gyre/verify.py .
python3 gyre/verify.py . --self-test
python3 gyre/privacy.py . --self-test
```

No installation, account, model, API, network service, worker environment, or
original private directory is required. The commands do not modify release
data. Negative controls mutate in-memory copies only. To see individual tests:

```sh
python3 -B -m unittest discover -s gyre -p test_evidence.py -v
```

## What is included

* All **20 offspring sources**: five speculative/success-conditioned and five
  conventional-repair candidates in each of two generations, plus the original
  flat-list seed.
* **41 original program frames**, byte-for-byte: one seed genesis and twenty
  candidate/evaluation pairs. Twenty non-genesis particle links are checked
  against their actual predecessors and all 21 stream identity records.
  This does **not** claim that all 94 private records are public.
* All **228 frozen case definitions and gold outputs**: 39 original, 70
  selection (40 valid extensions and 30 invalid inputs), and 119 reserved audit
  cases (15 original, 83 valid extensions, 21 invalid inputs). The fixture's
  random seed is synthetic test-generation data, not an account secret.
* Original evaluations and grades: **4,560 candidate measurements**
  (780 original, 1,400 selection, 2,380 audit), and 109 recorded seed
  measurements. Elapsed milliseconds remain original observations, not
  independently reproduced timing results.
* Recorded parent selections, the contract, task-only prompt/response
  projections, blocked model-demo projections, and the recorded local check.
  The original aggregate report remains in `data/observed-report.json`;
  `data/results.json` preserves its model/aggregate/seed shape and appends
  explicit publication limitations.
* A separate supplied **post-hoc corpus** at `data/posthoc/`: the three explicit
  case definitions, the recorded summary, and all 21 per-program evaluator
  files. These 23 synthetic JSON inputs passed privacy review and retain their
  supplied bytes. Newly authored `provenance.json` maps every historical program
  label to its frozen public source, source hash, frame, and evaluation file.

`data/manifest.json` binds every released data, tool, reference file, and this
README by repository-relative path, byte count, SHA-256, and provenance.
The manifest cannot hash itself; its integrity depends on the enclosing
reviewed repository revision. Parent-owned pages and integration files are
outside this manifest but inside the `gyre/` privacy scan.
Its `counts` describes the unchanged frozen pilot; `posthoc_scope` separately
accounts for the three targeted inputs, 21 recorded evaluator files, and
63 additional bounded replays/recorded measurements.

Raw program frames, sources, measurement files, seed grades, fixture, original
report, local-check record, and contract retain their original bytes and are
marked `byte-identical`. Relocation does not change their content addresses.
The separately supplied post-hoc cases, summary, and evaluator files likewise
retain their bytes, but remain explicitly **post-hoc**, not primary records.
Intra-stream `prev` links are **particle/payload** hashes; cross-stream parent
wave hashes are payload provenance, not substitutes for those links.

Parent-selection paths are relocated in a labeled projection.
`data/artifact-map.json` maps historical pilot-relative labels found inside
unchanged prompt text to real public files. Projection hashes describe the
**published projections**, never raw requests or responses. Transport/session
identifiers are omitted; actual task text and returned program text are kept.
For the public page, `data/selection-g2.json` retains the original arm-keyed
shape with `frame_path` and `source_frame_path` relative to `data/`. Its selected
full frame exposes the unchanged `payload.source` and `payload.source_sha256`.
The offline verifier checks this compatibility projection against independently
reconstructed selection; a page-side source digest alone checks bytes, not behavior.
The original controller and its local orchestration dependencies are not
vendored. `data/protocol.json` is an allowlisted projection without its
private file inventory, not an asserted byte-identical controller/protocol.

## What replay independently checks

1. Enforce the complete fixed design, case identities, file inventory, and
   measurement denominators. Missing, duplicated, or shortened data fails.
2. Validate the 11-field RAPP envelopes, particle/wave hashes, identity
   binding, and all nonzero chains using the current pinned canonical
   reference and checker.
3. Parse every frozen input with a separately written contract oracle.
   `reference/oracle.py` was written from `contract.txt` **before examining
   generated solvers, the original evaluator, or fixture-generation code**.
   It uses tokenization and an explicit stack, and never reads recorded gold
   or imports a candidate.
4. Re-execute all programs through `reference/interpreter.py`, a
   **byte-identical copy of the fixed original bounded AST interpreter**.
   Generated source is never imported, compiled for native execution, or run
   using `exec`/`eval`. Admission, output, step count, AST size, gold agreement,
   and every original grade are checked. Grades are not trusted as inputs.
5. Reconstruct candidate sources from actual response text, inherited parent
   frames and prompt text, original-floor eligibility, novel-case score,
   smallest-AST then lexical-source-hash tie-breaking, and both generations'
   parent choices. Audit scores are not used in the ranking rule.
6. Independently derive both arms' aggregate results and replay the local
   demo's before/after **values**, without claiming to recreate the original
   agent loader or model-mediated tool use.

The command performs 4,788 program/case runs (21 programs × 228 cases),
checks 4,669 originally recorded measurements, and separately replays two local
demo values. The seed's 119 audit runs are **new public replay measurements**,
not retrospectively invented original observations.
It also runs 63 separately labeled post-hoc probes (three targeted inputs ×
the seed and twenty candidates). Those probes are never added to the 228
frozen cases or the 4,560 original candidate outcomes. It checks all 63 supplied
post-hoc measurements against new bounded execution and independently derived
gold, then reconstructs the supplied summary—including its failures. Recorded
post-hoc elapsed milliseconds remain observations, not reproduced wall time.

The oracle and score derivation are independent of recorded grades.
**The execution interpreter is shared with the original study.** This is not
an independent normal-CPython countercheck, proof of unrestricted Python
correctness, or a general-purpose sandbox certification. The execution
language and its resource bounds are fixed by the supplied contract.
In particular, the frozen interpreter's **list `+=` alias semantics differs
from CPython**: it rebinds the target instead of mutating the aliased list.
The verifier confirms that none of the twenty frozen candidates has an
`AugAssign` AST node. The interpreter remains unchanged, not silently repaired.
Native guest replay would require a suitable OS-level isolation boundary and
**was not performed**.

An overall verifier **PASS means the evidence consistently replays, including
the known failures below**. It does not certify universal program correctness
or preservation of the complete contract.

Self-tests reject corrupted hashes, sources, frames, particle links, stream
identities, measurements, gold, grades, parent choices, and corpus sizes.
Crucially, behaviorally wrong source and an original-use-case regression have
their source/frame/manifest integrity metadata recomputed: semantic/regression
checking must still reject them. Privacy tests cover addresses, identifiers,
credentials, escaped text, and Python/text/CSV/JSON surfaces. **No privacy
exceptions or blanket source/reference skips are used.**

JSON scanning inspects decoded member names as well as values and refuses
duplicate members before a parser can discard an earlier value. Manifest
refresh uses the same strict decoding for its control documents. These are
recognized-indicator checks, not a guarantee of detecting every possible
encoding; release safety also depends on the explicit source allowlist and
review of the material being shipped.

## What remains private or cannot be authenticated

No raw health records, stdout logs, private journal/diagnostic frames,
account/session identities, auth caches, credentials, home paths, machine
addresses, unrelated source or estate inventories, worker environments, full
Brainstem source, or older private-session artifacts are included.
`export.py` reads only an explicit artifact allowlist and privacy-checks it
before writing. It does not copy a pilot directory wholesale.

These are unsigned synthetic `@example` stream records. Their hashes prove
internal content/link consistency, not who produced them, provider identity,
the truth of model labels, execution timing, the completeness of the private
journal, or that audit answers were unavailable during original generation.
Public fixtures are now unsuitable as secret held-out cases in a new study.
They do not authenticate the omitted private diagnostics.

Both model-mediated before/after tool requests returned **empty responses**.
The local record reports `content_filter` in a withheld worker log; the
public projections cannot authenticate that log. The separate local same-agent
hotload record succeeded, but it is **not a successful API demonstration**.
Offline value replay must not be substituted for one.

## Results and interpretation

All twenty candidates **passed frozen original-floor cases** and all frozen
selection and audit cases. That label must not be expanded to “preserved the
complete contract.” **Both arms saturated in generation 1.** There is
no observed speculative advantage. Opus 5's pretrained programming knowledge
is a major contribution, not emergence from nothing. One seed lineage and five
siblings per arm are not independent population-level evolutionary replicates.
There was no pure-random arm, fresh-reset control, mutable runtime/lens
implementation, or demonstrated general self-improvement.

### Known post-hoc counterexamples

`data/addenda/known-counterexamples.json` gives the exact targeted input
definitions and labels them as post-hoc. The default verifier independently
derives their gold with the unchanged contract oracle and runs each through
every frozen source using the unchanged bounded interpreter. It also requires
agreement with `data/posthoc/cases.json`, `data/posthoc/summary.json`, and every
supplied evaluator output. Missing programs, missing measurements, falsified
gold, or a failure rewritten as a pass all fail the evidence gate.

| Permitted input | Independently replayed limitation |
|---|---|
| `0000001` → `[1]` | Unselected `speculative-1-1` rejects it with `ValueError`. |
| `0000002*(1)` → `[1,1]` | The same candidate rejects it because its unsigned digit-length check caps tokens at six digits. |
| A comma-separated list of 256 copies of `0000001` → 256 ones | The seed finishes in **29,215** steps. Selected direct parents `direct-1-0` and `direct-2-2` hit `GuestLimit` at **120,001** steps. Selected speculative parents finish. |

The long input is a valid **original-use-case input**, so these are genuine
contract/resource counterexamples outside the frozen test floor, not a revised
scoring definition. The additional tests do not invalidate or rewrite the
original frozen tallies. They are targeted diagnostics discovered after the
pilot, not new held-out evidence of a prompt-arm advantage.

Across all twenty candidates, **9/20 fail the long original-scope probe**:
the unselected `speculative-1-g1` record is `ValueError`;
`speculative-2-g1`, `direct-0-g1`, `direct-3-g1`, and all five direct generation-2
records reach `GuestLimit` at 120,001 steps. Historical labels here match the
supplied summary and map to public sources through `data/posthoc/provenance.json`.
The seed passes both original-scope probes; the repeat probe is an extension
it does not implement. This is a targeted failure inventory, **not an unbiased
arm comparison**.

The original post-hoc controller imports private orchestration/journal code
and is not copied or run. Replay uses the self-contained public verifier.
No novelty claim is made for co-evolving meta-prompts, evolving mutation
prompts, or improving an improver by themselves; prior-art assessment belongs
to the accompanying research note.

Reviewer corrections or supplemental results belong in the append-only
`data/addenda.json` ledger, binding relevant original files by path and hash.
Supplemental artifacts can live under `data/addenda/` and must be listed in the
ledger and rebound into the manifest. An addendum does not waive a failing
gate and must not rewrite an original observation to obtain a better result.
Maintainers can update the manifest after editing authored tools, labeled
projections, or adding registered review material without private inputs:

```sh
python3 gyre/export.py --refresh-manifest --root .
python3 gyre/verify.py . --self-test
```

Refresh refuses changed `byte-identical` originals or upstream reference
files. A correction to one of those must be a separately labeled artifact.

## Reference and permissions

`reference/rapp.py` and `reference/rapp_check.py` are unmodified from
[`kody-w/rapp-1`](https://github.com/kody-w/rapp-1) at commit
`eb50008011447f5e69372ac22a1755f0978d15ed`, not the old protocol adapter.
`reference/provenance.json` and the manifest pin exact upstream byte hashes.
The upstream **MIT LICENSE accompanies those files**.

Existing repository copyright and permissions continue to govern new
material. This package introduces no new repository-wide license.
