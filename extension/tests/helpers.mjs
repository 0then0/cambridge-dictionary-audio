import { readFile } from 'node:fs/promises';
import { JSDOM } from 'jsdom';
import { readPage } from '../build/page.js';

const html = await readFile(new URL('fixtures/hello.html', import.meta.url), 'utf8');
export const dictionaryUrl = 'https://dictionary.cambridge.org/us/dictionary/english/hello';

export function parsePage(content = html, pageUrl = dictionaryUrl) {
  const dom = new JSDOM(content, { url: pageUrl, runScripts: 'outside-only' });
  try {
    // Run the serialized injection in its actual DOM context, with no module closures.
    return JSON.parse(JSON.stringify(dom.window.eval(`(${readPage.toString()})()`)));
  } finally {
    dom.window.close();
  }
}
