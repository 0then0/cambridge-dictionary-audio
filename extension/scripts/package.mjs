import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

// Use the repository's Python release helper for deterministic ZIP archives.
execFileSync(
  process.env.PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3'),
  [fileURLToPath(new URL('../../scripts/package_extension.py', import.meta.url))],
  { stdio: 'inherit' },
);
