#!/usr/bin/env python3
"""Allowlisted, read-only-input exporter. Not needed for public offline replay."""

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True
from privacy import detector_selftest, read_public_tree, scan_artifacts, strict_json

REFERENCE_COMMIT = "eb50008011447f5e69372ac22a1755f0978d15ed"
REFERENCE_HASHES = {
    "rapp.py": "1a04362b02f14c1e37b70c6b4f72d79e92df1cc9c2b5b394e8e1b141fc0b6050",
    "rapp_check.py": "a8dbc2dc242b2faabc959a917c23c37db3bd3d28b95dc57891cc8f623698b7c2",
    "LICENSE": "3b1952c1f983b4fc60337137cc6c863e9ea617ce551397c80e5b2d74eb1c476b",
}
ORACLE_INITIAL_HASH = "2899c97a318ecce64a311f2afbf30670f960d6a0dff9a791ece0bad08b0e422a"
ARMS = ("direct", "speculative")
AUTHORED = (
    "gyre/verify.py", "gyre/privacy.py", "gyre/test_evidence.py",
    "gyre/export.py", "gyre/evidence-README.md", "gyre/reference/oracle.py",
)
COUNTS = {
    "arms": 2, "generations": 2, "offspring_per_arm_per_generation": 5,
    "candidates": 20, "candidate_sources": 20, "seed_sources": 1,
    "program_frames": 41, "streams": 21, "non_genesis_links": 20,
    "original_cases": 39, "selection_cases": 70, "audit_cases": 119,
    "case_definitions": 228, "candidate_original_measurements": 780,
    "candidate_selection_measurements": 1400, "candidate_audit_measurements": 2380,
    "candidate_measurements": 4560, "seed_recorded_measurements": 109,
    "recorded_measurements": 4669, "candidate_prompt_response_projections": 20,
    "model_demo_projections": 2,
}
PROTOCOL_FIELDS = (
    "schema", "created_utc", "question", "model", "task", "conditions", "generations",
    "offspring_per_arm_per_generation", "total_candidate_requests",
    "max_concurrent_candidate_jobs", "max_request_seconds", "max_evaluator_seconds",
    "max_generation_window_seconds", "additional_hotload_demo_requests",
    "provider_budget_boundary", "sampling", "history_per_generation_request",
    "selection", "controls", "source_limits", "safety", "fixture_sha256",
    "reference_commit", "original_cases", "selection_cases", "audit_cases",
    "inference_policy", "limits",
)
PUBLIC_LIMITATIONS = [
    "Both arms reached the measured ceiling in generation 1; the observed comparison is a tie, not a speculative-mutation advantage.",
    "This release contains 41 program frames, not all 94 private records; diagnostic research-journal records are withheld.",
    "The interpreter is the unchanged pilot evaluator. Task gold is independently derived by a new contract oracle; execution semantics are not an independent native-Python implementation.",
    "The fixed Brainstem and fixed mutation instructions did not co-evolve; there is no mutable runtime/lens implementation in this pilot.",
    "Both model-mediated before/after demonstrations returned empty responses. A withheld worker log was reported to contain content_filter; a separate recorded local same-agent check succeeded.",
    "Unsigned synthetic stream records and exported response text cannot authenticate model identity, remote execution, audit secrecy at generation time, timing, or private diagnostic observations.",
    "Selection and audit cases are public after completion and cannot serve as hidden cases in a future confirmatory experiment.",
    "All 20 offspring passed frozen original-floor cases; this does not mean complete contract preservation. Known post-hoc contract and resource counterexamples are disclosed separately.",
    "Unselected speculative slot 1 in generation 1 rejects 0000001 and 0000002*(1), despite permitted leading zeros, because it caps unsigned digit length at six.",
    "For 256 comma-separated copies of 0000001, the seed completes in 29215 steps; selected direct parents hit GuestLimit at 120001 steps, while selected speculative parents complete this valid original input.",
    "The unchanged interpreter has list += alias semantics differing from CPython. None of the 20 frozen candidates uses augmented assignment. No general-Python equivalence or general-purpose sandbox claim is made.",
    "No native guest replay was performed. It would require an appropriately isolated OS execution boundary. Post-hoc probes do not alter the original 4560 candidate measurements or establish a prompt-arm advantage.",
]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def candidate_paths(arm, generation, slot):
    label = f"{arm}-{generation}-{slot}"
    directory = f"gyre/data/candidates/{label}"
    stream = f"gyre/data/streams/{label}"
    return {
        "candidate_id": "gyre-" + label, "arm": arm, "generation": generation, "slot": slot,
        "source_path": directory + "/candidate.py",
        "evaluation_path": directory + "/evaluation.json",
        "score_path": directory + "/score.json",
        "audit_evaluation_path": directory + "/audit-evaluation.json",
        "audit_score_path": directory + "/audit-score.json",
        "projection_path": directory + "/projection.json",
        "identity_path": stream + "/rappid.json",
        "source_frame_path": stream + "/frames/0.json",
        "evaluated_frame_path": stream + "/frames/1.json",
    }


