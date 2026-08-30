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
const interactionPlans = {
  "03-mars-colony": {
    positive: [{ selector: "#nextButton", repeat: 8, waitMs: 450 }],
    failure: [
      { selector: "#resetButton", waitMs: 300 },
      { selector: "#injectButton", waitMs: 300 },
      { selector: "#scanButton", waitMs: 700 },
      { selector: "#sweepButton", waitMs: 500 },
    ],
  },
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

async function matchingButton(page, patterns, label) {
  const buttons = page.locator("button, [role=button]");
  let disabledMatch = null;
  for (let index = 0; index < await buttons.count(); index += 1) {
    const button = buttons.nth(index);
    const text = compact(
      `${await button.innerText().catch(() => "")} `
      + `${await button.getAttribute("aria-label") || ""} `
      + `${await button.getAttribute("title") || ""}`,
    );
    if (patterns.some((pattern) => pattern.test(text))) {
      if (await button.isVisible() && !await button.isDisabled()) return button;
      disabledMatch ||= button;
    }
  }
  if (disabledMatch) throw new Error(`${label}: matching control is disabled`);
  throw new Error(`${label}: no matching control`);
}

async function hasVisibleVerdict(page, kind) {
  const pattern = kind === "pass"
    ? /PASS|VERIF(?:Y|IED|IES|ICATION)|AGREE|VALID|SUCCESS|✓/i
    : /FAIL|REJECT|BLOCK|DETECT|DIVERG|MISMATCH|VIOLAT|INVALID|RED OBSERVED|QUARANTIN|[×✗]/i;
  return page.evaluate(({ source, flags }) => {
    const expression = new RegExp(source, flags);
    const candidates = [
      ...document.querySelectorAll(
        '.assertion, .assertion-result, .live-region, .status-pill, .quarantine-item, .pass, .valid, .success, .fail, .failed, .bad, .invalid, .rejected, .error, .changed, .verdict, .ledger-result, [aria-invalid="true"], [data-status="pass"], [data-status="fail"], [role=status]',
      ),
    ].filter((node) => {
      const rect = node.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    });
    return candidates.some((node) => expression.test(node.textContent || ""));
  }, { source: pattern.source, flags: pattern.flags });
}

async function waitForVisibleVerdict(page, kind, label) {
  const pattern = kind === "pass"
    ? /PASS|VERIF(?:Y|IED|IES|ICATION)|AGREE|VALID|SUCCESS|✓/i
    : /FAIL|REJECT|BLOCK|DETECT|DIVERG|MISMATCH|VIOLAT|INVALID|RED OBSERVED|QUARANTIN|[×✗]/i;
  try {
    await page.waitForFunction(
      ({ source, flags }) => {
        const expression = new RegExp(source, flags);
        const candidates = [
          ...document.querySelectorAll(
            '.assertion, .assertion-result, .live-region, .status-pill, .quarantine-item, .pass, .valid, .success, .fail, .failed, .bad, .invalid, .rejected, .error, .changed, .verdict, .ledger-result, [aria-invalid="true"], [data-status="pass"], [data-status="fail"], [role=status]',
          ),
        ].filter((node) => {
          const rect = node.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0;
        });
        return candidates.some((node) => expression.test(node.textContent || ""));
      },
      { source: pattern.source, flags: pattern.flags },
      { timeout: 15_000 },
    );
  } catch {
    throw new Error(`${label}: no visible ${kind.toUpperCase()} verdict`);
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
  const before = compact(await page.locator("body").innerText());
  const plan = interactionPlans[slug];
  if (plan) {
    for (const action of plan.positive) {
      const control = page.locator(action.selector);
      for (let repeat = 0; repeat < (action.repeat || 1); repeat += 1) {
        check(
          !await control.isDisabled(),
          `${slug}: ${action.selector} disabled at positive step ${repeat + 1}`,
        );
        await control.click();
        await page.waitForTimeout(action.waitMs || 350);
      }
    }
  } else {
    const guided = await matchingButton(
      page,
      [/\bguided\b/i, /\brun all\b/i, /\brun next\b/i, /\brun control\b/i, /\bauto\b/i],
      `${slug} guided run`,
    );
    const guidedLabel = compact(
      `${await guided.innerText().catch(() => "")} `
      + `${await guided.getAttribute("aria-label") || ""} `
      + `${await guided.getAttribute("title") || ""}`,
    );
    const guidedSteps = /\bnext\b/i.test(guidedLabel) ? 14 : 1;
    for (let step = 0; step < guidedSteps; step += 1) {
      if (await guided.isDisabled()) break;
      await guided.click();
      await page.waitForTimeout(step === 0 ? 1_000 : 350);
      if (!/\bnext\b/i.test(guidedLabel) && await hasVisibleVerdict(page, "pass")) break;
    }
    if (!/\bnext\b/i.test(guidedLabel)) {
      let waitingForCompletion = await guided.isDisabled();
      if (waitingForCompletion) {
        const reportsRunning = /\b(?:running|working|playing|processing|building)\b/i.test(
          compact(await guided.innerText().catch(() => "")),
        );
        for (let attempt = 0; waitingForCompletion && attempt < 80; attempt += 1) {
          await page.waitForTimeout(250);
          waitingForCompletion = await guided.isDisabled();
          if (reportsRunning) {
            const currentLabel = compact(await guided.innerText().catch(() => ""));
            if (!/\b(?:running|working|playing|processing|building)\b/i.test(currentLabel)) {
              break;
            }
          }
        }
        await page.waitForTimeout(500);
      } else {
        let activeLabel = compact(
          `${await guided.innerText().catch(() => "")} `
          + `${await guided.getAttribute("aria-label") || ""} `
          + `${await guided.getAttribute("title") || ""}`,
        );
        if (/\b(?:pause|running|working|playing|processing|building)\b/i.test(activeLabel)) {
          for (let attempt = 0; attempt < 80; attempt += 1) {
            await page.waitForTimeout(250);
            activeLabel = compact(
              `${await guided.innerText().catch(() => "")} `
              + `${await guided.getAttribute("aria-label") || ""} `
              + `${await guided.getAttribute("title") || ""}`,
            );
            if (!/\b(?:pause|running|working|playing|processing|building)\b/i.test(activeLabel)) {
              break;
            }
          }
          await page.waitForTimeout(500);
        } else {
          await page.waitForTimeout(4_000);
        }
      }
    } else {
      await page.waitForTimeout(1_000);
    }
  }
  const afterGuided = compact(await page.locator("body").innerText());
  check(afterGuided !== before, `${slug}: guided run produced no visible change`);
  await waitForVisibleVerdict(page, "pass", `${slug} guided run`);

  if (plan) {
    for (const action of plan.failure) {
      const control = page.locator(action.selector);
      check(!await control.isDisabled(), `${slug}: ${action.selector} disabled in failure path`);
      await control.click();
      await page.waitForTimeout(action.waitMs || 350);
    }
  } else if (!await hasVisibleVerdict(page, "fail")) {
    const mutation = await matchingButton(
      page,
      [/\bmutat/i, /\btamper/i, /\battack/i, /\bforge/i, /\bunsafe/i, /\boverwrite/i, /\btyrant/i, /\bcorrupt/i, /\bfull sweep\b/i, /\bearly claim\b/i, /\bforce contradiction\b/i, /\bbreak\b/i],
      `${slug} failure path`,
    );
    await mutation.click();
    await page.waitForTimeout(700);
  }
  await waitForVisibleVerdict(page, "fail", `${slug} mutation`);

  await page.locator("details").evaluateAll((details) => {
    details.forEach((item) => { item.open = true; });
  });
  const copy = await matchingButton(page, [/\bcopy\b.*\bprompt\b/i], `${slug} prompt copy`);
  await copy.click();
  const copied = await page.evaluate(() => window.__showcaseClipboard || "");
  check(copied.trim().length > 400, `${slug}: copied proof prompt is too short`);
  check(
    /SHA-256/i.test(copied) && /canonical/i.test(copied),
    `${slug}: copied proof prompt omits hashing or canonicalization`,
  );

  const reset = await matchingButton(page, [/\breset\b/i], `${slug} reset`);
  const beforeReset = compact(await page.locator("body").innerText());
  await reset.click();
  await page.waitForTimeout(300);
  const afterReset = compact(await page.locator("body").innerText());
  check(afterReset !== beforeReset, `${slug}: reset produced no visible state change`);

  assertClean();
  await page.close();
  console.log(`  ✓ ${slug}: mobile, guided path, failure path, prompt copy, reset`);
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
