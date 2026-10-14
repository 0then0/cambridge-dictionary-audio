export type Accent = 'us' | 'uk';

export interface Pronunciation {
  accent: Accent;
  url: string;
  ipa: string;
}

export interface Entry {
  word: string;
  partOfSpeech: string;
  definition: string;
  pronunciations: Pronunciation[];
}

export interface PageRecordings {
  supported: boolean;
  entries: Entry[];
}

// executeScript serializes this function. Keep every runtime dependency inside it.
export function readPage(): PageRecordings {
  const page = new URL(location.href);
  if (
    page.protocol !== 'https:' ||
    page.hostname !== 'dictionary.cambridge.org' ||
    page.port ||
    page.username ||
    page.password ||
    !/^\/(?:[a-z]{2}(?:-[a-z]{2})?\/)?dictionary\//i.test(page.pathname)
  ) {
    return { supported: false, entries: [] };
  }
  const entries: Entry[] = [];
  for (const block of document.querySelectorAll('.entry-body__el')) {
    const header = block.querySelector('.pos-header, .dpos-h');
    const word = header?.querySelector('.hw, .headword, .di-title')?.textContent?.trim();
    if (!header || !word) continue;
    const pronunciations: Pronunciation[] = [];
    const seen = new Set<string>();
    for (const region of header.querySelectorAll('.us, .uk')) {
      const accent: Accent = region.classList.contains('us') ? 'us' : 'uk';
      for (const source of region.querySelectorAll('audio source[src], audio[src]')) {
        const src = source.getAttribute('src');
        if (!src) continue;
        try {
          // Resolve against the page URL, never against a document-supplied <base>.
          const url = new URL(src, page.href);
          const key = `${accent}:${url.href}`;
          if (
            url.protocol !== 'https:' ||
            url.hostname !== 'dictionary.cambridge.org' ||
            url.port ||
            url.username ||
            url.password ||
            !url.pathname.toLowerCase().endsWith('.mp3') ||
            seen.has(key)
          )
            continue;
          pronunciations.push({
            accent,
            url: url.href,
            ipa: region.querySelector('.ipa')?.textContent?.trim() ?? '',
          });
          seen.add(key);
        } catch {
          // Ignore malformed page-provided URLs and retain other pronunciations.
        }
      }
    }
    if (pronunciations.length) {
      entries.push({
        word,
        partOfSpeech: header.querySelector('.pos')?.textContent?.trim() ?? '',
        definition: (block.querySelector('.def.ddef_d')?.textContent ?? '')
          .trim()
          .replace(/:\s*$/, ''),
        pronunciations,
      });
    }
  }
  return { supported: true, entries };
}

export function isDictionaryPage(value: string | undefined): boolean {
  if (!value) return false;
  try {
    const url = new URL(value);
    return (
      url.protocol === 'https:' &&
      url.hostname === 'dictionary.cambridge.org' &&
      !url.port &&
      !url.username &&
      !url.password &&
      /^\/(?:[a-z]{2}(?:-[a-z]{2})?\/)?dictionary\//i.test(url.pathname)
    );
  } catch {
    return false;
  }
}

export function audioFilename(word: string, accent: Accent): string {
  let stem = word
    .normalize('NFC')
    .toLowerCase()
    // biome-ignore lint/suspicious/noControlCharactersInRegex: Windows filenames exclude ASCII control characters.
    .replace(/[<>:"/\\|?*\u0000-\u001f\u007f]/g, '-')
    .replace(/\s+/g, ' ')
    .replace(/^[ .]+|[ .]+$/g, '');
  stem =
    Array.from(stem)
      .slice(0, 80)
      .join('')
      .replace(/[ .]+$/g, '') || 'pronunciation';
  if (/^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(stem)) stem = `_${stem}`;
  return `${stem}.${accent}.mp3`;
}
