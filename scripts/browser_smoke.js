// Optional local smoke test: PLAYWRIGHT_CORE_PATH=<path-to-playwright-core> node scripts/browser_smoke.js
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_CORE_PATH || 'playwright-core');

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
  });
  const baseUrl = process.env.SMOKE_BASE_URL || 'http://localhost:8000';
  const browserOptions = viewport => ({
    viewport,
    ignoreHTTPSErrors: true,
    httpCredentials: process.env.SMOKE_USER ? {
      username: process.env.SMOKE_USER,
      password: process.env.SMOKE_PASSWORD,
    } : undefined,
  });
  const errors = [];
  const page = await browser.newPage(browserOptions({ width: 1280, height: 800 }));
  page.on('pageerror', error => errors.push(error.message));
  const choose = async name => page.getByRole('button', { name, exact: true }).click();

  await page.goto(baseUrl);
  await choose('Строительство');
  await page.getByRole('button', { name: 'Строительство или модернизация', exact: true }).waitFor();
  const suggestions = await page.locator('.quick button').allTextContents();
  assert.equal(suggestions[0], 'Строительство или модернизация');
  assert(!suggestions.includes('Семена, удобрения, сезонные работы'));
  assert.equal(await page.locator('.steps').count(), 0);

  for (const answer of [
    'Не хватает до ближайшей оплаты', 'В течение недели', 'Есть отгрузка и счёт к оплате',
    'Да, вся сумма сразу', 'Около 1 млн ₽', 'Через 2–3 месяца', '1–3 года', 'ИП',
    'До 1 млн ₽', 'Меньше 100 тыс. ₽', 'Без залога', 'Нет кредитов и просрочек',
  ]) await choose(answer);

  await page.locator('#results-view').waitFor({ timeout: 30000 });
  assert(await page.getByRole('heading', { name: 'Подходящие предложения' }).isVisible());
  assert(await page.locator('.card').count() > 0);
  assert.equal(await page.locator('#intake-view').isVisible(), false);
  const applyButton = page.getByRole('button', { name: 'Подать демо-заявку' }).first();
  await applyButton.click();
  await page.getByRole('heading', { name: 'Подать демо-заявку' }).waitFor();
  await page.getByRole('button', { name: 'Отправить заявку', exact: true }).click();
  await page.locator('#application.open').waitFor({ timeout: 10000 });
  assert((await page.locator('#application-status').textContent()).includes('Отправлена'));
  await page.waitForFunction(() => /На рассмотрении|Нужны уточнения/.test(document.querySelector('#application-status')?.textContent || ''), null, { timeout: 15000 });
  assert.deepEqual(errors, []);
  console.log('BROWSER_FLOW_AND_APPLICATION_OK', await page.locator('.card').count(), 'cards');

  const mobile = await browser.newPage(browserOptions({ width: 390, height: 700 }));
  mobile.on('pageerror', error => errors.push(error.message));
  await mobile.goto(baseUrl);
  await mobile.getByRole('button', { name: 'Сельское хозяйство', exact: true }).click();
  await mobile.getByRole('button', { name: 'Семена, удобрения, сезонные работы', exact: true }).waitFor();
  assert.equal(await mobile.getByRole('button', { name: 'Закупки для маркетплейса', exact: true }).count(), 0);
  const composer = await mobile.locator('#chat-form').boundingBox();
  console.log('MOBILE_COMPOSER_BOTTOM', Math.round(composer.y + composer.height));

  const empty = await browser.newPage(browserOptions({ width: 1280, height: 800 }));
  empty.on('pageerror', error => errors.push(error.message));
  await empty.goto(baseUrl);
  for (const answer of [
    'Строительство', 'Строительство или модернизация', 'Пока ищем объект',
    'Да, вся сумма сразу', 'Около 1 млн ₽', 'Через 7–12 месяцев',
    '1–3 года', 'ИП', 'До 1 млн ₽', 'Меньше 100 тыс. ₽',
    'Без залога', 'Нет кредитов и просрочек',
  ]) await empty.getByRole('button', { name: answer, exact: true }).click();
  await empty.locator('#results-view').waitFor({ timeout: 30000 });
  assert.equal(await empty.locator('.card').count(), 0);
  assert(await empty.getByText('По введённым параметрам в текущем каталоге нет совпадений.').isVisible());
  console.log('EMPTY_FEED_OK');
  const reviewer = await browser.newPage(browserOptions({ width: 1280, height: 800 }));
  reviewer.on('pageerror', error => errors.push(error.message));
  await reviewer.goto(baseUrl);
  await reviewer.getByRole('button', { name: 'Демо-кабинет эксперта', exact: true }).click();
  await reviewer.getByRole('button', { name: 'Открыть очередь', exact: true }).click();
  await reviewer.locator('#review-list .review-card').first().waitFor({ timeout: 10000 });
  assert(await reviewer.locator('#review-list .review-card').count() >= 2);
  console.log('REVIEWER_QUEUE_OK', await reviewer.locator('#review-list .review-card').count(), 'applications');
  assert.deepEqual(errors, []);
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
