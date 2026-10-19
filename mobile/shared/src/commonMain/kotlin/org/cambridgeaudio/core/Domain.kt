package org.cambridgeaudio.core

import com.fleeksoft.ksoup.Ksoup
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.*
import okio.ByteString.Companion.encodeUtf8
import okio.ByteString.Companion.toByteString

internal val json = Json {
    ignoreUnknownKeys = true
    encodeDefaults = true
    prettyPrint = true
}

internal fun obj(text: String) = json.parseToJsonElement(text).jsonObject

internal fun JsonObject.text(key: String, fallback: String = "") =
    this[key]?.jsonPrimitive?.contentOrNull ?: fallback

internal fun JsonObject.flag(key: String) = this[key]?.jsonPrimitive?.booleanOrNull == true

internal fun JsonObject.array(key: String) = this[key] as? JsonArray ?: JsonArray(emptyList())

internal fun document(vararg pairs: Pair<String, Any?>): JsonObject = buildJsonObject {
    pairs.forEach { (key, value) ->
        put(
            key,
            when (value) {
                null -> JsonNull
                is JsonElement -> value
                is Boolean -> JsonPrimitive(value)
                is Number -> JsonPrimitive(value)
                else -> JsonPrimitive(value.toString())
            },
        )
    }
}

internal fun JsonObject.with(vararg pairs: Pair<String, Any?>) = JsonObject(this + document(*pairs))

internal fun List<String>.strings() = JsonArray(map(::JsonPrimitive))

fun sha256(bytes: ByteArray): String = bytes.toByteString().sha256().hex()

fun stableId(vararg values: String): String =
    values.joinToString("\u0000").encodeUtf8().sha256().hex().take(24)

fun normalizeWord(input: String): String {
    val result =
        input
            .trim()
            .lowercase()
            .split(Regex("\\s+|\\u00a0"))
            .filter(String::isNotEmpty)
            .joinToString(" ")
    require(Regex("[a-z0-9]+(?:[ '\\-][a-z0-9]+)*").matches(result)) { "input" }
    return result
}

fun audioFilename(word: String, accent: String, variantId: String = ""): String {
    var name =
        if (word in setOf("con", "prn", "aux", "nul") || Regex("(?:com|lpt)[1-9]").matches(word))
            "_$word"
        else word
    name =
        when {
            variantId.isNotEmpty() -> "${name.take(80).trimEnd()}--$variantId"
            name.length > 100 -> "${name.take(80).trimEnd()}--${stableId(name)}"
            else -> name
        }
    return "$name.$accent.mp3"
}

fun dictionaryUrl(word: String, mode: String = "english"): String {
    require(Regex("english(?:-[a-z]+)?").matches(mode))
    return "https://dictionary.cambridge.org/us/dictionary/$mode/" +
        normalizeWord(word).replace(" ", "-").replace("'", "%27")
}

fun isMp3(bytes: ByteArray) =
    bytes.size >= 3 &&
        (bytes.take(3).toByteArray().decodeToString() == "ID3" ||
            (bytes[0].toInt() and 255 == 255 && bytes[1].toInt() and 224 == 224))

@Serializable
data class Pronunciation(val accent: String, val url: String, val ipa: String = "") {
    val id
        get() = stableId("cambridge-audio", accent, url)
}

@Serializable
data class Entry(
    val word: String,
    val definition: String,
    val pronunciations: List<Pronunciation>,
    val part_of_speech: String = "",
    val entry_id: String = "",
    val sense_id: String = "",
    val source_url: String = "",
    val lemma: String = "",
    val legacy_ids: List<String> = emptyList(),
)