def refreshed_manifest(artifacts):
    """Rebind authored/projection files, never silently replace preserved bytes."""
    manifest = strict_json(artifacts["gyre/data/manifest.json"])
    if manifest.get("schema") != "gyre-public-evidence/1" or manifest.get("counts") != COUNTS:
        raise ValueError("cannot refresh a different experiment")
    old_entries = {entry["path"]: entry for entry in manifest["files"]}
    if len(old_entries) != len(manifest["files"]):
        raise ValueError("duplicate manifest path")
    current = {
        path for path in artifacts
        if (path.startswith(("gyre/data/", "gyre/reference/")) or path in AUTHORED)
        and path != "gyre/data/manifest.json"
    }
    if not set(old_entries) <= current:
        raise ValueError("an existing release artifact is missing")
    addenda = strict_json(artifacts["gyre/data/addenda.json"])
    supplements = {
        path for entry in addenda["entries"] for path in entry.get("artifacts", [])
    }
    new_paths = current - set(old_entries)
    if not new_paths <= supplements or any(not path.startswith("gyre/data/addenda/") for path in new_paths):
        raise ValueError("new material must be an explicitly registered addendum")
    entries = []
    for path in sorted(current):
        parsed = PurePosixPath(path)
        if parsed.is_absolute() or ".." in parsed.parts or "\\" in path or parsed.as_posix() != path:
            raise ValueError("unsafe artifact path")
        raw = artifacts[path]
        origin = old_entries[path]["provenance"] if path in old_entries else {"mode": "publication-authored"}
        if origin["mode"] == "byte-identical":
            if digest(raw) != origin["source_sha256"] or digest(raw) != old_entries[path]["sha256"]:
                raise ValueError("preserved original/reference bytes changed; disclose a separate correction")
        entries.append({"path": path, "size": len(raw), "sha256": digest(raw), "provenance": origin})
    manifest["files"] = entries
    projected = dict(artifacts)
    projected["gyre/data/manifest.json"] = encoded(manifest)
    detector_selftest()
    if scan_artifacts(projected):
        raise ValueError("refreshed publication failed privacy")
    return manifest


def refresh(root):
    root = Path(root).resolve()
    manifest = refreshed_manifest(read_public_tree(root))
    destination = root / "gyre/data/manifest.json"
    if destination.is_symlink() or root not in destination.resolve().parents:
        raise ValueError("unsafe manifest destination")
    destination.write_bytes(encoded(manifest))
    return {"manifest_refresh": "PASS", "manifest_files": len(manifest["files"]), "original_bytes": "unchanged"}


