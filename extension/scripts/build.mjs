import { execFileSync } from 'node:child_process';
import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const metadata = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'));
const project = await readFile(new URL('../../pyproject.toml', import.meta.url), 'utf8');
const version = project.match(/^version = "([^"]+)"/m)?.[1];
if (version !== metadata.version) throw new Error('Extension and Python versions must match');
await rm(new URL('../build/', import.meta.url), { recursive: true, force: true });
execFileSync(
  process.execPath,
  [fileURLToPath(new URL('../node_modules/typescript/bin/tsc', import.meta.url))],
  { cwd: root, stdio: 'inherit' },
);
const icons = Object.fromEntries(
  [16, 32, 48, 128].map((size) => [String(size), `icons/icon-${size}.png`]),
);
for (const browser of ['chrome', 'firefox']) {
  const output = new URL(`../dist/${browser}/`, import.meta.url);
  await rm(output, { recursive: true, force: true });
  await mkdir(output, { recursive: true });
  await cp(new URL('../build/', import.meta.url), output, { recursive: true });
  for (const file of ['popup.html', 'popup.css', 'icons']) {
    await cp(new URL(`../${file}`, import.meta.url), new URL(file, output), { recursive: true });
  }
  await cp(new URL('../../assets/icon.svg', import.meta.url), new URL('icons/icon.svg', output));
  for (const file of ['LICENSE', 'LICENSE-MIT', 'NOTICE']) {
    await cp(new URL(`../../${file}`, import.meta.url), new URL(file, output));
  }
  for (const [locale, description] of Object.entries({
    en: 'Download US and UK pronunciation audio from the Cambridge Dictionary page you are viewing.',
    ru: 'Скачивайте американское и британское произношение с открытой страницы Cambridge Dictionary.',
  })) {
    const directory = new URL(`_locales/${locale}/`, output);
    await mkdir(directory, { recursive: true });
    await writeFile(
      new URL('messages.json', directory),
      `${JSON.stringify(
        {
          name: { message: 'Cambridge Dictionary Audio' },
          description: { message: description },
        },
        null,
        2,
      )}\n`,
    );
  }
  const manifest = {
    manifest_version: 3,
    name: '__MSG_name__',
    description: '__MSG_description__',
    default_locale: 'en',
    version,
    permissions: ['activeTab', 'scripting', 'downloads', 'storage'],
    icons,
    action: {
      default_popup: 'popup.html',
      default_title: 'Cambridge Dictionary Audio',
      default_icon: icons,
    },
    content_security_policy: {
      extension_pages: "script-src 'self'; object-src 'none'; base-uri 'none'",
    },
    ...(browser === 'chrome'
      ? { minimum_chrome_version: '102' }
      : {
          browser_specific_settings: {
            gecko: {
              id: 'cambridge-audio@0then0.github.io',
              strict_min_version: '140.0',
              data_collection_permissions: { required: ['none'] },
            },
            gecko_android: { strict_min_version: '142.0' },
          },
        }),
  };
  await writeFile(new URL('manifest.json', output), `${JSON.stringify(manifest, null, 2)}\n`);
}
console.log('Built Chrome and Firefox extensions in extension/dist/');
