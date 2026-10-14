import { startPopup } from './popup.js';

const globals = globalThis as typeof globalThis & { browser?: typeof chrome };
const api = globals.browser ?? globals.chrome;
void startPopup(document, api).catch(() => {
  const status = document.getElementById('status');
  if (status) status.textContent = 'Could not open the extension. Close this window and try again.';
});
