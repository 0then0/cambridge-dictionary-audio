package org.cambridgeaudio.core

import java.text.Normalizer
import java.util.Locale
import okio.FileSystem

internal actual fun systemFileSystem(): FileSystem = FileSystem.SYSTEM

internal actual fun normalizeGloss(text: String): String =
    Normalizer.normalize(text, Normalizer.Form.NFKC).lowercase(Locale.ROOT).replace("ß", "ss")