def export(pilot, reference, root):
    pilot, reference, root = map(lambda p: Path(p).resolve(), (pilot, reference, root))
    if pilot == root or pilot in root.parents or root in pilot.parents:
        raise ValueError("publication and original must be disjoint")
    artifacts, origins = {}, {}

    def include(relative, raw, mode, origin=None, note=None):
        if not relative.startswith(("gyre/data/", "gyre/reference/")):
            raise ValueError("export destination outside owned scope")
        artifacts[relative] = raw
        origins[relative] = {"mode": mode}
        if origin is not None:
            origins[relative]["source_artifact_label"] = origin
        if mode == "byte-identical":
            origins[relative]["source_sha256"] = digest(raw)
        if note:
            origins[relative]["note"] = note

    def copy(original, published):
        source = pilot / original
        if source.is_symlink() or pilot not in source.resolve().parents:
            raise ValueError("unsafe original artifact")
        include(published, source.read_bytes(), "byte-identical", original)

    def project(published, value, origin, note):
        include(published, encoded(value), "projection", origin, note)

    for name in ("contract.txt", "seed.py", "seed-evaluation.json", "seed-score.json"):
        copy(name, "gyre/data/" + name)
    copy("private-fixture.json", "gyre/data/cases.json")
    copy("report.json", "gyre/data/observed-report.json")
    copy("local-hotload-proof.json", "gyre/data/local-hotload.json")
    copy("evaluator.py", "gyre/reference/interpreter.py")
    copy("evidence/seed/rappid.json", "gyre/data/streams/seed/rappid.json")
    copy("seed-frame.json", "gyre/data/streams/seed/frames/0.json")
    if artifacts["gyre/data/streams/seed/frames/0.json"] != (
        pilot / "evidence/seed/frames/0.json"
    ).read_bytes():
        raise ValueError("original seed frame copies differ")

    original_protocol = json.loads((pilot / "protocol.json").read_bytes())
    protocol = {key: original_protocol[key] for key in PROTOCOL_FIELDS}
    protocol["publication"] = {
        "kind": "allowlisted projection, not original protocol bytes",
        "omitted": "Original file inventory and controller are withheld; it includes local orchestration dependencies. No endpoint or private path is required by replay.",
        "controller": "The public verifier independently implements the documented eligibility and ranking rule; it does not copy or run the private controller.",
    }
    project("gyre/data/protocol.json", protocol, "protocol.json", "Allowlisted study fields; original file inventory omitted.")

    records, path_map = [], {}
    for generation in (1, 2):
        for arm in ARMS:
            for slot in range(5):
                item = candidate_paths(arm, generation, slot)
                records.append(item)
                old = f"workers/{arm}-{slot}/g{generation}"
                for key, filename in (
                    ("source_path", "candidate.py"),
                    ("evaluation_path", "evaluation.json"),
                    ("score_path", "score.json"),
                    ("audit_evaluation_path", "audit-evaluation.json"),
                    ("audit_score_path", "audit-score.json"),
                    ("source_frame_path", "source-frame.json"),
                    ("evaluated_frame_path", "evaluated-frame.json"),
                ):
                    copy(old + "/" + filename, item[key])
                    path_map[old + "/" + filename] = item[key]
                original_stream = f"evidence/candidates/{arm}-{generation}-{slot}"
                copy(original_stream + "/rappid.json", item["identity_path"])
                for key, number in (("source_frame_path", 0), ("evaluated_frame_path", 1)):
                    if artifacts[item[key]] != (pilot / original_stream / "frames" / f"{number}.json").read_bytes():
                        raise ValueError("original candidate frame copies differ")
                request = json.loads((pilot / old / "request.json").read_bytes())
                response = json.loads((pilot / old / "response.json").read_bytes())
                if request["conversation_history"] != [] or response["agent_logs"] != "":
                    raise ValueError("unexpected non-task conversation/tool content")
                projection = {
                    "schema": "gyre-task-projection/1",
                    "notice": "Allowlisted text projection, not original request/response bytes. Session identifiers and non-task transport fields are omitted. Paths inside prompt text are historical labels resolved by artifact-map.json.",
                    "request": {key: request[key] for key in ("user_input", "conversation_history")},
                    "response": {key: response[key] for key in ("response", "model", "requested_model")},
                }
                project(item["projection_path"], projection, old, "Actual task and response text retained; raw request/response digests intentionally not published.")
    path_map["seed-frame.json"] = "gyre/data/streams/seed/frames/0.json"
    project("gyre/data/artifact-map.json", {
        "schema": "gyre-artifact-map/1",
        "notice": "Keys are historical pilot-relative labels, not public links. Values resolve from the public repository root.",
        "paths": path_map,
    }, "allowlisted pilot artifact labels", "Relocation mapping; no private directory prefixes.")
    include("gyre/data/candidates.json", encoded(records), "publication-derived")

    selections = {}
    for generation in (1, 2):
        old_selection = json.loads((pilot / f"selection-g{generation}.json").read_bytes())
        projected = {}
        for arm in ARMS:
            choice = dict(old_selection[arm])
            for key in ("frame_path", "source_frame_path"):
                choice[key] = path_map[choice[key]] if choice[key] else None
            projected[arm] = choice
        selections[f"generation_{generation}"] = projected
    project("gyre/data/selections.json", {
        "schema": "gyre-parent-selections/1",
        "notice": "Recorded selections with paths relocated only; frame hashes, scores, and parent_changed observations are unchanged.",
        "selections": selections,
    }, "selection-g1.json and selection-g2.json", "Path projection, not byte-identical originals.")
    page_selection = {}
    for arm, selected in selections["generation_2"].items():
        choice = dict(selected)
        for key in ("frame_path", "source_frame_path"):
            choice[key] = choice[key].removeprefix("gyre/data/") if choice[key] else None
        page_selection[arm] = choice
    project(
        "gyre/data/selection-g2.json", page_selection, "selection-g2.json",
        "Page compatibility projection: paths are relative to data/; frame hashes, scores, and selected original frame bytes are unchanged.",
    )

    posthoc_files = ["gyre/data/posthoc/cases.json", "gyre/data/posthoc/summary.json"]
    for path in posthoc_files:
        copy("posthoc/" + Path(path).name, path)
    posthoc_programs = [{
        "program": "seed", "candidate_id": "seed",
        "source_path": "gyre/data/seed.py",
        "frame_path": "gyre/data/streams/seed/frames/0.json",
    }] + [
        {
            "program": f"{item['arm']}-{item['slot']}-g{item['generation']}",
            "candidate_id": item["candidate_id"], "source_path": item["source_path"],
            "frame_path": item["evaluated_frame_path"],
        }
        for item in records
    ]
    for program in posthoc_programs:
        path = "gyre/data/posthoc/" + program["program"] + ".json"
        copy("posthoc/" + program["program"] + ".json", path)
        posthoc_files.append(path)
        program["evaluation_path"] = path
        program["source_sha256"] = digest(artifacts[program["source_path"]])
        program["frame_hash"] = json.loads(artifacts[program["frame_path"]])["frame_hash"]
    include("gyre/data/posthoc/provenance.json", encoded({
        "schema": "gyre-posthoc-publication/1",
        "status": "Separate post-hoc observations; not part of the primary frozen pilot.",
        "case_definitions": "gyre/data/posthoc/cases.json",
        "recorded_summary": "gyre/data/posthoc/summary.json",
        "byte_identity": "The allowlisted synthetic case, summary, and 21 evaluator files retain their supplied post-hoc bytes; this publication mapping is newly authored.",
        "controller_boundary": "The original posthoc_probe.py imports private orchestration and journal code. It is neither copied nor executed; the portable public verifier independently reconstructs and replays these probes.",
        "programs": posthoc_programs,
    }), "publication-authored")
    posthoc_files.append("gyre/data/posthoc/provenance.json")

    report = json.loads(artifacts["gyre/data/observed-report.json"])
    results = dict(report)
    results["limitations"] = report["limitations"] + PUBLIC_LIMITATIONS
    results["publication"] = {
        "kind": "aggregate projection with additional public-boundary limitations",
        "original_report": "gyre/data/observed-report.json",
        "counts": COUNTS,
        "addenda": "gyre/data/addenda.json",
        "measurement_status": "Original scores remain recorded observations until checked against offline replay.",
        "original_floor_label": "Passed frozen original-floor cases",
        "complete_contract_preservation": False,
        "known_counterexamples": "gyre/data/addenda/known-counterexamples.json",
        "posthoc_boundary": "Separately replayed targeted counterexamples, not additional frozen cases or an arm-effect estimate.",
        "posthoc_counts": {"cases": 3, "candidate_probes": 60, "seed_probes": 3},
        "posthoc_recorded_summary": "gyre/data/posthoc/summary.json",
    }
    project("gyre/data/results.json", results, "report.json", "Original aggregate, model, seed, and report fields retained; publication limitations appended.")
    addenda_path = root / "gyre/data/addenda.json"
    addenda = json.loads(addenda_path.read_bytes()) if addenda_path.exists() else {
        "schema": "gyre-evidence-addenda/1",
        "policy": "Append reviewer corrections and supplemental checks here. Do not rewrite preserved original frames, evaluations, scores, or report to improve outcomes. Rebind the manifest after an addition.",
        "entries": [],
    }
    if not any(entry.get("id") == "gyre-review-2" for entry in addenda["entries"]):
        addenda["entries"].append({
            "id": "gyre-review-2",
            "description": "Archive the supplied 63 post-hoc evaluator observations across the seed and every candidate, separately from the unchanged frozen tallies. Verification must reproduce failures as well as successes.",
            "subjects": [
                {"path": path, "sha256": digest(artifacts[path])}
                for path in ("gyre/data/observed-report.json", "gyre/data/posthoc/cases.json", "gyre/data/posthoc/summary.json")
            ],
            "artifacts": sorted(posthoc_files),
        })
    include("gyre/data/addenda.json", encoded(addenda), "publication-authored")
    for entry in addenda["entries"]:
        for path in entry.get("artifacts", []):
            if path in posthoc_files:
                continue
            if not path.startswith("gyre/data/addenda/") or ".." in PurePosixPath(path).parts:
                raise ValueError("supplement outside addendum scope")
            source = root / path
            if source.is_symlink() or root not in source.resolve().parents:
                raise ValueError("unsafe supplemental artifact")
            include(path, source.read_bytes(), "publication-authored")
    for phase in ("before", "after"):
        request = json.loads((pilot / f"demo-{phase}.request.json").read_bytes())
        response = json.loads((pilot / f"demo-{phase}.response.json").read_bytes())
        if request["conversation_history"] != [] or response["agent_logs"] != "":
            raise ValueError("unexpected model demo content")
        project(f"gyre/data/model-demos/{phase}.json", {
            "schema": "gyre-task-projection/1",
            "phase": phase,
            "notice": "Task-only projection; raw transport identifiers omitted. Empty response is preserved, not replaced by the local demonstration.",
            "request": {key: request[key] for key in ("user_input", "conversation_history")},
            "response": {key: response[key] for key in ("response", "model", "requested_model")},
            "outcome": "empty model response; no successful model-mediated tool demonstration",
            "log_observation": "content_filter was reported in a withheld private worker log; this public projection cannot independently authenticate that log.",
        }, f"demo-{phase} request/response", "Task/model/response projection only, not raw-byte identity.")

    for name, expected in REFERENCE_HASHES.items():
        raw = (reference / name).read_bytes()
        if digest(raw) != expected:
            raise ValueError("reference byte pin mismatch")
        include("gyre/reference/" + name, raw, "byte-identical", "canonical-rapp-1/" + name)
    include("gyre/reference/provenance.json", encoded({
        "schema": "gyre-reference-provenance/1",
        "repository": "https://github.com/kody-w/rapp-1",
        "commit": REFERENCE_COMMIT,
        "files": REFERENCE_HASHES,
        "license": "gyre/reference/LICENSE",
        "reference_status": "Unmodified current reference and compliance checker, not the old pilot protocol adapter.",
        "interpreter": {
            "path": "gyre/reference/interpreter.py",
            "source_artifact_label": "evaluator.py",
            "sha256": digest(artifacts["gyre/reference/interpreter.py"]),
            "status": "Byte-identical fixed pilot bounded interpreter; not native execution of candidate source.",
        },
        "oracle": {
            "path": "gyre/reference/oracle.py",
            "basis": "Task contract only; authored before reading pilot evaluator, fixture generator, or generated solver algorithms.",
            "initial_sha256": ORACLE_INITIAL_HASH,
            "relationship": "Independent token/explicit-stack grammar implementation, not copied gold or candidate logic; the execution interpreter is shared with the original study.",
        },
        "new_material_terms": "Existing repository copyright and permissions apply; the accompanying MIT license applies to the vendored upstream reference, not the whole repository.",
    }), "publication-authored")

    for path in AUTHORED:
        artifacts[path] = (root / path).read_bytes()
        origins[path] = {"mode": "publication-authored"}
    detector_selftest()
    failures = scan_artifacts(artifacts)
    if failures:
        raise ValueError("allowlisted material failed privacy: " + ", ".join(sorted(set(failures))))
    manifest = {
        "schema": "gyre-public-evidence/1",
        "scope": "Allowlisted synthetic completed-pilot data, separately labeled post-hoc counterexamples, offline tools, and pinned public RAPP reference. This is not the complete private journal.",
        "counts": COUNTS,
        "counts_scope": "counts describes the unchanged original pilot only; post-hoc probes are accounted for separately and do not revise frozen denominators.",
        "posthoc_scope": {
            "definitions": "gyre/data/addenda/known-counterexamples.json",
            "cases": 3, "candidate_probes": 60, "seed_probes": 3,
            "recorded_cases": "gyre/data/posthoc/cases.json",
            "recorded_summary": "gyre/data/posthoc/summary.json",
            "recorded_evaluation_files": 21, "recorded_measurements": 63,
            "included_in_frozen_denominators": False,
        },
        "provenance": {
            "model_reported": report["model"],
            "reference_commit": REFERENCE_COMMIT,
            "identity": "Synthetic keyless @example streams; signatures are null.",
            "raw_program_frames": "41 of 41 selected program frames retain original bytes, particle hashes, wave hashes, and parent provenance.",
            "withheld": "Private diagnostic/journal records, raw health and stdout, account/session identifiers, auth material, local endpoints/paths, worker environments, unrelated source, original controller, and full Brainstem.",
            "authentication_limit": "Hashes bind this export's contents, not provider identity, private logs, audit timing, or the original private journal's completeness.",
        },
        "manifest_policy": "Every released data/tool/reference file and evidence README is bound below. Manifest self-hashing is excluded; parent-owned narrative/integration files are outside this manifest, but the privacy command scans the entire gyre tree.",
        "files": [
            {"path": path, "size": len(raw), "sha256": digest(raw), "provenance": origins[path]}
            for path, raw in sorted(artifacts.items())
        ],
    }
    manifest_raw = encoded(manifest)
    if scan_artifacts({"gyre/data/manifest.json": manifest_raw}):
        raise ValueError("manifest failed privacy")
    destinations = [root / path for path in artifacts if path not in AUTHORED]
    destinations.append(root / "gyre/data/manifest.json")
    for destination in destinations:
        if destination.is_symlink() or root not in destination.resolve().parents:
            raise ValueError("unsafe export destination")
        if any(parent.is_symlink() for parent in destination.parents if root in parent.parents):
            raise ValueError("linked export directory")
    for path, raw in sorted(artifacts.items()):
        if path in AUTHORED:
            continue
        destination = root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    (root / "gyre/data/manifest.json").write_bytes(manifest_raw)
    return {"export": "PASS", "manifest_files": len(artifacts), **COUNTS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--root", default=Path("."), type=Path)
    parser.add_argument("--refresh-manifest", action="store_true")
    args = parser.parse_args()
    try:
        if args.refresh_manifest:
            result = refresh(args.root)
        else:
            if args.pilot is None or args.reference is None:
                parser.error("initial export requires --pilot and --reference")
            result = export(args.pilot, args.reference, args.root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, KeyError, ValueError, AssertionError) as error:
        # Only internally authored, content-free diagnostics are safe to print.
        print(json.dumps({"export": "FAIL", "reason": type(error).__name__}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
