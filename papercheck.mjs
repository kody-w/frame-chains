#!/usr/bin/env node

import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { readFile, stat } from "node:fs/promises";
import { dirname, extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, firefox, webkit } from "playwright";

const root = dirname(fileURLToPath(import.meta.url));
const browserName = process.argv[2] || "chromium";
const mode = process.argv[3] || "full";
const browserTypes = { chromium, firefox, webkit };

if (!browserTypes[browserName]) {
  throw new Error(`Unknown browser "${browserName}". Use chromium, firefox, or webkit.`);
}
if (!["full", "smoke"].includes(mode)) {
  throw new Error(`Unknown mode "${mode}". Use full or smoke.`);
}

const expectedExercises = [
  "play/scan-tile.html",
  "play/succession.html",
  "play/membrane.html",
  "play/reattach.html",
  "play/chain-is-the-clock.html",
  "play/merge-fidelity.html",
];
const guideExercises = [
  "play/chain-is-the-clock.html",
  "play/scan-tile.html",
  "play/succession.html",
  "play/membrane.html",
  "play/reattach.html",
  "play/merge-fidelity.html",
];
const smokePages = ["index.html", "guide.html", "paper.html", "evidence/index.html", ...expectedExercises];
const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".py": "text/x-python; charset=utf-8",
  ".svg": "image/svg+xml",
};

function check(condition, message) {
  if (!condition) throw new Error(message);
}

function compact(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

async function optionalText(page, selector) {
  const locator = page.locator(selector);
  return (await locator.count()) ? (await locator.first().textContent()) || "" : "";
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
      if (request.method === "HEAD") response.end();
      else response.end(body);
    } catch (error) {
      const status = error?.code === "ENOENT" ? 404 : 500;
      response.writeHead(status, { "content-type": "text/plain; charset=utf-8" });
      response.end(status === 404 ? "Not found" : "Server error");
    }
  });

  await new Promise((resolveListen, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolveListen);
  });
  const address = server.address();
  check(address && typeof address === "object", "Static server did not expose an address.");
  return { server, origin: `http://127.0.0.1:${address.port}` };
}

function monitorPage(page, label, origin) {
  const errors = [];
  page.on("pageerror", error => errors.push(`page error: ${error.message}`));
  page.on("console", message => {
    if (message.type() === "error") errors.push(`console error: ${message.text()}`);
  });
  page.on("response", response => {
    if (response.url().startsWith(origin) && response.status() >= 400) {
      errors.push(`HTTP ${response.status()}: ${response.url()}`);
    }
  });
  return () => {
    check(errors.length === 0, `${label} emitted errors:\n${errors.join("\n")}`);
  };
}

async function openCheckedPage(context, origin, relativePath, mobile = true) {
  const page = await context.newPage();
  if (mobile) await page.setViewportSize({ width: 390, height: 844 });
  const assertClean = monitorPage(page, relativePath, origin);
  const response = await page.goto(`${origin}/${relativePath}`, {
    waitUntil: "load",
    timeout: 15_000,
  });
  check(response?.ok(), `${relativePath} returned HTTP ${response?.status() ?? "no response"}.`);
  await page.waitForTimeout(100);

  const state = await page.evaluate(() => {
    const scrolling = document.scrollingElement || document.documentElement;
    return {
      bodyText: document.body?.innerText || "",
      childCount: document.body?.children.length || 0,
      clientWidth: scrolling.clientWidth,
      scrollWidth: scrolling.scrollWidth,
      title: document.title,
    };
  });
  check(state.title.trim().length > 0, `${relativePath} has no document title.`);
  check(state.childCount > 0, `${relativePath} rendered an empty body.`);
  check(compact(state.bodyText).length > 80, `${relativePath} rendered too little content.`);
  check(
    state.scrollWidth <= state.clientWidth + 1,
    `${relativePath} overflows at 390px (${state.scrollWidth}px > ${state.clientWidth}px).`,
  );
  assertClean();
  return { page, assertClean };
}

async function runSmoke(context, origin) {
  for (const relativePath of smokePages) {
    const mobile = ["index.html", "guide.html", "paper.html"].includes(relativePath);
    const { page } = await openCheckedPage(context, origin, relativePath, mobile);
    await page.close();
    console.log(
      `  ✓ ${relativePath} boots ${mobile ? "at 390px without overflow or " : "without "}page errors`,
    );
  }
}

