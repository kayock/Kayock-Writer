/* CI-only visual inspection of extracted synthetic EPUB XHTML pages.
 * Chromium proves HTML and CSS render, but is not an EPUB reading app.
 * No external URLs, real manuscripts, AI calls, or production services.
 */
'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');

const directory = path.resolve('test-results/release-proofs/epub-browser-view');
async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 620, height: 850 } });
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));

    for (const item of [
      {file: 'title.xhtml', heading: 'Fixture Manuscript Ω', screenshot: 'epub-cover-page.png'},
      {file: 'chapter_001.xhtml', heading: 'Chapter One', screenshot: 'epub-chapter-01.png'},
      {file: 'chapter_002.xhtml', heading: 'Chapter Two', screenshot: 'epub-chapter-02.png'},
    ]) {
      await page.goto(pathToFileURL(path.join(directory, item.file)).href, {
        waitUntil: 'load', timeout: 15000
      });
      assert.equal(await page.locator('h1').first().textContent(), item.heading);
      if (item.file === 'title.xhtml') {
        const image = await page.locator('img').evaluate(element => ({
          complete: element.complete, width: element.naturalWidth, height: element.naturalHeight
        }));
        assert.ok(image.complete && image.width > 0 && image.height > 0,
          'EPUB cover JPEG not rendered in Chromium: ' + JSON.stringify(image));
      }
      if (item.file === 'chapter_001.xhtml') {
        assert.match(await page.locator('body').textContent(),
          /The lantern glowed above the empty shore/);
      }
      await page.screenshot({
        path: path.resolve('test-results/release-proofs', item.screenshot),
        fullPage: true
      });
    }
    await page.goto(pathToFileURL(path.join(directory, 'nav.xhtml')).href, {
      waitUntil: 'load', timeout: 15000
    });
    assert.deepEqual(await page.locator('nav a').allTextContents(),
                     ['Chapter One', 'Chapter Two']);
    await page.locator('nav a').first().click();
    await page.waitForURL(/chapter_001\.xhtml/);
    assert.equal(await page.locator('h1').textContent(), 'Chapter One');
    assert.deepEqual(errors, []);
    process.stdout.write('PASS: synthetic EPUB cover + two chapters rendered, TOC link works in Chromium (not an e-reader acceptance).\n');
  } finally {
    await browser.close();
  }
}
main().catch(error => {
  process.stderr.write('EPUB BROWSER PROOF FAILED: ' + (error.stack || error) + '\n');
  process.exitCode = 1;
});
