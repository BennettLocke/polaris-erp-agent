const fs = require("node:fs");
const path = require("node:path");
const { Resvg } = require("@resvg/resvg-js");

const args = process.argv.slice(2);
const defaultFont = process.env.BAG_TEMPLATE_FONT_FAMILY || "Noto Sans CJK SC";

function resolveFontFiles() {
  const envFiles = (process.env.BAG_TEMPLATE_FONT_FILES || "")
    .split(path.delimiter)
    .map((file) => file.trim())
    .filter(Boolean);
  const candidates = [
    ...envFiles,
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/source-han-sans/SourceHanSansSC-Regular.otf",
    "/usr/share/fonts/opentype/source-han-sans/SourceHanSansSC-Bold.otf",
    "C:\\Windows\\Fonts\\msyh.ttc",
    "C:\\Windows\\Fonts\\msyhbd.ttc",
  ];
  return [...new Set(candidates)].filter((file) => fs.existsSync(file));
}

if (args.length < 2 || args.length % 2 !== 0) {
  console.error("Usage: node render_svg_resvg.js input.svg output.png [input2.svg output2.png ...]");
  process.exit(2);
}

for (let i = 0; i < args.length; i += 2) {
  const inputSvg = args[i];
  const outputPng = args[i + 1];
  const svg = fs.readFileSync(inputSvg);
  const fontFiles = resolveFontFiles();
  const resvg = new Resvg(svg, {
    fitTo: { mode: "original" },
    font: {
      fontFiles,
      loadSystemFonts: true,
      defaultFontFamily: defaultFont,
    },
  });

  fs.writeFileSync(outputPng, resvg.render().asPng());
}