async function checkPaperEmbeds(context, origin) {
  const { page, assertClean } = await openCheckedPage(context, origin, "paper.html");
  const embeds = await page.locator("iframe").evaluateAll(nodes =>
    nodes.map(node => ({
      src: node.getAttribute("src"),
      title: node.getAttribute("title"),
    })),
  );
  check(embeds.length === 6, `paper.html must embed exactly six iframes; found ${embeds.length}.`);
  check(
    JSON.stringify(embeds.map(embed => embed.src)) === JSON.stringify(expectedExercises),
    `paper.html iframe order/src mismatch: ${embeds.map(embed => embed.src).join(", ")}`,
  );
  check(embeds.every(embed => compact(embed.title).length > 20), "Every paper iframe needs a descriptive title.");
  check(new Set(embeds.map(embed => embed.src)).size === 6, "Paper iframe sources must be unique.");
  const paperText = compact(await page.locator("body").innerText());
  check(
    /executable explanatory models/i.test(paperText)
      && /do not substitute for the reported estate runs/i.test(paperText),
    "Paper must distinguish the embedded models from the reported empirical evidence.",
  );
  check(
    /sanitized evidence release/i.test(paperText)
      && /contains no raw estate frames/i.test(paperText)
      && /does not claim to independently verify the private field observations/i.test(paperText),
    "Paper must state the public evidence bundle's privacy and evidentiary limits.",
  );
  assertClean();
  await page.close();
  console.log("  ✓ paper.html embeds six unique, titled standalone exercises");
}

async function checkGuidePath(context, origin) {
  const { page, assertClean } = await openCheckedPage(context, origin, "guide.html");
  const cards = page.locator("article.evidence-card");
  check((await cards.count()) === 6, "guide.html must contain exactly six ordered evidence cards.");
  for (let index = 0; index < guideExercises.length; index += 1) {
    const card = cards.nth(index);
    const text = compact(await card.innerText());
    for (const heading of [
      /What you are looking at/i,
      /Do this/i,
      /Watch for/i,
      /What this (?:proves|demonstrates)/i,
    ]) {
      check(heading.test(text), `Guide card ${index + 1} is missing ${heading}.`);
    }
    check(
      (await card.locator(`a[href="${guideExercises[index]}"]`).count()) === 1,
      `Guide card ${index + 1} does not link to ${guideExercises[index]}.`,
    );
    check(
      (await card.locator('a[href^="paper.html#prompt-"]').count()) === 1,
      `Guide card ${index + 1} does not link to its paper proof prompt.`,
    );
  }
  const guideText = compact(await page.locator("body").innerText());
  check(/How to interpret failure/i.test(guideText), "Guide lacks failure interpretation.");
  check(
    /teaching models explain the claims/i.test(guideText),
    "Guide must distinguish teaching models from reported evidence.",
  );
  assertClean();
  await page.close();
  console.log("  ✓ guide.html provides six ordered, scoped newcomer evidence cards");
}

async function checkStandaloneGuidance(context, origin) {
  for (const relativePath of expectedExercises) {
    const { page, assertClean } = await openCheckedPage(context, origin, relativePath, false);
    const text = compact(await page.locator("body").innerText());
    for (const pattern of [
      /Do this/i,
      /Watch for/i,
      /What this demonstrates/i,
      /\bScope\b|Scope and limit/i,
    ]) {
      check(pattern.test(text), `${relativePath} is missing newcomer guidance matching ${pattern}.`);
    }
    check(
      (await page.locator('nav a[href="../guide.html"]').count()) === 1,
      `${relativePath} does not provide a route back to the guided evidence path.`,
    );
    check(
      (await page.locator('button, [role="button"]').filter({ hasText: /reset/i }).count()) >= 1,
      `${relativePath} does not expose a reset control.`,
    );
    assertClean();
    await page.close();
  }
  console.log("  ✓ all six standalone proofs include guidance, scope, reset, and return navigation");
}

async function checkEvidencePage(context, origin) {
  const { page, assertClean } = await openCheckedPage(context, origin, "evidence/index.html");
  const text = compact(await page.locator("body").innerText());
  check(
    /no raw estate frames/i.test(text)
      && /not presented as independently reproduced raw evidence/i.test(text),
    "Evidence page must state its privacy and field-evidence boundary.",
  );
  check(
    (await page.locator(".scenario").count()) === 6,
    "Evidence page must expose exactly six reproducible mechanism scenarios.",
  );
  for (const path of [
    "v1/manifest.json",
    "v1/environment.json",
    "v1/claims.json",
    "v1/data/clock-skew.json",
    "v1/data/scan-heal.json",
    "v1/data/succession.json",
    "v1/data/membrane.json",
    "v1/data/reattach.json",
    "v1/data/merge-fidelity.json",
  ]) {
    const response = await page.request.get(`${origin}/evidence/${path}`);
    check(response.ok(), `Evidence asset ${path} returned HTTP ${response.status()}.`);
  }
  assertClean();
  await page.close();
  console.log("  ✓ evidence page exposes six synthetic scenarios and every bound release asset");
}

