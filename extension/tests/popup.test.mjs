import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { JSDOM } from 'jsdom';
import { startPopup } from '../build/popup.js';
import { parsePage } from './helpers.mjs';

const html = await readFile(new URL('../popup.html', import.meta.url), 'utf8');
const dictionary = 'https://dictionary.cambridge.org/us/dictionary/english/hello';

async function popup(
  t,
  {
    settings = {},
    page = parsePage(),
    url = dictionary,
    readError = false,
    storageError = false,
    downloadError = false,
  } = {},
) {
  const dom = new JSDOM(html, { url: 'https://extension.test/popup.html' });
  t.after(() => dom.window.close());
  const state = { downloads: [], writes: [], reads: 0 };
  const api = {
    tabs: { query: async () => [{ id: 7, url }] },
    scripting: {
      executeScript: async (injection) => {
        state.reads++;
        assert.equal(injection.target.tabId, 7);
        assert.equal(typeof injection.func, 'function');
        if (readError) throw new Error('Permission denied');
        return [{ frameId: 0, result: page }];
      },
    },
    downloads: {
      download: async (options) => {
        if (downloadError) throw new Error('Network unavailable');
        state.downloads.push(options);
        return 1;
      },
    },
    storage: {
      local: {
        get: async () => settings,
        set: async (value) => {
          if (storageError) throw new Error('Storage unavailable');
          state.writes.push(value);
        },
      },
    },
  };
  await startPopup(dom.window.document, api);
  const byId = (id) => dom.window.document.getElementById(id);
  const change = (id, value) => {
    byId(id).value = value;
    byId(id).dispatchEvent(new dom.window.Event('change', { bubbles: true }));
  };
  return { dom, state, byId, change };
}

async function waitFor(predicate) {
  const deadline = Date.now() + 3000;
  while (!predicate() && Date.now() < deadline) await setImmediate();
  assert.ok(predicate(), 'Popup did not reach the expected state');
}

test('defaults to US and starts the chosen MP3 download with a safe filename', async (t) => {
  const { byId, state } = await popup(t);
  assert.equal(byId('word').textContent, 'hello');
  assert.equal(byId('ipa').textContent, '/heˈloʊ/');
  assert.equal(byId('download').disabled, false);
  byId('download').click();
  await waitFor(() => state.downloads.length === 1);
  assert.deepEqual(state.downloads[0], {
    url: 'https://dictionary.cambridge.org/us/media/hello-us.mp3',
    filename: 'hello.us.mp3',
    conflictAction: 'uniquify',
  });
  assert.match(byId('status').textContent, /Download started/);
  assert.ok(!Object.hasOwn(state.downloads[0], 'saveAs'));
});

test('switches accent immediately and remembers only preferences', async (t) => {
  const { dom, byId, state } = await popup(t);
  const uk = dom.window.document.querySelector('input[value="uk"]');
  uk.click();
  await waitFor(() => state.writes.length === 1);
  assert.equal(byId('ipa').textContent, '/heˈləʊ/');
  assert.equal(byId('filename').textContent, 'hello.uk.mp3');
  assert.deepEqual(state.writes[0], { language: 'en', theme: 'system', accent: 'uk' });
  byId('download').click();
  await waitFor(() => state.downloads.length === 1);
  assert.equal(state.downloads[0].filename, 'hello.uk.mp3');
});

test('settings apply live, persist, and preserve the selected pronunciation', async (t) => {
  const { dom, byId, change, state } = await popup(t, { settings: { accent: 'uk' } });
  assert.equal(byId('settings-panel').hidden, true);
  byId('settings-toggle').click();
  assert.equal(byId('settings-panel').hidden, false);
  assert.equal(dom.window.document.activeElement, byId('language'));
  change('language', 'ru');
  change('theme', 'dark');
  await waitFor(() => state.writes.length === 2);
  assert.equal(dom.window.document.documentElement.lang, 'ru');
  assert.equal(dom.window.document.documentElement.dataset.theme, 'dark');
  assert.equal(byId('download').textContent, 'Скачать MP3');
  assert.equal(byId('status').textContent, '');
  assert.equal(byId('ipa').textContent, '/heˈləʊ/');
  dom.window.document.dispatchEvent(
    new dom.window.KeyboardEvent('keydown', { key: 'Escape', cancelable: true }),
  );
  assert.equal(byId('settings-panel').hidden, true);
  assert.equal(dom.window.document.activeElement, byId('settings-toggle'));
});

