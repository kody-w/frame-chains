#!/usr/bin/env python3
"""Publication-blocking scan; findings never print matched private material."""

import argparse
import collections
import csv
import hashlib
import io
import ipaddress
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

TEXT_SUFFIXES = {".json", ".py", ".txt", ".csv", ".md", ".html", ".mjs", ".js", ".css", ".svg"}
FORBIDDEN_KEYS = re.compile(
    r"^(?:ip|ip_address|hostname|host_name|mac_address|email|username|user_path|"
    r"credential|password|passwd|token|secret|session_id|conversation_id|"
    r"account_id|tenant_id|user_guid|device_id|request_id|authorization)$", re.I
)
CASE_ID = re.compile(
    r"^(?:old-(?:valid|random|error)-\d+|new-(?:fixed|invalid)-\d+|select-\d{3}|"
    r"audit-\d{3}|audit-(?:original|invalid)-\d+|audit-depth-12|"
    r"audit-boundary-256|audit-empty-validated|live|"
    r"leading-zero-(?:integer|repeat)|maximum-flat-zero-padded-list|"
    r"gyre-(?:direct|speculative)-[12]-[0-4]|gyre-review-\d+)$"
)
SYNTHETIC_RAPPID = re.compile(
    r"rappid:@example/gyre-(?:selector-seed|(?:direct|speculative)-[12]-[0-4]):[0-9a-f]{64}"
)


def _ipv4(text):
    for match in re.finditer(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", text):
        if all(int(part) <= 255 for part in match[0].split(".")):
            yield match


def _ipv6(text):
    pattern = r"(?<![0-9a-f:])(?:[0-9a-f]{0,4}:){2,}[0-9a-f:.]*(?:%[a-z0-9]+)?"
    for match in re.finditer(pattern, text, re.I):
        try:
            ipaddress.IPv6Address(match[0])
        except ipaddress.AddressValueError:
            continue
        yield match


PATTERNS = {
    "MAC address": r"\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b",
    "email address": r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    "home path": r"(?:/(?:Users|home)/|[A-Z]:[\\/]+Users[\\/]+|~" r"/)[^\s\"'`]+",
    "local hostname": r"\b(?:local" r"host|[a-z0-9-]+\.(?:local|lan|internal|corp))\b",
    "UUID": r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "credential assignment": (
        r"\b(?:api[_-]?key|access[_-]?token|password|passwd|client[_-]?secret|"
        r"github[_-]?token|authorization)\b\s*[\"']?\s*[:=]\s*"
        r"(?:[\"'][^\"'\n]+[\"']|[A-Za-z0-9][A-Za-z0-9_.~+/=-]{7,})"
    ),
    "identifier assignment": (
        r"\b(?:session[_-]?id|conversation[_-]?id|account[_-]?id|tenant[_-]?id|"
        r"user[_-]?guid|device[_-]?id|user[_-]?path|username|host[_-]?name)\b"
        r"\s*[\"']?\s*[:=]\s*[\"'][^\"'\n]+[\"']"
    ),
    "known token prefix": (
        r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b"
    ),
    "bearer credential": r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}=*",
    "JWT credential": r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
}
DETECTORS = {"IPv4 address": _ipv4, "IPv6 address": _ipv6}
for _label, _pattern in PATTERNS.items():
    DETECTORS[_label] = re.compile(_pattern, re.I).finditer

# No exemptions are needed by the pinned reference or this release. If a future
# reference needs one, review a single match, not an entire file or file type.
# Keys are (relative path, whole-file SHA-256, detector label, match SHA-256).
EXCEPTIONS = {}

# Public rule/arm labels are not account or machine identifiers. Classification
# is restricted to exact labels in their declared document paths and schemas;
# device/node fields and all credential/address detectors remain unaffected.
DOCUMENT_IDS = {
    ("gyre/release-gate.json", "gyre-publication-gate/1"): {
        "complete-denominator", "observed-behavior", "independent-countercheck",
        "falsifiable-gates", "current-rapp", "privacy-boundary", "claims-within-evidence",
        "prior-art-and-hypothesis", "prospective-research", "review-closure",
        "publication-integrity",
    },
    ("gyre/research-protocol.json", "gyre-prospective-research/1"): {
        "direct", "independent-best-of-n", "fixed-lens-inheritance",
        "evolving-lens-inheritance", "inheritance-ablation", "equivalent-unframed-state",
    },
    ("gyre/reviews/independent-critique.json", "gyre-automated-scientific-review/1"): {
        "leading-zero-regression", "original-resource-retention",
    },
}


def indicators(text):
    return [
        (label, match[0])
        for label, detect in DETECTORS.items()
        for match in detect(text)
    ]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError("non-finite JSON number")


def strict_json(raw):
    """Decode before scanning, without discarding shadowed members."""
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)


def inspect_object(value, document_ids=frozenset()):
    findings = []
    if isinstance(value, list):
        for item in value:
            findings.extend(inspect_object(item, document_ids))
    elif isinstance(value, dict):
        for key, item in value.items():
            findings.extend(inspect_object(key, document_ids))
            if FORBIDDEN_KEYS.fullmatch(key):
                findings.append("forbidden identifier/credential field")
            if key in {"id", "device", "node"}:
                synthetic = isinstance(item, str) and bool(CASE_ID.fullmatch(item))
                document_label = key == "id" and isinstance(item, str) and item in document_ids
                if not synthetic and not document_label:
                    findings.append("non-synthetic identifier")
            findings.extend(inspect_object(item, document_ids))
    elif isinstance(value, str):
        findings.extend(label for label, _ in indicators(value))
        for match in re.finditer(r"rappid:@[a-z0-9-]+/[a-z0-9-]+:[0-9a-f]+", value):
            if not SYNTHETIC_RAPPID.fullmatch(match[0]):
                findings.append("non-synthetic RAPP identity")
    return findings