async function checkPromptCopy(context, origin) {
  const page = await context.newPage();
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        readText: async () => window.__papercheckClipboard || "",
        writeText: async text => {
          window.__papercheckClipboard = String(text);
        },
      },
    });
  });
  const assertClean = monitorPage(page, "paper prompt copy", origin);
  const response = await page.goto(`${origin}/paper.html`, { waitUntil: "load" });
  check(response?.ok(), "paper.html did not load for prompt-copy checks.");
  const prompts = page.locator(".proof-prompt");
  check((await prompts.count()) === 6, "Expected six proof-prompt sections.");

  const copiedPrompts = [];
  for (let index = 0; index < 6; index += 1) {
    const prompt = prompts.nth(index);
    await prompt.evaluate(details => {
      details.open = true;
    });
    const text = (await prompt.locator("pre").textContent())?.trim() || "";
    check(text.length > 250, `Proof prompt ${index + 1} is unexpectedly short.`);
    const button = prompt.locator(".copy-prompt");
    await button.click();
    const copied = await page.evaluate(() => window.__papercheckClipboard || "");
    check(copied.trim() === text, `Proof prompt ${index + 1} did not copy its full text.`);
    check((await button.innerText()) === "Copied", `Proof prompt ${index + 1} did not report a successful copy.`);
    copiedPrompts.push(text);
  }
  check(new Set(copiedPrompts).size === 6, "Proof prompts must be six distinct prompts.");
  assertClean();
  await page.close();

  let standaloneCopyPaths = 0;
  for (const relativePath of expectedExercises) {
    const standalone = await context.newPage();
    await standalone.addInitScript(() => {
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: {
          readText: async () => window.__papercheckClipboard || "",
          writeText: async text => {
            window.__papercheckClipboard = String(text);
          },
        },
      });
    });
    const assertStandaloneClean = monitorPage(standalone, `${relativePath} prompt copy`, origin);
    const standaloneResponse = await standalone.goto(`${origin}/${relativePath}`, { waitUntil: "load" });
    check(standaloneResponse?.ok(), `${relativePath} did not load for prompt-copy checks.`);
    const copyButton = standalone.locator("button.copy, #copyBtn").first();
    if ((await copyButton.count()) === 0) {
      assertStandaloneClean();
      await standalone.close();
      continue;
    }
    const details = standalone.locator("details.prompt");
    if ((await details.count()) === 1) {
      await details.evaluate(node => {
        node.open = true;
      });
    }
    const promptText = (await standalone.locator("pre").first().textContent())?.trim() || "";
    check(promptText.length > 500, `${relativePath} proof prompt is unexpectedly short.`);
    await copyButton.click();
    const copiedText = await standalone.evaluate(() => window.__papercheckClipboard || "");
    check(copiedText.trim() === promptText, `${relativePath} did not copy its full proof prompt.`);
    const copyFeedback = compact(
      `${await copyButton.innerText()} ${await optionalText(standalone, "#copyStatus")}`,
    );
    check(/copied/i.test(copyFeedback), `${relativePath} did not report a successful copy.`);
    standaloneCopyPaths += 1;
    assertStandaloneClean();
    await standalone.close();
  }
  check(standaloneCopyPaths >= 3, `Expected at least three standalone prompt-copy paths; found ${standaloneCopyPaths}.`);
  console.log(
    `  ✓ paper and ${standaloneCopyPaths} standalone prompt-copy paths copy complete, non-empty prompts`,
  );
}

async function matchingControl(page, patterns, label, required = true) {
  const controls = page.locator(
    'button, [role="button"], input[type="button"], input[type="submit"], label',
  );
  const count = await controls.count();
  for (let index = 0; index < count; index += 1) {
    const control = controls.nth(index);
    const text = compact(
      `${await control.innerText().catch(() => "")} ${await control.getAttribute("value") || ""} ` +
      `${await control.getAttribute("aria-label") || ""} ${await control.getAttribute("title") || ""}`,
    );
    if (patterns.some(pattern => pattern.test(text))) return control;
  }
  if (required) throw new Error(`Missing ${label} control (looked at ${count} controls).`);
  return null;
}

async function clickForChange(page, control, label) {
  const before = compact(await page.locator("body").innerText());
  await control.click();
  await page.waitForTimeout(180);
  const after = compact(await page.locator("body").innerText());
  check(after !== before, `${label} did not produce a visible state change.`);
  return after;
}

