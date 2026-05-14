const fs = require("node:fs");
const { Resvg } = require("@resvg/resvg-js");

const args = process.argv.slice(2);

if (args.length < 2 || args.length % 2 !== 0) {
  console.error("Usage: node render_svg_resvg.js input.svg output.png [input2.svg output2.png ...]");
  process.exit(2);
}

for (let i = 0; i < args.length; i += 2) {
  const inputSvg = args[i];
  const outputPng = args[i + 1];
  const svg = fs.readFileSync(inputSvg);
  const resvg = new Resvg(svg, {
    fitTo: { mode: "original" },
    font: {
      loadSystemFonts: true,
      defaultFontFamily: "Microsoft YaHei",
    },
  });

  fs.writeFileSync(outputPng, resvg.render().asPng());
}
