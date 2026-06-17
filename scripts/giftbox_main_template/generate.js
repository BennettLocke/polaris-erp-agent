#!/usr/bin/env node

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const {
  DEFAULT_OPTIONS,
  createGiftboxMainSvg,
} = require("./template.js");

const RENDERER = path.resolve(__dirname, "../bag_template/render_svg_resvg.js");
const TRIM_SCRIPT = path.resolve(__dirname, "trim_whitespace.py");
const DEFAULT_TRIM_MARGIN = 16;

const MIME_TYPES = new Map([
  [".apng", "image/apng"],
  [".avif", "image/avif"],
  [".gif", "image/gif"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".png", "image/png"],
  [".svg", "image/svg+xml"],
  [".webp", "image/webp"],
]);

function pythonCommandCandidates() {
  const candidates = [];
  if (process.env.PYTHON) {
    candidates.push(process.env.PYTHON);
  }
  candidates.push("python", "python3");
  return [...new Set(candidates.filter(Boolean))];
}

function runTrimScript(filePath, outputPath, margin) {
  const errors = [];
  for (const command of pythonCommandCandidates()) {
    const result = spawnSync(command, [TRIM_SCRIPT, filePath, outputPath, String(margin)], {
      cwd: path.resolve(__dirname, "../.."),
      encoding: "utf-8",
    });

    if (result.status === 0 && fs.existsSync(outputPath)) {
      return;
    }

    errors.push(
      [
        `command=${command}`,
        result.error && `error=${result.error.message}`,
        typeof result.status === "number" && `status=${result.status}`,
        result.stdout && `stdout:\n${result.stdout}`,
        result.stderr && `stderr:\n${result.stderr}`,
      ]
        .filter(Boolean)
        .join("\n")
    );
  }
  throw new Error(["Image trim failed.", ...errors].filter(Boolean).join("\n\n"));
}

function usage() {
  return [
    "Usage:",
    "  node scripts/giftbox_main_template/generate.js --output output.png [--image product.png]",
    "",
    "Options:",
    "  --image <path>             Product image. Uses placeholder when omitted.",
    "  --output <path>            Output .png or .svg path.",
    "  --headline <text>          Main title.",
    "  --series <text>            Series name.",
    "  --series-suffix <text>     Series suffix.",
    "  --top-note <text>          Top slogan.",
    "  --english-note <text>      English line.",
    "  --spec <text>              Spec text.",
    "  --colors <list>            Comma-separated swatches, for example #c1272d,#f7931e.",
    "  --no-trim                  Do not trim white/transparent margins before placing the product image.",
    "  --trim-margin <px>         Margin kept around the trimmed product image. Default: 16.",
  ].join("\n");
}

function parseArgs(argv) {
  const result = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) {
      throw new Error(`Unknown argument: ${arg}`);
    }

    const eqIndex = arg.indexOf("=");
    if (eqIndex > -1) {
      result[arg.slice(2, eqIndex)] = arg.slice(eqIndex + 1);
      continue;
    }

    const key = arg.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      result[key] = "true";
    } else {
      result[key] = next;
      i += 1;
    }
  }
  return result;
}

function imageToDataUri(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const mime = MIME_TYPES.get(ext) || "application/octet-stream";
  const data = fs.readFileSync(filePath).toString("base64");
  return `data:${mime};base64,${data}`;
}

function trimImageWhitespace(filePath, tempDir, args = {}) {
  if (args["no-trim"] === "true") {
    return filePath;
  }

  const ext = path.extname(filePath).toLowerCase();
  if (!MIME_TYPES.has(ext) || ext === ".svg" || ext === ".gif") {
    return filePath;
  }

  const margin = Number(args["trim-margin"] || DEFAULT_TRIM_MARGIN);
  const safeMargin = Number.isFinite(margin) && margin >= 0 ? Math.round(margin) : DEFAULT_TRIM_MARGIN;
  const outputPath = path.join(tempDir, `trimmed-${Date.now()}-${Math.random().toString(16).slice(2)}.png`);
  runTrimScript(filePath, outputPath, safeMargin);
  return outputPath;
}

function ensureParentDir(filePath) {
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
}

function buildOptions(args, runtime = {}) {
  const options = {};
  if (args.image) {
    const tempDir = runtime.tempDir || fs.mkdtempSync(path.join(os.tmpdir(), "giftbox-main-template-"));
    const imagePath = trimImageWhitespace(path.resolve(args.image), tempDir, args);
    options.imageHref = imageToDataUri(imagePath);
  }
  if (args.headline) {
    options.headline = args.headline;
  }
  if (args.series) {
    options.series = args.series;
  }
  if (args["series-suffix"]) {
    options.seriesSuffix = args["series-suffix"];
  }
  if (args["top-note"]) {
    options.topNote = args["top-note"];
  }
  if (args["english-note"]) {
    options.englishNote = args["english-note"];
  }
  if (args.spec) {
    options.specText = args.spec;
  }
  if (args.colors) {
    options.swatches = args.colors
      .split(",")
      .map((color) => color.trim())
      .filter(Boolean);
  }
  return {
    ...DEFAULT_OPTIONS,
    ...options,
  };
}

function renderPng(svg, outputPath) {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "giftbox-main-template-"));
  const tempSvg = path.join(tempDir, "source.svg");

  try {
    fs.writeFileSync(tempSvg, svg, "utf-8");
    const result = spawnSync(process.execPath, [RENDERER, tempSvg, outputPath], {
      cwd: path.resolve(__dirname, "../.."),
      env: {
        ...process.env,
        BAG_TEMPLATE_FONT_FAMILY:
          process.env.BAG_TEMPLATE_FONT_FAMILY || "Noto Sans CJK SC",
      },
      encoding: "utf-8",
    });

    if (result.status !== 0) {
      throw new Error(
        [
          "PNG render failed.",
          result.stdout && `stdout:\n${result.stdout}`,
          result.stderr && `stderr:\n${result.stderr}`,
        ]
          .filter(Boolean)
          .join("\n")
      );
    }
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || args.h) {
    console.log(usage());
    return;
  }

  if (!args.output) {
    console.error(usage());
    process.exit(2);
  }

  const outputPath = path.resolve(args.output);
  const outputExt = path.extname(outputPath).toLowerCase();
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "giftbox-main-template-"));

  try {
    const svg = createGiftboxMainSvg(buildOptions(args, { tempDir }));
    ensureParentDir(outputPath);
    if (outputExt === ".svg") {
      fs.writeFileSync(outputPath, svg, "utf-8");
    } else if (outputExt === ".png") {
      renderPng(svg, outputPath);
    } else {
      throw new Error("Only .png and .svg outputs are supported right now.");
    }
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }

  console.log(`Generated ${outputPath}`);
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}

module.exports = {
  buildOptions,
  imageToDataUri,
  pythonCommandCandidates,
  trimImageWhitespace,
};