async function checkClockExercise(context, origin) {
  const { page, assertClean } = await openCheckedPage(
    context,
    origin,
    "play/chain-is-the-clock.html",
    false,
  );
  await page.locator("#skew").fill("-120");
  await page.locator("#skew").dispatchEvent("input");
  check((await page.locator("#skewLabel").innerText()).includes("-120.0"), "Clock skew control did not update.");

  await page.getByRole("button", { name: /Mac/ }).click();
  await page.getByRole("button", { name: /Deck/ }).click();
  await page.waitForFunction(() => document.querySelectorAll(".frame").length === 2);
  check((await page.locator(".frame").count()) === 2, "Clock exercise did not append two frames.");
  const chainText = compact(await page.locator("#frames").innerText());
  check(
    /(?:holds|prev) (?:genesis|[0-9a-f]{8})/i.test(chainText),
    "Clock frames do not expose predecessor hashes.",
  );
  check(
    /(?:is|hash) [0-9a-f]{8}/i.test(chainText),
    "Clock frames do not expose computed SHA-256 hashes.",
  );
  if ((await page.locator("#chainCheck").count()) === 1) {
    await page.waitForFunction(() => document.querySelector("#chainCheck")?.classList.contains("pass"));
  }
  const chainVerdict = compact(
    `${await optionalText(page, "#verdict")} ${await optionalText(page, "#chainCheck")}`,
  );
  check(
    /Chain order|PASS.*hashes.*predecessor/i.test(chainVerdict),
    "Chain-order verification is missing.",
  );

  await page.locator("#sortBtn").click();
  if ((await page.locator("#orderCheck").count()) === 1) {
    await page.waitForFunction(() => document.querySelector("#orderCheck")?.classList.contains("fail"));
  } else {
    await page.waitForTimeout(80);
  }
  const badVerdict = compact(
    `${await optionalText(page, "#verdict")} ${await optionalText(page, "#orderCheck")}`,
  );
  check(
    /rearranged history|BEFORE the entries|timestamps contradict causality/i.test(badVerdict),
    "Wall-clock sorting did not visibly contradict dependency order.",
  );
  const tamperButton = page.locator("#tamperBtn");
  if ((await tamperButton.count()) === 1) {
    await tamperButton.click();
    await page.waitForFunction(() => document.querySelector("#chainCheck")?.classList.contains("fail"));
    check(
      /FAIL.*mutation detected/i.test(await page.locator("#chainCheck").innerText()),
      "Tampering did not make independent chain verification fail.",
    );
  }
  assertClean();
  await page.close();
  console.log("  ✓ chain-is-the-clock hashes frames and exposes bad wall-clock ordering");
}