def scan_artifacts(artifacts):
    """Return labels only: never leak a match, field value, or unsafe filename."""
    failures = []
    for relative, raw in sorted(artifacts.items()):
        failures.extend(label for label, _ in indicators(relative))
        suffix = Path(relative).suffix
        if suffix not in TEXT_SUFFIXES and Path(relative).name != "LICENSE":
            failures.append("unapproved file type")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            failures.append("non-text artifact")
            continue
        file_hash = hashlib.sha256(raw).hexdigest()
        for label, match in indicators(text):
            exception = (
                relative, file_hash, label,
                hashlib.sha256(match.encode("utf-8")).hexdigest(),
            )
            if exception not in EXCEPTIONS:
                failures.append(label)
        try:
            if suffix == ".json":
                document = strict_json(text)
                schema = document.get("schema") if isinstance(document, dict) else None
                failures.extend(inspect_object(document, DOCUMENT_IDS.get((relative, schema), frozenset())))
            elif suffix == ".csv":
                for row in csv.DictReader(io.StringIO(text)):
                    failures.extend(inspect_object(row))
            elif suffix in {".txt", ".md", ".html"}:
                failures.extend(inspect_object(text))
        except (ValueError, TypeError):
            failures.append("malformed structured artifact")
    return failures


def read_public_tree(root):
    root = Path(root).resolve()
    if not (root / "gyre").is_dir() or (root / "gyre").is_symlink():
        raise ValueError("missing or linked publication directory")
    artifacts = {}
    for path in sorted((root / "gyre").rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError("symlink in publication")
        if path.is_file():
            if "__pycache__" in path.parts and path.suffix == ".pyc":
                continue
            artifacts[relative] = path.read_bytes()
    return artifacts


def detector_selftest():
    samples = {
        "IPv4 address": ".".join(("192", "0", "2", "7")),
        "IPv6 address": ":".join(("2001", "db8", "", "7")),
        "MAC address": ":".join(("02", "00", "00", "00", "00", "07")),
        "email address": "reader" + "@" + "example.invalid",
        "home path": "/".join(("", "Users", "example", "record")),
        "local host" "name": ".".join(("machine", "local")),
        "UUID": "-".join(("12345678", "1234", "4123", "8123", "123456789abc")),
        "private key": "-----BEGIN " + "PRIVATE" + " KEY-----",
        "credential assignment": "api_key" + "=" + json.dumps("example-value"),
        "identifier assignment": "session" + "_id" + ": " + json.dumps("run-example"),
        "known token prefix": "ghp_" + "A" * 24,
        "bearer credential": "Bearer" + " " + "a" * 24,
        "JWT credential": ".".join(("eyJ" + "A" * 12, "B" * 12, "C" * 12)),
    }
    for label, sample in samples.items():
        if not list(DETECTORS[label](sample)):
            raise AssertionError("privacy detector self-test failed: " + label)
        for suffix in (".py", ".txt", ".csv", ".json"):
            raw = json.dumps({"text": sample}).encode() if suffix == ".json" else sample.encode()
            if label not in scan_artifacts({"gyre/data/probe" + suffix: raw}):
                raise AssertionError("privacy extension self-test failed")
    if not list(DETECTORS["IPv6 address"](":" * 2 + "1")):
        raise AssertionError("compressed IPv6 self-test failed")
    if not list(DETECTORS["credential assignment"]("api_key" + "=" + "example-value")):
        raise AssertionError("unquoted credential self-test failed")
    if not inspect_object({"id": "workstation-alpha"}):
        raise AssertionError("identifier self-test failed")
    if not inspect_object({"session" + "_id": "not-a-synthetic-label"}):
        raise AssertionError("session-field self-test failed")
    if not inspect_object({"rappid": "rappid:@" + "person/study:" + "a" * 64}):
        raise AssertionError("RAPP identity self-test failed")
    if scan_artifacts({"gyre/data/probe.json": b'{"id":"old-valid-0","expression":"2*(1..3)"}'}):
        raise AssertionError("synthetic material was rejected")
    escaped = "\\u0040".join(("reader", "example.invalid"))
    structured_probes = (
        ('{"' + escaped + '":"review"}', "email address"),
        ('{"nested":[{"' + escaped + '":"review"}]}', "email address"),
        ('{"note":"' + escaped + '","note":"review"}', "malformed structured artifact"),
        ('{"note":"review","no' + "\\u0074" + 'e":"review"}', "malformed structured artifact"),
    )
    for raw, expected in structured_probes:
        if expected not in scan_artifacts({"gyre/data/probe.json": raw.encode("utf-8")}):
            raise AssertionError("structured privacy self-test failed")
    return {"detectors": len(samples), "extension_probes": len(samples) * 4,
            "identifier_probes": 3, "structured_json_probes": len(structured_probes)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        tested = detector_selftest()
        artifacts = read_public_tree(args.root)
        failures = scan_artifacts(artifacts)
        if failures:
            print(json.dumps({"privacy": "FAIL", "rules": dict(collections.Counter(failures))}))
            return 1
        result = {"privacy": "PASS", "files": len(artifacts), "exceptions": len(EXCEPTIONS)}
        if args.self_test:
            result["self_tests"] = tested
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, AssertionError):
        print('{"privacy":"FAIL","reason":"unreadable publication or detector self-test"}')
        return 1


if __name__ == "__main__":
    sys.exit(main())
