#!/usr/bin/env python3
"""Offline behavioral replay, independent task gold, and publication gates."""

import argparse
import ast
import hashlib
import importlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True
import privacy

REFERENCE_COMMIT = "eb50008011447f5e69372ac22a1755f0978d15ed"
PINNED = {
    "gyre/reference/rapp.py": "1a04362b02f14c1e37b70c6b4f72d79e92df1cc9c2b5b394e8e1b141fc0b6050",
    "gyre/reference/rapp_check.py": "a8dbc2dc242b2faabc959a917c23c37db3bd3d28b95dc57891cc8f623698b7c2",
    "gyre/reference/LICENSE": "3b1952c1f983b4fc60337137cc6c863e9ea617ce551397c80e5b2d74eb1c476b",
    "gyre/reference/interpreter.py": "6ca11b820cd911a99b4bf9862cd8b0aa3d8907b641fdae4b9470b9bfb8d56e35",
    "gyre/reference/oracle.py": "2899c97a318ecce64a311f2afbf30670f960d6a0dff9a791ece0bad08b0e422a",
    "gyre/data/contract.txt": "ab0b365464c27812d251f60cf4f3b3bf26cf7f7ae77b2cbf06826618ba2210f6",
}
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
ARMS = ("direct", "speculative")
MANIFEST = "gyre/data/manifest.json"
AUTHORED = {
    "gyre/verify.py", "gyre/privacy.py", "gyre/test_evidence.py",
    "gyre/export.py", "gyre/evidence-README.md", "gyre/reference/oracle.py",
}


class EvidenceError(Exception):
    def __init__(self, gate, reason):
        self.gate, self.reason = gate, reason
        super().__init__(gate + ": " + reason)


def require(condition, gate, reason):
    if not condition:
        raise EvidenceError(gate, reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def same(left, right):
    return encoded(left) == encoded(right)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "structure", "duplicate JSON member")
        result[key] = value
    return result