async function checkScanExercise(context, origin) {
  const { page, assertClean } = await openCheckedPage(context, origin, "play/scan-tile.html", false);
  check((await page.locator(".node").count()) === 5, "Scan exercise must start with five devices.");
  if ((await page.locator("#sampleBtn").count()) === 1) {
    await page.locator("#sampleBtn").click();
    await page.waitForFunction(
      () => document.querySelector("#convergenceCheck")?.classList.contains("pass"),
      null,
      { timeout: 15_000 },
    );
    check((await page.locator("#responseMetric").innerText()) === "2", "Stable incremental scan did not narrow to the two-item exhaust.");
    check((await page.locator("#repairMetric").innerText()) === "4 / 5", "Guided repair did not follow four exhaust targets.");
    check((await page.locator("#findingMetric").innerText()) === "2", "Guided repair did not reach the human-only floor.");
    check((await page.locator("#stableMetric").innerText()) === "2 / 2", "Two identical reports were not recorded.");
    check((await page.locator("#chainCheck").getAttribute("class") || "").includes("pass"), "Scan frame chain did not verify.");
    check((await page.locator("#scopeCheck").getAttribute("class") || "").includes("pass"), "Repair scope did not pass.");
    const logText = compact(await page.locator("#log").innerText());
    check(/scan\.tile/i.test(logText) && /scan\.response/i.test(logText), "Scan log lacks tile or response frames.");
    check(/scan\.report/i.test(logText) && /repair\.delta/i.test(logText), "Scan log lacks report or repair frames.");

    await page.locator("#driftBtn").click();
    await page.locator("#scanBtn").click();
    await page.waitForFunction(() => document.querySelector("#healBtn")?.disabled === false);
    await page.locator("#healBtn").click();
    await page.waitForFunction(() => document.querySelector("#repairMetric")?.textContent === "1 / 5");
    check((await page.locator("#findingMetric").innerText()) === "2", "Single-device drift was not deterministically healed.");

    await page.locator("#scanBtn").click();
    await page.waitForFunction(() => document.querySelector("#wasteBtn")?.disabled === false);
    await page.locator("#wasteBtn").click();
    await page.waitForFunction(() => document.querySelector("#scopeCheck")?.classList.contains("fail"));
    check(/full-sweep mutation/i.test(await page.locator("#scopeCheck").innerText()), "Wasteful sweep was not rejected.");
    assertClean();
    await page.close();
    console.log("  ✓ scan-tile performs linked scan, exhaust-only repair, convergence, and mutation rejection");
    return;
  }

  await page.locator("#scanBtn").click();
  await page.waitForFunction(() => document.querySelector("#mTick")?.textContent === "1");
  check((await page.locator("#mWork").innerText()) === "5", "Initial scan did not invoke the full fleet.");
  check((await page.locator("#mFind").innerText()) === "10", "Initial scan finding total is wrong.");
  check((await page.locator("#log").innerText()).includes("holds"), "Scan responses do not expose tile links.");

  await page.locator("#healBtn").click();
  check((await page.locator("#mWork").innerText()) === "4", "Healing did not touch exactly four implicated devices.");
  check((await page.locator("#mFind").innerText()) === "2", "Deterministic healing did not reach its floor.");
  await page.locator("#scanBtn").click();
  await page.waitForFunction(() => document.querySelector("#mTick")?.textContent === "2");
  await page.locator("#scanBtn").click();
  await page.waitForFunction(() => document.querySelector("#mTick")?.textContent === "3");
  check((await page.locator("#mWork").innerText()) === "2", "Stable scan did not reduce work to the two-item delta.");
  check(/CONVERGED/i.test(await page.locator("#conv").innerText()), "Two stable ticks did not declare convergence.");
  assertClean();
  await page.close();
  console.log("  ✓ scan-tile performs linked scan, O(delta) healing, and convergence");
}

async function checkSuccessionExercise(context, origin) {
  const { page, assertClean } = await openCheckedPage(context, origin, "play/succession.html", false);
  if ((await page.locator("#sampleBtn").count()) === 1) {
    await page.waitForFunction(() => document.querySelector("#chainCheck")?.classList.contains("pass"));
    check((await page.locator("#nodes .node").count()) === 3, "Succession exercise must render three ranked members.");
    check((await page.locator("#leaderMetric").innerText()) === "rank 1", "Rank 1 did not start as leader.");
    check(await page.locator("#lagToggle").isChecked(), "Rank-3 lag must be enabled in the guided scenario.");

    await page.locator("#sampleBtn").click();
    await page.waitForFunction(
      () => document.querySelector("#sequenceCheck")?.textContent.includes("resumption boundary"),
      null,
      { timeout: 15_000 },
    );
    check((await page.locator("#leaderMetric").innerText()) === "rank 1", "Rank 1 did not resume at the boundary.");
    check((await page.locator("#safetyCheck").getAttribute("class") || "").includes("pass"), "Authorized succession failed its safety assertion.");
    check((await page.locator("#sequenceCheck").getAttribute("class") || "").includes("pass"), "Rank sequence/resumption assertion did not pass.");
    const logText = compact(await page.locator("#log").innerText());
    check(/estate\.succession/i.test(logText), "Succession frame was not appended.");
    check(/estate\.resumption/i.test(logText), "Resumption frame was not appended.");
    check(/rank 2 claimed/i.test(logText), "Rank 2 did not claim before lagged rank 3.");

    await page.locator("#unsafeBtn").click();
    await page.waitForFunction(() => document.querySelector("#safetyCheck")?.classList.contains("fail"));
    check(
      /unauthorized leadership claim/i.test(await page.locator("#safetyCheck").innerText()),
      "Unsafe rank-3 claim was not rejected by the independent verifier.",
    );
    check((await page.locator("#chainCheck").getAttribute("class") || "").includes("pass"), "Semantic rejection should not corrupt the hash chain.");
    assertClean();
    await page.close();
    console.log("  ✓ succession enforces lease/rank boundaries, lag safety, resumption, and mutation rejection");
    return;
  }

  check((await page.locator(".r").count()) === 3, "Succession exercise must render three ranked members.");
  check(/LEADER/.test(await page.locator(".r").nth(0).innerText()), "Rank 1 did not start as leader.");
  await page.locator("#knockBtn").click();
  check(/down/i.test(await page.locator(".r").nth(0).innerText()), "Knock-out control did not take rank 1 down.");
  await page.evaluate(() => {
    for (let index = 0; index < 10; index += 1) window.beat();
  });
  check(/LEADER/.test(await page.locator(".r").nth(1).innerText()), "Rank 2 did not succeed after lease plus grace.");
  check(/No vote happened/i.test(await page.locator("#log").innerText()), "Succession was not logged as election-free.");

  await page.locator("#reviveBtn").click();
  check(/defers/i.test(await page.locator("#log").innerText()), "Returning rank 1 did not visibly defer.");
  await page.evaluate(() => {
    for (let index = 0; index < 6; index += 1) window.beat();
  });
  check(/LEADER/.test(await page.locator(".r").nth(0).innerText()), "Rank 1 did not resume at the lease boundary.");
  check(/resumption frame/i.test(await page.locator("#log").innerText()), "Resumption frame was not appended.");
  assertClean();
  await page.close();
  console.log("  ✓ succession enforces expiry, rank grace, and boundary resumption");
}

