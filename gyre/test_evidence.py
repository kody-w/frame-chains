"""Stdlib-only adversarial tests. All corrupted releases exist only in memory."""

import ast
import io
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
import privacy
import export as exporter
import verify as V

_CONTEXT = None


def rebind(bundle):
    ledger = V.load(bundle, "gyre/data/addenda.json")
    for entry in ledger["entries"]:
        for subject in entry.get("subjects", []):
            if subject["path"] in bundle:
                subject["sha256"] = V.digest(bundle[subject["path"]])
    bundle["gyre/data/addenda.json"] = V.encoded(ledger)
    manifest = V.load(bundle, V.MANIFEST)
    for entry in manifest["files"]:
        raw = bundle[entry["path"]]
        entry["sha256"] = V.digest(raw)
        entry["size"] = len(raw)
        if entry["provenance"]["mode"] == "byte-identical":
            entry["provenance"]["source_sha256"] = entry["sha256"]
    bundle[V.MANIFEST] = V.encoded(manifest)


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _CONTEXT is None:
            cls.root = Path(__file__).resolve().parent.parent
            cls.bundle = privacy.read_public_tree(cls.root)
            V.integrity(cls.bundle)
            cls.tools = V.trusted_tools(cls.root, cls.bundle)
        else:
            cls.root, cls.bundle, cls.tools = _CONTEXT
        cls.R, _, cls.interpreter, cls.oracle = cls.tools
        cls.item = next(item for item in V.candidates() if item["candidate_id"] == "gyre-direct-1-1")

    def changed(self):
        return dict(self.bundle)

    def rejected(self, bundle, gate, integrity_passes=False):
        if integrity_passes:
            V.integrity(bundle)
        with self.assertRaises(V.EvidenceError) as caught:
            V.validate(bundle, self.tools)
        self.assertEqual(caught.exception.gate, gate)

    def posthoc_rejected(self, bundle):
        V.integrity(bundle)
        selections = V.load(bundle, "gyre/data/selections.json")["selections"]
        selected = {(arm, generation): selections[f"generation_{generation}"][arm] for arm in V.ARMS for generation in (1, 2)}
        with self.assertRaises(V.EvidenceError) as caught:
            V.replay_counterexamples(bundle, self.interpreter, self.oracle, selected)
        self.assertEqual(caught.exception.gate, "posthoc")

    def restamp(self, bundle, path):
        frame = V.load(bundle, path)
        bundle[path] = V.encoded(self.R.build_frame(
            frame["kind"], frame["stream_id"], frame["seq"], frame["utc"],
            frame["payload"], frame["prev"], frame["prev_wave"], frame["sig"],
        ))

    def rebind_evaluation(self, bundle):
        frame_path = self.item["evaluated_frame_path"]
        frame = V.load(bundle, frame_path)
        frame["payload"]["evaluation_artifact_sha256"] = V.digest(bundle[self.item["evaluation_path"]])
        bundle[frame_path] = V.encoded(frame)
        self.restamp(bundle, frame_path)
        rebind(bundle)

    def behavioral_mutant(self, expression):
        bundle = self.changed()
        source = bundle[self.item["source_path"]].decode()
        function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "solve")
        lines = source.splitlines(keepends=True)
        indentation = " " * function.body[0].col_offset
        lines.insert(
            function.body[0].lineno - 1,
            indentation + "if " + function.args.args[0].arg + " == " + repr(expression) + ":\n"
            + indentation + "    return []\n",
        )
        source = "".join(lines)
        bundle[self.item["source_path"]] = source.encode()
        for key in ("source_frame_path", "evaluated_frame_path"):
            path = self.item[key]
            frame = V.load(bundle, path)
            frame["payload"]["source"] = source
            frame["payload"]["source_sha256"] = V.digest(source.encode())
            if key == "evaluated_frame_path":
                frame["prev"] = V.load(bundle, self.item["source_frame_path"])["payload_hash"]
            bundle[path] = V.encoded(frame)
            self.restamp(bundle, path)
        projection = V.load(bundle, self.item["projection_path"])
        projection["response"]["response"] = source.strip()
        bundle[self.item["projection_path"]] = V.encoded(projection)
        rebind(bundle)
        V.check_frames(bundle, self.R)
        return bundle

    def test_complete_offline_baseline(self):
        result = V.validate(self.bundle, self.tools)
        self.assertEqual(result["canonical_frames"], 41)
        self.assertEqual(result["recorded_measurements_checked"], 4669)
        self.assertEqual(result["program_case_replays"], 21 * 228)
        self.assertEqual(result["candidate_original"], {"correct": 20 * 39, "total": 20 * 39})
        self.assertEqual(result["candidate_selection"], {"correct": 20 * 70, "total": 20 * 70})
        self.assertEqual(result["candidate_audit"], {"correct": 20 * 119, "total": 20 * 119})
        self.assertEqual(result["candidate_original_label"], "Passed frozen original-floor cases")
        self.assertFalse(result["posthoc"]["universal_contract_correctness"])
        self.assertEqual(result["posthoc"]["total_probes"], 63)
        self.assertEqual(result["posthoc"]["recorded_measurements_checked"], 63)
        self.assertEqual(result["posthoc"]["recorded_evaluation_files"], 21)
        self.assertEqual(
            result["posthoc"]["candidate_failures_by_probe"],
            {"gyre-review-1001": 1, "gyre-review-1002": 1, "gyre-review-1003": 9},
        )

    def test_corrupt_hash_fails(self):
        bundle = self.changed()
        manifest = V.load(bundle, V.MANIFEST)
        manifest["files"][0]["sha256"] = "0" * 64
        bundle[V.MANIFEST] = V.encoded(manifest)
        self.rejected(bundle, "integrity")

    def test_corrupt_source_bytes_fails(self):
        bundle = self.changed()
        bundle[self.item["source_path"]] += b"\n# changed source\n"
        self.rejected(bundle, "integrity")

    def test_rehashed_source_frame_disagreement_fails(self):
        bundle = self.changed()
        bundle[self.item["source_path"]] += b"\n# source not in frame\n"
        rebind(bundle)
        self.rejected(bundle, "source", integrity_passes=True)

    def test_corrupt_frame_body_fails(self):
        bundle = self.changed()
        path = self.item["source_frame_path"]
        frame = V.load(bundle, path)
        frame["payload"]["source"] += "\n# changed frame\n"
        bundle[path] = V.encoded(frame)
        rebind(bundle)
        self.rejected(bundle, "chain", integrity_passes=True)

    def test_rehashed_wave_in_particle_link_fails(self):
        bundle = self.changed()
        path = self.item["evaluated_frame_path"]
        frame = V.load(bundle, path)
        frame["prev"] = V.load(bundle, self.item["source_frame_path"])["frame_hash"]
        bundle[path] = V.encoded(frame)
        self.restamp(bundle, path)
        rebind(bundle)
        self.rejected(bundle, "chain", integrity_passes=True)

    def test_rehashed_identity_replay_fails(self):
        bundle = self.changed()
        path = self.item["source_frame_path"]
        frame = V.load(bundle, path)
        frame["stream_id"] = frame["stream_id"].rsplit(":", 1)[0] + ":" + "0" * 64
        bundle[path] = V.encoded(frame)
        self.restamp(bundle, path)
        rebind(bundle)
        self.rejected(bundle, "chain", integrity_passes=True)

    def test_falsified_recorded_result_fails_semantics(self):
        bundle = self.changed()
        path = self.item["evaluation_path"]
        evaluation = V.load(bundle, path)
        evaluation["results"][0]["outcome"] = {"kind": "value", "value": [9]}
        bundle[path] = V.encoded(evaluation)
        self.rebind_evaluation(bundle)
        V.check_frames(bundle, self.R)
        self.rejected(bundle, "semantic", integrity_passes=True)

    def test_rehashed_wrong_target_behavior_fails_semantics(self):
        self.rejected(self.behavioral_mutant("2..-2"), "semantic", integrity_passes=True)

    def test_rehashed_original_use_case_regression_fails(self):
        self.rejected(self.behavioral_mutant("1,-2,+03"), "regression", integrity_passes=True)

    def test_missing_measurement_fails(self):
        bundle = self.changed()
        path = self.item["evaluation_path"]
        evaluation = V.load(bundle, path)
        evaluation["results"].pop()
        bundle[path] = V.encoded(evaluation)
        self.rebind_evaluation(bundle)
        self.rejected(bundle, "measurement", integrity_passes=True)

    def test_duplicate_measurement_fails(self):
        bundle = self.changed()
        path = self.item["evaluation_path"]
        evaluation = V.load(bundle, path)
        evaluation["results"][-1] = evaluation["results"][0]
        bundle[path] = V.encoded(evaluation)
        self.rebind_evaluation(bundle)
        self.rejected(bundle, "measurement", integrity_passes=True)

    def test_partial_candidate_corpus_fails_even_with_shortened_manifest(self):
        bundle = self.changed()
        removed = {value for key, value in self.item.items() if key.endswith("_path")}
        for path in removed:
            del bundle[path]
        manifest = V.load(bundle, V.MANIFEST)
        manifest["files"] = [entry for entry in manifest["files"] if entry["path"] not in removed]
        bundle[V.MANIFEST] = V.encoded(manifest)
        self.rejected(bundle, "corpus")

    def test_wrong_denominator_fails(self):
        bundle = self.changed()
        manifest = V.load(bundle, V.MANIFEST)
        manifest["counts"]["candidate_measurements"] -= 1
        bundle[V.MANIFEST] = V.encoded(manifest)
        self.rejected(bundle, "corpus")

    def test_posthoc_probes_cannot_change_frozen_denominators(self):
        bundle = self.changed()
        manifest = V.load(bundle, V.MANIFEST)
        manifest["posthoc_scope"]["included_in_frozen_denominators"] = True
        bundle[V.MANIFEST] = V.encoded(manifest)
        self.rejected(bundle, "corpus")

    def test_falsified_gold_fails_independent_oracle(self):
        bundle = self.changed()
        fixture = V.load(bundle, "gyre/data/cases.json")
        fixture["selection"][0]["expected"]["value"] = []
        bundle["gyre/data/cases.json"] = V.encoded(fixture)
        protocol = V.load(bundle, "gyre/data/protocol.json")
        protocol["fixture_sha256"] = V.digest(bundle["gyre/data/cases.json"])
        bundle["gyre/data/protocol.json"] = V.encoded(protocol)
        rebind(bundle)
        self.rejected(bundle, "oracle", integrity_passes=True)

    def test_falsified_score_fails(self):
        bundle = self.changed()
        path = self.item["score_path"]
        score = V.load(bundle, path)
        score["families"]["original"]["correct"] -= 1
        bundle[path] = V.encoded(score)
        rebind(bundle)
        self.rejected(bundle, "score", integrity_passes=True)

    def test_parent_ranking_is_recomputed(self):
        bundle = self.changed()
        document = V.load(bundle, "gyre/data/selections.json")
        document["selections"]["generation_1"]["direct"]["parent_changed"] = False
        bundle["gyre/data/selections.json"] = V.encoded(document)
        rebind(bundle)
        self.rejected(bundle, "selection", integrity_passes=True)

    def test_page_selected_source_interface(self):
        selections = V.load(self.bundle, "gyre/data/selections.json")["selections"]["generation_2"]
        page_selection = V.load(self.bundle, "gyre/data/selection-g2.json")
        self.assertEqual(set(page_selection), {"direct", "speculative"})
        for arm, choice in page_selection.items():
            path = "gyre/data/" + choice["frame_path"]
            self.assertEqual(path, selections[arm]["frame_path"])
            frame = V.load(self.bundle, path)
            self.assertEqual(frame["frame_hash"], choice["frame_hash"])
            self.assertEqual(
                V.digest(frame["payload"]["source"].encode()),
                frame["payload"]["source_sha256"],
            )

    def test_page_selection_cannot_disagree_with_replay(self):
        bundle = self.changed()
        path = "gyre/data/selection-g2.json"
        document = V.load(bundle, path)
        document["speculative"]["frame_path"] = document["direct"]["frame_path"]
        bundle[path] = V.encoded(document)
        rebind(bundle)
        self.rejected(bundle, "selection", integrity_passes=True)

    def test_missing_reserved_audit_fails(self):
        bundle = self.changed()
        del bundle[self.item["audit_evaluation_path"]]
        self.rejected(bundle, "corpus")

    def test_duplicate_json_member_fails(self):
        bundle = self.changed()
        manifest = bundle[V.MANIFEST]
        bundle[V.MANIFEST] = b'{"schema":"gyre-public-evidence/1",' + manifest.lstrip()[1:]
        self.rejected(bundle, "privacy")
        with self.assertRaises(V.EvidenceError) as caught:
            V.load(bundle, V.MANIFEST)
        self.assertEqual(caught.exception.gate, "structure")

    def test_privacy_detectors_and_all_text_extensions(self):
        result = privacy.detector_selftest()
        self.assertEqual(result["detectors"], 13)
        self.assertEqual(result["extension_probes"], 52)
        for path, raw in (
            ("gyre/data/probe.csv", b"id,expression\nworkstation-alpha,1\n"),
            ("gyre/data/probe.txt", "/".join(("", "home", "example", "record")).encode()),
            ("gyre/data/probe.py", ("# " + ".".join(("192", "0", "2", "1"))).encode()),
        ):
            self.assertTrue(privacy.scan_artifacts({path: raw}))

    def test_reference_has_no_blanket_privacy_exception(self):
        bundle = self.changed()
        path = "gyre/reference/rapp.py"
        bundle[path] += ("# " + ".".join(("192", "0", "2", "1"))).encode()
        rebind(bundle)
        self.rejected(bundle, "privacy")
        self.assertEqual(privacy.EXCEPTIONS, {})

    def test_public_review_labels_are_narrowly_classified(self):
        path = "gyre/reviews/independent-critique.json"
        document = {
            "schema": "gyre-automated-scientific-review/1",
            "major_findings": [{"id": "leading-zero-regression"}],
        }
        self.assertFalse(privacy.scan_artifacts({path: V.encoded(document)}))
        self.assertTrue(privacy.scan_artifacts({"gyre/data/probe.json": V.encoded(document)}))
        document["major_findings"][0]["id"] = "workstation-alpha"
        self.assertTrue(privacy.scan_artifacts({path: V.encoded(document)}))

    def test_escaped_identity_is_still_private(self):
        document = '{"text":"' + "\\u0040".join(("reader", "example.invalid")) + '"}'
        self.assertIn("email address", privacy.scan_artifacts({"gyre/data/probe.json": document.encode()}))

    def test_escaped_json_member_names_are_scanned(self):
        escaped = "\\u0040".join(("reader", "example.invalid"))
        for document in (
            '{"' + escaped + '":"review"}',
            '{"nested":[{"' + escaped + '":"review"}]}',
        ):
            with self.subTest(document=document):
                self.assertIn("email address", privacy.scan_artifacts({"gyre/data/probe.json": document.encode()}))

    def test_json_duplicate_members_cannot_hide_earlier_values(self):
        escaped = "\\u0040".join(("reader", "example.invalid"))
        for document in (
            '{"note":"' + escaped + '","note":"review"}',
            '{"note":"review","no' + "\\u0074" + 'e":"review"}',
            '{"nested":{"note":"' + escaped + '","note":"review"}}',
        ):
            with self.subTest(document=document):
                self.assertIn("malformed structured artifact", privacy.scan_artifacts({"gyre/data/probe.json": document.encode()}))

    def test_escaped_supplements_fail_refresh_and_full_validation(self):
        escaped = "\\u0040".join(("reader", "example.invalid"))
        for document in (
            '{"' + escaped + '":"review"}',
            '{"note":"' + escaped + '","note":"review"}',
        ):
            bundle = self.changed()
            path = "gyre/data/addenda/privacy-probe.json"
            bundle[path] = document.encode()
            ledger = V.load(bundle, "gyre/data/addenda.json")
            ledger["entries"].append({
                "id": "gyre-review-99",
                "description": "Synthetic privacy negative control.",
                "subjects": [{"path": self.item["source_path"], "sha256": V.digest(bundle[self.item["source_path"]])}],
                "artifacts": [path],
            })
            bundle["gyre/data/addenda.json"] = V.encoded(ledger)
            with self.assertRaisesRegex(ValueError, "privacy"):
                exporter.refreshed_manifest(bundle)
            manifest = V.load(bundle, V.MANIFEST)
            manifest["files"].append({
                "path": path, "size": len(bundle[path]), "sha256": V.digest(bundle[path]),
                "provenance": {"mode": "publication-authored"},
            })
            bundle[V.MANIFEST] = V.encoded(manifest)
            rebind(bundle)
            self.rejected(bundle, "privacy")

    def test_refresh_rejects_duplicate_control_members_before_normalizing(self):
        for path in (V.MANIFEST, "gyre/data/addenda.json"):
            bundle = self.changed()
            raw = bundle[path].lstrip()
            bundle[path] = b'{"duplicate":"a","duplicate":"b",' + raw[1:]
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "duplicate"):
                exporter.refreshed_manifest(bundle)

    def test_oracle_public_examples_and_original_floor(self):
        examples = [
            ("", []), (" \t\n", []), ("1, -2, +03", [1, -2, 3]),
            ("1..3", [1, 2, 3]), ("3..1", [3, 2, 1]), ("1..1", [1]),
            ("2*(1,-1)", [1, -1, 1, -1]),
            ("2*(1,2*(3)),0", [1, 3, 3, 1, 3, 3, 0]),
            (" 2 * ( -1 .. +1 ) ", [-1, 0, 1, -1, 0, 1]),
            ("0*()", []), ("20*()", []), ("02*(+01)", [1, 1]),
            ("-1000,+1000", [-1000, 1000]),
            ("\u00a0-0,\u2003+0", [0, 0]),
            (",".join(["1"] * 256), [1] * 256),
            ("0" * 5000 + "1", [1]),
        ]
        for expression, expected in examples:
            with self.subTest(length=len(expression)):
                self.assertEqual(self.oracle.solve(expression), expected)

    def test_oracle_rejects_syntax_and_nonstring_regressions(self):
        expressions = [
            None, True, 12, [], {}, "1,", ",1", "1,,2", "+", "-", "1 2",
            "1_0", "\u0661", "\uff12", "(1)", "1*(1", "1*(1))", "1*(,1)",
            "0*(bad)", "0*(2,)", "0*(0..1000)", "0*(20*(20*(1)))",
            "+2*(1)", "-0*(1)", "0*(+0*())", "21*()", "1001..0", "-1001",
            "1...2", "1 . . 2", "2*(1)..3", "1*(1)2", "1*(1),",
            ",".join(["1"] * 257), "9" * 5000,
        ]
        for expression in expressions:
            with self.subTest(input_type=type(expression).__name__):
                with self.assertRaises(ValueError):
                    self.oracle.solve(expression)

    def test_oracle_depth_and_every_subexpression_bound(self):
        self.assertEqual(self.oracle.solve("1*(" * 12 + "7" + ")" * 12), [7])
        self.assertEqual(self.oracle.solve("16*(16*(9))"), [9] * 256)
        self.assertEqual(self.oracle.solve("0*(16*(16*(9)))"), [])
        self.assertEqual(self.oracle.solve("-127..128"), list(range(-127, 129)))
        for expression in (
            "1*(" * 13 + "7" + ")" * 13,
            "0*(17*(16*(9)))", "0*(-128..128)", "0*(0..255,256)",
            "0*(1*(" * 7 + "1" + "))" * 7,
        ):
            with self.assertRaises(ValueError):
                self.oracle.solve(expression)

    def test_interpreter_rejects_native_capabilities(self):
        sources = [
            "import os\ndef solve(expression):\n    return []\n",
            "def solve(expression):\n    return expression.__class__\n",
            "def solve(expression):\n    return open(expression)\n",
            "def solve(expression):\n    return [x for x in expression]\n",
            "def solve(expression):\n    while True:\n        pass\n",
        ]
        for source in sources:
            result = self.interpreter.evaluate(source, [{"id": "live", "expression": ""}])
            self.assertTrue(not result["admitted"] or result["results"][0]["outcome"]["kind"] == "execution_error")

    def test_known_counterexamples_cannot_be_labeled_complete_preservation(self):
        bundle = self.changed()
        path = "gyre/data/results.json"
        results = V.load(bundle, path)
        results["publication"]["complete_contract_preservation"] = True
        bundle[path] = V.encoded(results)
        rebind(bundle)
        self.rejected(bundle, "claims", integrity_passes=True)

    def test_posthoc_case_cannot_be_removed(self):
        bundle = self.changed()
        path = "gyre/data/addenda/known-counterexamples.json"
        document = V.load(bundle, path)
        document["probes"].pop()
        bundle[path] = V.encoded(document)
        rebind(bundle)
        V.integrity(bundle)
        selections = V.load(bundle, "gyre/data/selections.json")["selections"]
        selected = {(arm, generation): selections[f"generation_{generation}"][arm] for arm in V.ARMS for generation in (1, 2)}
        with self.assertRaises(V.EvidenceError) as caught:
            V.replay_counterexamples(bundle, self.interpreter, self.oracle, selected)
        self.assertEqual(caught.exception.gate, "posthoc")

    def test_supplied_posthoc_failure_cannot_be_faked_as_a_pass(self):
        bundle = self.changed()
        path = "gyre/data/posthoc/speculative-1-g1.json"
        record = V.load(bundle, path)
        record["results"][0]["outcome"] = {"kind": "value", "value": [1]}
        bundle[path] = V.encoded(record)
        rebind(bundle)
        self.posthoc_rejected(bundle)

    def test_supplied_posthoc_summary_is_independently_graded(self):
        bundle = self.changed()
        path = "gyre/data/posthoc/summary.json"
        summary = V.load(bundle, path)
        program = next(item for item in summary["results"] if item["program"] == "speculative-1-g1")
        program["probes"][0]["matches_contract"] = True
        bundle[path] = V.encoded(summary)
        rebind(bundle)
        self.posthoc_rejected(bundle)

    def test_missing_supplied_posthoc_program_is_not_optional(self):
        bundle = self.changed()
        del bundle["gyre/data/posthoc/direct-4-g2.json"]
        self.rejected(bundle, "corpus")

    def test_supplied_posthoc_measurement_cannot_be_dropped(self):
        bundle = self.changed()
        path = "gyre/data/posthoc/direct-0-g1.json"
        record = V.load(bundle, path)
        record["results"].pop()
        bundle[path] = V.encoded(record)
        rebind(bundle)
        self.posthoc_rejected(bundle)

    def test_supplied_posthoc_gold_is_not_trusted(self):
        bundle = self.changed()
        path = "gyre/data/posthoc/cases.json"
        cases = V.load(bundle, path)
        cases["cases"][0]["expected"]["value"] = [9]
        bundle[path] = V.encoded(cases)
        rebind(bundle)
        self.posthoc_rejected(bundle)

    def test_supplied_posthoc_sources_are_bound(self):
        bundle = self.changed()
        path = "gyre/data/posthoc/provenance.json"
        provenance = V.load(bundle, path)
        provenance["programs"][0]["source_sha256"] = "0" * 64
        bundle[path] = V.encoded(provenance)
        rebind(bundle)
        self.posthoc_rejected(bundle)

    def test_frozen_interpreter_alias_difference_is_not_silently_fixed(self):
        source = (
            "def solve(expression):\n"
            "    first = [1]\n"
            "    alias = first\n"
            "    first += [2]\n"
            "    return alias\n"
        )
        result = self.interpreter.evaluate(source, [{"id": "live", "expression": ""}])
        self.assertEqual(result["results"][0]["outcome"], {"kind": "value", "value": [1]})
        self.assertEqual(V.digest(self.bundle["gyre/reference/interpreter.py"]), V.PINNED["gyre/reference/interpreter.py"])

    def test_no_generated_program_is_natively_executed(self):
        for name in ("gyre/verify.py", "gyre/reference/interpreter.py"):
            tree = ast.parse(self.bundle[name].decode())
            forbidden = [
                node for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in {"exec", "eval", "compile"}
            ]
            self.assertEqual(forbidden, [])

    def test_release_bytes_unchanged_by_controls(self):
        current = privacy.read_public_tree(self.root)
        for path, raw in self.bundle.items():
            if V.owned(path):
                self.assertEqual(current[path], raw)

    def test_manifest_refresh_does_not_rewrite_originals(self):
        bundle = self.changed()
        bundle[self.item["source_path"]] += b"\n# different observation\n"
        with self.assertRaises(ValueError):
            exporter.refreshed_manifest(bundle)

    def test_review_addenda_can_be_bound_without_private_inputs(self):
        bundle = self.changed()
        path = "gyre/data/addenda/review.json"
        bundle[path] = V.encoded({"description": "Supplemental reviewer observation, not an original trial."})
        ledger = V.load(bundle, "gyre/data/addenda.json")
        ledger["entries"].append({
            "id": "gyre-review-3", "description": "An append-only reviewer observation.",
            "subjects": [{"path": self.item["source_path"], "sha256": V.digest(bundle[self.item["source_path"]])}],
            "artifacts": [path],
        })
        bundle["gyre/data/addenda.json"] = V.encoded(ledger)
        bundle[V.MANIFEST] = V.encoded(exporter.refreshed_manifest(bundle))
        V.integrity(bundle)
        for key in ("source_path", "evaluation_path", "score_path", "source_frame_path", "evaluated_frame_path"):
            self.assertEqual(bundle[self.item[key]], self.bundle[self.item[key]])


def run_selftests(root, bundle, tools):
    global _CONTEXT
    _CONTEXT = (root, bundle, tools)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EvidenceTests)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    V.require(result.wasSuccessful(), "self-test", "adversarial detector/control test failed")
    return {
        "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "mutation_storage": "memory only; release artifacts unchanged",
        "privacy": privacy.detector_selftest(),
    }


if __name__ == "__main__":
    unittest.main()
