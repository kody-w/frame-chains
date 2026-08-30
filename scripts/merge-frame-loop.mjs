#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const planPath = resolve(root, process.argv[2] || "showcase/loop-01.plan.json");
const plan = JSON.parse(await readFile(planPath, "utf8"));

function git(args, options = {}) {
  const output = execFileSync("git", args, {
    cwd: root,
    encoding: "utf8",
    stdio: options.stdio || ["ignore", "pipe", "pipe"],
  });
  return typeof output === "string" ? output.trim() : "";
}

function check(condition, message) {
  if (!condition) throw new Error(message);
}

check(plan.schema === "frame-chains.frame-loop-plan/1", "unexpected loop plan schema");
check(plan.frames?.length === 10, "a frame loop must contain exactly ten frames");
check(git(["status", "--porcelain"]) === "", "integration worktree must be clean");

git(["fetch", "origin", "--prune"], { stdio: "ignore" });
const baseCommit = git(["rev-parse", plan.base]);
const mergedFrames = [];

for (const frame of [...plan.frames].sort((left, right) => left.frame - right.frame)) {
  check(frame.frame >= 1 && frame.frame <= 10, `${frame.slug}: invalid frame number`);
  const head = git(["rev-parse", frame.branch]);
  const commits = git(["rev-list", "--reverse", `${baseCommit}..${head}`])
    .split("\n")
    .filter(Boolean);
  check(commits.length >= 1, `${frame.slug}: branch has no frame commits`);

  const changed = git(["diff", "--name-only", `${baseCommit}...${head}`])
    .split("\n")
    .filter(Boolean);
  check(changed.length >= 2, `${frame.slug}: expected frame files`);
  check(
    changed.every((path) => path.startsWith(`${frame.path}/`)),
    `${frame.slug}: branch changed files outside ${frame.path}`,
  );
  check(changed.includes(`${frame.path}/index.html`), `${frame.slug}: missing index.html`);
  check(changed.includes(`${frame.path}/frame.json`), `${frame.slug}: missing frame.json`);

  const message = [
    `Merge Frame ${String(frame.frame).padStart(2, "0")}: ${frame.slug}`,
    "",
    "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>",
    "Copilot-Session: d9677ff3-485e-4a62-b74e-3e213b208701",
  ].join("\n");
  execFileSync(
    "git",
    [
      "-c",
      "user.name=Kody Wildfeuer",
      "-c",
      "user.email=kody-w@users.noreply.github.com",
      "merge",
      "--no-ff",
      frame.branch,
      "-m",
      message,
    ],
    { cwd: root, stdio: "inherit" },
  );

  mergedFrames.push({
    frame: frame.frame,
    slug: frame.slug,
    branch: frame.branch,
    path: frame.path,
    commit: head,
    commits,
  });
}

const ledger = {
  schema: "frame-chains.frame-loop/1",
  loop: plan.loop,
  base_commit: baseCommit,
  integration_head_before_ledger: git(["rev-parse", "HEAD"]),
  merge_strategy: "git merge --no-ff",
  squash: false,
  frame_count: mergedFrames.length,
  frames: mergedFrames,
};

await writeFile(
  resolve(root, "showcase/FRAME-LOOP.json"),
  `${JSON.stringify(ledger, null, 2)}\n`,
);

console.log(
  `frame loop ${plan.loop}: merged ${mergedFrames.length}/10 branches and wrote showcase/FRAME-LOOP.json`,
);
