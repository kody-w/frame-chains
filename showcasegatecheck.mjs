#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const probes = [
  {
    frame: "01-many-worlds",
    selector: "#mutate-btn",
    expected: "Frame 01 mutation did not isolate one branch",
  },
  {
    frame: "05-causal-detective",
    selector: "#accuseBtn",
    expected: "Frame 05 supported accusation was rejected",
  },
  {
    frame: "09-attack-timeline",
    selector: "#attackAllBtn",
    expected: "Frame 09 attacks were not rejected",
  },
];

for (const probe of probes) {
  const result = spawnSync(process.execPath, ["showcasecheck.mjs"], {
    cwd: root,
    encoding: "utf8",
    env: {
      ...process.env,
      SHOWCASE_FRAME: probe.frame,
      SHOWCASE_SKIP_SELECTOR: probe.selector,
    },
  });
  const output = `${result.stdout || ""}\n${result.stderr || ""}`;
  if (result.status === 0) {
    throw new Error(
      `${probe.frame}: gate stayed green when ${probe.selector} was skipped`,
    );
  }
  if (!output.includes(probe.expected)) {
    throw new Error(
      `${probe.frame}: gate failed for the wrong reason while skipping ${probe.selector}\n${output}`,
    );
  }
  console.log(
    `  ✓ ${probe.frame}: skipping ${probe.selector} turns the exact oracle red`,
  );
}

console.log(`showcase gate mutation check: PASS · ${probes.length}/${probes.length}`);
