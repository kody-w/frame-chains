#!/usr/bin/env node

import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const evidenceRoot = dirname(fileURLToPath(import.meta.url));
const releaseRoot = join(evidenceRoot, "v1");
const checkOnly = process.argv.includes("--check");

function canonical(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  return `{${Object.keys(value).sort()
    .map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`)
    .join(",")}}`;
}

function sha256Bytes(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function sha256Value(value) {
  return sha256Bytes(Buffer.from(canonical(value)));
}

function jsonBytes(value) {
  return Buffer.from(`${JSON.stringify(value, null, 2)}\n`);
}

function appendFrame(chain, kind, payload, claimedMs = null) {
  const preimage = {
    seq: chain.length,
    prev: chain.length ? chain.at(-1).hash : null,
    kind,
    payload,
    claimed_ms: claimedMs,
  };
  const frame = { ...preimage, hash: sha256Value(preimage) };
  chain.push(frame);
  return frame;
}

function declaration(value) {
  return { value, content_hash: sha256Value(value) };
}

function makeRecord(name, value, visibility) {
  const contentHash = sha256Value(value);
  const preimage = {
    kind: "declaration",
    name,
    visibility,
    content_hash: contentHash,
    value,
  };
  return { ...preimage, frame_hash: sha256Value(preimage) };
}

function makeBase(order, tier, name, reads) {
  const preimage = { kind: "candidate.base", order, tier, name, reads };
  return { ...preimage, base_hash: sha256Value(preimage) };
}

function conflictSet(reads, candidateReads) {
  return Object.keys(reads)
    .filter((name) => Object.hasOwn(candidateReads, name))
    .filter((name) => reads[name] !== candidateReads[name])
    .sort();
}

function clockEvidence() {
  const chain = [];
  appendFrame(chain, "action", { node: "node-a", action: "store-snapshot" }, 1_000_000);
  appendFrame(chain, "action", { node: "node-b", action: "save-session" }, 987_400);
  appendFrame(chain, "action", { node: "node-a", action: "record-result" }, 1_010_000);
  appendFrame(chain, "action", { node: "node-b", action: "publish-summary" }, 997_400);
  return {
    schema: "frame-chains.clock-skew/1",
    fixture_class: "synthetic",
    chain,
    expected: {
      dependency_order: chain.map((frame) => frame.seq),
      claimed_time_order: [...chain]
        .sort((left, right) => left.claimed_ms - right.claimed_ms)
        .map((frame) => frame.seq),
      node_b_skew_ms: -17_600,
      chain_valid: true,
      wall_clock_matches_chain: false,
    },
  };
}

function scanEvidence() {
  const nodes = [
    { id: "node-a", findings: 4, healable: 3 },
    { id: "node-b", findings: 0, healable: 0 },
    { id: "node-c", findings: 3, healable: 3 },
    { id: "node-d", findings: 1, healable: 1 },
    { id: "node-e", findings: 2, healable: 1 },
  ];
  const before = nodes.map((node) => node.findings);
  const repairTargets = nodes
    .filter((node) => node.findings > 0 && node.healable > 0)
    .map((node) => node.id);
  const after = nodes.map((node) => node.findings - Math.min(node.findings, node.healable));
  const followupTargets = nodes
    .filter((node, index) => after[index] !== before[index] || after[index] > 0)
    .map((node) => node.id);
  const stableTargets = nodes
    .filter((_, index) => after[index] > 0)
    .map((node) => node.id);
  const chain = [];
  appendFrame(chain, "scan.baseline", {
    targets: nodes.map((node) => node.id),
    report: before,
  });
  appendFrame(chain, "repair.delta", { targets: repairTargets, before, after });
  appendFrame(chain, "scan.followup", { targets: followupTargets, report: after });
  appendFrame(chain, "scan.stable", { targets: stableTargets, report: after });
  return {
    schema: "frame-chains.scan-heal/1",
    fixture_class: "synthetic",
    nodes,
    chain,
    expected: {
      baseline_responses: 5,
      repair_targets: repairTargets,
      followup_targets: followupTargets,
      stable_targets: stableTargets,
      final_findings: after.reduce((sum, count) => sum + count, 0),
      identical_reports_required: 2,
      converged: true,
    },
  };
}

function successionEvidence() {
  const chain = [];
  appendFrame(chain, "estate.roster", { ranks: [1, 2, 3], grace_beats: 2 });
  appendFrame(chain, "leadership.start", { actor_rank: 1, beat: 0, lease_until: 4 });
  appendFrame(chain, "node.down", { rank: 1, beat: 0, lease_until: 4 });
  appendFrame(chain, "estate.succession", {
    actor_rank: 2,
    beat: 6,
    previous_lease_until: 4,
    candidates: [
      { rank: 2, eligible_beat: 6 },
      { rank: 3, eligible_beat: 10 },
    ],
    next_lease_until: 10,
  });
  appendFrame(chain, "node.up", { rank: 1, beat: 6 });
  appendFrame(chain, "estate.resumption", {
    actor_rank: 1,
    beat: 10,
    previous_lease_until: 10,
    next_lease_until: 14,
  });
  return {
    schema: "frame-chains.succession/1",
    fixture_class: "synthetic",
    chain,
    expected: {
      first_successor_rank: 2,
      successor_claim_beat: 6,
      rank_3_eligible_beat: 10,
      resumption_rank: 1,
      resumption_beat: 10,
    },
  };
}

function membraneEvidence() {
  const localPolicy = makeRecord("policy.retention", { days: 30 }, "private");
  const localSetting = makeRecord("local.setting", { mode: "local-only" }, "private");
  const publicPolicy = makeRecord("policy.retention", { days: 30 }, "public");
  const publicCatalog = makeRecord("catalog.agent", { version: 3 }, "public");
  const publicConflict = makeRecord("policy.retention", { days: 7 }, "public");
  const publicBefore = [publicPolicy.frame_hash, publicCatalog.frame_hash].sort();
  const publicAfterBlockedExport = [...publicBefore];
  return {
    schema: "frame-chains.membrane/1",
    fixture_class: "synthetic",
    private_records: [localPolicy, localSetting],
    public_records: [publicPolicy, publicCatalog, publicConflict],
    expected: {
      accepted_public_frames: [publicPolicy.frame_hash, publicCatalog.frame_hash].sort(),
      refused_conflict_frame: publicConflict.frame_hash,
      public_bytes_before_export: canonical(publicBefore),
      public_bytes_after_blocked_export: canonical(publicAfterBlockedExport),
      blocked_private_frame: localSetting.frame_hash,
    },
  };
}

function reattachEvidence() {
  const addresses = {
    model4: sha256Value({ model: "atlas", version: 4 }),
    model3: sha256Value({ model: "atlas", version: 3 }),
    policy30: sha256Value({ retention_days: 30 }),
    policy14: sha256Value({ retention_days: 14 }),
    schema9: sha256Value({ schema: 9 }),
    note2: sha256Value({ note_format: 2 }),
    blocker: sha256Value({ conflict: true }),
  };
  const strandedPreimage = {
    kind: "stranded.frame",
    reads: {
      "model.runtime": addresses.model4,
      "policy.retention": addresses.policy30,
      "schema.frame": addresses.schema9,
    },
  };
  const stranded = {
    ...strandedPreimage,
    frame_hash: sha256Value(strandedPreimage),
  };
  const candidates = [
    makeBase(0, "local-head", "candidate-a", {
      "model.runtime": addresses.model4,
      "policy.retention": addresses.policy14,
    }),
    makeBase(1, "local-dimension", "candidate-b", {
      "model.runtime": addresses.model3,
      "policy.retention": addresses.policy30,
      "schema.frame": addresses.schema9,
    }),
    makeBase(2, "public-history", "candidate-c", {
      "model.runtime": addresses.model4,
      "policy.retention": addresses.policy30,
      "schema.frame": addresses.schema9,
      "notes.format": addresses.note2,
    }),
    makeBase(3, "public-history", "candidate-d", {
      "policy.retention": addresses.policy30,
      "schema.frame": addresses.schema9,
    }),
  ];
  const evaluations = candidates.map((base) => ({
    base_hash: base.base_hash,
    conflicts: conflictSet(stranded.reads, base.reads),
  }));
  const selected = candidates[evaluations.findIndex((item) => item.conflicts.length === 0)];
  const graftPreimage = {
    kind: "graft.frame",
    grafted_from: stranded.frame_hash,
    selected_base: selected.base_hash,
    reads: stranded.reads,
  };
  const dryHoleCandidates = candidates.map((base) =>
    makeBase(base.order, base.tier, `${base.name}-blocked`, {
      ...base.reads,
      "policy.retention": addresses.blocker,
    })
  );
  return {
    schema: "frame-chains.reattach/1",
    fixture_class: "synthetic",
    stranded,
    candidates,
    dry_hole_candidates: dryHoleCandidates,
    expected: {
      conflict_sets: evaluations,
      selected_base: selected.base_hash,
      graft: { ...graftPreimage, frame_hash: sha256Value(graftPreimage) },
      original_history: [stranded.frame_hash],
      dry_hole_history_before: [stranded.frame_hash],
      dry_hole_history_after: [stranded.frame_hash],
    },
  };
}

function mergeEvidence() {
  const left = {
    roster: {
      10: declaration({ leader: "r1", lease_beats: 6 }),
      11: declaration({ leader: "r1", lease_beats: 6 }),
    },
    notes: {
      10: declaration({ format: "markdown" }),
      11: declaration({ note: "left-continuation" }),
    },
    configuration: {
      10: declaration({ mode: "safe", retries: 3 }),
    },
    telemetry: {
      10: declaration({ nodes: 5 }),
    },
  };
  const right = {
    roster: {
      10: declaration({ leader: "r1", lease_beats: 6 }),
    },
    notes: {
      10: declaration({ format: "markdown" }),
      12: declaration({ note: "right-continuation" }),
    },
    configuration: {
      10: declaration({ mode: "fast", retries: 1 }),
    },
    diagnostics: {
      10: declaration({ checks: 12 }),
    },
  };
  return {
    schema: "frame-chains.merge-fidelity/1",
    fixture_class: "synthetic",
    histories: { left, right },
    expected: {
      shared_dimensions: ["configuration", "notes", "roster"],
      mergeable_shared_dimensions: ["notes", "roster"],
      conflicted_dimensions: ["configuration"],
      one_sided_dimensions: ["diagnostics", "telemetry"],
      fidelity: { numerator: 2, denominator: 3, decimal: "0.667" },
      conflict_mode: "parallel",
    },
  };
}

function claimsEvidence() {
  return {
    schema: "frame-chains.claim-ledger/1",
    release: "frame-chains-evidence-v1.0.0",
    claims: [
      {
        id: "mechanism.clock-order",
        classification: "publicly-reproducible-mechanism",
        evidence: ["data/clock-skew.json"],
      },
      {
        id: "mechanism.scan-heal",
        classification: "publicly-reproducible-mechanism",
        evidence: ["data/scan-heal.json"],
      },
      {
        id: "mechanism.succession",
        classification: "publicly-reproducible-mechanism",
        evidence: ["data/succession.json"],
      },
      {
        id: "mechanism.membrane",
        classification: "publicly-reproducible-mechanism",
        evidence: ["data/membrane.json"],
      },
      {
        id: "mechanism.reattach",
        classification: "publicly-reproducible-mechanism",
        evidence: ["data/reattach.json"],
      },
      {
        id: "mechanism.merge-fidelity",
        classification: "publicly-reproducible-mechanism",
        evidence: ["data/merge-fidelity.json"],
      },
      {
        id: "field.estate-survey",
        classification: "aggregated-field-observation",
        public_aggregate: "eight devices; five reachable during the reported survey",
        raw_record_published: false,
      },
      {
        id: "field.scan-and-heal",
        classification: "aggregated-field-observation",
        public_aggregate: "66 findings; 35 after the reported deterministic repair pass",
        raw_record_published: false,
      },
      {
        id: "field.recursive-drill",
        classification: "aggregated-field-observation",
        public_aggregate: "27 findings re-dimensioned in a 29-frame sub-chain",
        raw_record_published: false,
      },
      {
        id: "field.clock-disagreement",
        classification: "aggregated-field-observation",
        public_aggregate: "17,620 ms reported clock disagreement",
        raw_record_published: false,
      },
    ],
  };
}

function environmentEvidence() {
  return {
    schema: "frame-chains.reproduction-environment/1",
    release: "frame-chains-evidence-v1.0.0",
    runtime: {
      node: ">=20",
      dependencies: [],
      network_required: false,
      operating_system: "portable",
    },
    data_policy: {
      fixture_class: "synthetic",
      contains_raw_estate_data: false,
      contains_network_addresses: false,
      contains_credentials: false,
      contains_private_source_artifacts: false,
    },
  };
}

async function emit(relativePath, bytes) {
  const target = join(releaseRoot, relativePath);
  if (checkOnly) {
    const current = await readFile(target);
    if (!current.equals(bytes)) {
      throw new Error(`${relativePath} differs from deterministic generator output`);
    }
    return;
  }
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, bytes);
}

const generated = new Map([
  ["claims.json", jsonBytes(claimsEvidence())],
  ["environment.json", jsonBytes(environmentEvidence())],
  ["data/clock-skew.json", jsonBytes(clockEvidence())],
  ["data/scan-heal.json", jsonBytes(scanEvidence())],
  ["data/succession.json", jsonBytes(successionEvidence())],
  ["data/membrane.json", jsonBytes(membraneEvidence())],
  ["data/reattach.json", jsonBytes(reattachEvidence())],
  ["data/merge-fidelity.json", jsonBytes(mergeEvidence())],
]);

const tooling = await Promise.all(
  ["../generate.mjs", "../verify.mjs", "../privacycheck.mjs"].map(async (path) => {
    const bytes = await readFile(join(releaseRoot, path));
    return {
      path,
      bytes: bytes.length,
      sha256: sha256Bytes(bytes),
    };
  }),
);

const manifest = {
  schema: "frame-chains.evidence-manifest/1",
  release: "frame-chains-evidence-v1.0.0",
  release_date: "2026-08-30",
  fixture_class: "synthetic",
  contains_raw_estate_data: false,
  tooling,
  files: [...generated.entries()]
    .map(([path, bytes]) => ({
      path,
      bytes: bytes.length,
      sha256: sha256Bytes(bytes),
    }))
    .sort((left, right) => left.path.localeCompare(right.path)),
};

for (const [relativePath, bytes] of generated) {
  await emit(relativePath, bytes);
}
await emit("manifest.json", jsonBytes(manifest));

console.log(
  checkOnly
    ? `evidence generator: committed bytes match ${generated.size + 1} deterministic files`
    : `evidence generator: wrote ${generated.size + 1} deterministic files`,
);