async function checkMembraneExercise(context, origin) {
  const { page, assertClean } = await openCheckedPage(context, origin, "play/membrane.html", false);
  const initial = compact(await page.locator("body").innerText());
  check(/public/i.test(initial) && /private/i.test(initial), "Membrane must expose public and private stores.");
  check(/SHA-?256|hash/i.test(initial), "Membrane must expose content hashes.");
  check((initial.match(/[0-9a-f]{8,64}/gi) || []).length >= 2, "Membrane must show real hash values.");

  const reset = await matchingControl(page, [/reset/i], "membrane reset");
  const inward = await matchingControl(
    page,
    [/verify.*read/i, /read.*public/i, /pull.*public/i, /import.*public/i, /assimil/i],
    "verified inward-read",
  );
  const outward = await matchingControl(
    page,
    [/export/i, /outward/i, /private.*public/i, /send.*public/i],
    "private-to-public attempt",
  );
  const conflict = await matchingControl(page, [/conflict/i, /contradict/i], "conflict injection");
  const mutation = await matchingControl(
    page,
    [/mutat/i, /unsafe/i, /allow.*out/i, /disable.*membrane/i, /break.*privacy/i],
    "privacy mutation",
  );

  await reset.click();
  await page.waitForTimeout(100);
  const inwardResult = await clickForChange(page, inward, "Verified inward read");
  check(
    /verified|accepted|enrich|assimil|imported|copied/i.test(inwardResult),
    "Verified public data was not visibly accepted into the private view.",
  );
  check(
    (await page.locator("#inward-assertion").getAttribute("class") || "").includes("pass"),
    "Verified inward assimilation did not produce a passing computed assertion.",
  );
  const outwardResult = await clickForChange(page, outward, "Private export attempt");
  check(
    /block|refus|denied|unchanged|never leave|privacy.*pass/i.test(outwardResult),
    "Outward private write was not visibly blocked with public bytes unchanged.",
  );
  check(
    (await page.locator("#privacy-assertion").getAttribute("class") || "").includes("pass"),
    "Blocked outward transfer did not preserve a passing byte-level privacy assertion.",
  );

  await reset.click();
  await page.waitForTimeout(100);
  await clickForChange(page, conflict, "Conflict injection");
  const conflictResult = await clickForChange(page, inward, "Conflicting inward read");
  check(
    /conflict|contradiction|reject|refus/i.test(conflictResult),
    "A conflicting public frame was not visibly refused.",
  );
  check(
    (await page.locator("#conflict-assertion").getAttribute("class") || "").includes("pass"),
    "Conflict refusal did not produce a passing contradiction-gate assertion.",
  );

  await clickForChange(page, mutation, "Unsafe membrane mutation");
  const mutated = compact(await page.locator("body").innerText());
  const failureNodeCount = await page.locator(
    '.fail, .failed, .bad, [data-status="fail"], [aria-invalid="true"]',
  ).count();
  check(
    failureNodeCount > 0 || /\bFAIL(?:ED)?\b|privacy breach|privacy violated|unsafe write/i.test(mutated),
    "Privacy mutation did not turn a visible assertion red/failing.",
  );
  assertClean();
  await page.close();
  console.log("  ✓ membrane verifies inward data, rejects conflicts, and blocks modeled private export");
}

