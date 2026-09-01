/* v3.2 增量验证：变体分组 / 同学基线填写位 / 面板展开 */
const pw = require('E:/EDR/frontend/_uitest/node_modules/playwright-core');

(async () => {
  const browser = await pw.chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  const jsErrors = [];
  page.on('pageerror', (e) => jsErrors.push('pageerror: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') jsErrors.push('console: ' + m.text()); });

  await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(1500);

  /* 1) 能力行（变体组） */
  const capRows = await page.$$eval('#modules tr[data-cap]', (els) => els.map((e) => e.dataset.cap));
  console.log('能力行(' + capRows.length + '):', capRows.join(', '));
  const capBadge = await page.$eval('#modules tr[data-cap] .badge', (e) => e.textContent.trim()).catch(() => 'N/A');
  console.log('首个能力行并集徽章:', capBadge);
  await page.screenshot({ path: 'v32_1_matrix_collapsed.png' });

  /* 2) 点击能力行展开变体子行 */
  await page.click('#modules tr[data-cap]');
  await page.waitForTimeout(400);
  const capKey = capRows[0];
  const subs = await page.$$eval(`#modules tr[data-parent="${capKey}"]`, (els) =>
    els.map((e) => ({ id: e.dataset.case, badge: e.querySelector('.badge').textContent.trim(), shown: e.style.display !== 'none' })));
  console.log('展开后变体子行:', JSON.stringify(subs));
  await page.screenshot({ path: 'v32_2_matrix_expanded.png' });

  /* 3) 点变体子行 → 抽屉「变体」tab */
  await page.click(`#modules tr[data-parent="${capKey}"]`);
  await page.waitForTimeout(800);
  await page.click('#d-tabs .tab[data-tab="variants"]');
  await page.waitForTimeout(500);
  const varItems = await page.$$eval('#d-body .var-item', (els) => els.length);
  const varHead = await page.$eval('#d-body .note-box', (e) => e.textContent.replace(/\s+/g, ' ').slice(0, 120)).catch(() => 'N/A');
  console.log('抽屉变体列表条目:', varItems, '| 头部:', varHead);
  await page.screenshot({ path: 'v32_3_drawer_variants.png' });

  /* 4) 抽屉「分析」tab 有映射名称输入 */
  await page.click('#d-tabs .tab[data-tab="analysis"]');
  await page.waitForTimeout(500);
  const hasMapName = await page.$('#ana-mapname') !== null;
  console.log('分析 tab 映射名称输入框:', hasMapName);
  await page.screenshot({ path: 'v32_4_drawer_analysis.png' });

  /* 5) 展开按钮（抽屉） */
  const expBtn = await page.$('#drawer .slide-expand') !== null;
  await page.click('#drawer .slide-expand');
  await page.waitForTimeout(300);
  const drawerWide = await page.$eval('#drawer', (e) => e.classList.contains('wide'));
  console.log('抽屉展开按钮:', expBtn, '| wide:', drawerWide);
  await page.screenshot({ path: 'v32_5_drawer_wide.png' });
  await page.click('#drawer .slide-expand'); // 还原
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);

  /* 6) Baseline 同学基线 tab：映射名称 + 采集分析列 */
  await page.click('#btn-baseline');
  await page.waitForTimeout(1000);
  await page.click('#baseline-seg button[data-seg="classmate"]');
  await page.waitForTimeout(600);
  const cmHeads = await page.$$eval('#baseline-body th', (els) => els.map((e) => e.textContent));
  const nName = await page.$$eval('#baseline-body .cm-name', (els) => els.length);
  const nAna = await page.$$eval('#baseline-body .cm-ana', (els) => els.length);
  console.log('同学基线表头:', cmHeads.join(' | '));
  console.log('行内编辑控件: 映射名称 x' + nName + ', 采集分析 x' + nAna);
  await page.screenshot({ path: 'v32_6_classmate.png' });

  /* 7) Baseline 面板展开 */
  await page.click('#panel-baseline .slide-expand');
  await page.waitForTimeout(300);
  const blWide = await page.$eval('#panel-baseline', (e) => e.classList.contains('wide'));
  const blWidth = await page.$eval('#panel-baseline', (e) => Math.round(e.getBoundingClientRect().width));
  console.log('Baseline wide:', blWide, '| 宽度:', blWidth + 'px（视口 1500）');
  await page.screenshot({ path: 'v32_7_baseline_wide.png' });

  console.log('JS 错误:', jsErrors.length ? jsErrors.join(' ; ') : '无');
  await browser.close();
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1); });
