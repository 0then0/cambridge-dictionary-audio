import type { Accent } from './page.js';

export const languages = [
  { code: 'en', name: 'English' },
  { code: 'ru', name: 'Русский' },
  { code: 'es', name: 'Español' },
  { code: 'de', name: 'Deutsch' },
  { code: 'fr', name: 'Français' },
  { code: 'ja', name: '日本語' },
  { code: 'pt-BR', name: 'Português (Brasil)' },
] as const;
export type Language = (typeof languages)[number]['code'];

export function parseLanguage(value: unknown): Language {
  return languages.find((language) => language.code === value)?.code ?? 'en';
}
export type Theme = 'system' | 'light' | 'dark';
export interface Settings {
  language: Language;
  theme: Theme;
  accent: Accent;
}

export function parseSettings(value: Record<string, unknown>): Settings {
  return {
    language: parseLanguage(value.language),
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
  es: {
    subtitle: 'Pronunciación de esta página',
    settings: 'Configuración',
    language: 'Idioma',
    theme: 'Apariencia',
    system: 'Sistema',
    light: 'Claro',
    dark: 'Oscuro',
    entry: 'Entrada del diccionario',
    pronunciation: 'Pronunciación',
    us: 'Estadounidense (US)',
    uk: 'Británico (UK)',
    variant: 'Grabación',
    download: 'Descargar MP3',
    retry: 'Actualizar las grabaciones de la página',
    loading: 'Leyendo esta página…',
    opening: 'Iniciando la descarga…',
    started: 'La descarga ha empezado. Revisa las descargas del navegador.',
    empty:
      'No se encontró audio de pronunciación. Espera a que cargue la página del diccionario y actualiza.',
    wrongPage: 'Abre una palabra o frase en Cambridge Dictionary y haz clic en esta extensión.',
    readError:
      'No se pudo leer esta pestaña. Recarga la página del diccionario e inténtalo de nuevo.',
    downloadError:
      'No se pudo iniciar la descarga. Inténtalo de nuevo o revisa las descargas del navegador.',
    storageError:
      'No se pudo guardar la configuración. Se aplicará hasta que cierres esta ventana.',
    unavailable: 'Esta pronunciación no está disponible. Elige el otro acento.',
    open: 'Abrir Cambridge Dictionary',
    app: 'Obtener la aplicación',
    noIpa: 'AFI no disponible',
    filename: 'Nombre de archivo',
    more: 'Para traducciones, grabaciones guardadas y unión de frases, usa la aplicación.',
  },
  de: {
    subtitle: 'Aussprache von dieser Seite',
    settings: 'Einstellungen',
    language: 'Sprache',
    theme: 'Erscheinungsbild',
    system: 'System',
    light: 'Hell',
    dark: 'Dunkel',
    entry: 'Wörterbucheintrag',
    pronunciation: 'Aussprache',
    us: 'Amerikanisch (US)',
    uk: 'Britisch (UK)',
    variant: 'Aufnahme',
    download: 'MP3 herunterladen',
    retry: 'Aufnahmen der Seite aktualisieren',
    loading: 'Seite wird gelesen …',
    opening: 'Download wird gestartet …',
    started: 'Download gestartet. Sieh in den Downloads deines Browsers nach.',
    empty:
      'Kein Aussprache-Audio gefunden. Warte, bis die Wörterbuchseite geladen ist, und aktualisiere dann.',
    wrongPage:
      'Öffne ein Wort oder eine Wendung im Cambridge Dictionary und klicke dann auf diese Erweiterung.',
    readError:
      'Dieser Tab konnte nicht gelesen werden. Lade die Wörterbuchseite neu und versuche es erneut.',
    downloadError:
      'Der Download konnte nicht gestartet werden. Versuche es erneut oder sieh in den Downloads deines Browsers nach.',
    storageError:
      'Die Einstellungen konnten nicht gespeichert werden. Sie gelten, bis du dieses Fenster schließt.',
    unavailable: 'Diese Aussprache ist nicht verfügbar. Wähle den anderen Akzent.',
    open: 'Cambridge Dictionary öffnen',
    app: 'App herunterladen',
    noIpa: 'IPA nicht verfügbar',
    filename: 'Dateiname',
    more: 'Für Übersetzungen, gespeicherte Aufnahmen und das Zusammenfügen von Wendungen nutze die App.',
  },
  fr: {
    subtitle: 'Prononciation de cette page',
    settings: 'Réglages',
    language: 'Langue',
    theme: 'Apparence',
    system: 'Système',
    light: 'Clair',
    dark: 'Sombre',
    entry: 'Entrée de dictionnaire',
    pronunciation: 'Prononciation',
    us: 'Américain (US)',
    uk: 'Britannique (UK)',
    variant: 'Enregistrement',
    download: 'Télécharger le MP3',
    retry: 'Actualiser les enregistrements de la page',
    loading: 'Lecture de la page…',
    opening: 'Démarrage du téléchargement…',
    started: 'Le téléchargement a commencé. Consultez les téléchargements du navigateur.',
    empty:
      'Aucun audio de prononciation trouvé. Attendez que la page du dictionnaire se charge, puis actualisez.',
    wrongPage:
      'Ouvrez un mot ou une expression dans le Cambridge Dictionary, puis cliquez sur cette extension.',
    readError: 'Impossible de lire cet onglet. Rechargez la page du dictionnaire et réessayez.',
    downloadError:
      'Impossible de démarrer le téléchargement. Réessayez ou consultez les téléchargements du navigateur.',
    storageError:
      'Impossible d’enregistrer les réglages. Ils s’appliquent jusqu’à la fermeture de cette fenêtre.',
    unavailable: 'Cette prononciation est indisponible. Choisissez l’autre accent.',
    open: 'Ouvrir le Cambridge Dictionary',
    app: 'Obtenir l’application',
    noIpa: 'API indisponible',
    filename: 'Nom du fichier',
    more: 'Pour les traductions, les enregistrements sauvegardés et l’assemblage d’expressions, utilisez l’application.',
  },
  ja: {
    subtitle: 'このページの発音',
    settings: '設定',
    language: '言語',
    theme: '外観',
    system: 'システム',
    light: 'ライト',
    dark: 'ダーク',
    entry: '辞書の項目',
    pronunciation: '発音',
    us: 'アメリカ英語（US）',
    uk: 'イギリス英語（UK）',
    variant: '録音',
    download: 'MP3 をダウンロード',
    retry: 'ページの録音を更新',
    loading: 'ページを読み込み中…',
    opening: 'ダウンロードを開始しています…',
    started: 'ダウンロードを開始しました。ブラウザーのダウンロードを確認してください。',
    empty:
      '発音の音声が見つかりません。辞書のページが読み込まれるまで待ってから、更新してください。',
    wrongPage:
      'Cambridge Dictionary で単語またはフレーズを開き、この拡張機能をクリックしてください。',
    readError:
      'このタブを読み取れませんでした。辞書のページを再読み込みして、もう一度お試しください。',
    downloadError:
      'ダウンロードを開始できませんでした。もう一度お試しいただくか、ブラウザーのダウンロードを確認してください。',
    storageError: '設定を保存できませんでした。このウィンドウを閉じるまでは設定が有効です。',
    unavailable: 'この発音は利用できません。もう一方のアクセントを選んでください。',
    open: 'Cambridge Dictionary を開く',
    app: 'アプリを入手',
    noIpa: 'IPA はありません',
    filename: 'ファイル名',
    more: '翻訳、保存済みの録音、フレーズの結合はアプリで利用できます。',
  },
  'pt-BR': {
    subtitle: 'Pronúncia desta página',
    settings: 'Configurações',
    language: 'Idioma',
    theme: 'Aparência',
    system: 'Sistema',
    light: 'Claro',
    dark: 'Escuro',
    entry: 'Verbete do dicionário',
    pronunciation: 'Pronúncia',
    us: 'Americano (US)',
    uk: 'Britânico (UK)',
    variant: 'Gravação',
    download: 'Baixar MP3',
    retry: 'Atualizar as gravações da página',
    loading: 'Lendo esta página…',
    opening: 'Iniciando o download…',
    started: 'O download foi iniciado. Confira os downloads do navegador.',
    empty:
      'Nenhum áudio de pronúncia encontrado. Aguarde o carregamento da página do dicionário e atualize.',
    wrongPage: 'Abra uma palavra ou frase no Cambridge Dictionary e clique nesta extensão.',
    readError:
      'Não foi possível ler esta aba. Recarregue a página do dicionário e tente novamente.',
    downloadError:
      'Não foi possível iniciar o download. Tente novamente ou confira os downloads do navegador.',
    storageError:
      'Não foi possível salvar as configurações. Elas valem até você fechar esta janela.',
    unavailable: 'Esta pronúncia não está disponível. Escolha o outro sotaque.',
    open: 'Abrir o Cambridge Dictionary',
    app: 'Baixar o aplicativo',
    noIpa: 'IPA indisponível',
    filename: 'Nome do arquivo',
    more: 'Para traduções, gravações salvas e junção de frases, use o aplicativo.',
  },
} as const;
export type Message = keyof typeof messages.en;
