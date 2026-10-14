import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { audioFilename, isDictionaryPage } from '../build/page.js';
import { parseSettings } from '../build/settings.js';
import { parsePage } from './helpers.mjs';

const html = await readFile(new URL('fixtures/hello.html', import.meta.url), 'utf8');

test('reads the header audio for US and UK, removes duplicates and trailing colon', () => {
  const result = parsePage();
  assert.equal(result.supported, true);
  assert.equal(result.entries.length, 1);
  assert.equal(result.entries[0].word, 'hello');
  assert.equal(result.entries[0].partOfSpeech, 'exclamation');
  assert.equal(result.entries[0].definition, 'used when meeting or greeting someone');
  assert.deepEqual(result.entries[0].pronunciations, [
    { accent: 'us', url: 'https://dictionary.cambridge.org/us/media/hello-us.mp3', ipa: 'heˈloʊ' },
    { accent: 'uk', url: 'https://dictionary.cambridge.org/us/media/hello-uk.mp3', ipa: 'heˈləʊ' },
  ]);
});

for (const pageUrl of [
  'https://dictionary.cambridge.org/dictionary/english/hello',
  'https://dictionary.cambridge.org/ru/dictionary/english-russian/hello',
  'https://dictionary.cambridge.org/es-LA/dictionary/english/hello',
]) {
  test(`accepts dictionary locale ${pageUrl}`, () => {
    assert.equal(isDictionaryPage(pageUrl), true);
    assert.equal(parsePage(undefined, pageUrl).entries.length, 1);
  });
}

for (const pageUrl of [
  'https://dictionary.cambridge.org/us/',
  'http://dictionary.cambridge.org/dictionary/english/hello',
  'https://dictionary.cambridge.org.attacker.example/dictionary/english/hello',
  'https://dictionary.cambridge.org:444/dictionary/english/hello',
  'https://user@dictionary.cambridge.org/dictionary/english/hello',
  'https://example.com/dictionary/english/hello',
]) {
  test(`refuses unrelated or unsupported page ${pageUrl}`, () => {
    assert.equal(isDictionaryPage(pageUrl), false);
    assert.deepEqual(parsePage(undefined, pageUrl), { supported: false, entries: [] });
  });
}

test('ignores remote, insecure, credentialed, malformed and non-MP3 audio URLs', () => {
  const sources = [
    'https://attacker.example/stolen.mp3',
    'http://dictionary.cambridge.org/test.mp3',
    'https://dictionary.cambridge.org:444/test.mp3',
    'javascript:alert(1)',
    'https://a@dictionary.cambridge.org/test.mp3',
    'https://[invalid',
    '/media/audio.ogg',
  ]
    .map((src) => `<source src="${src}">`)
    .join('');
  const result = parsePage(
    html.replace('<source type="audio/ogg"', `${sources}<source type="audio/ogg"`),
  );
  assert.equal(result.entries[0].pronunciations.length, 2);
});

test('uses the real page URL even when a hostile base tag is present', () => {
  const result = parsePage(html.replace('<head>', '<head><base href="https://attacker.example/">'));
  assert.equal(
    result.entries[0].pronunciations[0].url,
    'https://dictionary.cambridge.org/us/media/hello-us.mp3',
  );
});

test('preserves independent entries, variants and safe plain text', () => {
  const extra = `<div class="entry-body__el"><div class="pos-header">
    <span class="hw">read</span><span class="pos">verb</span>
    <span class="us"><audio src="/media/read1.mp3"></audio><span class="ipa">riːd</span></span>
    <span class="us"><audio src="/media/read2.mp3"></audio><span class="ipa">red</span></span>
  </div><div class="def ddef_d">a definition: with a colon:</div></div>`;
  const result = parsePage(html.replace('</body>', `${extra}</body>`));
  assert.equal(result.entries.length, 2);
  assert.equal(result.entries[1].pronunciations.length, 2);
  assert.equal(result.entries[1].definition, 'a definition: with a colon');
});

test('missing or changed markup produces an empty supported page', () => {
  assert.deepEqual(parsePage('<h1>No audio</h1>'), { supported: true, entries: [] });
  assert.equal(isDictionaryPage(undefined), false);
  assert.equal(isDictionaryPage('not a URL'), false);
});

for (const [word, expected] of [
  ['Hello', 'hello.us.mp3'],
  ['good morning', 'good morning.us.mp3'],
  ['con', '_con.us.mp3'],
  ['COM9', '_com9.us.mp3'],
  ['nul.txt', '_nul.txt.us.mp3'],
  ['../../hello', '-..-hello.us.mp3'],
  ['a/b', 'a-b.us.mp3'],
  ['  .  ', 'pronunciation.us.mp3'],
  ["can't", "can't.us.mp3"],
]) {
  test(`creates portable download filename for ${word}`, () => {
    assert.equal(audioFilename(word, 'us'), expected);
    assert.equal(audioFilename(word, 'uk').endsWith('.uk.mp3'), true);
  });
}

test('limits filenames and accepts only supported preferences', () => {
  assert.ok(audioFilename('hello'.repeat(100), 'us').length <= 87);
  assert.deepEqual(parseSettings({}), { language: 'en', theme: 'system', accent: 'us' });
  assert.deepEqual(parseSettings({ language: 'de', theme: {}, accent: 'both' }), parseSettings({}));
  assert.deepEqual(parseSettings({ language: 'ru', theme: 'dark', accent: 'uk' }), {
    language: 'ru',
    theme: 'dark',
    accent: 'uk',
  });
});

test('strips ASCII control characters from portable filenames', () => {
  for (const word of ['a\u0000b', 'a\u001fb', 'a\u007fb']) {
    assert.equal(audioFilename(word, 'us'), 'a-b.us.mp3');
  }
});
