const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const templatePath = process.argv[2];
const imagePath = process.argv[3];
const outDir = process.argv[4] || path.resolve("data", "generated");

if (!templatePath || !imagePath) {
  console.error("Usage: node render_bag_template_preview.js <template.html> <image.png> [out_dir]");
  process.exit(1);
}

function fileUrl(filePath) {
  return `file:///${path.resolve(filePath).replace(/\\/g, "/")}`;
}

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
  const browser = await chromium.launch({
    headless: true,
    executablePath: fs.existsSync(edgePath) ? edgePath : undefined,
  });
  const page = await browser.newPage({ viewport: { width: 1800, height: 4200 }, deviceScaleFactor: 1 });
  await page.goto(fileUrl(templatePath), { waitUntil: "load" });

  const imageBytes = fs.readFileSync(imagePath);
  const imageDataUrl = `data:image/png;base64,${imageBytes.toString("base64")}`;

  await page.evaluate(async ({ imageDataUrl }) => {
    const $ = (id) => document.getElementById(id);
    const values = {
      codeInput: "SJ0506",
      colorNameInput: "天青蓝",
      subtitleInput: "烫金工艺 尽显格调",
      typeInput: "武夷岩茶",
      widthInput: "55MM",
      heightInput: "150MM",
      specInput: "55MMx150MM",
      bagColorInput: "#88b8ca",
      cornerXInput: "45",
      cornerYInput: "1608",
      cornerAngleInput: "48",
      cornerSizeInput: "800",
      cornerHeightInput: "1080",
      cornerScaleInput: "1.00",
      bigXInput: "1200",
      bigYInput: "1800",
      bigAngleInput: "49",
      bigWidthInput: "800",
      topLeftXInput: "58",
      topLeftYInput: "104",
      topLeftSizeInput: "430",
      topRightXInput: "520",
      topRightYInput: "492",
      topRightSizeInput: "430",
    };
    for (const [id, value] of Object.entries(values)) {
      const el = $(id);
      if (el) el.value = value;
    }
    if (typeof window.setProductImage === "function") {
      await window.setProductImage(imageDataUrl);
    }
    if (typeof window.render === "function") window.render();

    const setText = (id, value) => {
      const el = $(id);
      if (el) el.textContent = value;
    };
    setText("topCodeText", "编号：SJ0506");
    setText("titleText", "天青蓝");
    setText("subtitleText", "烫金工艺 尽显格调");
    setText("typeText", "武夷岩茶");
    setText("specText", "规格：55MMx150MM");
    setText("detailTitleA", "烫金工艺");
    setText("detailTitleB", "尽显格调");
    setText("detailCodeText", "编号：SJ0506");
    setText("detailTypeText", "武夷岩茶");
    setText("detailSpecText", "规格：55MMx150MM");
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }, { imageDataUrl });

  async function svgToPng(selector, width, height, background, outputPath) {
    const dataUrl = await page.evaluate(async ({ selector, width, height, background }) => {
      const svg = document.querySelector(selector);
      const serializer = new XMLSerializer();
      const source = serializer.serializeToString(svg);
      const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const image = new Image();
      await new Promise((resolve, reject) => {
        image.onload = resolve;
        image.onerror = reject;
        image.src = url;
      });
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      context.fillStyle = background;
      context.fillRect(0, 0, width, height);
      context.drawImage(image, 0, 0, width, height);
      URL.revokeObjectURL(url);
      return canvas.toDataURL("image/png");
    }, { selector, width, height, background });
    fs.writeFileSync(outputPath, Buffer.from(dataUrl.split(",")[1], "base64"));
  }

  const mainPath = path.join(outDir, "SJ0506-bag-main.png");
  const detailPath = path.join(outDir, "SJ0506-bag-detail.png");
  await svgToPng("#poster", 1600, 1600, "#f5f5f7", mainPath);
  await svgToPng("#detailPoster", 1000, 3591, "#ffffff", detailPath);
  await browser.close();

  console.log(JSON.stringify({ mainPath, detailPath }, null, 2));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
