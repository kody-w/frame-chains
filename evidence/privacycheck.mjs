#!/usr/bin/env node

import { readFile, readdir } from "node:fs/promises";
import { dirname, extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const evidenceRoot = dirname(fileURLToPath(import.meta.url));
const includedExtensions = new Set([".html", ".json", ".md", ".mjs"]);
const excluded = new Set(["privacycheck.mjs"]);

function findIpv4(text) {
  const matches = text.match(/(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])/g) || [];
  return matches.filter((value) => value.split(".").every((part) => Number(part) <= 255));
}

const detectors = [
  ["IPv4 address", findIpv4],
  ["IPv6 address", (text) => text.match(/\b(?:[0-9a-f]{1,4}:){2,}[0-9a-f:]{1,39}\b/gi) || []],
  ["MAC address", (text) => text.match(/\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b/gi) || []],
  ["email address", (text) => text.match(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi) || []],
  ["home path", (text) => text.match(/(?:\/Users\/|\/home\/|[A-Z]:\\Users\\)[^\s"'`]+/gi) || []],
  ["local hostname", (text) => text.match(/\b(?:localhost|[a-z0-9-]+\.(?:local|lan|internal|corp))\b/gi) || []],
  ["UUID", (text) => text.match(/\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi) || []],
  ["private key", (text) => text.match(/-----BEGIN [A-Z ]*PRIVATE KEY-----/g) || []],
  ["credential assignment", (text) => text.match(/\b(?:api[_-]?key|access[_-]?token|password|passwd|client[_-]?secret)\b\s*["']?\s*[:=]\s*["'][^"']+["']/gi) || []],
  ["known token prefix", (text) => text.match(/\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b/g) || []],
];

const forbiddenKeys = /^(?:ip|ip_address|hostname|host_name|mac_address|email|username|user_path|credential|password|token|secret)$/i;

function inspectJson(value, path = "$", failures = []) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => inspectJson(item, `${path}[${index}]`, failures));
    return failures;
  }
  if (!value || typeof value !== "object") return failures;
  for (const [key, item] of Object.entries(value)) {
    if (forbiddenKeys.test(key)) failures.push(`${path}.${key}: forbidden key`);
    const syntheticIdentifier = key === "device"
      || key === "id"
      || (key === "node" && path.includes(".payload"));
    if (syntheticIdentifier && typeof item === "string") {
      if (!/^(?:node-[a-z]|mechanism\.|field\.)/.test(item)) {
        failures.push(`${path}.${key}: non-synthetic identifier ${JSON.stringify(item)}`);
      }
    }
    inspectJson(item, `${path}.${key}`, failures);
  }
  return failures;
}

const detectorMutations = new Map([
  ["IPv4 address", [["192", "0", "2", "1"].join(".")]],
  ["IPv6 address", [["2001", "db8", "", "1"].join(":")]],
  ["MAC address", [["02", "00", "00", "00", "00", "01"].join(":")]],
  ["email address", [`reader${"@"}example.invalid`]],
  ["home path", [["", "Users", "example", "record"].join("/")]],
  ["local hostname", [["node", "local"].join(".")]],
  ["UUID", [["12345678", "1234", "4123", "8123", "123456789abc"].join("-")]],
  ["private key", [`-----BEGIN ${"PRIVATE"} KEY-----`]],
  ["credential assignment", [`api_key=${'"'}example-value${'"'}`]],
  ["known token prefix", [`ghp_${"A".repeat(24)}`]],
]);
for (const [label, detect] of detectors) {
  const samples = detectorMutations.get(label) || [];
  if (!samples.some((sample) => detect(sample).length > 0)) {
    throw new Error(`privacy detector self-test failed: ${label}`);
  }
}
if (!inspectJson({ id: "workstation-alpha" }).length) {
  throw new Error("privacy detector self-test failed: non-synthetic identifier");
}

const entries = await readdir(evidenceRoot, { recursive: true, withFileTypes: true });
const files = entries
  .filter((entry) => entry.isFile())
  .map((entry) => join(entry.parentPath, entry.name))
  .filter((path) => includedExtensions.has(extname(path)))
  .filter((path) => !excluded.has(relative(evidenceRoot, path)))
  .sort();

const failures = [];
for (const file of files) {
  const relativePath = relative(evidenceRoot, file);
  const text = await readFile(file, "utf8");
  for (const [label, detect] of detectors) {
    for (const match of detect(text)) {
      failures.push(`${relativePath}: ${label}: ${match}`);
    }
  }
  if (extname(file) === ".json") {
    for (const failure of inspectJson(JSON.parse(text))) {
      failures.push(`${relativePath}: ${failure}`);
    }
  }
}

if (failures.length) {
  throw new Error(`privacy scan failed:\n${failures.join("\n")}`);
}

console.log(
  `evidence privacy scan: PASS · ${files.length} files · no network, identity, path, or credential indicators`,
);
