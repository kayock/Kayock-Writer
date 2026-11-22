/* Browser-level release smoke test. Runs ONLY on a temporary fixture server.
 * No real model, internet endpoint, private manuscripts, tokens or saved config.
 * Playwright is installed only in the GitHub Actions browser job.
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const readline = require('node:readline');

const ORIGINAL = 'The lantern glowed above the quiet shore.\n\nA bell rang at dusk.';
const REVISION = 'The lantern glowed above the empty shore.\n\nA bell rang twice at dusk.';
const resultFolder = path.resolve('test-results');
fs.mkdirSync(resultFolder, { recursive: true });

function fixtureReady(child) {
  return new Promise((resolve, reject) => {
    let finished = false;
    const timeout = setTimeout(() => stop(new Error('Fixture server did not become ready')), 30000);
    const rl = readline.createInterface({ input: child.stdout });
    function stop(err, url) {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      rl.off('line', onLine);
      child.off('error', onError);
      child.off('exit', onExit);
      if (err) reject(err); else resolve(url);
    }
    const onError = (err) => stop(err);
    const onExit = (code) => stop(new Error('Fixture server exited before ready: ' + code));
    function onLine(line) {
      if (line.startsWith('READY ')) stop(null, line.slice(6).trim());
      else process.stdout.write('[fixture] ' + line + '\n');
    }
    rl.on('line', onLine);
    child.on('error', onError);
    child.on('exit', onExit);
  });
}

function requireText(value, part, context) {
  assert.ok(value.includes(part), context + ': expected ' + JSON.stringify(part) +
    ' in ' + JSON.stringify(value.slice(0, 400)));
}

async function waitStatus(page, id, text) {
  await page.waitForFunction(
    ({ id, text }) => document.getElementById(id)?.textContent.includes(text),
    { id, text }, { timeout: 18000 }
  );
}

async function downloadAndInspect(page, button, format, prefix) {
  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 18000 }),
    page.locator(button).click()
  ]);
  assert.ok(download.suggestedFilename().endsWith('.' + format),
            'Unexpected ' + format + ' filename: ' + download.suggestedFilename());
  const failure = await download.failure();
  assert.equal(failure, null, format + ' download failed');
  const file = fs.readFileSync(await download.path());
  assert.ok(file.length > 400, format + ' output is unexpectedly small');
  assert.ok(file.subarray(0, prefix.length).equals(prefix),
            format + ' does not have the expected file signature');
  process.stdout.write('OK browser download: ' + download.suggestedFilename() +
                       ' (' + file.length + ' bytes)\n');
}

async function exercise(page, url) {
  const errors = [];
  page.on('pageerror', error => errors.push(error.stack || String(error)));
  page.on('dialog', dialog => dialog.accept());
  await page.goto(url + '/', { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.locator('nav#tree button[data-page="finishing"]').click();
  await page.waitForFunction(() => (
    document.querySelector('#revisionChapter')?.options.length >= 2 &&
    document.querySelector('#bookPublishChoices')?.children.length >= 2
  ), null, { timeout: 20000 });

  assert.equal(await page.locator('#revisionProject').inputValue(), 'ReleaseFixture');
  assert.equal(await page.locator('#bookPublishProject').inputValue(), 'ReleaseFixture');
  await page.locator('#finishTitle').fill('Lantern Manuscript');
  await page.locator('#finishText').fill(ORIGINAL);

  // Inference is an isolated mock, but the browser must parse actual streaming
  // SSE responses and render the independent reviews as live UI controls.
  await page.locator('summary').filter({ hasText: 'Editorial Council' }).click();
  assert.equal(await page.locator('#councilSynthesizeButton').isDisabled(), true);
  await page.locator('#councilRunButton').click();
  await waitStatus(page, 'councilStatus', 'Council reviews complete');
  assert.equal(await page.locator('#councilReports textarea').count(), 2);
  assert.equal(await page.locator('#councilSynthesizeButton').isEnabled(), true);
  const firstReport = await page.locator('#councilReports textarea').first().inputValue();
  requireText(firstReport, 'Preserve the lantern image', 'Story Architect report');
  assert.equal(await page.locator('#finishText').inputValue(), ORIGINAL,
               'Council silently edited the original Finishing Desk passage');
  process.stdout.write('OK browser Council: independent streamed reports are read-only\n');

  // Decision choices belong only to the author, never to a model.
  const field = page.locator('#councilReports textarea').first();
  await field.evaluate(el => { el.focus(); el.setSelectionRange(0, 70); });
  await page.locator('#councilReports button').first().click();
  await page.locator('summary').filter({ hasText: 'Author Decision Board' }).click();
  assert.equal(await page.locator('#councilDecisionBoard select').count(), 1);
  await page.locator('#councilDecisionBoard select').first().selectOption('approved');
  const [boardDownload] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download decision board JSON' }).click()
  ]);
  const board = JSON.parse(fs.readFileSync(await boardDownload.path(), 'utf8'));
  assert.equal(board.manuscript_applied, false);
  assert.equal(board.source_text_included, false);
  assert.equal(board.choices[0].status, 'approved');
  assert.equal(JSON.stringify(board).includes(ORIGINAL), false,
               'Decision board unexpectedly includes full source prose');
  process.stdout.write('OK browser Decision Board: approved-for-consideration, JSON downloaded, no write\n');

  await page.locator('#councilSynthesizeButton').click();
  await waitStatus(page, 'councilStatus', 'Synthesis complete');
  requireText(await page.locator('#councilSummary').inputValue(),
              'CONSENSUS', 'Council synthesis');
  assert.equal(await page.locator('#finishText').inputValue(), ORIGINAL);
  process.stdout.write('OK browser synthesis: requires a separate click\n');

  // Direct revision acceptance exercises the actual browser diff/approval UI
  // and the server's stale-source and append-only save safeguards.
  await page.locator('summary').filter({ hasText: 'Controlled Revision Workspace' }).click();
  await page.locator('#revisionChapter').selectOption('Chapter One');
  await page.getByRole('button', { name: 'Load latest saved chapter' }).click();
  await waitStatus(page, 'revisionStatus', 'Verified Chapter One');
  assert.equal(await page.locator('#revisionOriginal').inputValue(), ORIGINAL);
  assert.equal(await page.locator('#revisionApproveButton').isDisabled(), true);
  await page.locator('#revisionCandidate').fill(REVISION);
  await page.getByRole('button', { name: 'Preview precise changes' }).click();
  await waitStatus(page, 'revisionStatus', 'Read the diff');
  requireText(await page.locator('#revisionDiff').textContent(),
              'A bell rang twice at dusk', 'Revision diff');
  assert.equal(await page.locator('#revisionApproveButton').isDisabled(), true);
  await page.locator('#revisionApproval').check();
  assert.equal(await page.locator('#revisionApproveButton').isEnabled(), true);
  await page.locator('#revisionApproveButton').click();
  await waitStatus(page, 'revisionStatus', 'Saved new canonical draft v2');
  assert.equal(await page.locator('#revisionOriginal').inputValue(), REVISION);
  assert.equal(await page.locator('#revisionApproveButton').isDisabled(), true);
  process.stdout.write('OK browser revision: explicit preview and approval append v2\n');

  // Full-book preview must find the newly approved chapter version and
  // download real binary formats, not just fake a success notification.
  await page.getByRole('button', { name: 'Refresh saved versions' }).click();
  await waitStatus(page, 'bookPublishStatus', '2 saved chapter(s) found');
  await page.getByRole('button', { name: 'Preview exact chapter selection' }).click();
  await waitStatus(page, 'bookPublishPreviewStatus', 'READ-ONLY PREVIEW');
  const preview = await page.locator('#bookPublishPreviewStatus').textContent();
  requireText(preview, 'Chapter One · v2', 'Verified book preview');
  assert.equal(await page.locator('#bookPublishDocx').isEnabled(), true);

  // Changing metadata after preview disables downloads until re-preview.
  const priorTitle = await page.locator('#bookPublishTitle').inputValue();
  await page.locator('#bookPublishTitle').fill('Changed After Preview');
  assert.equal(await page.locator('#bookPublishDocx').isDisabled(), true);
  await page.locator('#bookPublishTitle').fill(priorTitle);
  await page.getByRole('button', { name: 'Preview exact chapter selection' }).click();
  await waitStatus(page, 'bookPublishPreviewStatus', 'READ-ONLY PREVIEW');

  await downloadAndInspect(page, '#bookPublishDocx', 'docx', Buffer.from([0x50, 0x4b]));
  await downloadAndInspect(page, '#bookPublishEpub', 'epub', Buffer.from([0x50, 0x4b]));
  await downloadAndInspect(page, '#bookPublishPdf', 'pdf', Buffer.from('%PDF-'));
  requireText(await page.locator('#bookPublishDownloadStatus').textContent(),
              'No manuscripts were edited', 'Publishing status');
  process.stdout.write('OK browser book publishing: verified chapter v2, DOCX EPUB PDF\n');

  // Ensure user-entered text remains unchanged throughout review/publishing.
  assert.equal(await page.locator('#finishText').inputValue(), ORIGINAL);
  assert.deepEqual(errors, [], 'Uncaught browser errors detected');
  process.stdout.write('PASS: Kayock Writer browser integration acceptance, temporary mock only\n');
}

async function main() {
  const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const child = spawn(python, ['-u', 'tests/browser_fixture_server.py'], {
    cwd: path.resolve('.'),
    stdio: ['ignore', 'pipe', 'pipe']
  });
  child.stderr.on('data', data => process.stderr.write('[fixture] ' + data));
  let browser, page;
  try {
    const url = await fixtureReady(child);
    browser = await chromium.launch({ headless: true });
    page = await browser.newPage({
      acceptDownloads: true,
      viewport: { width: 1440, height: 1100 }
    });
    await exercise(page, url);
  } catch (error) {
    process.stderr.write('BROWSER SMOKE FAILED: ' + (error.stack || error) + '\n');
    if (page) {
      try { await page.screenshot({ path: path.join(resultFolder,'browser-failure.png'), fullPage: true }); }
      catch (error2) { process.stderr.write('Screenshot unavailable: ' + error2 + '\n'); }
    }
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    child.kill('SIGTERM');
  }
}

main().catch(error => {
  process.stderr.write(String(error.stack || error) + '\n');
  process.exitCode = 1;
});
