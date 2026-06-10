import { existsSync } from "node:fs";
import { mkdir, readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright-core");

const root = process.cwd();
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, "..", "..");

const dataPath = path.resolve(process.argv[2] || path.join(root, "taobao-detail-source", "product-data.json"));
const templatePath = path.resolve(process.argv[3] || path.join(projectRoot, "assets", "taobao_detail", "detail-template.html"));
const outputDir = path.resolve(process.argv[4] || path.join(root, "taobao-detail-editable-output"));

const fontRegularPath = process.env.TAOBAO_DETAIL_FONT_REGULAR || path.join(
  projectRoot,
  "assets",
  "fonts",
  "alibaba-puhui",
  "AlibabaPuHuiTi-3-55-Regular.woff2"
);
const fontMediumPath = process.env.TAOBAO_DETAIL_FONT_MEDIUM || path.join(
  projectRoot,
  "assets",
  "fonts",
  "alibaba-puhui",
  "AlibabaPuHuiTi-3-65-Medium.woff2"
);

const slices = [
  { name: "detail-01.jpg", y: 0, height: 1139 },
  { name: "detail-02.jpg", y: 1139, height: 696 },
  { name: "detail-03.jpg", y: 1835, height: 893 },
  { name: "detail-04.jpg", y: 2728, height: 842 },
  { name: "detail-05.jpg", y: 3570, height: 918 },
];

function fontUrl(filePath) {
  if (!existsSync(filePath)) return "";
  return pathToFileURL(filePath).href;
}

function detectBrowserExecutable() {
  const candidates = [
    process.env.TAOBAO_DETAIL_CHROMIUM_PATH,
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
  ].filter(Boolean);
  return candidates.find((candidate) => existsSync(candidate));
}

function jsonForScriptTag(data) {
  return JSON.stringify(data, null, 2).replace(/</g, "\\u003c").replace(/<\/script/gi, "<\\/script");
}

function injectDataIntoTemplate(template, data) {
  const pattern = /(<script id="taobao-detail-data" type="application\/json">\s*)[\s\S]*?(\s*<\/script>)/;
  if (!pattern.test(template)) {
    throw new Error("detail-template.html is missing the taobao-detail-data JSON script");
  }
  return template.replace(pattern, (_match, start, end) => `${start}${jsonForScriptTag(data)}${end}`);
}

function fontFaceOverrideCss() {
  const regular = fontUrl(fontRegularPath);
  const medium = fontUrl(fontMediumPath);
  if (!regular || !medium) return "";

  return `@font-face {
        font-family: "AlibabaPuhuiEditable";
        src: url("${regular}") format("woff2");
        font-weight: 400;
      }

      @font-face {
        font-family: "AlibabaPuhuiEditable";
        src: url("${medium}") format("woff2");
        font-weight: 500;
      }`;
}

const data = JSON.parse(await readFile(dataPath, "utf8"));
const template = await readFile(templatePath, "utf8");
const pageWidth = data.page?.width || 800;
const taobaoWidth = data.page?.taobaoWidth || 800;

const renderedHtml = injectDataIntoTemplate(template, data)
  .replace("/* __EDITABLE_FONT_FACE__ */", fontFaceOverrideCss());

await mkdir(outputDir, { recursive: true });

const executablePath = detectBrowserExecutable();
if (!executablePath) {
  throw new Error("No Chromium or Edge executable found. Set TAOBAO_DETAIL_CHROMIUM_PATH to enable Taobao detail rendering.");
}
const browser = await chromium.launch({
  headless: true,
  executablePath,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const page = await browser.newPage({
  viewport: { width: pageWidth, height: 4600 },
  deviceScaleFactor: 1,
});

await page.setContent(renderedHtml, { waitUntil: "load" });
await page.evaluate(() => document.fonts && document.fonts.ready);
await page.waitForTimeout(100);

for (const slice of slices) {
  await page.screenshot({
    path: path.join(outputDir, slice.name),
    type: "jpeg",
    quality: 100,
    clip: {
      x: 0,
      y: slice.y,
      width: pageWidth,
      height: slice.height,
    },
  });
}

await browser.close();

console.log(
  JSON.stringify(
    {
      dataPath,
      templatePath,
      outputDir,
      executablePath,
      images: slices.map((slice) => slice.name),
      taobaoWidth,
    },
    null,
    2
  )
);
