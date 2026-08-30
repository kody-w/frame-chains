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
  for (let index = 0; index < await buttons.count(); index += 1) {
    const button = buttons.nth(index);
    const text = compact(
      `${await button.innerText().catch(() => "")} `
      + `${await button.getAttribute("aria-label") || ""} `
      + `${await button.getAttribute("title") || ""}`,
    );
    if (patterns.some((pattern) => pattern.test(text))) return button;
  }
  throw new Error(`${label}: no matching control`);
}

async function waitForVisibleVerdict(page, kind) {
  const pattern = kind === "pass" ? /\bPASS\b/i : /\b(?:FAIL|REJECTED|BLOCKED|DETECTED)\b/i;
  await page.waitForFunction(
    ({ source, flags }) => {
      const expression = new RegExp(source, flags);
      const candidates = [
        ...document.querySelectorAll(
          '.pass, .fail, .failed, .bad, [data-status="pass"], [data-status="fail"], [role=status]',
        ),
      ].filter((node) => {
        const rect = node.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
      });
      return candidates.some((node) => expression.test(node.textContent || ""));
    },
    { source: pattern.source, flags: pattern.flags },
    { timeout: 8_000 },
  );
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
  const guided = await matchingButton(
    page,
    [/\bguided\b/i, /\brun\b.*\b(?:mission|scenario|demo|loop|swarm|tour)\b/i, /\bauto\b/i],
    `${slug} guided run`,
  );
  await guided.click();
  await page.waitForTimeout(2_500);
  const afterGuided = compact(await page.locator("body").innerText());
  check(afterGuided !== before, `${slug}: guided run produced no visible change`);
  await waitForVisibleVerdict(page, "pass");

  const mutation = await matchingButton(
    page,
    [/\bmutat/i, /\btamper/i, /\battack/i, /\bforge/i, /\bunsafe/i, /\boverwrite/i, /\btyrant/i, /\bcorrupt/i, /\bbreak\b/i],
    `${slug} failure path`,
  );
  await mutation.click();
  await page.waitForTimeout(700);
  await waitForVisibleVerdict(page, "fail");

  const copy = await matchingButton(page, [/\bcopy\b.*\bprompt\b/i], `${slug} prompt copy`);
  const prompt = await copy.evaluate((button) => {
    const scope = button.closest("details, section, article") || document;
    const candidate = scope.querySelector("pre") || document.querySelector("pre");
    return candidate?.textContent?.trim() || "";
  });
  check(prompt.length > 400, `${slug}: proof prompt is too short`);
  await copy.click();
  const copied = await page.evaluate(() => window.__showcaseClipboard || "");
  check(copied.trim() === prompt, `${slug}: prompt copy did not copy exact text`);

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

  for (const slug of frames) {
    await exerciseFrame(context, started.origin, slug);
  }
  await context.close();
  console.log("showcasecheck: PASS · 10/10 frames");
} catch (error) {
  console.error("showcasecheck: FAIL");
  console.error(error?.stack || error);
  process.exitCode = 1;
} finally {
  await browser?.close().catch(() => {});
  if (server) await new Promise((resolveClose) => server.close(resolveClose));
}