def load(bundle, path):
    require(path in bundle, "corpus", "required artifact missing")
    try:
        return json.loads(
            bundle[path], object_pairs_hook=_unique_object,
            parse_constant=lambda _: require(False, "structure", "non-finite JSON number"),
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise EvidenceError("structure", "invalid JSON artifact") from error


def candidates():
    items = []
    for generation in (1, 2):
        for arm in ARMS:
            for slot in range(5):
                label = f"{arm}-{generation}-{slot}"
                directory = f"gyre/data/candidates/{label}"
                stream = f"gyre/data/streams/{label}"
                items.append({
                    "candidate_id": "gyre-" + label,
                    "arm": arm, "generation": generation, "slot": slot,
                    "source_path": directory + "/candidate.py",
                    "evaluation_path": directory + "/evaluation.json",
                    "score_path": directory + "/score.json",
                    "audit_evaluation_path": directory + "/audit-evaluation.json",
                    "audit_score_path": directory + "/audit-score.json",
                    "projection_path": directory + "/projection.json",
                    "identity_path": stream + "/rappid.json",
                    "source_frame_path": stream + "/frames/0.json",
                    "evaluated_frame_path": stream + "/frames/1.json",
                })
    return items


def posthoc_programs():
    return [{
        "program": "seed", "candidate_id": "seed",
        "source_path": "gyre/data/seed.py",
        "frame_path": "gyre/data/streams/seed/frames/0.json",
        "evaluation_path": "gyre/data/posthoc/seed.json",
    }] + [
        {
            "program": f"{item['arm']}-{item['slot']}-g{item['generation']}",
            "candidate_id": item["candidate_id"], "source_path": item["source_path"],
            "frame_path": item["evaluated_frame_path"],
            "evaluation_path": f"gyre/data/posthoc/{item['arm']}-{item['slot']}-g{item['generation']}.json",
        }
        for item in candidates()
    ]


def required_paths():
    paths = AUTHORED | set(PINNED) | {
        "gyre/reference/provenance.json", "gyre/data/cases.json",
        "gyre/data/seed.py", "gyre/data/seed-evaluation.json", "gyre/data/seed-score.json",
        "gyre/data/observed-report.json", "gyre/data/results.json", "gyre/data/protocol.json",
        "gyre/data/candidates.json", "gyre/data/selections.json", "gyre/data/selection-g2.json",
        "gyre/data/artifact-map.json",
        "gyre/data/addenda.json", "gyre/data/local-hotload.json",
        "gyre/data/model-demos/before.json", "gyre/data/model-demos/after.json",
        "gyre/data/streams/seed/rappid.json", "gyre/data/streams/seed/frames/0.json",
        "gyre/data/posthoc/cases.json", "gyre/data/posthoc/summary.json",
        "gyre/data/posthoc/provenance.json",
    }
    for item in candidates():
        paths.update(value for key, value in item.items() if key.endswith("_path"))
    paths.update(item["evaluation_path"] for item in posthoc_programs())
    return paths


def owned(path):
    return path.startswith(("gyre/data/", "gyre/reference/")) or path in AUTHORED


def integrity(bundle):
    privacy.detector_selftest()
    require(not privacy.scan_artifacts(bundle), "privacy", "publication contains a privacy indicator")
    manifest = load(bundle, MANIFEST)
    require(manifest.get("schema") == "gyre-public-evidence/1", "manifest", "wrong manifest schema")
    require(same(manifest.get("counts"), COUNTS), "corpus", "wrong fixed-pilot denominator")
    require(same(manifest.get("posthoc_scope"), {
        "definitions": "gyre/data/addenda/known-counterexamples.json",
        "cases": 3, "candidate_probes": 60, "seed_probes": 3,
        "recorded_cases": "gyre/data/posthoc/cases.json",
        "recorded_summary": "gyre/data/posthoc/summary.json",
        "recorded_evaluation_files": 21, "recorded_measurements": 63,
        "included_in_frozen_denominators": False,
    }), "corpus", "post-hoc scope is missing or mixed into frozen denominators")
    require(
        manifest.get("provenance", {}).get("reference_commit") == REFERENCE_COMMIT,
        "reference", "wrong canonical commit",
    )
    entries = manifest.get("files")
    require(isinstance(entries, list) and entries, "manifest", "empty file inventory")
    paths = []
    for entry in entries:
        require(isinstance(entry, dict), "manifest", "invalid file entry")
        path = entry.get("path")
        require(isinstance(path, str), "manifest", "invalid artifact path")
        parsed = PurePosixPath(path)
        require(
            not parsed.is_absolute() and ".." not in parsed.parts and "\\" not in path
            and parsed.as_posix() == path and owned(path) and path != MANIFEST,
            "manifest", "artifact outside declared scope",
        )
        paths.append(path)
        require(path in bundle, "corpus", "manifest artifact missing")
        require(type(entry.get("size")) is int and entry["size"] == len(bundle[path]), "integrity", "artifact size mismatch")
        require(entry.get("sha256") == digest(bundle[path]), "integrity", "artifact hash mismatch")
        origin = entry.get("provenance", {})
        require(origin.get("mode") in {"byte-identical", "projection", "publication-authored", "publication-derived"}, "manifest", "unclassified provenance")
        if origin["mode"] == "byte-identical":
            require(origin.get("source_sha256") == entry["sha256"], "integrity", "raw-byte identity mislabeled")
        else:
            require("source_sha256" not in origin, "manifest", "projection mislabeled with raw-byte hash")
    require(len(set(paths)) == len(paths), "manifest", "duplicate manifest path")
    require(required_paths() <= set(paths), "corpus", "partial fixed-pilot corpus")
    actual = {path for path in bundle if owned(path) and path != MANIFEST}
    require(actual == set(paths), "corpus", "unbound or missing publication artifact")
    extras = actual - required_paths()
    require(all(path.startswith("gyre/data/addenda/") for path in extras), "corpus", "unexpected experimental material")
    for path, expected in PINNED.items():
        require(digest(bundle[path]) == expected, "reference", "pinned contract or reference changed")
    provenance = load(bundle, "gyre/reference/provenance.json")
    require(provenance.get("commit") == REFERENCE_COMMIT, "reference", "reference provenance drift")
    require(
        provenance.get("files") == {Path(p).name: h for p, h in PINNED.items() if Path(p).name in {"rapp.py", "rapp_check.py", "LICENSE"}},
        "reference", "reference file pins drift",
    )
    require(provenance["interpreter"]["sha256"] == PINNED["gyre/reference/interpreter.py"], "reference", "interpreter provenance drift")
    require(provenance["oracle"]["initial_sha256"] == PINNED["gyre/reference/oracle.py"], "reference", "oracle provenance drift")
    addenda = load(bundle, "gyre/data/addenda.json")
    require(addenda.get("schema") == "gyre-evidence-addenda/1" and isinstance(addenda.get("entries"), list), "addenda", "invalid addendum ledger")
    referenced = set()
    for entry in addenda["entries"]:
        require(isinstance(entry, dict) and isinstance(entry.get("description"), str), "addenda", "missing correction description")
        for subject in entry.get("subjects", []):
            path = subject.get("path")
            require(path in actual and digest(bundle[path]) == subject.get("sha256"), "addenda", "correction does not bind its subject")
        for path in entry.get("artifacts", []):
            require(path in extras or (path in actual and path.startswith("gyre/data/posthoc/")), "addenda", "missing supplemental artifact")
            if path in extras:
                referenced.add(path)
    require(extras == referenced, "addenda", "orphaned supplemental artifact")
    return manifest


def trusted_tools(root, bundle):
    """Import only checked, fixed reference code; never import a candidate."""
    directory = Path(root).resolve() / "gyre/reference"
    for name in ("rapp", "rapp_check", "interpreter", "oracle"):
        path = "gyre/reference/" + name + ".py"
        require(digest(bundle[path]) == PINNED[path], "reference", "unchecked execution tool")
        require((directory / (name + ".py")).read_bytes() == bundle[path], "reference", "execution tool differs from checked snapshot")
    sys.path.insert(0, str(directory))
    try:
        tools = tuple(importlib.import_module(name) for name in ("rapp", "rapp_check", "interpreter", "oracle"))
    finally:
        sys.path.pop(0)
    for module in tools:
        require(Path(module.__file__).resolve().parent == directory, "reference", "unintended reference module")
    return tools


def fixture_gold(bundle, oracle):
    fixture = load(bundle, "gyre/data/cases.json")
    require(set(fixture) == {"original", "selection", "audit", "gold_method", "rng_seed_hex"}, "corpus", "wrong fixture shape")
    expected = {
        "original": (
            [(f"old-valid-{n}", "original") for n in range(8)]
            + [(f"old-random-{n}", "original") for n in range(12)]
            + [(f"old-error-{n}", "original") for n in range(19)]
        ),
        "selection": (
            [(f"new-fixed-{n}", "new-valid") for n in range(10)]
            + [(f"select-{n:03d}", "new-valid") for n in range(30)]
            + [(f"new-invalid-{n}", "new-invalid") for n in range(30)]
        ),
        "audit": (
            [(f"audit-original-{n}", "original") for n in range(15)]
            + [(f"audit-{n:03d}", "new-valid") for n in range(80)]
            + [(name, "new-valid") for name in ("audit-depth-12", "audit-boundary-256", "audit-empty-validated")]
            + [(f"audit-invalid-{n}", "new-invalid") for n in range(21)]
        ),
    }
    all_ids = []
    for phase, identities in expected.items():
        cases = fixture[phase]
        require(isinstance(cases, list) and len(cases) == len(identities), "corpus", "missing frozen case")
        for case, (identifier, family) in zip(cases, identities):
            require(set(case) == {"id", "family", "expression", "expected"}, "corpus", "invalid case definition")
            require(case["id"] == identifier and case["family"] == family, "corpus", "case identity or family changed")
            all_ids.append(identifier)
            try:
                outcome = {"kind": "value", "value": oracle.solve(case["expression"])}
            except ValueError:
                outcome = {"kind": "error", "error": "ValueError"}
            require(same(outcome, case["expected"]), "oracle", "frozen gold disagrees with independent contract grammar")
    require(len(all_ids) == len(set(all_ids)) == 228, "corpus", "wrong unique-case denominator")
    return fixture


def grade(evaluation, cases):
    families, rows = {}, []
    for result, case in zip(evaluation["results"], cases):
        correct = same(result["outcome"], case["expected"])
        family = families.setdefault(case["family"], {"correct": 0, "total": 0})
        family["total"] += 1
        family["correct"] += int(correct)
        rows.append({
            "id": case["id"], "family": case["family"], "correct": correct,
            "actual": result["outcome"], "expected": case["expected"],
        })
    original = families["original"]
    return {
        "admitted": evaluation["admitted"], "admission_reason": None,
        "families": families,
        "original_preserved": evaluation["admitted"] and original["correct"] == original["total"],
        "all_correct": evaluation["admitted"] and all(row["correct"] for row in rows),
        "ast_nodes": evaluation["ast_nodes"], "rows": rows,
    }


def replay_measurement(bundle, source, cases, evaluation_path, score_path, interpreter):
    observed = load(bundle, evaluation_path)
    require(set(observed) == {"admitted", "ast_nodes", "elapsed_ms", "results"}, "measurement", "incomplete evaluation metadata")
    require(observed["admitted"] is True, "measurement", "missing admission measurement")
    require(type(observed["elapsed_ms"]) is int and observed["elapsed_ms"] >= 0, "measurement", "invalid recorded duration")
    results = observed["results"]
    require(isinstance(results, list) and len(results) == len(cases), "measurement", "missing measurement or wrong denominator")
    require([row.get("id") for row in results] == [case["id"] for case in cases], "measurement", "measurement identities are incomplete or reordered")
    replay = interpreter.evaluate(source, cases)
    require(replay.get("admitted") is True, "semantic", "candidate is not admitted by the fixed interpreter")
    require(len(replay["results"]) == len(cases), "semantic", "interpreter returned a partial corpus")
    for recorded, actual, case in zip(results, replay["results"], cases):
        require(set(recorded) == {"id", "outcome", "steps"}, "measurement", "incomplete per-case measurement")
        if case["family"] == "original":
            require(same(actual["outcome"], case["expected"]), "regression", "program lost frozen original-use-case behavior")
        require(same(recorded["outcome"], actual["outcome"]), "semantic", "recorded outcome differs from bounded replay")
    for recorded, actual in zip(results, replay["results"]):
        require(type(recorded["steps"]) is int and recorded["steps"] == actual["steps"], "measurement", "recorded instruction count differs from replay")
    require(type(observed["ast_nodes"]) is int and observed["ast_nodes"] == replay["ast_nodes"], "measurement", "recorded AST size differs from replay")
    score = grade(replay, cases)
    require(same(load(bundle, score_path), score), "score", "recorded score differs from independently derived score")
    return score


def check_frames(bundle, R):
    frames = {}
    streams = [(
        "gyre/data/streams/seed/rappid.json", ["gyre/data/streams/seed/frames/0.json"],
        "gyre-selector-seed",
    )]
    for item in candidates():
        streams.append((
            item["identity_path"], [item["source_frame_path"], item["evaluated_frame_path"]],
            item["candidate_id"],
        ))
    identities = set()
    for identity_path, paths, slug in streams:
        identity = load(bundle, identity_path)
        require(set(identity) == {"schema", "rappid", "kind", "name"}, "chain", "invalid stream identity record")
        rid = identity["rappid"]
        require(
            identity["schema"] == "rapp/1" and R.rappid_valid(rid)
            and re.fullmatch("rappid:@example/" + re.escape(slug) + r":[0-9a-f]{64}", rid),
            "chain", "stream record is not the expected synthetic identity",
        )
        require(rid not in identities, "chain", "duplicate stream identity")
        identities.add(rid)
        head = None
        for path in paths:
            frame = load(bundle, path)
            okay, _, _ = R.verify_frame(frame, head=head, stream_id_of_record=rid)
            require(okay, "chain", "canonical frame or particle link failed")
            require(frame["sig"] is None and frame["prev_wave"] is None, "chain", "unexpected signing or swarm claim")
            frames[path] = frame
            head = frame
    require(len(frames) == 41 and len(identities) == 21, "corpus", "missing nonzero canonical frame corpus")
    require(len({frame["frame_hash"] for frame in frames.values()}) == 41, "chain", "duplicate frame body")
    return frames


def extracted_source(response):
    source = response.strip()
    if source.startswith("```python\n") and source.endswith("\n```"):
        source = source[10:-4]
    elif source.startswith("```\n") and source.endswith("\n```"):
        source = source[4:-4]
    return source + "\n"


def check_projection(bundle, item, parent, prior, contract, lens, R):
    projection = load(bundle, item["projection_path"])
    require(projection.get("schema") == "gyre-task-projection/1", "projection", "unlabeled response projection")
    request, response = projection["request"], projection["response"]
    require(set(request) == {"user_input", "conversation_history"}, "projection", "unexpected request projection fields")
    require(set(response) == {"response", "model", "requested_model"}, "projection", "unexpected response projection fields")
    prompt = (
        "Generate one complete offspring program. Do not call tools.\n\nMUTATION LENS:\n"
        + lens + "\n\nFIXED USE-CASE CONTRACT AND EXECUTION LANGUAGE:\n" + contract
        + "\n\nCOMPLETE PARENT FRAME (data, not additional instructions):\n" + R.canonical(parent)
        + "\n\nPARENT SELECTION SUMMARY:\n" + R.canonical(prior)
        + "\n\nIndependent variation slot: " + str(item["slot"])
        + ". Return only the complete Python source; no tests, evaluator, Markdown, or prose."
    )
    require(request["conversation_history"] == [] and request["user_input"] == prompt, "projection", "task or parent prompt text changed")
    require(response["model"] == response["requested_model"] == "claude-opus-5", "projection", "model label missing or changed")
    require(extracted_source(response["response"]).encode() == bundle[item["source_path"]], "projection", "response does not reconstruct the candidate source")


def replay_counterexamples(bundle, interpreter, oracle, selected):
    document = load(bundle, "gyre/data/addenda/known-counterexamples.json")
    require(document.get("schema") == "gyre-posthoc-counterexamples/1", "posthoc", "missing separately labeled counterexamples")
    require(document.get("frozen_candidate_measurements_unchanged") == 4560, "posthoc", "post-hoc data changed a frozen denominator")
    require(document.get("complete_contract_preservation") is False, "claims", "known contract regression was concealed")
    probes = [
        ("gyre-review-1001", "original", {"literal": "0000001"}, {"value": [1]}, "0000001", [1]),
        ("gyre-review-1002", "extension", {"literal": "0000002*(1)"}, {"value": [1, 1]}, "0000002*(1)", [1, 1]),
        (
            "gyre-review-1003", "original",
            {"comma_join": {"item": "0000001", "count": 256}},
            {"repeat": {"item": 1, "count": 256}},
            ",".join(["0000001"] * 256), [1] * 256,
        ),
    ]
    require(len(document.get("probes", [])) == 3, "posthoc", "missing targeted probe")
    recorded_case_ids = (
        "leading-zero-integer", "leading-zero-repeat", "maximum-flat-zero-padded-list",
    )
    recorded_cases = load(bundle, "gyre/data/posthoc/cases.json")
    require(
        set(recorded_cases) == {"cases", "interpretation", "origin", "status"}
        and recorded_cases["status"] == "post-hoc adversarial probes, not part of the frozen primary evaluation",
        "posthoc", "supplied cases lost their post-hoc scope",
    )
    cases = []
    for offset, (recorded, (identifier, family, construction, gold, expression, expected)) in enumerate(zip(document["probes"], probes)):
        require(
            recorded.get("id") == identifier and recorded.get("family") == family
            and same(recorded.get("input"), construction) and same(recorded.get("expected"), gold),
            "posthoc", "targeted counterexample definition changed",
        )
        require(same(oracle.solve(expression), expected), "oracle", "post-hoc gold disagrees with contract grammar")
        cases.append({
            "id": recorded_case_ids[offset], "expression": expression,
            "expected": {"kind": "value", "value": expected}, "scope": family + "-contract",
        })
    require(same(recorded_cases["cases"], cases), "posthoc", "supplied post-hoc gold or case definition differs from independent reconstruction")
    supplied = load(bundle, "gyre/data/posthoc/summary.json")
    require(
        set(supplied) == {"caution", "results", "schema", "status", "subjects"}
        and supplied["schema"] == "gyre-posthoc-contract-probes/1"
        and supplied["status"] == "post-hoc; not preregistered; original data unchanged"
        and same(supplied["subjects"], 21),
        "posthoc", "supplied summary has the wrong scope or denominator",
    )
    programs = posthoc_programs()
    require(isinstance(supplied["results"], list) and len(supplied["results"]) == 21, "posthoc", "partial post-hoc summary")
    supplied_by_program = {}
    for row in supplied["results"]:
        require(isinstance(row, dict) and isinstance(row.get("program"), str), "posthoc", "invalid post-hoc program identity")
        require(row["program"] not in supplied_by_program, "posthoc", "duplicate post-hoc subject")
        supplied_by_program[row["program"]] = row
    require(set(supplied_by_program) == {item["program"] for item in programs}, "posthoc", "missing post-hoc subject")
    provenance = load(bundle, "gyre/data/posthoc/provenance.json")
    expected_provenance = [
        {
            **item, "source_sha256": digest(bundle[item["source_path"]]),
            "frame_hash": load(bundle, item["frame_path"])["frame_hash"],
        }
        for item in programs
    ]
    require(
        provenance.get("schema") == "gyre-posthoc-publication/1"
        and provenance.get("case_definitions") == "gyre/data/posthoc/cases.json"
        and provenance.get("recorded_summary") == "gyre/data/posthoc/summary.json"
        and same(provenance.get("programs"), expected_provenance),
        "posthoc", "supplied post-hoc data is not bound to the frozen sources and frames",
    )
    observations, summaries, augmented_candidates = {}, [], 0
    for item in programs:
        identifier = item["candidate_id"]
        source = bundle[item["source_path"]].decode()
        if identifier != "seed":
            augmented_candidates += int(any(isinstance(node, ast.AugAssign) for node in ast.walk(ast.parse(source))))
        recorded = load(bundle, item["evaluation_path"])
        require(
            set(recorded) == {"admitted", "ast_nodes", "elapsed_ms", "results"}
            and recorded["admitted"] is True
            and type(recorded["elapsed_ms"]) is int and recorded["elapsed_ms"] >= 0,
            "posthoc", "incomplete supplied post-hoc evaluator metadata",
        )
        require(
            isinstance(recorded["results"], list) and len(recorded["results"]) == 3
            and [row.get("id") for row in recorded["results"]] == list(recorded_case_ids),
            "posthoc", "missing or duplicate supplied post-hoc measurement",
        )
        evaluation = interpreter.evaluate(source, cases)
        require(evaluation.get("admitted") is True and len(evaluation["results"]) == 3, "posthoc", "missing post-hoc execution")
        require(
            same({key: value for key, value in recorded.items() if key != "elapsed_ms"}, evaluation),
            "posthoc", "supplied evaluator output differs from bounded replay",
        )
        expected_summary = {
            "program": item["program"], "admitted": evaluation["admitted"],
            "probes": [
                {
                    "id": case["id"], "scope": case["scope"],
                    "matches_contract": same(row["outcome"], case["expected"]),
                    "outcome": row["outcome"], "steps": row["steps"],
                }
                for row, case in zip(evaluation["results"], cases)
            ],
        }
        require(same(supplied_by_program[item["program"]], expected_summary), "posthoc", "supplied summary differs from independently graded post-hoc behavior")
        observations[identifier] = evaluation["results"]
        summaries.append({
            "program": identifier,
            "cases": [
                {
                    "case": case["id"], "correct": same(row["outcome"], case["expected"]),
                    "kind": row["outcome"]["kind"], "error": row["outcome"].get("error"),
                    "steps": row["steps"],
                }
                for row, case in zip(evaluation["results"], cases)
            ],
        })
    bad = observations["gyre-speculative-1-1"]
    require(all(row["outcome"] == {"kind": "error", "error": "ValueError"} for row in bad), "posthoc", "reported leading-zero regression no longer reproduces")
    expected_limited = {
        "gyre-speculative-1-2", "gyre-direct-1-0", "gyre-direct-1-3",
        *(f"gyre-direct-2-{slot}" for slot in range(5)),
    }
    limited = {
        identifier for identifier, rows in observations.items()
        if rows[2]["outcome"].get("error") == "GuestLimit"
    }
    require(limited == expected_limited, "posthoc", "the reported resource-failure subjects no longer reproduce")
    require(all(observations[identifier][2]["steps"] == 120001 for identifier in limited), "posthoc", "reported resource-failure step count changed")
    bad_frame_path = next(item["evaluated_frame_path"] for item in candidates() if item["candidate_id"] == "gyre-speculative-1-1")
    require(all(choice["frame_path"] != bad_frame_path for choice in selected.values()), "posthoc", "unselected counterexample status changed")
    long_expected = cases[2]["expected"]
    seed = observations["seed"][2]
    require(same(seed["outcome"], long_expected) and seed["steps"] == 29215, "posthoc", "seed resource-baseline countercheck differs")
    require(
        same(observations["seed"][0]["outcome"], cases[0]["expected"])
        and observations["seed"][1]["outcome"] == {"kind": "error", "error": "ValueError"},
        "posthoc", "seed original-scope versus extension-scope behavior changed",
    )
    selected_behavior = {}
    for (arm, generation), choice in selected.items():
        item = next(item for item in candidates() if item["evaluated_frame_path"] == choice["frame_path"])
        observed = observations[item["candidate_id"]][2]
        if arm == "direct":
            require(
                observed["outcome"].get("kind") == "execution_error"
                and observed["outcome"].get("error") == "GuestLimit" and observed["steps"] == 120001,
                "posthoc", "selected direct resource counterexample no longer reproduces",
            )
        else:
            require(same(observed["outcome"], long_expected), "posthoc", "selected speculative long-probe observation changed")
        selected_behavior[f"{arm}-g{generation}"] = {
            "program": item["candidate_id"], "correct": same(observed["outcome"], long_expected),
            "error": observed["outcome"].get("error"), "steps": observed["steps"],
        }
    require(augmented_candidates == 0, "posthoc", "augmented-assignment applicability changed")
    semantics = document.get("execution_semantics", {})
    require(semantics.get("frozen_candidates_with_augassign") == 0 and semantics.get("native_guest_countercheck_performed") is False, "claims", "restricted interpreter boundary was misstated")
    candidate_summaries = [program for program in summaries if program["program"] != "seed"]
    failed_by_probe = {
        probe[0]: sum(not program["cases"][offset]["correct"] for program in candidate_summaries)
        for offset, probe in enumerate(probes)
    }
    return {
        "status": "Known post-hoc failures reproduced; frozen tallies remain unchanged.",
        "universal_contract_correctness": False,
        "candidate_probes": 60, "seed_probes": 3, "total_probes": 63,
        "recorded_measurements_checked": 63, "recorded_evaluation_files": 21,
        "recorded_summary": "gyre/data/posthoc/summary.json",
        "candidate_failures_by_probe": failed_by_probe,
        "candidate_failures_by_recorded_probe": {
            recorded_case_ids[offset]: failed_by_probe[probe[0]]
            for offset, probe in enumerate(probes)
        },
        "long_probe_failure_programs": sorted(limited | {"gyre-speculative-1-1"}),
        "selected_parent_long_probe": selected_behavior,
        "seed_long_probe_steps": seed["steps"],
        "frozen_candidates_with_augassign": augmented_candidates,
        "native_guest_countercheck_performed": False,
        "boundary": "Targeted post-hoc diagnosis, not preregistered confirmation or evidence of a prompt-arm advantage.",
        "programs": summaries,
    }


def validate(bundle, tools):
    manifest = integrity(bundle)
    R, _, interpreter, oracle = tools
    fixture = fixture_gold(bundle, oracle)
    frames = check_frames(bundle, R)
    require(same(load(bundle, "gyre/data/candidates.json"), candidates()), "corpus", "candidate inventory is not the complete matched design")
    protocol = load(bundle, "gyre/data/protocol.json")
    for key, value in {
        "reference_commit": REFERENCE_COMMIT, "generations": 2,
        "offspring_per_arm_per_generation": 5, "total_candidate_requests": 20,
        "model": "claude-opus-5", "original_cases": 39, "selection_cases": 70, "audit_cases": 119,
        "fixture_sha256": digest(bundle["gyre/data/cases.json"]),
    }.items():
        require(same(protocol.get(key), value), "protocol", "fixed protocol metadata drift")
    require(set(protocol["conditions"]) == set(ARMS), "protocol", "missing mutation instruction")
    contract = bundle["gyre/data/contract.txt"].decode()
    main_cases = fixture["original"] + fixture["selection"]
    seed = frames["gyre/data/streams/seed/frames/0.json"]
    seed_source = bundle["gyre/data/seed.py"].decode()
    require(seed["kind"] == "program.genesis" and seed["payload"]["generation"] == 0, "lineage", "invalid seed")
    require(seed["payload"]["source"] == seed_source and seed["payload"]["source_sha256"] == digest(bundle["gyre/data/seed.py"]), "source", "seed source differs from its frame")
    seed_score = replay_measurement(bundle, seed_source, main_cases, "gyre/data/seed-evaluation.json", "gyre/data/seed-score.json", interpreter)
    require(seed_score["original_preserved"], "regression", "seed lost original use cases")
    selections_document = load(bundle, "gyre/data/selections.json")
    require(selections_document.get("schema") == "gyre-parent-selections/1", "selection", "unlabeled parent-selection projection")
    selections = selections_document["selections"]
    require(set(selections) == {"generation_1", "generation_2"}, "selection", "missing parent selection")
    path_map = load(bundle, "gyre/data/artifact-map.json")["paths"]
    expected_map = {"seed-frame.json": "gyre/data/streams/seed/frames/0.json"}
    for item in candidates():
        historical = f"workers/{item['arm']}-{item['slot']}/g{item['generation']}"
        for key, old_name in (
            ("source_path", "candidate.py"), ("evaluation_path", "evaluation.json"),
            ("score_path", "score.json"), ("audit_evaluation_path", "audit-evaluation.json"),
            ("audit_score_path", "audit-score.json"),
            ("source_frame_path", "source-frame.json"), ("evaluated_frame_path", "evaluated-frame.json"),
        ):
            expected_map[historical + "/" + old_name] = item[key]
    require(same(path_map, expected_map), "lineage", "historical artifact projection is incomplete")
    reverse_map = {value: key for key, value in path_map.items()}
    scores, audits, selected, source_hashes, ast_hashes = {}, {}, {}, set(), set()
    for generation in (1, 2):
        generation_key = f"generation_{generation}"
        require(set(selections[generation_key]) == set(ARMS), "selection", "missing arm selection")
        for arm in ARMS:
            if generation == 1:
                parent = seed
                prior = {"source": "seed", "score": seed_score["families"]}
            else:
                previous = selected[(arm, generation - 1)]
                parent = frames[previous["frame_path"]]
                prior = dict(previous)
                for key in ("frame_path", "source_frame_path"):
                    prior[key] = reverse_map[prior[key]] if prior[key] else None
            group = [item for item in candidates() if item["arm"] == arm and item["generation"] == generation]
            ranking = []
            for item in group:
                source = bundle[item["source_path"]].decode()
                source_hash = digest(bundle[item["source_path"]])
                source_hashes.add(source_hash)
                ast_hashes.add(digest(ast.dump(ast.parse(source), include_attributes=False).encode()))
                source_frame = frames[item["source_frame_path"]]
                evaluated_frame = frames[item["evaluated_frame_path"]]
                payload = source_frame["payload"]
                require(source_frame["kind"] == "program.candidate" and evaluated_frame["kind"] == "program.evaluated", "lineage", "wrong source/evaluation frame roles")
                require(payload["source"] == source and payload["source_sha256"] == source_hash, "source", "candidate source differs from its source frame")
                require(source != parent["payload"]["source"], "lineage", "offspring is unchanged from its selected parent")
                for key, expected in {
                    "schema": "gyre-program/1", "entrypoint": "solve", "generation": generation,
                    "arm": arm, "slot": item["slot"], "parent_frame_hash": parent["frame_hash"],
                    "parent_stream_id": parent["stream_id"], "lens": protocol["conditions"][arm],
                    "contract_sha256": PINNED["gyre/data/contract.txt"], "model_reported": "claude-opus-5",
                }.items():
                    require(same(payload.get(key), expected), "lineage", "parent provenance or task binding differs")
                check_projection(bundle, item, parent, prior, contract, protocol["conditions"][arm], R)
                score = replay_measurement(bundle, source, main_cases, item["evaluation_path"], item["score_path"], interpreter)
                require(score["original_preserved"], "regression", "candidate lost frozen original-use-case behavior")
                require(score["all_correct"], "semantic", "candidate does not satisfy frozen selection cases")
                expected_payload = {
                    **payload, "evaluation": {key: value for key, value in score.items() if key != "rows"},
                    "evaluation_artifact_sha256": digest(bundle[item["evaluation_path"]]),
                }
                require(same(evaluated_frame["payload"], expected_payload), "measurement", "evaluation frame disagrees with replayed source or measurement")
                identifier = item["candidate_id"]
                scores[identifier] = score
                audit = replay_measurement(bundle, source, fixture["audit"], item["audit_evaluation_path"], item["audit_score_path"], interpreter)
                require(audit["all_correct"] and audit["original_preserved"], "semantic", "candidate fails reserved audit or original regression")
                audits[identifier] = audit
                novel_correct = sum(part["correct"] for family, part in score["families"].items() if family != "original")
                if score["original_preserved"]:
                    ranking.append(((-novel_correct, score["ast_nodes"], source_hash), item, score))
            require(len(ranking) == 5, "selection", "missing eligible offspring")
            _, winner, winner_score = min(ranking, key=lambda row: row[0])
            choice = {
                "frame_path": winner["evaluated_frame_path"],
                "source_frame_path": winner["source_frame_path"],
                "frame_hash": frames[winner["evaluated_frame_path"]]["frame_hash"],
                "parent_changed": True, "score": winner_score["families"],
            }
            require(same(selections[generation_key][arm], choice), "selection", "recorded parent violates independent eligibility/ranking")
            selected[(arm, generation)] = choice
    require(len(source_hashes) == len(ast_hashes) == 20, "corpus", "candidate source/AST diversity denominator changed")
    page_selection = load(bundle, "gyre/data/selection-g2.json")
    expected_page_selection = {}
    for arm in ARMS:
        choice = dict(selected[(arm, 2)])
        for key in ("frame_path", "source_frame_path"):
            choice[key] = choice[key].removeprefix("gyre/data/") if choice[key] else None
        expected_page_selection[arm] = choice
    require(same(page_selection, expected_page_selection), "selection", "page selection differs from the independently selected parent")
    aggregate = {}
    for arm in ARMS:
        aggregate[arm] = {}
        for generation in (1, 2):
            group = [item for item in candidates() if item["arm"] == arm and item["generation"] == generation]
            winner = next(item for item in group if item["evaluated_frame_path"] == selected[(arm, generation)]["frame_path"])
            selected_audit = audits[winner["candidate_id"]]
            aggregate[arm][f"generation_{generation}"] = {
                "candidates": len(group),
                "admitted": sum(scores[item["candidate_id"]]["admitted"] for item in group),
                "original_preserved": sum(scores[item["candidate_id"]]["original_preserved"] for item in group),
                "selection_flag_captured": sum(scores[item["candidate_id"]]["all_correct"] for item in group),
                "audit_flag_captured": sum(audits[item["candidate_id"]]["all_correct"] and scores[item["candidate_id"]]["original_preserved"] for item in group),
                "selected_parent_audit": selected_audit["families"],
                "selected_parent_all_audit_correct": selected_audit["all_correct"],
            }
    report = load(bundle, "gyre/data/observed-report.json")
    for key, value in {
        "aggregate": aggregate, "seed": seed_score["families"], "model": "claude-opus-5",
        "candidate_requests": 20, "generations": 2,
    }.items():
        require(same(report.get(key), value), "aggregate", "original report disagrees with independent replay")
    results = load(bundle, "gyre/data/results.json")
    for key, value in report.items():
        if key != "limitations":
            require(same(results.get(key), value), "aggregate", "public aggregate altered an original observation")
    require(results["limitations"][:len(report["limitations"])] == report["limitations"], "claims", "original limitations removed")
    require(len(results["limitations"]) >= len(report["limitations"]) + 7, "claims", "public-boundary limitations omitted")
    require(same(results["publication"]["counts"], COUNTS), "corpus", "rendered results use a different denominator")
    require(results["publication"]["original_report"] in bundle and results["publication"]["addenda"] in bundle, "corpus", "dangling results artifact reference")
    require(results["publication"].get("original_floor_label") == "Passed frozen original-floor cases", "claims", "frozen-case floor was mislabeled as complete-contract preservation")
    require(results["publication"].get("complete_contract_preservation") is False, "claims", "known complete-contract counterexamples were omitted")
    require(results["publication"].get("known_counterexamples") == "gyre/data/addenda/known-counterexamples.json", "claims", "missing known-counterexample disclosure")
    require(same(results["publication"].get("posthoc_counts"), {"cases": 3, "candidate_probes": 60, "seed_probes": 3}), "corpus", "rendered post-hoc counts differ from their separate scope")
    require(results["publication"].get("posthoc_recorded_summary") == "gyre/data/posthoc/summary.json", "claims", "missing supplied post-hoc observations")
    posthoc = replay_counterexamples(bundle, interpreter, oracle, selected)
    for phase in ("before", "after"):
        demo = load(bundle, f"gyre/data/model-demos/{phase}.json")
        require(demo["response"]["response"] == "", "claims", "a successful model demo was synthesized")
        require(demo["response"]["model"] == demo["response"]["requested_model"] == "claude-opus-5", "claims", "demo model observation changed")
        require(demo["request"]["conversation_history"] == [], "claims", "unexpected demo history")
        require(demo["outcome"] == "empty model response; no successful model-mediated tool demonstration", "claims", "blocked-demo limitation removed")
    local = load(bundle, "gyre/data/local-hotload.json")
    live_case = [{"id": "live", "expression": "2*(1,2*(3)),0"}]
    for phase, frame in (("before", seed), ("after", frames[selected[("speculative", 2)]["frame_path"]])):
        require(local[phase]["frame_hash"] == frame["frame_hash"], "claims", "local check references the wrong program")
        require(same(local[phase]["result"], interpreter.evaluate(frame["payload"]["source"], live_case)), "semantic", "local-demo recorded result does not replay")
    seed_audit = grade(interpreter.evaluate(seed_source, fixture["audit"]), fixture["audit"])
    return {
        "verification": "PASS", "network_or_model_calls": 0, "native_candidate_executions": 0,
        "pass_means": "Evidence replay is consistent, including known post-hoc failures; it does not mean universal program or complete-contract correctness.",
        "manifest_files": len(manifest["files"]), "privacy_exceptions": len(privacy.EXCEPTIONS),
        "canonical_frames": 41, "canonical_streams": 21, "canonical_non_genesis_links": 20,
        "independent_gold_cases": 228, "distinct_candidate_sources": len(source_hashes),
        "distinct_candidate_asts": len(ast_hashes),
        "candidate_original": {"correct": 780, "total": 780},
        "candidate_original_label": "Passed frozen original-floor cases",
        "candidate_selection": {"correct": 1400, "total": 1400},
        "candidate_audit": {"correct": 2380, "total": 2380},
        "recorded_measurements_checked": 4669,
        "program_case_replays": 4788,
        "posthoc": posthoc,
        "seed_original_and_selection": seed_score["families"],
        "seed_audit_new_replay_not_original_measurement": seed_audit["families"],
        "local_demo_result_replays": 2,
        "selected_parent_paths": {
            f"{arm}-g{generation}": value["frame_path"]
            for (arm, generation), value in selected.items()
        },
        "comparison": "Both arms saturated in generation 1; no observed speculative advantage.",
        "execution_boundary": "Fixed original bounded interpreter; independently implemented task-gold oracle, not an independent native-Python execution engine.",
        "model_demo": "Empty before/after responses retained; local result replay is not an authenticated model-mediated hotload demonstration.",
    }


def verify(root, self_test=False):
    root = Path(root).resolve()
    bundle = privacy.read_public_tree(root)
    integrity(bundle)
    tools = trusted_tools(root, bundle)
    result = validate(bundle, tools)
    verdict, findings, evidence = tools[1].check_repo(str(root / "gyre/data/streams"))
    require(verdict == "COMPLIANT" and not findings and len(evidence) == 42, "chain", "canonical repository checker did not verify 21 identities and 21 nonempty chains")
    result["canonical_checker"] = {"verdict": verdict, "positive_evidence_entries": len(evidence)}
    if self_test:
        from test_evidence import run_selftests
        try:
            result["self_tests"] = run_selftests(root, bundle, tools)
        except Exception as error:
            raise EvidenceError("self-test", "adversarial detector/control test failed") from error
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root, args.self_test), sort_keys=True, indent=2))
        return 0
    except EvidenceError as error:
        print(json.dumps({"verification": "FAIL", "gate": error.gate, "reason": error.reason}))
        return 1
    except (OSError, ValueError, KeyError, TypeError, IndexError, RecursionError):
        print('{"verification":"FAIL","gate":"structure","reason":"malformed or unreadable publication"}')
        return 1


if __name__ == "__main__":
    sys.exit(main())