/** One parser shared by both mobile applications. Never accepts an HTML base tag. */
fun parseEntries(html: String, pageUrl: String): List<Entry> {
    val soup = Ksoup.parse(html, pageUrl)
    val result = mutableListOf<Entry>()
    val fallbackBlocks = mutableMapOf<String, Int>()
    for (block in soup.select(".entry-body__el")) {
        val header = block.selectFirst(".pos-header, .dpos-h") ?: continue
        val word = header.selectFirst(".hw, .headword, .di-title")?.text().orEmpty()
        val part = header.selectFirst(".pos, .dpos")?.text().orEmpty()
        val audio = mutableListOf<Pronunciation>()
        for (region in header.select(".uk, .us")) {
            val accent = if (region.hasClass("us")) "us" else "uk"
            for (source in region.select("audio source[src]")) {
                val raw = source.attr("src")
                val url =
                    when {
                        raw.startsWith("//") -> "https:$raw"
                        raw.startsWith("/") -> "https://dictionary.cambridge.org$raw"
                        raw.startsWith("https://") -> raw
                        else -> pageUrl.substringBeforeLast('/') + "/" + raw
                    }
                if (
                    !Regex(
                            "https://dictionary\\.cambridge\\.org/[^?#]*\\.mp3(?:[?#].*)?",
                            RegexOption.IGNORE_CASE,
                        )
                        .matches(url) || audio.any { it.accent == accent && it.url == url }
                )
                    continue
                val owner = source.parents().firstOrNull { it.hasClass("dpron-i") } ?: region
                audio +=
                    Pronunciation(
                        accent,
                        url,
                        owner.selectFirst(".ipa")?.text()?.replace(" ", "").orEmpty(),
                    )
            }
        }
        val upstream = block.id().ifEmpty { header.id() }
        val fallback = "$word:$part"
        val ordinal = fallbackBlocks[fallback] ?: 0
        fallbackBlocks[fallback] = ordinal + 1
        val entryId =
            stableId(
                "cambridge-entry",
                pageUrl.substringBefore('#'),
                upstream.ifEmpty { "$fallback:$ordinal" },
            )
        val legacyEntry =
            stableId(
                "cambridge",
                word,
                part,
                block.id(),
                *audio.map { it.url }.sorted().toTypedArray(),
            )
        val senses = mutableMapOf<String, Int>()
        val definitions = block.select(".def.ddef_d").toList()
        for (definition in if (definitions.isEmpty()) listOf(null) else definitions) {
            val text = definition?.text().orEmpty().removeSuffix(":").trimEnd()
            val sense = definition?.parents()?.firstOrNull { it.hasClass("def-block") }
            val key = sense?.attr("data-wl-senseid").orEmpty().ifEmpty { sense?.id().orEmpty() }
            val occurrence = senses[text] ?: 0
            senses[text] = occurrence + 1
            val senseId =
                if (key.isNotEmpty()) stableId("cambridge-sense", pageUrl.substringBefore('#'), key)
                else stableId(entryId, "text", text, occurrence.toString())
            result +=
                Entry(
                    word,
                    text,
                    audio,
                    part,
                    entryId,
                    senseId,
                    pageUrl,
                    word,
                    audio.map { stableId(stableId(legacyEntry, key, text), it.accent, it.url) },
                )
        }
    }
    return result
}

@Serializable
data class TranslationOption(
    val id: String,
    val texts: List<String>,
    val definition: String = "",
    val part_of_speech: String = "",
    val origin: String = "",
    val matched: Boolean = false,
)

@Serializable
data class TranslationResult(
    val language: String,
    val sense_id: String,
    val source: String,
    val options: List<TranslationOption> = emptyList(),
    val selected_id: String = "",
    val status: String = "ok",
    val error: String = "",
    val version: String = "",
    val alignment: String = "",
) {
    val texts: List<String>
        get() {
            options
                .find { it.id == selected_id }
                ?.let {
                    return it.texts
                }
            val matched = options.filter { it.matched }
            if (matched.isNotEmpty()) return matched.flatMap { it.texts }.distinct()
            return if (alignment != "unmatched" && options.size == 1) options[0].texts
            else emptyList()
        }
}

private val stopWords =
    "a an the to of in on at by for from with or and is are be been being that which where when who you your it its can as into etc"
        .split(' ')
        .toSet()

// Definitions are English. Full Unicode NFKC is supplied by the platform for
// externally imported strings before this lexical tokenizer is used.
private fun glossWords(text: String): List<String> =
    Regex("[\\p{L}\\p{N}]+")
        .findAll(
            normalizeGloss(text)
                .replace('’', '\'')
                .replace("cannot", "can not")
                .replace("can't", "can not")
                .replace("won't", "will not")
                .replace("n't", " not")
        )
        .map { it.value }
        .toList()

fun matchOptions(
    options: List<TranslationOption>,
    definition: String,
    part: String = "",
): List<TranslationOption> {
    if (definition.isEmpty()) return options
    val eligible = options.filter {
        part.isEmpty() ||
            it.part_of_speech.isEmpty() ||
            it.part_of_speech.lowercase() == part.lowercase()
    }
    val words = glossWords(definition)
    val exact = eligible.filter { glossWords(it.definition) == words }
    if (exact.isNotEmpty()) return exact.map { it.copy(matched = true) }
    if (part.lowercase() != "noun")
        return (eligible.ifEmpty { options }).map { it.copy(matched = false) }
    val anchors = words.filter { it !in stopWords }
    val target = anchors.toSet()
    val negatives = setOf("not", "no", "never", "without", "only", "except", "excluding")
    val scores =
        eligible
            .map { option ->
                val tokens = glossWords(option.definition).filter { it !in stopWords }
                val other = tokens.toSet()
                val overlap = target.intersect(other)
                val phrases = anchors.zipWithNext().toSet().intersect(tokens.zipWithNext().toSet())
                val score =
                    if (
                        overlap.size < 3 ||
                            phrases.isEmpty() ||
                            target.intersect(negatives) != other.intersect(negatives)
                    )
                        0.0
                    else overlap.size.toDouble() / maxOf(1, minOf(target.size, other.size))
                score to option
            }
            .sortedByDescending { it.first }
    if (scores.isNotEmpty() && scores[0].first >= .6) {
        val best = scores[0].first
        val winners = scores.filter { it.first == best }.map { it.second }
        val runner = scores.filter { it.first < best }.maxOfOrNull { it.first } ?: 0.0
        if (winners.map { it.texts }.distinct().size == 1 && best - runner >= .2)
            return winners.map { it.copy(matched = true) }
    }
    return eligible.ifEmpty { options }.map { it.copy(matched = false) }
}

fun align(result: TranslationResult, definition: String, part: String): TranslationResult {
    if (
        result.source == "User" ||
            result.selected_id.isNotEmpty() ||
            definition.isEmpty() ||
            result.options.isEmpty() ||
            result.options.none {
                it.definition.isNotEmpty() ||
                    it.part_of_speech.isNotEmpty() ||
                    it.origin.isNotEmpty()
            }
    )
        return result
    val options = matchOptions(result.options, definition, part)
    return result.copy(
        options = options,
        alignment = if (options.any { it.matched }) "matched" else "unmatched",
    )
}

fun cachedTranslation(metadata: JsonObject, language: String = "russian"): TranslationResult? {
    val candidates =
        metadata
            .array("translation_cache")
            .reversed()
            .mapNotNull {
                runCatching { json.decodeFromJsonElement<TranslationResult>(it) }.getOrNull()
            }
            .filter {
                it.language == language &&
                    it.sense_id == metadata.text("sense_id") &&
                    it.options.isNotEmpty() &&
                    it.source in setOf("User", "Cambridge", "WikDict")
            }
            .map {
                if (it.options.any { o -> o.definition.isNotEmpty() })
                    align(it, metadata.text("definition"), metadata.text("part_of_speech"))
                else it
            }
    return candidates.maxWithOrNull(
        compareBy<TranslationResult> {
                when {
                    it.source == "User" -> 3
                    it.options.any { o -> o.id == it.selected_id } -> 2
                    it.texts.isNotEmpty() -> 1
                    else -> 0
                }
            }
            .thenBy {
                if (it.selected_id.isNotEmpty()) 0
                else
                    when (it.source) {
                        "User" -> 3
                        "Cambridge" -> 2
                        else -> 1
                    }
            }
    )
}

fun ankiGuid(identity: String): String {
    val alphabet =
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#\$%&()*+,-./:;<=>?@[]^_`{|}~"
    val bytes = "cambridge-dictionary-audio__$identity".encodeUtf8().sha256().toByteArray()
    var value = 0uL
    for (byte in bytes.take(8)) value = (value shl 8) or (byte.toUByte().toULong())
    var result = ""
    while (value > 0uL) {
        result = alphabet[(value % 91u).toInt()] + result
        value /= 91u
    }
    return result
}
