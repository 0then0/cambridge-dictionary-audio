import type { Accent } from './page.js';

export type Language = 'en' | 'ru';
export type Theme = 'system' | 'light' | 'dark';
export interface Settings {
  language: Language;
  theme: Theme;
  accent: Accent;
}

export function parseSettings(value: Record<string, unknown>): Settings {
  return {
    language: value.language === 'ru' ? 'ru' : 'en',
    theme: value.theme === 'light' || value.theme === 'dark' ? value.theme : 'system',
    accent: value.accent === 'uk' ? 'uk' : 'us',
  };
}

export const messages = {
  en: {
    subtitle: 'Pronunciation from this page',
    settings: 'Settings',
    language: 'Language',
    theme: 'Appearance',
    system: 'System',
    light: 'Light',
    dark: 'Dark',
    entry: 'Dictionary entry',
    pronunciation: 'Pronunciation',
    us: 'American (US)',
    uk: 'British (UK)',
    variant: 'Recording',
    download: 'Download MP3',
    retry: 'Refresh page recordings',
    loading: 'Reading this page…',
    opening: 'Starting download…',
    started: 'Download started. Check your browser’s downloads.',
    empty: 'No pronunciation audio found. Wait for the dictionary page to load, then refresh.',
    wrongPage: 'Open a word or phrase on Cambridge Dictionary, then click this extension.',
    readError: 'Could not read this tab. Reload the dictionary page and try again.',
    downloadError: 'Could not start the download. Try again or check your browser’s downloads.',
    storageError: 'Could not save settings. They will apply until you close this window.',
    unavailable: 'This pronunciation is unavailable. Choose the other accent.',
    open: 'Open Cambridge Dictionary',
    app: 'Get the app',
    noIpa: 'IPA unavailable',
    filename: 'Filename',
    more: 'For translations, saved recordings and phrase synthesis, use the app.',
  },
  ru: {
    subtitle: 'Произношение с этой страницы',
    settings: 'Настройки',
    language: 'Язык',
    theme: 'Оформление',
    system: 'Системное',
    light: 'Светлое',
    dark: 'Тёмное',
    entry: 'Словарная запись',
    pronunciation: 'Произношение',
    us: 'Американское (US)',
    uk: 'Британское (UK)',
    variant: 'Аудиозапись',
    download: 'Скачать MP3',
    retry: 'Обновить записи страницы',
    loading: 'Чтение страницы…',
    opening: 'Начало скачивания…',
    started: 'Скачивание началось. Проверьте загрузки браузера.',
    empty:
      'Аудио произношения не найдено. Дождитесь загрузки словарной страницы и обновите записи.',
    wrongPage: 'Откройте слово или фразу в Cambridge Dictionary и нажмите иконку расширения.',
    readError: 'Не удалось прочитать вкладку. Перезагрузите словарную страницу и попробуйте снова.',
    downloadError:
      'Не удалось начать скачивание. Повторите попытку или проверьте загрузки браузера.',
    storageError: 'Не удалось сохранить настройки. Они действуют до закрытия этого окна.',
    unavailable: 'Это произношение недоступно. Выберите другой вариант.',
    open: 'Открыть Cambridge Dictionary',
    app: 'Скачать приложение',
    noIpa: 'Транскрипция недоступна',
    filename: 'Имя файла',
    more: 'Переводы, сохранённые записи и склейка фраз доступны в приложении.',
  },
} as const;
export type Message = keyof typeof messages.en;
