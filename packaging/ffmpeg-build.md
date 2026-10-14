# Rebuilding the bundled FFmpeg

The desktop application includes FFmpeg and LAME under their LGPL terms.
The matching `ffmpeg-lame-sources-<platform>-<architecture>.tar.gz` release asset
contains unmodified upstream source archives, their SHA-256 hashes, the build
helper, exact configure commands and license texts. No GPL or nonfree components
are enabled. Application source is available in the same GitHub release.

Extract that source asset into an empty directory. With Python 3.14 or newer,
Bash, Make, a C compiler and pkg-config/pkgconf installed, run:

```sh
python scripts/build_ffmpeg.py
```

On Windows, run the command in an MSYS2 UCRT64 shell with `make`,
`mingw-w64-ucrt-x86_64-gcc` and `mingw-w64-ucrt-x86_64-pkgconf` installed.
On macOS, use the Xcode command-line tools and pkgconf; the deployment target is
macOS 14. On Linux, use GCC, Make and pkg-config. Build on the same architecture
as the executable being replaced.

The helper validates the original source hashes, compiles static FFmpeg/LAME
libraries into the standalone executable, and tests MP3 encoding, concatenation,
loudness normalization and decoding. Only system libraries remain external.
The generated executable is in `build/bundled-ffmpeg/`. `BUILD.json` records the
original build commands; prefixes are recalculated for your extraction directory.

To use a rebuilt executable, replace `tools/ffmpeg` (or `tools/ffmpeg.exe`) in the
application's runtime directory. On macOS this is
`Cambridge Dictionary Audio.app/Contents/Frameworks/tools/ffmpeg`; changing the
bundle invalidates its existing signature, so local macOS signing may be needed.
Windows/Linux onedir bundles keep this directory under `_internal/`.

## Upstream projects

- [FFmpeg licensing](https://ffmpeg.org/legal.html)
- [LAME](https://lame.sourceforge.io/)