async function checkReattachExercise(context, origin) {
  const { page, assertClean } = await openCheckedPage(context, origin, "play/reattach.html", false);
  const initial = compact(await page.locator("body").innerText());
  check(/stranded/i.test(initial), "Re-attach page does not expose the stranded frame.");
  check(/local head/i.test(initial), "Re-attach ladder is missing the local head.");
  check(/local dimension/i.test(initial), "Re-attach ladder is missing another local dimension.");
  check(/federat|public/i.test(initial), "Re-attach ladder is missing federated candidates.");
  check(
    /dry[- ]?hole|no[- ]?op/i.test(initial),
    "Re-attach algorithm must state its dry-hole no-op behavior.",
  );
  const candidateCount = Math.max(
    await page.locator("[data-candidate], .candidate").count(),
    await page.locator("#candidate-body tr").count(),
    (initial.match(/\bcandidate\b/gi) || []).length,
  );
  check(candidateCount >= 4, `Re-attach page must expose at least four candidates; found ${candidateCount}.`);

  const reset = await matchingControl(page, [/reset/i], "re-attach reset");
  const run = await matchingControl(
    page,
    [/run.*attach/i, /reattach/i, /re-attach/i, /search.*ladder/i, /graft/i],
    "deterministic re-attach",
  );
  const tamper = await matchingControl(page, [/tamper/i, /change.*read/i, /mutat/i], "declared-read tamper");
  await reset.click();
  await page.waitForTimeout(100);
  const firstRun = await clickForChange(page, run, "Deterministic re-attach");
  check(/conflict/i.test(firstRun), "Re-attach run did not expose exact conflict results.");
  check(/first.*(?:free|valid|compatible)|selected|chosen/i.test(firstRun), "Re-attach run did not expose its first valid choice.");
  check(/grafted[_ -]from|provenance/i.test(firstRun), "Graft provenance was not exposed.");
  check(/preserv/i.test(firstRun), "Superseded original was not visibly preserved.");
  check(
    (await page.locator("#integrity-assertion").getAttribute("class") || "").includes("pass"),
    "Re-attach did not independently verify stranded and candidate hashes.",
  );
  check(
    (await page.locator("#choice-assertion").getAttribute("class") || "").includes("pass"),
    "Re-attach did not prove that the first contradiction-free candidate won.",
  );
  check(
    (await page.locator("#provenance-assertion").getAttribute("class") || "").includes("pass"),
    "Re-attach provenance or original preservation did not pass.",
  );

  await clickForChange(page, tamper, "Declared-read tamper");
  const secondRun = await clickForChange(page, run, "Re-attach after tamper");
  check(/tamper|changed|different|conflict/i.test(secondRun), "Tampering did not visibly alter conflict evaluation.");
  check(firstRun !== secondRun, "Tampering did not change the deterministic re-attach result.");

  const dryHole = await matchingControl(page, [/dry[- ]?hole/i, /make.*conflict/i], "dry-hole", false);
  if (dryHole) {
    await clickForChange(page, dryHole, "Dry-hole scenario");
    check(
      /dry[- ]?hole|no[- ]?op|no candidate/i.test(await page.locator("body").innerText()),
      "Dry-hole scenario did not remain a no-op.",
    );
    check(
      (await page.locator("#dry-assertion").getAttribute("class") || "").includes("pass"),
      "Dry-hole scenario did not produce a passing no-op assertion.",
    );
  }
  assertClean();
  await page.close();
  console.log("  ✓ re-attach uses an ordered conflict ladder, provenance, preservation, and tamper response");
}

function parseFidelity(text) {
  const ratio = text.match(/fidelity[^0-9]*(\d+)\s*\/\s*(\d+)/i);
  if (ratio) return { numerator: Number(ratio[1]), denominator: Number(ratio[2]) };
  const percent = text.match(/fidelity[^0-9]*(\d+(?:\.\d+)?)\s*%/i);
  if (percent) return { numerator: Number(percent[1]), denominator: 100 };
  const decimal = text.match(/fidelity[^0-9]*(0(?:\.\d+)|1(?:\.0+)?)/i);
  if (decimal) return { numerator: Number(decimal[1]), denominator: 1 };
  return null;
}

