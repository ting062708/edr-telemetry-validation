/* 用 playwright-core + 系统 Edge 验证 EDR 前端渲染（不下载 Chromium）。
   重跑方法：cd frontend && npm i playwright-core --prefix _uitest
   然后 node _verify_ui.cjs（截图输出到当前目录）。 */
const path = require('path');
const pw = require('E:/EDR/frontend/_uitest/node_modules/playwright-core');

(async () => {
  const browser = await pw.chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const jsErrors = [];
  page.on('pageerror', (e) => jsErrors.push('pageerror: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') jsErrors.push('console: ' + m.text()); });

  const resp = await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle', timeout: 20000 });
  console.log('HTTP:', resp.status());
  await page.waitForTimeout(1500);

  // 1) 汇总条
  const stats = await page.$$eval('#statstrip .num', (els) => els.map((e) => e.textContent));
  console.log('汇总条数字 [采集,疑问,缺失,待测]:', stats.join(' / '));
  const pct = await page.$eval('.stat.total .pct', (e) => e.textContent).catch(() => 'N/A');
  console.log('覆盖率:', pct);

  // 2) 侧栏模块数
  const mods = await page.$$eval('#sidebar .mod .name', (els) => els.map((e) => e.textContent));
  console.log('侧栏模块 (' + mods.length + '):', mods.slice(0, 8).join(', '), '...');

  // 3) 矩阵行数与首行内容
  const rows = await page.$$('#modules tbody tr[data-case]');
  console.log('矩阵 case 行数:', rows.length);
  const firstCells = await page.$$eval('#modules tbody tr[data-case] td', (els) => els.slice(0, 6).map((e) => e.textContent.trim()));
  console.log('首行:', firstCells.join(' | '));

  await page.screenshot({ path: 'verify_1_matrix.png' });

  // 4) 点开第一个 case 的抽屉
  await rows[0].click();
  await page.waitForTimeout(1200);
  const drawerOpen = await page.$eval('#drawer', (e) => e.classList.contains('open'));
  const dTitle = await page.$eval('#d-title', (e) => e.textContent);
  console.log('抽屉打开:', drawerOpen, '| case:', dTitle);
  const tabs = await page.$$eval('#d-tabs .tab', (els) => els.map((e) => e.textContent.trim()));
  console.log('抽屉 tabs:', tabs.join(' / '));
  await page.screenshot({ path: 'verify_2_drawer.png' });

  // 5) 切到「变体」tab
  await page.click('#d-tabs .tab[data-tab="variants"]');
  await page.waitForTimeout(800);
  const variantTxt = await page.$eval('#d-body', (e) => e.textContent.slice(0, 60));
  console.log('变体 tab 内容开头:', variantTxt.trim().replace(/\s+/g, ' '));

  // 6) Sysmon tab
  await page.click('#d-tabs .tab[data-tab="sysmon"]');
  await page.waitForTimeout(800);
  await page.screenshot({ path: 'verify_3_sysmon.png' });

  // 7) 关闭抽屉，开手册
  await page.keyboard.press('Escape');
  await page.click('#btn-manual');
  await page.waitForTimeout(1000);
  const manualTxt = await page.$eval('#manual-body', (e) => e.textContent.slice(0, 50));
  console.log('手册内容开头:', manualTxt.trim().replace(/\s+/g, ' '));

  // 8) Baseline 面板
  await page.keyboard.press('Escape');
  await page.click('#btn-baseline');
  await page.waitForTimeout(1000);
  const blRows = await page.$$('#baseline-body tbody tr');
  console.log('Baseline 行业表行数:', blRows.length);
  await page.click('#baseline-seg button[data-seg="classmate"]');
  await page.waitForTimeout(800);
  const cmRows = await page.$$('#baseline-body tbody tr');
  console.log('Baseline 同学表行数:', cmRows.length);
  await page.screenshot({ path: 'verify_4_baseline.png' });

  // 9) 报告面板
  await page.keyboard.press('Escape');
  await page.click('#btn-report');
  await page.waitForTimeout(800);
  const rcards = await page.$$eval('#report-body .rcard .v', (els) => els.map((e) => e.textContent));
  console.log('报告卡片:', rcards.join(' / '));
  await page.screenshot({ path: 'verify_5_report.png' });

  // 10) 终端：展开 + 拖拽 + 最大化
  await page.keyboard.press('Escape');
  await page.click('#term-bar');
  await page.waitForTimeout(400);
  const h0 = await page.$eval('#term', (e) => e.getBoundingClientRect().height);
  await page.click('#btn-term-max');
  await page.waitForTimeout(400);
  const hMax = await page.$eval('#term', (e) => e.getBoundingClientRect().height);
  const maximized = await page.$eval('#terminal', (e) => e.classList.contains('maximized'));
  console.log('终端高度 默认→最大化:', Math.round(h0), '→', Math.round(hMax), '| maximized:', maximized);
  await page.screenshot({ path: 'verify_6_term_max.png' });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);

  console.log('JS 错误:', jsErrors.length ? jsErrors : '无');
  await browser.close();
})().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });
