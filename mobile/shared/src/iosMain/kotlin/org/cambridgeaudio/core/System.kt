package org.cambridgeaudio.core

import okio.FileSystem
import platform.Foundation.NSString
import platform.Foundation.create
import platform.Foundation.precomposedStringWithCompatibilityMapping

internal actual fun systemFileSystem(): FileSystem = FileSystem.SYSTEM

@OptIn(kotlinx.cinterop.BetaInteropApi::class)
internal actual fun normalizeGloss(text: String): String =
    NSString.create(string = text)
        .precomposedStringWithCompatibilityMapping
        .lowercase()
        .replace("ß", "ss")
