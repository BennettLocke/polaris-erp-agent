const fs = require("node:fs");
const { Resvg } = require("@resvg/resvg-js");

const [, , inputSvg, outputPng] = process.argv;

if (!inputSvg || !outputPng) {
  console.error("Usage: node render_svg_resvg.js input.svg output.png");
  process.exit(2);
}

const svg = fs.readFileSync(inputSvg);
const resvg = new Resvg(svg, {
  fitTo: { mode: "original" },
  font: {
    loadSystemFonts: true,
    defaultFontFamily: "Microsoft YaHei",
  },
});

fs.writeFileSync(outputPng, resvg.render().asPng());
