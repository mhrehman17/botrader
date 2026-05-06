// Screenshot each tab of the mobile UI at iPhone-14-Pro size.
const { chromium } = require('/home/user/botrader/mobile/node_modules/playwright');
const path = require('path');

const APP = 'http://127.0.0.1:8082/index.html';
const OUT = path.resolve(__dirname, '..', 'screenshots');

const tabs = ['Dashboard', 'Positions', 'Scanner', 'Chart', 'History', 'Settings'];

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--no-sandbox'],
  });
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 ' +
      '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  });
  const page = await ctx.newPage();
  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log('console.error:', msg.text());
  });
  page.on('pageerror', (e) => console.log('pageerror:', e.message));

  await page.goto(APP, { waitUntil: 'networkidle' });
  // Wait for the first tab content to render
  await page.waitForTimeout(2500);

  for (const tab of tabs) {
    // Tab labels in our nav use a 4-character uppercase ID; the visible label is "Dashboard"/"Positions"/...
    // Click by text — RN-Web renders these as a <div> with role="button"
    const found = await page.getByText(tab, { exact: true }).first();
    try {
      await found.click({ timeout: 4000 });
    } catch (e) {
      console.log(`Could not click ${tab}: ${e.message}`);
    }
    await page.waitForTimeout(2000);
    const file = path.join(OUT, `${tab.toLowerCase()}.png`);
    await page.screenshot({ path: file, fullPage: false });
    console.log('saved', file);
  }

  // Bonus: open the mode-switcher sheet on the Dashboard
  await page.getByText('Dashboard', { exact: true }).first().click();
  await page.waitForTimeout(1000);
  // The mode pill text is "PAPER" / "TESTNET" / "MAINNET"
  for (const label of ['PAPER', 'TESTNET', 'MAINNET', 'OFFLINE']) {
    const el = page.getByText(label, { exact: true }).first();
    if (await el.count()) {
      await el.click();
      await page.waitForTimeout(800);
      await page.screenshot({ path: path.join(OUT, 'mode-switcher.png'), fullPage: false });
      console.log('saved mode-switcher.png');
      break;
    }
  }

  await browser.close();
})().catch((e) => {
  console.error('FATAL', e);
  process.exit(1);
});
