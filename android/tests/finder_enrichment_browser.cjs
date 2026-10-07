// Test language switcher and Finder enrichment (cities, callsign, swap, hubs, return/next leg)
const {chromium} = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const port = Number(process.argv[2]), base = `http://127.0.0.1:${port}`;
  const request = async (method, args = {}) => (await (await fetch(base + '/rpc', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({method, args})
  })).json());

  const boot = await request('bootstrap');
  assert(boot.ok);
  // Test fresh state with intro_seen false to check welcome page language chips
  const state = boot.result.value.state;
  Object.assign(state, {intro_seen: false, joke_seen: true, tutorial_seen: true, language: 'en'});
  assert((await request('save', {state})).ok);

  const browser = await chromium.launch({headless: true,...(process.env.RFS_TEST_BROWSER?{channel:process.env.RFS_TEST_BROWSER}:{})});
  try {
    const page = await browser.newPage({viewport: {width: 390, height: 844}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));

    await page.exposeFunction('testRequest', async (id, method, payload) => {
      const envelope = await request(method, JSON.parse(payload));
      await page.evaluate(({id, envelope}) => window.androidReply(id, envelope), {id, envelope});
    });
    await page.addInitScript(() => window.Android = {request: (id, method, payload) => window.testRequest(id, method, payload)});

    await page.goto(base + '/index.html');
    await page.locator('.welcome').waitFor();

    // 1. Language switcher on Welcome Page
    const langRow = page.locator('.welcome-lang-row');
    assert(await langRow.isVisible(), 'Welcome language row should be visible');
    const frChip = page.locator('[data-action="set-welcome-lang"][data-lang="fr"]');
    const enChip = page.locator('[data-action="set-welcome-lang"][data-lang="en"]');
    assert(await frChip.isVisible() && await enChip.isVisible());
    assert(await enChip.evaluate(el => el.classList.contains('primary')));

    // Switch to French on Welcome Page
    await frChip.click();
    await page.waitForFunction(() => document.querySelector('#lang-btn').textContent === 'EN');
    assert.equal(await page.locator('#lang-btn').textContent(), 'EN');

    // 2. Language button toggle in header
    await page.locator('#lang-btn').click();
    await page.waitForFunction(() => document.querySelector('#lang-btn').textContent === 'FR');
    assert.equal(await page.locator('#lang-btn').textContent(), 'FR');

    // Proceed past welcome screen
    await page.locator('[data-action="welcome-done"]').click();
    await page.locator('#flight-callsign').waitFor();

    // 3. Navigate to Finder
    await page.locator('[data-screen="finder"]').click();
    await page.locator('#finder-origin').waitFor();

    // 4. Callsign filter field exists
    assert(await page.locator('#finder-callsign').isVisible(), 'Callsign filter should be visible in basic filters');

    // 5. Swap endpoints button
    await page.locator('#finder-origin').fill('LFPG');
    await page.locator('#finder-destination').fill('EGLL');
    const swapBtn = page.locator('[data-action="finder-swap"]');
    assert(await swapBtn.isVisible(), 'Swap endpoints button should be visible');
    await swapBtn.click();
    assert.equal(await page.locator('#finder-origin').inputValue(), 'EGLL');
    assert.equal(await page.locator('#finder-destination').inputValue(), 'LFPG');

    // 6. Hub chips
    const hubCdg = page.locator('[data-action="finder-hub"][data-hub="CDG"]');
    assert(await hubCdg.isVisible(), 'Hub chip CDG should be visible');
    await hubCdg.click();
    assert.equal(await page.locator('#finder-origin').inputValue(), 'CDG');

    // 7. Search and result action buttons (Return and Next leg)
    await page.locator('#finder-origin').fill('VIDP');
    await page.locator('#finder-destination').fill('');
    await page.locator('#search').click();
    await page.waitForFunction(() => finderResponse && !finderBusy);

    const firstCard = page.locator('#result-0');
    assert(await firstCard.isVisible(), 'Search results should appear');
    const returnBtn = firstCard.locator('[data-action="finder-return"]');
    const nextLegBtn = firstCard.locator('[data-action="finder-next-leg"]');
    assert(await returnBtn.isVisible(), 'Return flight button should be visible on result');
    assert(await nextLegBtn.isVisible(), 'Next leg button should be visible on result');

    // Click Return flight
    const destCode = await page.evaluate(() => finderRows[0].destination);
    const origCode = await page.evaluate(() => finderRows[0].origin);
    await returnBtn.click();
    await page.waitForFunction(() => finderResponse && !finderBusy);
    assert.equal(await page.locator('#finder-origin').inputValue(), destCode);
    assert.equal(await page.locator('#finder-destination').inputValue(), origCode);

    assert.equal(errors.length, 0, 'No errors during test: ' + errors.join(', '));
    console.log(JSON.stringify({
      languageSwitcherWelcome: true,
      headerToggle: true,
      finderCallsign: true,
      finderSwap: true,
      finderHubs: true,
      finderReturnLeg: true,
      noErrors: true
    }));
  } finally {
    await browser.close();
  }
})().catch(e => {
  console.error(e);
  process.exit(1);
});
