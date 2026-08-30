#!/usr/bin/env node

import { createServer } from "node:http";
import { execFileSync } from "node:child_process";
import { readFile, stat } from "node:fs/promises";
import { dirname, extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = dirname(fileURLToPath(import.meta.url));
const frames = [
  "01-many-worlds",
  "02-soul-passport",
  "03-mars-colony",
  "04-five-realities",
  "05-causal-detective",
  "06-space-station",
  "07-constitution",
  "08-teleporting-roguelike",
  "09-attack-timeline",
  "10-futures-museum",
];
const copySelectors = {
  "01-many-worlds": "#copy-btn",
  "02-soul-passport": "#copy-prompt-button",
  "03-mars-colony": "#copyPromptButton",
  "04-five-realities": "#copyBtn",
  "05-causal-detective": "#copyPromptBtn",
  "06-space-station": "#copy-prompt",
  "07-constitution": "#copyBtn",
  "08-teleporting-roguelike": "#copyPrompt",
  "09-attack-timeline": "#copyBtn",
  "10-futures-museum": "#copyPromptBtn",
};
const resetSelectors = {
  "01-many-worlds": "#reset-btn",
  "02-soul-passport": "#reset-button",
  "03-mars-colony": "#resetButton",
  "04-five-realities": "#resetBtn",
  "05-causal-detective": "#resetBtn",
  "06-space-station": "#reset",
  "07-constitution": "#resetBtn",
  "08-teleporting-roguelike": "#reset",
  "09-attack-timeline": "#resetBtn",
  "10-futures-museum": "#resetBtn",
};
const runtimeFrames = process.env.SHOWCASE_FRAME
  ? frames.filter((slug) => slug === process.env.SHOWCASE_FRAME)
  : frames;
check(
  runtimeFrames.length > 0,
  `unknown SHOWCASE_FRAME ${process.env.SHOWCASE_FRAME || ""}`,
);
const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
};

function check(condition, message) {
  if (!condition) throw new Error(message);
}

