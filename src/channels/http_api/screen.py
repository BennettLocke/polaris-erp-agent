"""480x320 Orange Pi screen page."""

from __future__ import annotations

from pathlib import Path


SCREEN_ASSETS_DIR = Path(__file__).resolve().parent / "screen_assets"


def get_screen_html() -> str:
    return r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=480, height=320, initial-scale=1, maximum-scale=1, user-scalable=no">
  <title>北极星小屏</title>
  <style>
    * { box-sizing: border-box; }
    html, body { margin: 0; width: 480px; height: 320px; overflow: hidden; background: #000816; }
    body {
      color: rgba(233, 255, 255, .94);
      font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", Arial, sans-serif;
      letter-spacing: 0;
      touch-action: manipulation;
      user-select: none;
    }
    button { font: inherit; border: 0; color: inherit; background: transparent; cursor: pointer; }

    .screen {
      position: relative;
      width: 480px;
      height: 320px;
      overflow: hidden;
      contain: strict;
      background:
        radial-gradient(circle at 50% 52%, rgba(0, 109, 255, .08), transparent 42%),
        #000816;
    }

    .main-view {
      position: absolute;
      inset: 0;
      display: none;
      grid-template-rows: 40px minmax(0, 1fr) 46px;
      background:
        radial-gradient(circle at 50% 0%, rgba(125, 211, 252, .14), transparent 34%),
        #111820;
      color: #f4f7fa;
    }
    .main-view.active { display: grid; }
    .top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 7px 10px;
      background: #0b1015;
      border-bottom: 1px solid #273440;
      font-size: 12px;
      font-weight: 900;
    }
    .title { display: flex; align-items: center; gap: 7px; }
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: #39d98a;
      box-shadow: 0 0 0 5px rgba(57, 217, 138, .13);
    }
    .clock { text-align: right; font-size: 15px; line-height: 1; font-weight: 900; }
    .clock span { display: block; margin-top: 3px; color: #9aa8b5; font-size: 9px; font-weight: 700; }
    .content { min-height: 0; padding: 8px; overflow: hidden; }
    .page { display: none; min-height: 100%; gap: 8px; }
    .page.active { display: grid; }
    #overview.active, #inventory.active { grid-template-columns: 108px minmax(0, 1fr) minmax(0, 1fr); }
    #orders.active { grid-template-columns: 108px minmax(0, 1fr); }
    .metrics { display: grid; grid-template-columns: 1fr; grid-auto-rows: minmax(0, 1fr); gap: 7px; }
    .mini, .panel, .row, .order {
      min-width: 0;
      background: #18222c;
      border: 1px solid #2d3b47;
      border-radius: 6px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.03);
    }
    .mini { display: grid; place-items: center; align-content: center; gap: 4px; padding: 8px; text-align: center; }
    .mini b { color: #7dd3fc; font-size: 22px; line-height: 1; }
    .mini b.warn { color: #fbbf24; }
    .mini span { color: #9aa8b5; font-size: 10px; white-space: nowrap; }
    .panel { padding: 9px; overflow: hidden; }
    .panel-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
    .panel-head h2 { margin: 0; font-size: 12px; line-height: 1; display: flex; align-items: center; gap: 5px; }
    .panel-head svg, .nav svg { width: 14px; height: 14px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .tag {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 34px;
      height: 20px;
      padding: 0 7px;
      border-radius: 4px;
      color: #7dd3fc;
      background: #13202b;
      font-size: 9px;
      font-weight: 900;
      white-space: nowrap;
    }
    .tag.ok { color: #39d98a; }
    .tag.warn { color: #fbbf24; }
    .tag.bad { color: #fb7185; }
    .list { display: grid; gap: 7px; }
    .row, .order { min-height: 46px; padding: 8px; display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .row div, .order div { min-width: 0; display: grid; gap: 3px; }
    .row strong, .order strong { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; }
    .row span, .order span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #9aa8b5; font-size: 9px; }
    #orders > .list { grid-template-columns: repeat(2, minmax(0, 1fr)); align-content: start; }
    .nav {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 6px;
      padding: 7px 6px;
      background: #0b1015;
      border-top: 1px solid #273440;
    }
    .nav button {
      display: grid;
      grid-template-columns: auto auto;
      align-items: center;
      justify-content: center;
      gap: 5px;
      height: 32px;
      border: 1px solid #2d3b47;
      border-radius: 5px;
      color: #9aa8b5;
      font-size: 11px;
      font-weight: 850;
    }
    .nav button.active { color: #7dd3fc; border-color: #7dd3fc; background: #18222c; }

    .standby-view {
      position: absolute;
      inset: 0;
      z-index: 20;
      overflow: hidden;
      contain: strict;
      color: rgba(233, 255, 255, .94);
      background:
        radial-gradient(circle at 50% 52%, rgba(0, 109, 255, .06), transparent 42%),
        #000816;
      display: block;
    }
    .standby-view.hidden { display: none; }
    .standby-view::before {
      content: "";
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(rgba(71, 166, 255, .035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(71, 166, 255, .035) 1px, transparent 1px);
      background-size: 16px 16px;
      opacity: .32;
    }
    .standby-view::after {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(90deg, transparent 0 23px, rgba(0, 109, 255, .055) 23px 24px, transparent 24px 48px),
        linear-gradient(0deg, transparent 0 23px, rgba(0, 109, 255, .04) 23px 24px, transparent 24px 48px);
      opacity: .18;
    }
    .standby-frame { position: absolute; z-index: 2; inset: 0; width: 100%; height: 100%; pointer-events: none; }
    .standby-frame path { fill: none; vector-effect: non-scaling-stroke; stroke-linejoin: miter; }
    .standby-frame .frame-shadow { stroke: #02050c; stroke-width: 6; }
    .standby-frame .frame-line {
      stroke: rgba(14, 76, 142, .95);
      stroke-width: 2;
    }
    .standby-ghost {
      position: absolute;
      z-index: 1;
      left: 24px;
      right: 150px;
      top: 54px;
      bottom: 54px;
      overflow: hidden;
      pointer-events: none;
      mask-image:
        linear-gradient(90deg, transparent 0, black 4%, black 80%, transparent 100%),
        linear-gradient(180deg, transparent 0, black 16%, black 84%, transparent 100%);
      mask-composite: intersect;
    }
    .standby-ghost span {
      position: absolute;
      color: rgba(0, 109, 255, .1);
      font-weight: 950;
      line-height: 1;
      white-space: nowrap;
    }
    .standby-ghost .g1 { left: 4%; top: 6%; font-size: 27px; opacity: .34; }
    .standby-ghost .g2 { left: 10%; top: 25%; font-size: 38px; opacity: .38; }
    .standby-ghost .g3 { left: 0; top: 47%; font-size: 24px; opacity: .34; }
    .standby-ghost .g4 { left: 44%; top: 39%; font-size: 20px; opacity: .28; }
    .standby-ghost .g5 { left: 5%; top: 76%; font-size: 30px; opacity: .34; }
    .standby-ghost .g6 { left: 37%; top: 90%; font-size: 18px; opacity: .26; }
    .standby-ghost .g7 { left: 52%; top: 4%; font-size: 17px; opacity: .2; }
    .standby-ghost .g8 { left: 48%; top: 58%; font-size: 19px; opacity: .22; }
    .standby-ghost .g9 { left: 44%; top: 72%; font-size: 18px; opacity: .24; }
    .standby-ghost .g10 { left: 0; top: 96%; font-size: 17px; opacity: .2; }
    .standby-ghost .g11 { left: 4%; top: 58%; font-size: 36px; opacity: .38; }
    .standby-ghost .g12 { left: 38%; top: 16%; color: rgba(0, 216, 255, .12); font-size: 22px; opacity: .28; }

    .standby-time {
      position: absolute;
      z-index: 5;
      top: 28px;
      left: 30px;
      width: 216px;
      text-shadow: 0 0 6px rgba(0, 216, 255, .26), 0 0 14px rgba(0, 109, 255, .22);
    }
    .standby-time-head { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 8px; margin-bottom: 2px; }
    .standby-time-head span { font-size: 10px; font-weight: 900; line-height: 1; }
    .standby-time-head i { height: 2px; background: rgba(233, 255, 255, .34); }
    .standby-date-row { display: flex; align-items: center; gap: 8px; }
    .standby-date-row strong { font-size: 46px; font-weight: 950; line-height: .92; }
    .standby-time-stack { display: grid; gap: 1px; padding-top: 4px; font-weight: 850; }
    .standby-time-stack span { font-size: 11px; line-height: 1.05; }
    .standby-time-stack b { font-size: 17px; }
    .standby-date-meta { display: flex; justify-content: space-between; margin-top: 6px; color: rgba(233, 255, 255, .68); font-size: 11px; font-weight: 750; }

    .screen-log {
      position: absolute;
      z-index: 6;
      left: 22px;
      top: 92px;
      bottom: 86px;
      width: 292px;
      height: auto;
      display: grid;
      align-content: end;
      gap: 5px;
      pointer-events: none;
    }
    .log-item {
      max-height: none;
      overflow: visible;
      padding: 6px 8px;
      border: 1px solid rgba(0, 109, 255, .32);
      border-radius: 7px;
      background: rgba(0, 13, 32, .72);
    }
    .log-item.user { border-color: rgba(0,216,255,.44); background: rgba(0, 35, 70, .72); }
    .log-item strong { display: block; margin-bottom: 2px; color: rgba(0,216,255,.9); font-size: 9px; line-height: 1; }
    .log-item.user strong { color: rgba(251,191,36,.92); }
    .log-item span {
      display: block;
      overflow: visible;
      color: rgba(233,255,255,.92);
      font-size: 10px;
      line-height: 1.28;
      font-weight: 760;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .log-item.latest span { font-size: 10px; line-height: 1.28; }

    .standby-scene { position: absolute; inset: 0; transform: none; transform-origin: 50% 50%; }
    .standby-star {
      position: absolute;
      z-index: 1;
      width: var(--size);
      height: var(--size);
      left: var(--x);
      top: var(--y);
      object-fit: contain;
      opacity: .58;
      transform: translate(-50%, -50%) scale(.86);
      animation: standbyTwinkle var(--dur) steps(3) infinite;
      animation-delay: var(--delay);
    }
    .standby-star.tall { height: calc(var(--size) * 1.16); }
    .standby-star.s1 { --x: 58%; --y: 20%; --size: 20px; --dur: 2800ms; --delay: -200ms; }
    .standby-star.s2 { --x: 86%; --y: 18%; --size: 11px; --dur: 3400ms; --delay: -900ms; }
    .standby-star.s3 { --x: 92%; --y: 35%; --size: 18px; --dur: 3100ms; --delay: -600ms; }
    .standby-star.s4 { --x: 49%; --y: 39%; --size: 13px; --dur: 3600ms; --delay: -1200ms; }
    .standby-star.s5 { --x: 83%; --y: 47%; --size: 9px; --dur: 2600ms; --delay: -500ms; }
    .standby-star.s6 { --x: 62%; --y: 54%; --size: 15px; --dur: 3300ms; --delay: -1100ms; }
    .standby-star.s7 { --x: 94%; --y: 62%; --size: 14px; --dur: 3700ms; --delay: -300ms; }
    .standby-star.s8 { --x: 52%; --y: 69%; --size: 17px; --dur: 3000ms; --delay: -800ms; }
    .standby-star.s9 { --x: 79%; --y: 72%; --size: 10px; --dur: 3900ms; --delay: -1500ms; }
    .standby-star.s10 { --x: 69%; --y: 30%; --size: 12px; --dur: 3100ms; --delay: -100ms; }
    .standby-star.s11 { --x: 73%; --y: 58%; --size: 16px; --dur: 3500ms; --delay: -1300ms; }
    .standby-star.s12 { --x: 77%; --y: 15%; --size: 8px; --dur: 4200ms; --delay: -1700ms; }
    .standby-halo {
      position: absolute;
      z-index: 2;
      left: 74%;
      top: 77%;
      width: 230px;
      height: 84px;
      transform: translate(-50%, -50%);
      pointer-events: none;
      will-change: transform;
      animation: standbyHover 3600ms steps(4) infinite;
    }
    .standby-orbit { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
    .standby-orbit ellipse { fill: none; vector-effect: non-scaling-stroke; stroke-linecap: square; }
    .standby-track {
      stroke: rgba(0, 92, 255, .34);
      stroke-width: 4;
      stroke-dasharray: 18 8 5 12;
      animation: standbyTrack 3600ms steps(8) infinite;
    }
    .standby-runner {
      stroke: #35eaff;
      stroke-width: 6;
      stroke-dasharray: 30 416;
      animation: standbyOrbit 2800ms steps(10) infinite;
    }
    .standby-runner.b {
      opacity: .72;
      stroke-width: 4;
      stroke: #0078ff;
      stroke-dasharray: 18 428;
      animation-duration: 3400ms;
      animation-delay: -500ms;
    }
    .standby-robot {
      position: absolute;
      z-index: 3;
      left: 74%;
      top: 49%;
      width: 222px;
      height: 222px;
      transform: translate(-50%, -50%);
      will-change: transform;
      animation: standbyRobot 3600ms steps(4) infinite;
    }
    .standby-robot img {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: contain;
    }
    .standby-face {
      position: absolute;
      left: 43.6%;
      top: 49%;
      width: 49px;
      height: 41px;
      transform: translate(-50%, -50%);
    }
    .standby-eye, .standby-mouth { position: absolute; background: #00d8ff; }
    .standby-eye { top: 13px; width: 6px; height: 9px; animation: standbyBlink 4200ms steps(1) infinite; }
    .standby-eye.left { left: 13px; }
    .standby-eye.right { right: 13px; }
    .standby-mouth {
      left: 50%;
      bottom: 2px;
      width: 19px;
      height: 7px;
      transform: translateX(-50%);
      background:
        linear-gradient(90deg, transparent 0 5px, #00d8ff 5px 21px, transparent 21px),
        linear-gradient(90deg, transparent 0 9px, #00d8ff 9px 17px, transparent 17px);
      background-size: 100% 4px, 100% 4px;
      background-position: 0 0, 0 4px;
      background-repeat: no-repeat;
    }
    .standby-view[data-expression="talk"] .standby-mouth,
    .standby-view[data-expression="processing"] .standby-mouth {
      height: 16px;
      animation: standbyTalk 620ms steps(1) infinite;
    }
    .standby-view[data-expression="listen"] .standby-eye {
      top: 14px;
      width: 10px;
      height: 15px;
      animation: standbyListen 2600ms steps(1) infinite;
    }
    .standby-view[data-expression="listen"] .standby-mouth {
      bottom: 2px;
      width: 14px;
      height: 4px;
      background: #00d8ff;
    }
    .standby-bubble {
      display: none !important;
      position: absolute;
      z-index: 4;
      left: 58%;
      top: 30%;
      min-width: 124px;
      max-width: 146px;
      padding: 9px 11px;
      border: 1px solid rgba(0, 216, 255, .68);
      border-radius: 7px;
      color: rgba(233, 255, 255, .94);
      background: rgba(0, 13, 32, .86);
      font-size: 12px;
      font-weight: 850;
      line-height: 1.25;
      opacity: 0;
      transform: translateY(4px) scale(.96);
    }
    .standby-bubble::after {
      content: "";
      position: absolute;
      left: 16px;
      bottom: -6px;
      width: 9px;
      height: 9px;
      border-right: 1px solid rgba(0, 216, 255, .68);
      border-bottom: 1px solid rgba(0, 216, 255, .68);
      background: rgba(0, 13, 32, .86);
      transform: rotate(45deg);
    }
    .standby-view[data-expression="talk"] .standby-bubble,
    .standby-view[data-expression="processing"] .standby-bubble,
    .standby-view[data-expression="listen"] .standby-bubble {
      opacity: 1;
      transform: translateY(0) scale(1);
      animation: standbyBubble 1300ms steps(2) infinite;
    }
    .standby-view[data-expression="error"] .standby-bubble {
      opacity: 1;
      border-color: rgba(251, 113, 133, .7);
    }
    .standby-stats {
      position: absolute;
      z-index: 5;
      left: 30px;
      bottom: 30px;
      width: 222px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 7px;
    }
    .standby-card {
      height: 44px;
      display: grid;
      align-content: center;
      justify-items: center;
      gap: 3px;
      padding: 6px;
      border: 1px solid rgba(0, 109, 255, .44);
      border-radius: 7px;
      background: linear-gradient(180deg, rgba(0, 39, 92, .62), rgba(0, 10, 28, .72));
      box-shadow: inset 0 0 0 1px rgba(2, 5, 12, .72);
    }
    .standby-card strong { color: rgba(233, 255, 255, .96); font-size: 16px; font-weight: 950; line-height: 1; }
    .standby-card span { color: rgba(233, 255, 255, .68); font-size: 10px; font-weight: 750; line-height: 1; white-space: nowrap; }

    @keyframes standbyTrack { to { stroke-dashoffset: -86; } }
    @keyframes standbyOrbit { to { stroke-dashoffset: -446; } }
    @keyframes standbyHover { 0%, 100% { transform: translate(-50%, -50%) translateY(0); } 50% { transform: translate(-50%, -50%) translateY(-2px); } }
    @keyframes standbyRobot { 0%, 100% { transform: translate(-50%, -50%) translateY(0); } 50% { transform: translate(-50%, -50%) translateY(-5px); } }
    @keyframes standbyBlink { 0%, 88%, 100% { height: 14px; transform: translateY(0); } 90%, 94% { height: 4px; transform: translateY(5px); } }
    @keyframes standbyTalk {
      0%, 100% {
        height: 8px;
        background:
          linear-gradient(90deg, transparent 0 6px, #00d8ff 6px 16px, transparent 16px),
          linear-gradient(90deg, transparent 0 9px, #00d8ff 9px 13px, transparent 13px);
        background-size: 100% 4px, 100% 4px;
        background-position: 0 0, 0 4px;
        background-repeat: no-repeat;
      }
      50% {
        height: 16px;
        background:
          linear-gradient(90deg, transparent 0 7px, #00d8ff 7px 15px, transparent 15px),
          linear-gradient(90deg, transparent 0 5px, #00d8ff 5px 17px, transparent 17px),
          linear-gradient(90deg, transparent 0 8px, #00d8ff 8px 14px, transparent 14px);
        background-size: 100% 4px, 100% 4px, 100% 4px;
        background-position: 0 0, 0 6px, 0 12px;
        background-repeat: no-repeat;
      }
    }
    @keyframes standbyListen { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(1px); } }
    @keyframes standbyBubble { 0%, 100% { opacity: .9; } 50% { opacity: 1; } }
    @keyframes standbyTwinkle {
      0% { opacity: .28; transform: translate(-50%, -50%) scale(.72); }
      33% { opacity: .72; transform: translate(-50%, -50%) scale(.95); }
      50% { opacity: 1; transform: translate(-50%, -50%) scale(1.08); }
      100% { opacity: .35; transform: translate(-50%, -50%) scale(.78); }
    }
  </style>
</head>
<body>
  <section class="screen">
    <section class="main-view" id="mainView">
      <header class="top">
        <div class="title"><span class="status-dot"></span><span id="pageTitle">总览</span></div>
        <div class="clock"><span id="topClock">--:--</span><span>ONLINE</span></div>
      </header>
      <section class="content">
        <div class="page active" id="overview">
          <div class="metrics">
            <div class="mini"><b id="metricOrders">--</b><span>今日订单</span></div>
            <div class="mini"><b id="metricSales">--</b><span>今日销售额</span></div>
            <div class="mini"><b class="warn" id="metricPending">--</b><span>待完成</span></div>
          </div>
          <article class="panel">
            <div class="panel-head"><h2><svg viewBox="0 0 24 24"><path d="M4 12h4l2-7 4 14 2-7h4"/></svg>最近业务</h2><span class="tag">LIVE</span></div>
            <div class="list" id="recentList"></div>
          </article>
          <article class="panel">
            <div class="panel-head"><h2><svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>系统状态</h2><span class="tag ok">OK</span></div>
            <div class="list">
              <div class="row"><div><strong>本机服务</strong><span>WebUI / 小屏页面</span></div><span class="tag ok">OK</span></div>
              <div class="row"><div><strong>语音助手</strong><span>唤醒 / 播报 / Agent</span></div><span class="tag ok">OK</span></div>
              <div class="row"><div><strong>刷新</strong><span>状态 0.5s / 业务 2s</span></div><span class="tag">LIVE</span></div>
            </div>
          </article>
        </div>
        <div class="page" id="inventory">
          <div class="metrics">
            <div class="mini"><b id="inventoryTotal">--</b><span>库存项</span></div>
            <div class="mini"><b class="warn" id="inventoryLow">--</b><span>预警</span></div>
            <div class="mini"><b>实时</b><span>库存</span></div>
          </div>
          <article class="panel">
            <div class="panel-head"><h2><svg viewBox="0 0 24 24"><path d="M4 19V5"/><path d="M8 17V9"/><path d="M12 15V7"/><path d="M16 13V4"/></svg>卖得最多</h2><span class="tag">本周</span></div>
            <div class="list" id="salesList"></div>
          </article>
          <article class="panel">
            <div class="panel-head"><h2><svg viewBox="0 0 24 24"><path d="M4 8.5 12 4l8 4.5-8 4.5z"/><path d="M4 8.5V16l8 4 8-4V8.5"/></svg>库存预警</h2><span class="tag bad">ALARM</span></div>
            <div class="list" id="inventoryList"></div>
          </article>
        </div>
        <div class="page" id="orders">
          <div class="metrics">
            <div class="mini"><b id="orderMetricToday">--</b><span>今日订单</span></div>
            <div class="mini"><b class="warn" id="orderMetricPending">--</b><span>待制作</span></div>
            <div class="mini"><b id="orderMetricShip">--</b><span>待配送</span></div>
          </div>
          <div class="list" id="ordersList"></div>
        </div>
      </section>
      <nav class="nav">
        <button class="active" data-page="overview" data-title="总览"><svg viewBox="0 0 24 24"><path d="M4 13.5 12 6l8 7.5"/><path d="M6.5 12.5V20h11v-7.5"/></svg>总览</button>
        <button data-page="inventory" data-title="库存"><svg viewBox="0 0 24 24"><path d="M4 8.5 12 4l8 4.5-8 4.5z"/><path d="M4 8.5V16l8 4 8-4V8.5"/></svg>库存</button>
        <button data-page="orders" data-title="订单"><svg viewBox="0 0 24 24"><path d="M7 3h8l4 4v14H7z"/><path d="M15 3v5h5"/></svg>订单</button>
        <button data-standby-enter><svg viewBox="0 0 24 24"><path d="M12 2v4"/><path d="M12 18v4"/><path d="m4.93 4.93 2.83 2.83"/><path d="m16.24 16.24 2.83 2.83"/></svg>待机</button>
        <button data-reset-state><svg viewBox="0 0 24 24"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/></svg>清屏</button>
      </nav>
    </section>

    <section class="standby-view" id="standby" data-expression="idle" aria-label="北极星待机屏">
      <svg class="standby-frame" viewBox="0 0 480 320" aria-hidden="true">
        <path class="frame-shadow" d="M30 12 H450 L468 30 V290 L450 308 H30 L12 290 V30 Z"/>
        <path class="frame-line" d="M30 12 H450 L468 30 V290 L450 308 H30 L12 290 V30 Z"/>
      </svg>
      <div class="standby-ghost" aria-hidden="true">
        <span class="g1">订单系统</span><span class="g2">肆计包装</span><span class="g3">SJBZ ORDER</span><span class="g4">PACKAGING</span>
        <span class="g5">包装订单</span><span class="g6">ORDER SYSTEM</span><span class="g7">SHOPXO ERP</span><span class="g8">AI ASSISTANT</span>
        <span class="g9">STOCK SYNC</span><span class="g10">KNOWLEDGE BASE</span><span class="g11">包装系统</span><span class="g12">业务中台</span>
      </div>
      <div class="standby-time">
        <div class="standby-time-head"><span>TIME</span><i></i></div>
        <div class="standby-date-row">
          <strong id="standbyTime">--:--</strong>
          <div class="standby-time-stack">
            <span><b id="standbyMonthDay">--月--日</b></span>
            <span><b id="standbyWeekday">星期-</b></span>
          </div>
        </div>
        <div class="standby-date-meta"><span id="standbyDateFull">----年--月--日</span><span>北极星在线中..</span></div>
      </div>
      <div class="screen-log" id="screenLog">
        <div class="log-item"><strong>小星</strong><span>等待唤醒，查询结果会显示在这里。</span></div>
      </div>
      <div class="standby-scene">
        <img class="standby-star tall s1" src="/api/screen/assets/stars/star-tall.svg" alt="">
        <img class="standby-star s2" src="/api/screen/assets/stars/star-square.svg" alt="">
        <img class="standby-star s3" src="/api/screen/assets/stars/star-square.svg" alt="">
        <img class="standby-star tall s4" src="/api/screen/assets/stars/star-tall.svg" alt="">
        <img class="standby-star s5" src="/api/screen/assets/stars/star-square.svg" alt="">
        <img class="standby-star tall s6" src="/api/screen/assets/stars/star-tall.svg" alt="">
        <img class="standby-star s7" src="/api/screen/assets/stars/star-square.svg" alt="">
        <img class="standby-star tall s8" src="/api/screen/assets/stars/star-tall.svg" alt="">
        <img class="standby-star s9" src="/api/screen/assets/stars/star-square.svg" alt="">
        <img class="standby-star tall s10" src="/api/screen/assets/stars/star-tall.svg" alt="">
        <img class="standby-star s11" src="/api/screen/assets/stars/star-square.svg" alt="">
        <img class="standby-star tall s12" src="/api/screen/assets/stars/star-tall.svg" alt="">
        <div class="standby-halo" aria-hidden="true">
          <svg class="standby-orbit" viewBox="0 0 260 92">
            <defs>
              <filter id="standbyOrbitGlow" x="-20%" y="-80%" width="140%" height="260%">
                <feGaussianBlur stdDeviation="2.4" result="blur"/>
                <feColorMatrix in="blur" type="matrix" values="0 0 0 0 0  0 0 0 0 .7  0 0 0 0 1  0 0 0 .9 0" result="glow"/>
                <feMerge><feMergeNode in="glow"/><feMergeNode in="SourceGraphic"/></feMerge>
              </filter>
            </defs>
            <ellipse class="standby-track" cx="130" cy="46" rx="104" ry="25"/>
            <ellipse class="standby-track" cx="130" cy="49" rx="82" ry="16"/>
            <ellipse class="standby-runner" cx="130" cy="46" rx="104" ry="25"/>
            <ellipse class="standby-runner b" cx="130" cy="46" rx="104" ry="25"/>
          </svg>
        </div>
        <div class="standby-robot">
          <img src="/api/screen/assets/north-star-body.png" alt="">
          <div class="standby-face" aria-hidden="true"><span class="standby-eye left"></span><span class="standby-eye right"></span><span class="standby-mouth"></span></div>
        </div>
        <div class="standby-bubble" id="standbyBubble" aria-hidden="true">我在。</div>
      </div>
      <div class="standby-stats">
        <div class="standby-card"><strong id="standbyOrders">--</strong><span>今日订单</span></div>
        <div class="standby-card"><strong id="standbySales">--</strong><span>今日销售额</span></div>
        <div class="standby-card"><strong id="standbyPending">--</strong><span>待完成</span></div>
      </div>
    </section>
  </section>

  <script>
    const $ = (id) => document.getElementById(id);
    const standby = $("standby");
    const mainView = $("mainView");
    const title = $("pageTitle");
    let latestVersion = -1;
    let mainTimer = 0;
    let expressionTimer = 0;

    function escapeHtml(text) {
      return String(text || "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
    }

    async function api(path, options = {}) {
      const init = { ...options };
      if (init.body && typeof init.body !== "string") {
        init.headers = { "Content-Type": "application/json", ...(init.headers || {}) };
        init.body = JSON.stringify(init.body);
      }
      const res = await fetch(path, init);
      const data = await res.json();
      if (!res.ok || data.code !== 0) throw new Error(data.msg || res.statusText);
      return data.data || {};
    }

    function updateTime() {
      const now = new Date();
      const pad = (value) => String(value).padStart(2, "0");
      const month = pad(now.getMonth() + 1);
      const day = pad(now.getDate());
      const weekdays = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
      const time = now.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
      $("standbyTime").textContent = time;
      $("topClock").textContent = time;
      $("standbyMonthDay").textContent = `${Number(month)}月${Number(day)}日`;
      $("standbyDateFull").textContent = `${now.getFullYear()}年${month}月${day}日`;
      $("standbyWeekday").textContent = weekdays[now.getDay()];
    }

    function showStandby() {
      mainView.classList.remove("active");
      standby.classList.remove("hidden");
    }

    function showMain() {
      standby.classList.add("hidden");
      mainView.classList.add("active");
      clearTimeout(mainTimer);
      mainTimer = setTimeout(showStandby, 15000);
    }

    function renderMessages(messages) {
      const items = (messages || []).slice(-2);
      if (!items.length) {
        $("screenLog").innerHTML = '<div class="log-item"><strong>小星</strong><span>等待唤醒，查询结果会显示在这里。</span></div>';
        return;
      }
      $("screenLog").innerHTML = items.map((item, index) => {
        const role = item.role === "user" ? "你" : "小星";
        const cls = `${item.role === "user" ? " user" : ""}${index === items.length - 1 ? " latest" : ""}`;
        return `<div class="log-item${cls}"><strong>${role}</strong><span>${escapeHtml(item.text)}</span></div>`;
      }).join("");
    }

    function renderState(state) {
      const expression = state.expression || state.status || "idle";
      standby.dataset.expression = expression;
      const latest = state.latest || {};
      renderMessages(state.messages || []);
      latestVersion = Number(state.version || 0);
      clearTimeout(expressionTimer);
      if (expression === "talk") {
        expressionTimer = setTimeout(() => {
          if (latestVersion === Number(state.version || 0)) standby.dataset.expression = "idle";
        }, 3600);
      } else if (expression === "listen") {
        expressionTimer = setTimeout(() => {
          if (latestVersion === Number(state.version || 0)) standby.dataset.expression = "idle";
        }, 8000);
      }
    }

    function moneyShort(text) {
      const raw = String(text || "--");
      return raw.replace(".00", "");
    }

    function rowHtml(title, sub, tag = "", cls = "") {
      return `<div class="row"><div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(sub)}</span></div>${tag ? `<span class="tag ${cls}">${escapeHtml(tag)}</span>` : ""}</div>`;
    }

    function orderHtml(item) {
      return `<div class="order"><div><strong>${escapeHtml(item.customer_name || "客户")}</strong><span>${escapeHtml(item.goods_name || item.product_summary || "订单")}</span><span>${escapeHtml(item.status_text || item.date_text || "")}</span></div><span class="tag warn">${escapeHtml(item.status_tag || "订单")}</span></div>`;
    }

    function renderDashboard(data) {
      const summary = data.summary || {};
      const orders = String(summary.today_sales_count ?? "--");
      const sales = moneyShort(summary.today_sales_amount_text || summary.today_sales_amount || "--");
      const pending = String(summary.pending_workflow_count ?? "--");
      $("metricOrders").textContent = orders;
      $("metricSales").textContent = sales;
      $("metricPending").textContent = pending;
      $("standbyOrders").textContent = orders;
      $("standbySales").textContent = sales;
      $("standbyPending").textContent = pending;
      $("orderMetricToday").textContent = orders;
      $("orderMetricPending").textContent = pending;
      $("orderMetricShip").textContent = data.pending_delivery_count ?? "--";
      const recent = (data.recent || []).slice(0, 3);
      $("recentList").innerHTML = recent.map((item) => rowHtml(item.title, item.sub, item.tag || "LIVE", item.class || "")).join("") || rowHtml("暂无业务", "等待数据刷新", "LIVE");
      const salesItems = (data.sales || []).slice(0, 3);
      $("salesList").innerHTML = salesItems.map((item) => rowHtml(item.title, item.sub, item.value || "", "")).join("") || rowHtml("暂无销售", "等待数据刷新", "本周");
      const inventory = (data.inventory || []).slice(0, 3);
      $("inventoryList").innerHTML = inventory.map((item) => rowHtml(item.title, item.sub, item.tag || "LOW", item.class || "warn")).join("") || rowHtml("暂无预警", "库存数据正常", "OK", "ok");
      $("inventoryTotal").textContent = data.inventory_total ?? inventory.length ?? "--";
      $("inventoryLow").textContent = inventory.length;
      const ordersList = (data.orders || []).slice(0, 4);
      $("ordersList").innerHTML = ordersList.map(orderHtml).join("") || orderHtml({ customer_name: "暂无订单", goods_name: "等待数据刷新", status_text: "" });
    }

    async function pollState() {
      try {
        const state = await api("/api/screen/state");
        if (Number(state.version || 0) !== latestVersion) renderState(state);
      } catch (err) {}
    }

    async function pollDashboard() {
      try {
        renderDashboard(await api("/api/screen/dashboard"));
      } catch (err) {}
    }

    document.querySelectorAll("[data-page]").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".page").forEach((page) => page.classList.toggle("active", page.id === button.dataset.page));
        document.querySelectorAll("[data-page]").forEach((item) => item.classList.toggle("active", item === button));
        title.textContent = button.dataset.title || "总览";
        showMain();
      });
    });
    document.querySelector("[data-standby-enter]").addEventListener("click", showStandby);
    document.querySelector("[data-reset-state]").addEventListener("click", async () => {
      await api("/api/screen/state", { method: "POST", body: { reset: true, status: "idle" } });
      showMain();
    });
    standby.addEventListener("pointerup", showMain);

    updateTime();
    setInterval(updateTime, 1000);
    pollState();
    pollDashboard();
    setInterval(pollState, 700);
    setInterval(pollDashboard, 5000);
    showStandby();
  </script>
</body>
</html>'''
