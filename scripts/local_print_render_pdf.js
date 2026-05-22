#!/usr/bin/env node
/**
 * Render a sjagent printable HTML URL to PDF.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const puppeteer = require('puppeteer');

function findEdge() {
  const candidates = [
    process.env.CHROMIUM_PATH,
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  ].filter(Boolean);
  return candidates.find((p) => fs.existsSync(p)) || undefined;
}

async function main() {
  const htmlUrl = process.argv[2];
  const outputPath = process.argv[3];
  if (!htmlUrl || !outputPath) {
    console.error('用法: node local_print_render_pdf.js <html_url> <output.pdf>');
    process.exit(1);
  }
  if (!/^https?:\/\//i.test(htmlUrl)) {
    console.error(`不是有效的打印地址: ${htmlUrl}`);
    process.exit(1);
  }

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  const userDataDir = path.join(os.tmpdir(), `sjagent_print_${Date.now()}_${Math.floor(Math.random() * 10000)}`);
  const executablePath = findEdge();
  const launchOptions = {
    headless: 'shell',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu',
      '--disable-dev-shm-usage',
      '--disable-extensions',
      '--disable-background-networking',
      `--user-data-dir=${userDataDir}`,
    ],
  };
  if (executablePath) {
    launchOptions.executablePath = executablePath;
  }

  console.log('[1/3] 打开打印页面...');
  console.log(`URL: ${htmlUrl}`);
  console.log(`浏览器: ${executablePath || 'puppeteer default'}`);

  const browser = await puppeteer.launch(launchOptions);
  try {
    const page = await browser.newPage();
    const token = (process.env.SJAGENT_PRINT_AGENT_TOKEN || '').trim();
    if (token) {
      await page.setExtraHTTPHeaders({ 'X-SJ-Print-Token': token });
    }
    const response = await page.goto(htmlUrl, { waitUntil: 'networkidle0', timeout: 45000 });
    if (!response || !response.ok()) {
      throw new Error(`打印页面打开失败: HTTP ${response ? response.status() : 'no response'}`);
    }
    await page.emulateMediaType('print');
    await page.waitForSelector('.sheet, body', { timeout: 15000 });
    await page.evaluate(async () => {
      if (document.fonts && document.fonts.ready) {
        await document.fonts.ready;
      }
    });

    console.log('[2/3] 生成 PDF...');
    await page.pdf({
      path: outputPath,
      printBackground: true,
      preferCSSPageSize: true,
      margin: { top: '0', right: '0', bottom: '0', left: '0' },
    });
  } finally {
    await browser.close();
    fs.rmSync(userDataDir, { recursive: true, force: true });
  }

  const sizeKb = (fs.statSync(outputPath).size / 1024).toFixed(1);
  console.log(`[3/3] PDF 已生成: ${outputPath} (${sizeKb} KB)`);
}

main().catch((err) => {
  console.error(`错误: ${err.message}`);
  process.exit(1);
});