test('restores language, theme and accent after reopening', async (t) => {
  const { dom, byId } = await popup(t, {
    settings: { language: 'ru', theme: 'light', accent: 'uk' },
  });
  assert.equal(dom.window.document.documentElement.dataset.theme, 'light');
  assert.equal(byId('language').value, 'ru');
  assert.equal(byId('download').textContent, 'Скачать MP3');
  assert.equal(byId('filename').textContent, 'hello.uk.mp3');
});

test('does not inject into unrelated tabs, and offers the dictionary link', async (t) => {
  const { byId, state } = await popup(t, { url: 'https://example.com/' });
  assert.equal(state.reads, 0);
  assert.equal(byId('recording').hidden, true);
  assert.match(byId('status').textContent, /Open a word/);
  byId('download').click();
  assert.equal(state.downloads.length, 0);
});

test('shows read failure and empty-page feedback instead of a broken download button', async (t) => {
  const failed = await popup(t, { readError: true });
  assert.match(failed.byId('status').textContent, /Could not read/);
  assert.equal(failed.byId('download').disabled, true);
  const empty = await popup(t, { page: { supported: true, entries: [] } });
  assert.match(empty.byId('status').textContent, /No pronunciation audio/);
});

test('reports download and settings failures without disabling subsequent use', async (t) => {
  const { byId, change } = await popup(t, { downloadError: true, storageError: true });
  byId('download').click();
  await waitFor(() => byId('status').textContent.includes('Could not start'));
  assert.equal(byId('download').disabled, false);
  change('theme', 'dark');
  await waitFor(() => byId('status').textContent.includes('Could not save settings'));
});

test('missing US audio is explicit and UK remains downloadable', async (t) => {
  const page = parsePage();
  page.entries[0].pronunciations = page.entries[0].pronunciations.filter((p) => p.accent === 'uk');
  const { dom, byId } = await popup(t, { page });
  assert.equal(byId('download').disabled, true);
  assert.equal(byId('unavailable').hidden, false);
  dom.window.document.querySelector('input[value="uk"]').click();
  assert.equal(byId('download').disabled, false);
  assert.equal(byId('unavailable').hidden, true);
});

test('supports multiple entries and variants and renders dictionary text safely', async (t) => {
  const page = parsePage();
  page.entries.push({
    word: '<img src="x" onerror="alert(1)">',
    partOfSpeech: 'noun',
    definition: 'text',
    pronunciations: [
      { accent: 'us', url: 'https://dictionary.cambridge.org/a.mp3', ipa: 'first' },
      { accent: 'us', url: 'https://dictionary.cambridge.org/b.mp3', ipa: 'second' },
    ],
  });
  const { byId, change, state } = await popup(t, { page });
  assert.equal(byId('entry-field').hidden, false);
  change('entry', '1');
  assert.equal(byId('word').childElementCount, 0);
  assert.equal(byId('variant-field').hidden, false);
  change('variant', '1');
  assert.equal(byId('ipa').textContent, '/second/');
  byId('download').click();
  await waitFor(() => state.downloads.length === 1);
  assert.equal(state.downloads[0].url, 'https://dictionary.cambridge.org/b.mp3');
});

for (const language of ['en', 'ru']) {
  test(`all UI labels and links are translated in ${language}`, async t => {
    const { dom } = await popup(t, { settings: { language } });
    for (const node of dom.window.document.querySelectorAll('[data-i18n]')) {
      assert.ok(node.textContent.trim(), `Missing translation: ${node.dataset.i18n}`);
    }
    for (const title of dom.window.document.querySelectorAll('svg title')) {
      assert.ok(title.textContent.trim(), 'SVG title must not be empty');
    }
  });
}
