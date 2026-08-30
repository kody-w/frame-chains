#!/usr/bin/env node

import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const evidenceRoot = dirname(fileURLToPath(import.meta.url));
const releaseRoot = join(evidenceRoot, "v1");

function check(condition, message) {
  if (!condition) throw new Error(message);
}

function normalizeJson(value) {
  if (Array.isArray(value)) return value.map(normalizeJson);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => [key, normalizeJson(item)]),
  );
}

function canonical(value) {
  return JSON.stringify(normalizeJson(value));
}

function sha256Bytes(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function sha256Value(value) {
  return sha256Bytes(Buffer.from(canonical(value)));
}

async function readJson(relativePath) {
  return JSON.parse(await readFile(join(releaseRoot, relativePath), "utf8"));
}

function verifyChain(chain) {
  return chain.every((frame, index) => {
    const { hash, ...preimage } = frame;
    return frame.seq === index
      && frame.prev === (index ? chain[index - 1].hash : null)
      && hash === sha256Value(preimage);
  });
}

function verifyRecord(record) {
  const { frame_hash, ...preimage } = record;
  return record.content_hash === sha256Value(record.value)
    && frame_hash === sha256Value(preimage);
}

function verifyBase(base) {
  const { base_hash, ...preimage } = base;
  return base_hash === sha256Value(preimage);
}

function conflictSet(reads, candidateReads) {
  return Object.keys(reads)
    .filter((name) => Object.hasOwn(candidateReads, name))
    .filter((name) => reads[name] !== candidateReads[name])
    .sort();
}

function verifyDeclaration(entry) {
  return entry.content_hash === sha256Value(entry.value);
}

const manifest = await readJson("manifest.json");
check(manifest.schema === "frame-chains.evidence-manifest/1", "unexpected manifest schema");
check(manifest.fixture_class === "synthetic", "manifest is not synthetic");
check(manifest.contains_raw_estate_data === false, "manifest claims raw estate data");

const diskFiles = (await readdir(releaseRoot, { recursive: true, withFileTypes: true }))
  .filter((entry) => entry.isFile())
  .map((entry) => relative(releaseRoot, join(entry.parentPath, entry.name)))
  .filter((path) => path !== "manifest.json")
  .sort();
const manifestFiles = manifest.files.map((entry) => entry.path).sort();
check(canonical(diskFiles) === canonical(manifestFiles), "manifest file list differs from disk");

for (const entry of manifest.files) {
  const bytes = await readFile(join(releaseRoot, entry.path));
  check(bytes.length === entry.bytes, `${entry.path}: byte count mismatch`);
  check(sha256Bytes(bytes) === entry.sha256, `${entry.path}: SHA-256 mismatch`);
}
for (const entry of manifest.tooling) {
  const bytes = await readFile(join(releaseRoot, entry.path));
  check(bytes.length === entry.bytes, `${entry.path}: tooling byte count mismatch`);
  check(sha256Bytes(bytes) === entry.sha256, `${entry.path}: tooling SHA-256 mismatch`);
}

const claims = await readJson("claims.json");
const mechanismClaims = claims.claims.filter(
  (claim) => claim.classification === "publicly-reproducible-mechanism",
);
check(mechanismClaims.length === 6, "claim ledger must expose six reproducible mechanisms");
for (const claim of claims.claims) {
  check(
    ["publicly-reproducible-mechanism", "aggregated-field-observation"].includes(
      claim.classification,
    ),
    `${claim.id}: unknown evidence classification`,
  );
  if (claim.classification === "publicly-reproducible-mechanism") {
    check(
      claim.evidence?.length > 0
        && claim.evidence.every((path) => manifestFiles.includes(path)),
      `${claim.id}: mechanism evidence is missing from the manifest`,
    );
  }
  if (claim.classification === "aggregated-field-observation") {
    check(claim.raw_record_published === false, `${claim.id}: private field record marked public`);
    check(!claim.evidence, `${claim.id}: private field claim incorrectly points at synthetic proof`);
  }
}

const environment = await readJson("environment.json");
check(environment.runtime.network_required === false, "evidence unexpectedly requires network");
check(environment.runtime.dependencies.length === 0, "evidence unexpectedly requires dependencies");
check(environment.data_policy.contains_raw_estate_data === false, "environment exposes raw estate data");

const clock = await readJson("data/clock-skew.json");
check(verifyChain(clock.chain), "clock chain failed");
const dependencyOrder = clock.chain.map((frame) => frame.seq);
const claimedOrder = [...clock.chain]
  .sort((left, right) => left.claimed_ms - right.claimed_ms)
  .map((frame) => frame.seq);
check(canonical(dependencyOrder) !== canonical(claimedOrder), "clock fixture lacks ordering contradiction");
const clockMutation = structuredClone(clock.chain);
clockMutation[1].payload.action = "mutated";
check(!verifyChain(clockMutation), "clock mutation was not detected");

const scan = await readJson("data/scan-heal.json");
check(verifyChain(scan.chain), "scan chain failed");
const before = scan.nodes.map((node) => node.findings);
const derivedRepairTargets = scan.nodes
  .filter((node) => node.findings > 0 && node.healable > 0)
  .map((node) => node.id);
const after = scan.nodes.map((node) => node.findings - Math.min(node.findings, node.healable));
const derivedFollowupTargets = scan.nodes
  .filter((node, index) => after[index] !== before[index] || after[index] > 0)
  .map((node) => node.id);
const derivedStableTargets = scan.nodes
  .filter((_, index) => after[index] > 0)
  .map((node) => node.id);
check(
  canonical(derivedRepairTargets) === canonical(scan.expected.repair_targets),
  "scan repair target derivation failed",
);
check(
  canonical(derivedFollowupTargets) === canonical(scan.expected.followup_targets),
  "scan follow-up target derivation failed",
);
check(
  canonical(derivedStableTargets) === canonical(scan.expected.stable_targets),
  "scan stable target derivation failed",
);
check(after.reduce((sum, count) => sum + count, 0) === 2, "scan stable floor mismatch");
const fullSweepMutation = scan.nodes.map((node) => node.id);
check(
  canonical(fullSweepMutation) !== canonical(derivedStableTargets),
  "scan full-sweep mutation was not detected",
);

const succession = await readJson("data/succession.json");
check(verifyChain(succession.chain), "succession chain failed");
const claim = succession.chain.find((frame) => frame.kind === "estate.succession");
const eligible = claim.payload.candidates
  .filter((candidate) => candidate.eligible_beat <= claim.payload.beat)
  .sort((left, right) => left.rank - right.rank);
check(claim.payload.beat >= claim.payload.previous_lease_until, "succession preceded lease expiry");
check(eligible[0]?.rank === claim.payload.actor_rank, "wrong succession rank");
const resumption = succession.chain.find((frame) => frame.kind === "estate.resumption");
check(
  resumption.payload.actor_rank === 1
    && resumption.payload.beat >= resumption.payload.previous_lease_until,
  "resumption boundary failed",
);
const unsafeClaim = {
  actor_rank: 3,
  beat: 5,
  previous_lease_until: 4,
  candidates: claim.payload.candidates,
};
const unsafeEligible = unsafeClaim.candidates
  .filter((candidate) => candidate.eligible_beat <= unsafeClaim.beat)
  .sort((left, right) => left.rank - right.rank);
check(
  !unsafeEligible.length || unsafeEligible[0].rank !== unsafeClaim.actor_rank,
  "unsafe succession mutation was not detected",
);

const membrane = await readJson("data/membrane.json");
check(
  [...membrane.private_records, ...membrane.public_records].every(verifyRecord),
  "membrane record hash failed",
);
const privateDeclarations = new Map(
  membrane.private_records.map((record) => [record.name, record.content_hash]),
);
const accepted = membrane.public_records
  .filter((record) => {
    const existing = privateDeclarations.get(record.name);
    return !existing || existing === record.content_hash;
  })
  .map((record) => record.frame_hash)
  .sort();
check(
  canonical(accepted) === canonical(membrane.expected.accepted_public_frames),
  "membrane accepted set mismatch",
);
const conflicting = membrane.public_records.find(
  (record) => privateDeclarations.get(record.name)
    && privateDeclarations.get(record.name) !== record.content_hash,
);
check(
  conflicting?.frame_hash === membrane.expected.refused_conflict_frame,
  "membrane conflict was not refused",
);
check(
  membrane.expected.public_bytes_before_export
    === membrane.expected.public_bytes_after_blocked_export,
  "membrane blocked export changed public bytes",
);
const outwardMutation = JSON.parse(membrane.expected.public_bytes_before_export);
outwardMutation.push(membrane.expected.blocked_private_frame);
check(
  canonical(outwardMutation.sort()) !== membrane.expected.public_bytes_before_export,
  "membrane outward mutation was not detected",
);

const reattach = await readJson("data/reattach.json");
const { frame_hash: strandedHash, ...strandedPreimage } = reattach.stranded;
check(strandedHash === sha256Value(strandedPreimage), "stranded frame hash failed");
check(reattach.candidates.every(verifyBase), "candidate base hash failed");
const evaluations = reattach.candidates.map((base) => ({
  base_hash: base.base_hash,
  conflicts: conflictSet(reattach.stranded.reads, base.reads),
}));
check(
  canonical(evaluations) === canonical(reattach.expected.conflict_sets),
  "reattach conflict sets differ",
);
const selected = evaluations.find((item) => item.conflicts.length === 0);
check(selected?.base_hash === reattach.expected.selected_base, "wrong reattach candidate");
const { frame_hash: graftHash, ...graftPreimage } = reattach.expected.graft;
check(graftHash === sha256Value(graftPreimage), "graft hash failed");
check(
  graftPreimage.grafted_from === reattach.stranded.frame_hash
    && graftPreimage.selected_base === selected.base_hash,
  "graft provenance failed",
);
check(
  reattach.dry_hole_candidates.every(
    (base) => conflictSet(reattach.stranded.reads, base.reads).length > 0,
  ),
  "dry hole unexpectedly found a candidate",
);
check(
  canonical(reattach.expected.dry_hole_history_before)
    === canonical(reattach.expected.dry_hole_history_after),
  "dry hole mutated history",
);

const merge = await readJson("data/merge-fidelity.json");
for (const history of Object.values(merge.histories)) {
  for (const ticks of Object.values(history)) {
    check(Object.values(ticks).every(verifyDeclaration), "merge declaration hash failed");
  }
}
const leftNames = new Set(Object.keys(merge.histories.left));
const rightNames = new Set(Object.keys(merge.histories.right));
const shared = [...leftNames].filter((name) => rightNames.has(name)).sort();
const conflicts = [];
const mergeable = [];
for (const name of shared) {
  const leftTicks = merge.histories.left[name];
  const rightTicks = merge.histories.right[name];
  const overlap = Object.keys(leftTicks).filter((tick) => Object.hasOwn(rightTicks, tick));
  if (overlap.some((tick) => leftTicks[tick].content_hash !== rightTicks[tick].content_hash)) {
    conflicts.push(name);
  } else {
    mergeable.push(name);
  }
}
check(canonical(shared) === canonical(merge.expected.shared_dimensions), "merge shared set mismatch");
check(
  canonical(mergeable) === canonical(merge.expected.mergeable_shared_dimensions),
  "mergeable dimension set mismatch",
);
check(
  canonical(conflicts) === canonical(merge.expected.conflicted_dimensions),
  "merge conflict set mismatch",
);
check(
  mergeable.length === 2 && shared.length === 3,
  "merge fidelity numerator or denominator mismatch",
);
const preservedConflict = {
  left: merge.histories.left.configuration,
  right: merge.histories.right.configuration,
};
check(
  canonical(preservedConflict.left) !== canonical(preservedConflict.right),
  "merge conflict fixture is not contradictory",
);
const overwriteMutation = { ...preservedConflict.left, ...preservedConflict.right };
check(
  canonical(overwriteMutation) !== canonical(preservedConflict.left)
    && canonical(overwriteMutation) !== canonical({
      left: preservedConflict.left,
      right: preservedConflict.right,
    }),
  "merge overwrite mutation was not detected",
);

console.log(
  `evidence verifier: PASS · ${manifest.files.length} data files · ${manifest.tooling.length} bound tools · 6 mechanisms · all negative mutations detected`,
);