async function checkMergeExercise(context, origin) {
  const { page, assertClean } = await openCheckedPage(context, origin, "play/merge-fidelity.html", false);
  const initial = compact(await page.locator("body").innerText());
  check(/dimension/i.test(initial) && /tick/i.test(initial), "Merge page must expose dimensions and logical ticks.");
  check(/align/i.test(initial), "Merge page is missing an aligned shared dimension.");
  check(/contradict|conflict/i.test(initial), "Merge page is missing a contradictory shared dimension.");
  check(/one[- ]sided|only one|disjoint/i.test(initial), "Merge page is missing a one-sided dimension.");
  check(/hash|[0-9a-f]{8,64}/i.test(initial), "Merge page must expose content hashes.");

  const reset = await matchingControl(page, [/reset/i], "merge reset");
  const merge = await matchingControl(
    page,
    [/compute.*fidelity/i, /run.*merge/i, /^merge/i, /deterministic.*merge/i],
    "fidelity merge",
  );
  const mutation = await matchingControl(
    page,
    [/mutat/i, /overwrite/i, /discard.*conflict/i, /break.*preserv/i],
    "conflict-overwrite mutation",
  );
  await reset.click();
  await page.waitForTimeout(100);
  const result = await clickForChange(page, merge, "Fidelity merge");
  const fidelity = parseFidelity(result);
  check(fidelity, "Merge did not expose an exact fidelity ratio, decimal, or percentage.");
  check(fidelity.denominator > 0, "Fidelity denominator must be non-zero.");
  check(
    fidelity.numerator === 2 && fidelity.denominator === 3,
    `Expected exact fidelity 2/3; found ${fidelity.numerator}/${fidelity.denominator}.`,
  );
  check(/parallel/i.test(result), "Conflicting dimensions were not visibly preserved in parallel.");
  check(/one[- ]sided|assimil|import|disjoint/i.test(result), "One-sided dimensions were not visibly assimilated.");
  for (const selector of ["#integrity-assertion", "#merge-assertion", "#preservation-assertion"]) {
    check(
      (await page.locator(selector).getAttribute("class") || "").includes("pass"),
      `${selector} did not pass after the valid merge.`,
    );
  }

  await clickForChange(page, mutation, "Conflict-overwrite mutation");
  const mutated = compact(await page.locator("body").innerText());
  const failureNodeCount = await page.locator(
    '.fail, .failed, .bad, [data-status="fail"], [aria-invalid="true"]',
  ).count();
  check(
    failureNodeCount > 0 || /\bFAIL(?:ED)?\b|silently overwrote|preservation violated/i.test(mutated),
    "Conflict-overwrite mutation did not turn a visible preservation assertion red/failing.",
  );
  assertClean();
  await page.close();
  console.log("  ✓ merge computes non-trivial fidelity and preserves conflicts in parallel");
}

async function runPythonSample() {
  const result = await new Promise((resolveRun, reject) => {
    const child = spawn(process.env.PYTHON || "python3", ["samples/frame_chain.py"], {
      cwd: root,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => child.kill("SIGTERM"), 15_000);
    child.stdout.on("data", chunk => {
      stdout += chunk;
    });
    child.stderr.on("data", chunk => {
      stderr += chunk;
    });
    child.once("error", reject);
    child.once("close", code => {
      clearTimeout(timer);
      resolveRun({ code, stderr, stdout });
    });
  });
  check(result.code === 0, `samples/frame_chain.py failed (${result.code}):\n${result.stderr}`);
  check(/verify\(chain\) -> True/.test(result.stdout), "Python sample did not verify the intact chain.");
  check(
    (result.stdout.match(/verify(?:\(chain\))?.*False/g) || []).length >= 1,
    "Python sample did not demonstrate tamper detection.",
  );
  check(/broken at #2/.test(result.stdout), "Python sample did not prove that the next link remembers tampering.");
  console.log("  ✓ samples/frame_chain.py verifies integrity and detects both tamper cases");
}

let server;
let browser;
try {
  console.log(`papercheck: ${browserName} ${mode}`);
  const started = await startServer();
  server = started.server;
  const launchOptions = { headless: true };
  if (browserName === "chromium") {
    launchOptions.args = [
      "--disable-gpu-sandbox",
      "--enable-unsafe-swiftshader",
      "--use-gl=swiftshader",
    ];
  }
  browser = await browserTypes[browserName].launch(launchOptions);
  const context = await browser.newContext();

  await runSmoke(context, started.origin);
  await checkPaperEmbeds(context, started.origin);
  await checkGuidePath(context, started.origin);
  await checkStandaloneGuidance(context, started.origin);
  await checkEvidencePage(context, started.origin);
  if (mode === "full") {
    await checkPromptCopy(context, started.origin);
    await checkClockExercise(context, started.origin);
    await checkScanExercise(context, started.origin);
    await checkSuccessionExercise(context, started.origin);
    await checkMembraneExercise(context, started.origin);
    await checkReattachExercise(context, started.origin);
    await checkMergeExercise(context, started.origin);
    await runPythonSample();
  }
  await context.close();
  console.log(`papercheck: PASS (${browserName} ${mode})`);
} catch (error) {
  console.error(`papercheck: FAIL (${browserName} ${mode})`);
  console.error(error?.stack || error);
  process.exitCode = 1;
} finally {
  await browser?.close().catch(() => {});
  if (server) await new Promise(resolveClose => server.close(resolveClose));
}
