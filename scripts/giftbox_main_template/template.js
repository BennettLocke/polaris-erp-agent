(function giftboxMainTemplateFactory(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.GiftboxMainTemplate = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function buildGiftboxMainTemplate() {
  const VIEWBOX = {
    width: 1196.61,
    height: 1196.61,
  };

  const DEFAULT_SWATCHES = [
    "#c1272d",
    "#f7931e",
    "#f15a24",
    "#42210b",
    "#c1272d",
  ];
  const TEMPLATE_FONT_FAMILY =
    '"Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", Arial, sans-serif';

  const DEFAULT_OPTIONS = {
    imageHref: "",
    headline: "礼盒包装订制",
    series: "茶派",
    seriesSuffix: "系列",
    topNote: "免费设计/整件包邮/来图订制",
    englishNote: "Custom Gift Box Packaging",
    specText: "30套/件",
    background: "#f8f8f8",
    swatches: DEFAULT_SWATCHES,
    swatchConfig: {
      x: 282,
      y: 1081,
      size: 29.24,
      gap: 7.2,
      radius: 5.44,
    },
    specBadgeConfig: {
      x: 918,
      y: 1068,
      width: 220,
      height: 52,
      radius: 9,
      textX: 930,
      textY: 1105,
    },
    productFrameConfig: {
      x: 42,
      safeTopY: 365,
      width: 1112,
      bottomY: 1147,
    },
  };

  function productFrame(config) {
    return {
      x: config.x,
      y: config.safeTopY,
      width: config.width,
      height: config.bottomY - config.safeTopY,
    };
  }

  const IMAGE_FRAME = productFrame(DEFAULT_OPTIONS.productFrameConfig);

  const PLACEHOLDER_IMAGE = [
    "data:image/svg+xml;utf8,",
    encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 820">
        <defs>
          <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#f6e7d6"/>
            <stop offset="0.5" stop-color="#d64b2d"/>
            <stop offset="1" stop-color="#281711"/>
          </linearGradient>
          <linearGradient id="box" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#ff7a35"/>
            <stop offset="1" stop-color="#b8201a"/>
          </linearGradient>
        </defs>
        <rect width="1200" height="820" fill="url(#bg)"/>
        <g transform="translate(205 170)">
          <path d="M90 170 540 80 820 205 355 330Z" fill="#6c241d" opacity=".55"/>
          <path d="M120 180 515 92 790 212 375 312Z" fill="url(#box)"/>
          <path d="M375 312 790 212 790 485 375 610Z" fill="#d94a22"/>
          <path d="M120 180 375 312 375 610 120 462Z" fill="#f36f2c"/>
          <path d="M218 292 350 335 350 440 218 390Z" fill="#f7d8b3" opacity=".85"/>
          <path d="M400 326 682 262 680 380 400 450Z" fill="#f7d8b3" opacity=".9"/>
        </g>
      </svg>`
    ),
  ].join("");

  function escapeXml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function normalizeSwatches(swatches) {
    const source = Array.isArray(swatches) && swatches.length ? swatches : DEFAULT_SWATCHES;
    return source
      .map((value) => String(value || "").trim())
      .filter(Boolean)
      .map((value) => (value.startsWith("#") ? value : `#${value}`));
  }

  function mergeOptions(options) {
    const merged = {
      ...DEFAULT_OPTIONS,
      ...(options || {}),
      swatchConfig: {
        ...DEFAULT_OPTIONS.swatchConfig,
        ...((options || {}).swatchConfig || {}),
      },
      specBadgeConfig: {
        ...DEFAULT_OPTIONS.specBadgeConfig,
        ...((options || {}).specBadgeConfig || {}),
      },
      productFrameConfig: {
        ...DEFAULT_OPTIONS.productFrameConfig,
        ...((options || {}).productFrameConfig || {}),
      },
    };
    merged.swatches = normalizeSwatches(merged.swatches);
    return merged;
  }

  function swatchRects(swatches, config) {
    return swatches
      .map((color, index) => {
        const x = config.x + index * (config.size + config.gap);
        return `<rect class="swatch" x="${x.toFixed(2)}" y="${config.y}" width="${config.size}" height="${config.size}" rx="${config.radius}" ry="${config.radius}" fill="${escapeXml(color)}"/>`;
      })
      .join("\n  ");
  }

  function createGiftboxMainSvg(options) {
    const config = mergeOptions(options);
    const imageHref = config.imageHref || PLACEHOLDER_IMAGE;
    const imageFrame = productFrame(config.productFrameConfig);
    const seriesLine = `*${config.series}/${config.seriesSuffix}`;
    const specLine = `规格：${config.specText}`;

    return `<?xml version="1.0" encoding="UTF-8"?>
<svg id="giftbox-main-template" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" viewBox="0 0 ${VIEWBOX.width} ${VIEWBOX.height}" role="img" aria-label="礼盒主图模板">
  <defs>
    <filter id="productShadow" x="-12%" y="-12%" width="124%" height="130%">
      <feDropShadow dx="12" dy="22" stdDeviation="14" flood-color="#000000" flood-opacity=".18"/>
    </filter>
    <style>
      .template-bg { fill: ${escapeXml(config.background)}; }
      .headline { font-family: ${TEMPLATE_FONT_FAMILY}; font-size: 132px; font-weight: 800; font-style: normal; letter-spacing: .045em; fill: #050505; }
      .english { font-family: ${TEMPLATE_FONT_FAMILY}; font-size: 23.52px; font-weight: 400; font-style: normal; letter-spacing: .02em; fill: #050505; }
      .note { font-family: ${TEMPLATE_FONT_FAMILY}; font-size: 37.88px; font-weight: 500; font-style: normal; letter-spacing: .02em; fill: #4d4d4d; }
      .series { font-family: ${TEMPLATE_FONT_FAMILY}; font-size: 36.26px; font-weight: 500; font-style: normal; letter-spacing: 0; fill: #050505; }
      .spec { font-family: ${TEMPLATE_FONT_FAMILY}; font-size: 28.02px; font-weight: 500; font-style: normal; letter-spacing: 0; fill: #050505; }
      .spec-badge { fill: none; stroke: #050505; stroke-width: 2; }
    </style>
  </defs>
  <rect class="template-bg" width="${VIEWBOX.width}" height="${VIEWBOX.height}"/>
  <image x="${imageFrame.x}" y="${imageFrame.y}" width="${imageFrame.width.toFixed(2)}" height="${imageFrame.height.toFixed(2)}" href="${escapeXml(imageHref)}" xlink:href="${escapeXml(imageHref)}" preserveAspectRatio="xMidYMax meet" filter="url(#productShadow)"/>
  <text class="headline" text-anchor="middle" transform="translate(598.3 244)"><tspan x="0" y="0">${escapeXml(config.headline)}</tspan></text>
  <text class="series" transform="translate(74 1108.4725)"><tspan x="0" y="0">${escapeXml(seriesLine)}</tspan></text>
  <text class="note" text-anchor="middle" transform="translate(598.3 326)"><tspan x="0" y="0">${escapeXml(config.topNote)}</tspan></text>
  <text class="english" text-anchor="middle" transform="translate(598.3 113)"><tspan x="0" y="0">${escapeXml(config.englishNote)}</tspan></text>
  <rect class="spec-badge" x="${config.specBadgeConfig.x}" y="${config.specBadgeConfig.y}" width="${config.specBadgeConfig.width}" height="${config.specBadgeConfig.height}" rx="${config.specBadgeConfig.radius}" ry="${config.specBadgeConfig.radius}"/>
  <text class="spec" transform="translate(${config.specBadgeConfig.textX} ${config.specBadgeConfig.textY})"><tspan x="0" y="0">${escapeXml(specLine)}</tspan></text>
  ${swatchRects(config.swatches, config.swatchConfig)}
</svg>`;
  }

  return {
    DEFAULT_OPTIONS,
    DEFAULT_SWATCHES,
    PLACEHOLDER_IMAGE,
    TEMPLATE_FONT_FAMILY,
    VIEWBOX,
    createGiftboxMainSvg,
    normalizeSwatches,
  };
});
