import type { Entry, Pronunciation } from './page.js';
import { audioFilename, isDictionaryPage, readPage } from './page.js';
import type { Message, Settings } from './settings.js';
import { messages, parseSettings } from './settings.js';

export type BrowserApi = Pick<typeof chrome, 'tabs' | 'scripting' | 'downloads' | 'storage'>;

export async function startPopup(document: Document, api: BrowserApi): Promise<void> {
  function element<T extends HTMLElement>(id: string): T {
    const node = document.getElementById(id);
    if (!node) throw new Error(`Missing popup element: ${id}`);
    return node as T;
  }
  let settings: Settings = parseSettings({});
  let entries: Entry[] = [];
  let busy = false;
  let status: Message | null = 'loading';
  let statusError = false;
  const entrySelect = element<HTMLSelectElement>('entry');
  const variantSelect = element<HTMLSelectElement>('variant');
  const download = element<HTMLButtonElement>('download');
  const refresh = element<HTMLButtonElement>('refresh');
  const language = element<HTMLSelectElement>('language');
  const theme = element<HTMLSelectElement>('theme');
  const accentControls = Array.from(
    document.querySelectorAll<HTMLInputElement>('input[name="accent"]'),
  );

  const selectedEntry = () => entries[Number(entrySelect.value)];
  const variants = () =>
    selectedEntry()?.pronunciations.filter((p) => p.accent === settings.accent) ?? [];
  const selectedAudio = (): Pronunciation | undefined => variants()[Number(variantSelect.value)];
  const text = (key: Message) => messages[settings.language][key];

  function report(key: Message, error = false): void {
    status = key;
    statusError = error;
    const node = element('status');
    node.textContent = text(status);
    node.dataset.error = String(statusError);
  }

  function option(value: string, label: string): HTMLOptionElement {
    const node = document.createElement('option');
    node.value = value;
    node.textContent = label;
    return node;
  }

  function renderAudio(resetVariant = true): void {
    const record = selectedEntry();
    element('recording').hidden = !record;
    element('entry-field').hidden = entries.length < 2;
    element('word').textContent = record?.word ?? '';
    element('part-of-speech').textContent = record?.partOfSpeech ?? '';
    element('definition').textContent = record?.definition ?? '';
    for (const control of accentControls) {
      control.checked = control.value === settings.accent;
      control.disabled = busy || !record?.pronunciations.some((p) => p.accent === control.value);
    }
    const items = variants();
    const previous = resetVariant ? '0' : variantSelect.value;
    variantSelect.replaceChildren(
      ...items.map((p, i) =>
        option(String(i), p.ipa ? `/${p.ipa}/` : `${text('variant')} ${i + 1}`),
      ),
    );
    variantSelect.value = items[Number(previous)] ? previous : '0';
    element('variant-field').hidden = items.length < 2;
    const audio = selectedAudio();
    element('ipa').textContent = audio?.ipa ? `/${audio.ipa}/` : audio ? text('noIpa') : '';
    element('unavailable').hidden = !record || !!audio;
    const filename = record && audio ? audioFilename(record.word, audio.accent) : '';
    element('filename').textContent = filename;
    download.disabled = busy || !audio;
    entrySelect.disabled = busy;
    variantSelect.disabled = busy;
    refresh.disabled = busy;
  }

  function localize(): void {
    document.documentElement.lang = settings.language;
    document.documentElement.dataset.theme = settings.theme;
    for (const node of document.querySelectorAll<HTMLElement>('[data-i18n]')) {
      const key = node.dataset.i18n as Message;
      node.textContent = text(key);
    }
    element('settings-toggle').setAttribute('aria-label', text('settings'));
    refresh.setAttribute('aria-label', text('retry'));
    language.value = settings.language;
    theme.value = settings.theme;
    if (status) report(status, statusError);
    else element('status').textContent = '';
    element('settings-icon-title').textContent = text('settings');
    element('refresh-icon-title').textContent = text('retry');
    for (const control of accentControls) {
      control.setAttribute('aria-label', text(control.value === 'uk' ? 'uk' : 'us'));
    }
    renderAudio(false);
  }

  async function persist(): Promise<void> {
    try {
      // Store only preferences, not words, URLs or download history.
      await api.storage.local.set({ ...settings });
    } catch {
      report('storageError', true);
    }
  }

  async function loadPage(): Promise<void> {
    busy = true;
    entries = [];
    entrySelect.replaceChildren();
    report('loading');
    renderAudio();
    try {
      const [tab] = await api.tabs.query({ active: true, currentWindow: true });
      if (!tab || tab.id === undefined || !isDictionaryPage(tab.url)) {
        report('wrongPage');
        return;
      }
      const results = await api.scripting.executeScript({
        target: { tabId: tab.id },
        func: readPage,
      });
      const page = results.find((result) => result.frameId === 0)?.result;
      if (!page) {
        report('readError', true);
        return;
      }
      if (!page.supported) {
        report('wrongPage');
        return;
      }
      entries = page.entries;
      entrySelect.replaceChildren(
        ...entries.map((entry, index) =>
          option(
            String(index),
            `${entry.word}${entry.partOfSpeech ? ` · ${entry.partOfSpeech}` : ''}` +
              (entries.filter((e) => e.word === entry.word && e.partOfSpeech === entry.partOfSpeech)
                .length > 1
                ? ` (${index + 1})`
                : ''),
          ),
        ),
      );
      if (entries.length) {
        status = null;
        element('status').textContent = '';
      } else {
        report('empty');
      }
    } catch {
      report('readError', true);
    } finally {
      busy = false;
      renderAudio();
    }
  }

  download.addEventListener('click', async () => {
    const audio = selectedAudio();
    const record = selectedEntry();
    if (busy || !audio || !record) return;
    busy = true;
    report('opening');
    renderAudio(false);
    try {
      await api.downloads.download({
        url: audio.url,
        filename: audioFilename(record.word, audio.accent),
        conflictAction: 'uniquify',
      });
      report('started');
    } catch {
      report('downloadError', true);
    } finally {
      busy = false;
      renderAudio(false);
    }
  });
  refresh.addEventListener('click', () => {
    void loadPage();
  });
  entrySelect.addEventListener('change', () => renderAudio());
  variantSelect.addEventListener('change', () => renderAudio(false));
  for (const control of accentControls) {
    control.addEventListener('change', () => {
      settings = { ...settings, accent: control.value === 'uk' ? 'uk' : 'us' };
      renderAudio();
      void persist();
    });
  }
  language.addEventListener('change', () => {
    settings = { ...settings, language: language.value === 'ru' ? 'ru' : 'en' };
    localize();
    void persist();
  });
  theme.addEventListener('change', () => {
    settings = {
      ...settings,
      theme: theme.value === 'light' || theme.value === 'dark' ? theme.value : 'system',
    };
    localize();
    void persist();
  });
  element('settings-toggle').addEventListener('click', () => {
    const panel = element('settings-panel');
    panel.hidden = !panel.hidden;
    element('settings-toggle').setAttribute('aria-expanded', String(!panel.hidden));
    if (!panel.hidden) language.focus();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !element('settings-panel').hidden) {
      event.preventDefault();
      element('settings-panel').hidden = true;
      element('settings-toggle').setAttribute('aria-expanded', 'false');
      element('settings-toggle').focus();
    }
  });
  try {
    settings = parseSettings(await api.storage.local.get(['language', 'theme', 'accent']));
  } catch {
    // Storage may be unavailable; keep the popup usable with defaults.
  }
  localize();
  await loadPage();
}