function compact(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function assertNoSensitiveIndicators(text, label) {
  const ipv4 = text.match(/(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])/g) || [];
  const validIpv4 = ipv4.filter((value) =>
    value.split(".").every((part) => Number(part) <= 255)
  );
  const checks = [
    ["IPv4 address", validIpv4],
    ["email address", text.match(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi) || []],
    ["home path", text.match(/(?:\/Users\/|\/home\/|[A-Z]:\\Users\\)[^\s"'`]+/gi) || []],
    ["local hostname", text.match(/\blocalhost\b|["'`](?:https?:\/\/)?[a-z0-9-]+\.(?:local|lan|internal|corp)(?::\d+)?["'`]/gi) || []],
    ["private key", text.match(/-----BEGIN [A-Z ]*PRIVATE KEY-----/g) || []],
    ["token prefix", text.match(/\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b/g) || []],
  ];
  const failures = checks.flatMap(([kind, matches]) =>
    matches.map((match) => `${kind}: ${match}`)
  );
  check(failures.length === 0, `${label}: sensitive indicators found: ${failures.join(", ")}`);
}

async function startServer() {
  const server = createServer(async (request, response) => {
    try {
      const requestUrl = new URL(request.url || "/", "http://127.0.0.1");
      let pathname = decodeURIComponent(requestUrl.pathname);
      if (pathname.endsWith("/")) pathname += "index.html";
      const filePath = resolve(root, `.${pathname}`);
      if (filePath !== root && !filePath.startsWith(`${root}${sep}`)) {
        response.writeHead(403).end("Forbidden");
        return;
      }
      const info = await stat(filePath);
      const finalPath = info.isDirectory() ? resolve(filePath, "index.html") : filePath;
      const body = await readFile(finalPath);
      response.writeHead(200, {
        "cache-control": "no-store",
        "content-type": mimeTypes[extname(finalPath)] || "application/octet-stream",
      });
      response.end(body);
    } catch (error) {
      response.writeHead(error?.code === "ENOENT" ? 404 : 500).end("Not found");
    }
  });
  await new Promise((resolveListen, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolveListen);
  });
  return { server, origin: `http://127.0.0.1:${server.address().port}` };
}

function assertCommitIsMerged(commit, label) {
  try {
    execFileSync("git", ["merge-base", "--is-ancestor", commit, "HEAD"], {
      cwd: root,
      stdio: "ignore",
    });
  } catch {
    throw new Error(`${label}: frame commit ${commit} is not preserved in HEAD`);
  }
}

async function checkStaticContract() {
  const ledger = JSON.parse(
    await readFile(resolve(root, "showcase/FRAME-LOOP.json"), "utf8"),
  );
  check(ledger.schema === "frame-chains.frame-loop/1", "unexpected frame-loop schema");
  check(ledger.loop === 1, "expected frame loop 1");
  check(ledger.frames.length === 10, "merge ledger must contain ten frames");

  for (let index = 0; index < frames.length; index += 1) {
    const slug = frames[index];
    const frameNumber = index + 1;
    const directory = resolve(root, "showcase", slug);
    const metadata = JSON.parse(await readFile(resolve(directory, "frame.json"), "utf8"));
    const html = await readFile(resolve(directory, "index.html"), "utf8");
    const ledgerEntry = ledger.frames.find((entry) => entry.frame === frameNumber);

    check(metadata.frame === frameNumber, `${slug}: wrong frame number`);
    check(metadata.slug === slug, `${slug}: wrong slug`);
    check(metadata.entry === "index.html", `${slug}: entry must be index.html`);
    check(metadata.synthetic_only === true, `${slug}: must declare synthetic_only`);
    check(metadata.network_required === false, `${slug}: must declare network_required false`);
    check(compact(metadata.title).length >= 8, `${slug}: missing title metadata`);
    check(compact(metadata.claim).length >= 30, `${slug}: claim metadata is too short`);
    check(metadata.invariants?.length >= 3, `${slug}: expected at least three invariants`);
    check(metadata.positive_path?.length >= 2, `${slug}: expected a positive path`);
    check(compact(metadata.failure_path).length >= 20, `${slug}: missing failure path`);
    check(ledgerEntry?.slug === slug, `${slug}: missing from merge ledger`);
    check(/^[0-9a-f]{40}$/.test(ledgerEntry?.commit || ""), `${slug}: invalid ledger commit`);
    assertCommitIsMerged(ledgerEntry.commit, slug);

    for (const phrase of [
      "What you are looking at",
      "Do this",
      "Watch for",
      "What this demonstrates",
      "Scope",
      "Copy",
      "Reset",
    ]) {
      check(html.includes(phrase), `${slug}: missing ${phrase}`);
    }
    check(/crypto\.subtle|subtle\.digest/.test(html), `${slug}: missing Web Crypto SHA-256`);
    check(/canonical/i.test(html), `${slug}: missing canonical serialization`);
    check(/aria-live/.test(html), `${slug}: missing aria-live feedback`);
    check(/prefers-reduced-motion/.test(html), `${slug}: missing reduced-motion handling`);
    check(!/<(?:script|img|link)[^>]+(?:src|href)=["']https?:/i.test(html), `${slug}: external runtime asset`);
    assertNoSensitiveIndicators(html, slug);
    assertNoSensitiveIndicators(JSON.stringify(metadata), `${slug}/frame.json`);
  }
  console.log("  ✓ ten metadata contracts and ten preserved frame commits");
}

function monitorPage(page, label, origin) {
  const errors = [];
  page.on("pageerror", (error) => errors.push(`page error: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console error: ${message.text()}`);
  });
  page.on("request", (request) => {
    const url = request.url();
    if (!url.startsWith(origin) && !url.startsWith("data:") && !url.startsWith("blob:")) {
      errors.push(`external request: ${url}`);
    }
  });
  return () => check(errors.length === 0, `${label} emitted errors:\n${errors.join("\n")}`);
}

async function poll(label, predicate, timeout = 30_000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await predicate()) return;
    await new Promise((resolveWait) => setTimeout(resolveWait, 100));
  }
  throw new Error(`${label}: timed out`);
}

async function clickControl(page, selector, waitMs = 150) {
  const control = page.locator(selector);
  check(await control.count() === 1, `${selector}: expected one control`);
  await control.waitFor({ state: "visible" });
  await poll(`${selector} enabled`, async () => !await control.isDisabled());
  if (process.env.SHOWCASE_SKIP_SELECTOR === selector) return;
  await control.click();
  if (waitMs) await page.waitForTimeout(waitMs);
}

async function copyControlIfNeeded(page, control) {
  await page.locator("details").evaluateAll((details) => {
    details.forEach((item) => { item.open = true; });
  });
  await control.waitFor({ state: "visible" });
  await poll("prompt-copy control enabled", async () => !await control.isDisabled());
  await control.click();
  await page.waitForTimeout(100);
}

async function textOf(page, selector) {
  return compact(await page.locator(selector).innerText());
}

async function classesOf(page, selector) {
  return page.locator(selector).evaluateAll((nodes) =>
    nodes.map((node) => String(node.className)),
  );
}

async function runFrameContract(page, slug) {
  if (slug === "01-many-worlds") {
    await clickControl(page, "#guided-btn", 500);
    await poll("Frame 01 guided completion", async () =>
      !await page.locator("#guided-btn").isDisabled()
      && !await page.locator("#mutate-btn").isDisabled(),
    );
    check(await page.locator(".branch-card.valid").count() === 3, "Frame 01 did not create three valid branches");
    check(await page.locator(".branch-card.invalid").count() === 0, "Frame 01 had an invalid branch before mutation");
    check(/9\/15 = 0\.6/.test(await textOf(page, "#chip-merge")), "Frame 01 merge fidelity was not derived");
    const positiveStates = await classesOf(page, "#assertions .assertion");
    check(positiveStates.slice(0, 6).every((state) => state.includes("pass")), "Frame 01 positive assertions did not all pass");
    check(positiveStates[6]?.includes("wait"), "Frame 01 failure assertion did not begin waiting");

    await clickControl(page, "#mutate-btn", 500);
    check(await page.locator(".branch-card.invalid").count() === 1, "Frame 01 mutation did not isolate one branch");
    check(/Rescue SABLE-2/i.test(await textOf(page, ".branch-card.invalid")), "Frame 01 invalidated the wrong branch");
    check(
      /Independent branch verification/i.test(await textOf(page, "#assertions .assertion.fail")),
      "Frame 01 independent verifier did not turn red",
    );
    check(
      /Failure is isolated/i.test(await textOf(page, "#assertions .assertion.pass:last-child")),
      "Frame 01 isolation assertion did not pass",
    );
    return;
  }

  if (slug === "02-soul-passport") {
    for (let step = 0; step < 6; step += 1) {
      await clickControl(page, "#step-button", 350);
    }
    check(await page.locator("#assertion-list .assertion.pass").count() === 6, "Frame 02 continuity path did not produce six passes");
    check(/8 RECORDS/i.test(await textOf(page, "#ledger-count")), "Frame 02 continuity ledger did not reach eight records");
    check(!await page.locator("#forge-button").isDisabled(), "Frame 02 counterfeit control did not become available");

    await clickControl(page, "#forge-button", 250);
    check(!await page.locator("#verify-button").isDisabled(), "Frame 02 counterfeit verifier did not become available");
    await clickControl(page, "#verify-button", 350);
    check(/REJECTED/i.test(await textOf(page, "#mutation-diff")), "Frame 02 counterfeit was not visibly rejected");
    check(/content_address/i.test(await textOf(page, "#mutation-diff")), "Frame 02 rejection omitted the changed identity address");
    check(await page.locator("#assertion-list .assertion.pass").count() === 7, "Frame 02 counterfeit assertion did not pass");
    check(/Counterfeit rejected/i.test(await textOf(page, "#live-status")), "Frame 02 did not announce counterfeit rejection");
    return;
  }

  if (slug === "03-mars-colony") {
    for (let step = 0; step < 8; step += 1) {
      await clickControl(page, "#nextButton", 450);
    }
    check(/Scenario complete/i.test(await textOf(page, "#nextButton")), "Frame 03 guided scenario did not complete");
    const positive = await page.locator("#assertions .assertion, .assertions .assertion").allInnerTexts();
    for (const label of [
      "Canonical hash chain",
      "Scan children link to tile",
      "Lease oracle gates succession",
      "Contradiction-safe reattachment",
      "Homeostatic convergence",
    ]) {
      const assertion = positive.find((value) => value.includes(label));
      check(assertion && /\bpass\b/i.test(assertion), `Frame 03 did not pass ${label}`);
    }

    await clickControl(page, "#resetButton", 300);
    await clickControl(page, "#injectButton", 300);
    await clickControl(page, "#scanButton", 700);
    await clickControl(page, "#sweepButton", 500);
    const scopeAssertion = (await page.locator(".assertion").allInnerTexts())
      .find((value) => value.includes("Repair scope equals report delta"));
    check(scopeAssertion && /\bfail\b/i.test(scopeAssertion), "Frame 03 overbroad repair was not rejected");
    check(/report authorized 3/i.test(await page.locator("body").innerText()), "Frame 03 failure did not expose the derived authorization");
    return;
  }

  if (slug === "04-five-realities") {
    await clickControl(page, "#guideBtn", 500);
    await poll("Frame 04 guided replay", async () =>
      /Guided run/i.test(await textOf(page, "#guideBtn"))
      && /5 \/ 5 canonical agreement/i.test(await textOf(page, "#consensusBadge")),
      25_000,
    );
    check(await page.locator("#ledgerBody tr").count() === 9, "Frame 04 did not replay all nine events");
    check(await page.locator("#mutationBtn").getAttribute("aria-pressed") === "false", "Frame 04 began mutated");
    await clickControl(page, "#rebuildBtn", 500);
    check(
      /Delete \+ rebuild reproduced consensus/i.test(await textOf(page, "#assertionList .assertion:last-child")),
      "Frame 04 did not prove projection deletion and rebuild",
    );

    await clickControl(page, "#mutationBtn", 350);
    check(await page.locator("#mutationBtn").getAttribute("aria-pressed") === "true", "Frame 04 mutation flag was not set");
    check(/1 divergent view/i.test(await textOf(page, "#consensusBadge")), "Frame 04 did not report one divergent view");
    const mutated = await page.locator("#assertionList .assertion").allInnerTexts();
    check(mutated.some((value) => value.includes("Four honest projections still agree")), "Frame 04 lost majority agreement");
    check(mutated.some((value) => value.includes("Exactly Command is isolated")), "Frame 04 did not identify Command");
    return;
  }

  if (slug === "05-causal-detective") {
    const selections = [
      ["#slot-person", "E02"],
      ["#slot-object", "E03"],
      ["#slot-location", "E04"],
      ["#slot-lifecycle", "E06"],
      ["#slot-chronology", "E07"],
    ];
    for (const [selector, evidenceId] of selections) {
      const value = await page.locator(`${selector} option`).filter({ hasText: evidenceId }).first().getAttribute("value");
      check(value, `Frame 05 could not find ${evidenceId}`);
      await page.locator(selector).selectOption(value);
    }
    await clickControl(page, "#accuseBtn", 350);
    check((await page.locator("#verdict").getAttribute("class")).includes("ok"), "Frame 05 supported accusation was rejected");
    check(/Accusation accepted/i.test(await textOf(page, "#verdict")), "Frame 05 omitted the positive accusation verdict");
    check(await page.locator("#assertions .assertion.pass").count() === 4, "Frame 05 positive assertions did not all pass");
    await clickControl(page, '.theory-btn[data-id="T-MARA"]', 150);
    await clickControl(page, '.theory-btn[data-id="T-ELIAS"]', 150);
    check((await page.locator("#compare").getAttribute("class")).includes("show"), "Frame 05 theory comparison did not open");
    check(/2 FORKS/i.test(await textOf(page, "#forkCount")), "Frame 05 did not preserve two theories");

    await clickControl(page, "#mutateBtn", 350);
    check((await page.locator("#oracleLight").getAttribute("class")).includes("red"), "Frame 05 causal oracle did not turn red");
    check(/Causal transition oracle: red/i.test(await textOf(page, "#oracleTitle")), "Frame 05 did not label the semantic failure");
    check(
      /Cryptographic shape/i.test(await textOf(page, "#assertions .assertion.pass:first-child")),
      "Frame 05 cryptographic shape did not stay green",
    );
    check(
      /Causal transitions/i.test(await textOf(page, "#assertions .assertion.fail")),
      "Frame 05 semantic assertion did not fail",
    );
    check(await page.locator("#ledger .ledger-item.bad").count() === 1, "Frame 05 did not isolate one forged clue");
    check(/F01/i.test(await textOf(page, "#ledger .ledger-item.bad")), "Frame 05 did not identify forged frame F01");
    return;
  }

  if (slug === "06-space-station") {
    await clickControl(page, "#guided", 500);
    await poll("Frame 06 guided run", async () =>
      /Tick 8 \/ 8/i.test(await textOf(page, "#tick-label"))
      && /^PASS$/i.test(await textOf(page, "#verdict")),
      30_000,
    );
    check(await page.locator("#assertions .assertion.pass").count() >= 4, "Frame 06 positive assertions did not pass");
    check(/5\s*\/\s*6/.test(await textOf(page, "#fidelity")), "Frame 06 did not derive 5/6 fidelity");
    check(/68 kPa/i.test(await page.locator("#alternatives").innerText()), "Frame 06 omitted the first airlock alternative");
    check(/72 kPa/i.test(await page.locator("#alternatives").innerText()), "Frame 06 omitted the second airlock alternative");

    await page.locator("#mutate-overwrite").evaluate((button) => {
      button.closest("details").open = true;
    });
    await clickControl(page, "#mutate-overwrite", 350);
    check(/FAIL|REJECT/i.test(await textOf(page, "#mutation-result")), "Frame 06 overwrite mutation was not rejected");
    return;
  }

  if (slug === "07-constitution") {
    await clickControl(page, "#guidedBtn", 350);
    await poll("Frame 07 guided history", async () =>
      /Guided history complete/i.test(await textOf(page, "#status")),
    );
    check(await page.locator("#ledgerBody tr").count() === 8, "Frame 07 guided history had the wrong frame count");
    await clickControl(page, "#forkBtn", 350);
    check(/Fork comparison ready/i.test(await textOf(page, "#status")), "Frame 07 lawful fork was not created");
    check(await page.locator("#forkView .branch").count() === 2, "Frame 07 did not render two lawful societies");
    check(await page.locator("#assertionView .assertion.pass").count() === 4, "Frame 07 positive assertions did not all pass");

    await clickControl(page, "#tyrantBtn", 350);
    check((await page.locator("#status").getAttribute("class")).includes("bad"), "Frame 07 tyrant frame did not produce a bad status");
    check(/Replay refused frame 8/i.test(await textOf(page, "#status")), "Frame 07 did not identify the refused frame");
    check(/Exact law: LAW-TREASURY-1/i.test(await textOf(page, "#assertionView .assertion.fail")), "Frame 07 did not identify the violated law");
    check(/visible society remains at valid frame 7/i.test(await page.locator("#assertionView").innerText()), "Frame 07 did not preserve last valid state");
    return;
  }

  if (slug === "08-teleporting-roguelike") {
    await clickControl(page, "#runDemo", 250);
    await poll("Frame 08 guided proof", async () =>
      /STEP 8 \/ 8/i.test(await textOf(page, "#demoCounter"))
      && !await page.locator("#runDemo").isDisabled(),
      30_000,
    );
    check(await page.locator("[data-assert].pass").count() === 6, "Frame 08 guided proof did not satisfy six assertions");
    check(await page.locator("#ledgerBody tr").count() === 6, "Frame 08 accepted ledger changed unexpectedly");
    check(/Inventory forgery refused/i.test(await textOf(page, "#status")), "Frame 08 guided failure did not execute");

    await clickControl(page, "#forgeParent", 350);
    check(/Parent forgery refused/i.test(await textOf(page, "#status")), "Frame 08 parent forgery was not rejected");
    check(/Last good head preserved/i.test(await textOf(page, "#status")), "Frame 08 did not preserve the verified game");
    check((await page.locator('[data-assert="mutation"]').getAttribute("class")).includes("pass"), "Frame 08 mutation assertion did not pass");
    return;
  }

  if (slug === "09-attack-timeline") {
    await clickControl(page, "#controlBtn", 500);
    check(await page.locator("#labStatus").getAttribute("data-state") === "verified", "Frame 09 control did not verify");
    check(await page.locator("#quarantine .quarantine-item").count() === 0, "Frame 09 control quarantined healthy data");
    check(await page.locator("#assertions .assertion[data-state=unmeasured]").count() === 9, "Frame 09 control did not leave nine detectors ready");

    await clickControl(page, "#attackAllBtn", 4_500);
    check(await page.locator("#labStatus").getAttribute("data-state") === "rejected", "Frame 09 attacks were not rejected");
    check(await page.locator("#quarantine .quarantine-item").count() === 9, "Frame 09 did not quarantine all nine attacks");
    check(await page.locator("#assertions .assertion[data-state=pass]").count() === 9, "Frame 09 detector mutations did not all turn red");
    const attackAssertions = await page.locator("#assertions .assertion").allInnerTexts();
    check(attackAssertions.every((value) => /red observed/i.test(value)), "Frame 09 reported a detector without observing red");
    return;
  }

  if (slug === "10-futures-museum") {
    await clickControl(page, "#playBtn", 250);
    await poll("Frame 10 guided replay", async () =>
      /Start guided replay/i.test(await page.locator("#playBtn").getAttribute("aria-label") || "")
      && /7 \/ 7/.test(await textOf(page, "#assertionScore")),
      35_000,
    );
    check(await page.locator("#ledgerBody tr").count() === 9, "Frame 10 replay lost museum frames");
    check(!(await page.locator("#integrityBanner").getAttribute("class")).includes("visible"), "Frame 10 began corrupt");

    await clickControl(page, "#mutateBtn", 500);
    check((await page.locator("#integrityBanner").getAttribute("class")).includes("visible"), "Frame 10 integrity banner did not appear");
    check(/First corrupt frame: F02/i.test(await textOf(page, "#integrityText")), "Frame 10 did not identify F02");
    check(/Frozen on last valid F01/i.test(await textOf(page, "#integrityText")), "Frame 10 did not freeze on F01");
    check(/7 \/ 7/.test(await textOf(page, "#assertionScore")), "Frame 10 mutation assertions did not all pass");
    const museumAssertions = await page.locator("#assertions .assertion").allInnerTexts();
    check(museumAssertions.some((value) => /3 affected frame/i.test(value)), "Frame 10 did not quarantine the affected path");
    check(museumAssertions.some((value) => /independent accepted branches retained/i.test(value)), "Frame 10 lost independent branches");
    return;
  }

  throw new Error(`${slug}: no explicit interaction contract`);
}

async function assertResetContract(page, slug) {
  if (slug === "01-many-worlds") {
    check(/0 \/ 3 minted/i.test(await textOf(page, "#chip-forks")), "Frame 01 reset kept branches");
    check(await page.locator(".branch-card.invalid").count() === 0, "Frame 01 reset kept invalid state");
    check(await page.locator("#mutate-btn").isDisabled(), "Frame 01 reset left mutation enabled");
    return;
  }
  if (slug === "02-soul-passport") {
    check(/1 RECORD/i.test(await textOf(page, "#ledger-count")), "Frame 02 reset did not return to genesis");
    check(await page.locator("#assertion-list .assertion.pass").count() === 4, "Frame 02 reset assertions are wrong");
    check(await page.locator("#verify-button").isDisabled(), "Frame 02 reset kept counterfeit verification enabled");
    return;
  }
  if (slug === "03-mars-colony") {
    check(await page.locator("#ledgerBody tr, #ledger .ledger-row").count() >= 1, "Frame 03 reset lost genesis");
    check(/1 frames verified/i.test(await page.locator("body").innerText()), "Frame 03 reset did not verify one-frame genesis");
    return;
  }
  if (slug === "04-five-realities") {
    check(/5 \/ 5 canonical agreement/i.test(await textOf(page, "#consensusBadge")), "Frame 04 reset did not restore consensus");
    check(await page.locator("#mutationBtn").getAttribute("aria-pressed") === "false", "Frame 04 reset kept mutation active");
    return;
  }
  if (slug === "05-causal-detective") {
    const values = await page.locator("#slots select").evaluateAll((nodes) => nodes.map((node) => node.value));
    check(values.every((value) => value === ""), "Frame 05 reset kept cited causes");
    check(!(await page.locator("#verdict").getAttribute("class")).includes("show"), "Frame 05 reset kept accusation verdict");
    check(await page.locator("#ledger .ledger-item").count() === 10, "Frame 05 reset did not restore ten evidence frames");
    return;
  }
  if (slug === "06-space-station") {
    check(/0 verified frames/i.test(await textOf(page, "#head-count")), "Frame 06 reset kept station frames");
    check(/NOT RUN/i.test(await textOf(page, "#verdict")), "Frame 06 reset kept a verdict");
    return;
  }
  if (slug === "07-constitution") {
    check(await page.locator("#ledgerBody tr").count() === 1, "Frame 07 reset did not return to founding frame");
    check(/Founding constitution sealed/i.test(await textOf(page, "#status")), "Frame 07 reset status is wrong");
    check(await page.locator("#assertionView .assertion.fail").count() === 0, "Frame 07 reset kept a failed assertion");
    return;
  }
  if (slug === "08-teleporting-roguelike") {
    check(/STEP 0 \/ 8/i.test(await textOf(page, "#demoCounter")), "Frame 08 reset kept guided progress");
    check(await page.locator("#ledgerBody tr").count() === 1, "Frame 08 reset did not return to genesis");
    check(/Genesis verified/i.test(await textOf(page, "#status")), "Frame 08 reset status is wrong");
    return;
  }
  if (slug === "09-attack-timeline") {
    check(await page.locator("#quarantine .quarantine-item").count() === 0, "Frame 09 reset kept quarantined attacks");
    check(await page.locator("#assertions .assertion[data-state=unmeasured]").count() === 9, "Frame 09 reset did not clear detector evidence");
    check(await page.locator("#labStatus").getAttribute("data-state") === "verified", "Frame 09 reset did not restore verified projection");
    return;
  }
  if (slug === "10-futures-museum") {
    check(!(await page.locator("#integrityBanner").getAttribute("class")).includes("visible"), "Frame 10 reset kept corruption banner");
    check(/9 verified frames/i.test(await textOf(page, "#headerStatus")), "Frame 10 reset did not restore all frames");
    check(/7 \/ 7/.test(await textOf(page, "#assertionScore")), "Frame 10 reset assertions did not recover");
    return;
  }
}

async function exerciseFrame(context, origin, slug) {
  const page = await context.newPage();
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (text) => {
          window.__showcaseClipboard = String(text);
        },
      },
    });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  const assertClean = monitorPage(page, slug, origin);
  const response = await page.goto(
    `${origin}/showcase/${slug}/index.html?scoutTheme=dark`,
    { waitUntil: "load", timeout: 15_000 },
  );
  check(response?.ok(), `${slug}: HTTP ${response?.status()}`);
  await page.waitForTimeout(150);

  const mobile = await page.evaluate(() => ({
    title: document.title,
    body: document.body.innerText,
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    theme: document.documentElement.getAttribute("data-theme"),
  }));
  check(compact(mobile.title).length > 5, `${slug}: missing title`);
  check(compact(mobile.body).length > 500, `${slug}: rendered too little content`);
  check(mobile.scrollWidth <= mobile.clientWidth + 1, `${slug}: mobile horizontal overflow`);
  check(mobile.theme === "dark", `${slug}: forced dark theme was not applied`);

  const controls = page.locator("button, [role=button]");
  check(await controls.count() >= 4, `${slug}: expected at least four controls`);
  const undersized = await controls.evaluateAll((nodes) =>
    nodes
      .filter((node) => {
        const rect = node.getBoundingClientRect();
        const style = getComputedStyle(node);
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0;
      })
      .filter((node) => node.getBoundingClientRect().height < 40)
      .map((node) => ({
        text: (node.textContent || node.getAttribute("aria-label") || "").trim(),
        height: node.getBoundingClientRect().height,
      })),
  );
  check(undersized.length === 0, `${slug}: undersized controls ${JSON.stringify(undersized)}`);

  await page.setViewportSize({ width: 1100, height: 900 });
  await runFrameContract(page, slug);

  const copy = page.locator(copySelectors[slug]);
  check(await copy.count() === 1, `${slug}: missing exact prompt-copy control`);
  await copyControlIfNeeded(page, copy);
  const copied = await page.evaluate(() => window.__showcaseClipboard || "");
  check(copied.trim().length > 400, `${slug}: copied proof prompt is too short`);
  check(
    /SHA-256/i.test(copied) && /canonical/i.test(copied),
    `${slug}: copied proof prompt omits hashing or canonicalization`,
  );

  await clickControl(page, resetSelectors[slug], 400);
  await assertResetContract(page, slug);

  assertClean();
  await page.close();
  console.log(`  ✓ ${slug}: explicit positive oracle, explicit failure oracle, prompt copy, reset`);
}

let server;
let browser;
try {
  console.log("showcasecheck: ten-frame loop 01");
  await checkStaticContract();
  const started = await startServer();
  server = started.server;
  browser = await chromium.launch({
    headless: true,
    args: ["--disable-gpu-sandbox", "--enable-unsafe-swiftshader", "--use-gl=swiftshader"],
  });
  const context = await browser.newContext();

  const catalog = await context.newPage();
  await catalog.setViewportSize({ width: 390, height: 844 });
  const catalogClean = monitorPage(catalog, "showcase catalog", started.origin);
  const catalogResponse = await catalog.goto(`${started.origin}/showcase/`, { waitUntil: "load" });
  check(catalogResponse?.ok(), "showcase catalog failed to load");
  check(await catalog.locator(".card").count() === 10, "catalog must contain ten frame cards");
  const catalogWidth = await catalog.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  check(catalogWidth.scroll <= catalogWidth.client + 1, "showcase catalog overflows at 390px");
  catalogClean();
  await catalog.close();

  for (const slug of runtimeFrames) {
    await exerciseFrame(context, started.origin, slug);
  }
  await context.close();
  console.log(
    process.env.SHOWCASE_FRAME
      ? `showcasecheck: PASS · ${process.env.SHOWCASE_FRAME}`
      : "showcasecheck: PASS · 10/10 frames",
  );
} catch (error) {
  console.error("showcasecheck: FAIL");
  console.error(error?.stack || error);
  process.exitCode = 1;
} finally {
  await browser?.close().catch(() => {});
  if (server) await new Promise((resolveClose) => server.close(resolveClose));
}
