"""Generate and check the Android/iOS interface catalogues from mobile/locales/*.json.

English and Russian stay inline at each `t(english, russian)` call. Every other
language is looked up by the English text, so the catalogues must cover exactly the
English strings used by the sources. Text with numbers uses `{0}`, `{1}` placeholders
numbered by first appearance of each interpolated expression.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "mobile/locales"
ANDROID = ROOT / "mobile/androidApp/src/main"
IOS = ROOT / "mobile/iosApp/CambridgeAudio"
KOTLIN_TARGET = ANDROID / "java/org/cambridgeaudio/app/Locales.kt"
SWIFT_TARGET = IOS / "Locales.swift"
GENERATED = (KOTLIN_TARGET, SWIFT_TARGET)

# Keep in sync with cambridge_audio.i18n.LANGUAGES (a test compares them).
LANGUAGES = {
    "en": "English",
    "ru": "Русский",
    "es": "Español",
    "de": "Deutsch",
    "fr": "Français",
    "ja": "日本語",
    "pt-BR": "Português (Brasil)",
}
TRANSLATED = [code for code in LANGUAGES if code not in {"en", "ru"}]
PLACEHOLDER = re.compile(r"\{(\d+)\}")
ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "$": "$", "'": "'", "r": "\r"}


def read_literal(source, start, swift):
    """Parse the string literal at source[start]; interpolations become \\0expr\\0."""
    triple = source.startswith('"""', start)
    i = start + (3 if triple else 1)
    out = []
    while True:
        char = source[i]
        if source.startswith('"""', i) if triple else char == '"':
            return "".join(out), i + (3 if triple else 1)
        if char == "\\":
            if swift and source[i + 1] == "(":
                end = matching(source, i + 1, "(", ")")
                out.append("\0" + source[i + 2 : end] + "\0")
                i = end + 1
            elif source[i + 1] == "u":
                out.append(chr(int(source[i + 2 : i + 6], 16)))
                i += 6
            else:
                out.append(ESCAPES.get(source[i + 1], source[i + 1]))
                i += 2
        elif not swift and char == "$" and source[i + 1] == "{":
            end = matching(source, i + 1, "{", "}")
            out.append("\0" + source[i + 2 : end] + "\0")
            i = end + 1
        elif not swift and char == "$" and (name := re.match(r"[A-Za-z_]\w*", source[i + 1 :])):
            out.append("\0" + name.group(0) + "\0")
            i += 1 + len(name.group(0))
        else:
            out.append(char)
            i += 1


def matching(source, opening, left, right):
    depth, i = 0, opening
    while True:
        depth += source[i] == left
        depth -= source[i] == right
        if depth == 0:
            return i
        i += 1


def template(text, expressions):
    def number(match):
        expression = match.group(1)
        if expression not in expressions:
            expressions.append(expression)
        return "{" + str(expressions.index(expression)) + "}"

    return re.sub(r"\0(.*?)\0", number, text)


def english_strings():
    """English templates passed to t(...) in the Android and iOS sources, in source order."""
    found = {}
    files = sorted(ANDROID.rglob("*.kt")) + sorted(IOS.rglob("*.swift"))
    for path in files:
        if path in GENERATED:
            continue
        source = path.read_text(encoding="utf-8")
        for call in re.finditer(r"(?<![\w.])(?:model\.)?t\(\s*(?=\")", source):
            english, end = read_literal(source, call.end(), path.suffix == ".swift")
            rest = source[end:].lstrip()
            if not rest.startswith(","):
                continue
            russian_start = len(source) - len(rest[1:].lstrip())
            if source[russian_start] != '"':
                continue
            expressions = []
            found.setdefault(template(english, expressions), path.name)
    return list(found)


def load(language):
    return json.loads((LOCALES / f"{language}.json").read_text(encoding="utf-8"))


def problems():
    """Describe every mismatch between the sources and the catalogues."""
    english = english_strings()
    issues = []
    for language in TRANSLATED:
        try:
            catalogue = load(language)
        except FileNotFoundError:
            issues.append(f"{language}: mobile/locales/{language}.json is missing")
            continue
        issues += [
            f"{language}: missing translation for {key!r}"
            for key in english
            if key not in catalogue
        ]
        issues += [
            f"{language}: unused translation {key!r}" for key in catalogue if key not in english
        ]
        for key, value in catalogue.items():
            if sorted(PLACEHOLDER.findall(key)) != sorted(PLACEHOLDER.findall(value)):
                issues.append(f"{language}: placeholders differ for {key!r}")
            if not value.strip() or key.count("\n") != value.count("\n"):
                issues.append(f"{language}: empty or reflowed translation for {key!r}")
            spacing = key.startswith(" ") != value.startswith(" ") or key.endswith(
                " "
            ) != value.endswith(" ")
            # A full-width colon carries its own space.
            if spacing and not value.endswith("："):
                issues.append(f"{language}: leading/trailing space differs for {key!r}")
            if len(PLACEHOLDER.findall(key)) != len(set(PLACEHOLDER.findall(key))):
                issues.append(f"{language}: repeated placeholder in {key!r}")
    return issues


def kotlin_string(text):
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")
    return '"' + escaped.replace("\n", "\\n").replace("\t", "\\t") + '"'


def swift_string(text):
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + escaped.replace("\n", "\\n").replace("\t", "\\t") + '"'


def ident(code):
    return code.replace("-", "_").lower()


def render_kotlin():
    lines = [
        "// Generated by scripts/mobile_locales.py from mobile/locales/*.json; do not edit.",
        "package org.cambridgeaudio.app",
        "",
        "internal object Locales {",
        "    /** Language code and its own name, in menu order. */",
        "    val names: List<Pair<String, String>> =",
        "        listOf(",
    ]
    lines += [
        f"            {kotlin_string(c)} to {kotlin_string(n)}," for c, n in LANGUAGES.items()
    ]
    lines += ["        )", ""]
    for code in TRANSLATED:
        lines.append(f"    private val {ident(code)} =")
        lines.append("        mapOf(")
        for key, value in load(code).items():
            lines.append(f"            {kotlin_string(key)} to {kotlin_string(value)},")
        lines += ["        )", ""]
    lines += ["    private val catalogues ="]
    lines += ["        mapOf("]
    lines += [f"            {kotlin_string(c)} to {ident(c)}," for c in TRANSLATED]
    lines += ["        )", ""]
    lines += KOTLIN_LOOKUP.splitlines()
    lines.append("}")
    return "\n".join(lines) + "\n"


KOTLIN_LOOKUP = """\
    private val placeholder = Regex("\\\\{(\\\\d+)}")

    /** English and Russian come from the call site; other languages from the catalogues. */
    fun text(language: String, english: String, russian: String): String =
        when (language) {
            "en" -> english
            "ru" -> russian
            else -> translate(language, english) ?: english
        }

    private fun translate(language: String, english: String): String? {
        val entries = catalogues[language] ?: return null
        entries[english]?.let {
            return it
        }
        // Text with numbers is looked up by its template: "Meanings (3)" -> "Meanings ({0})".
        for ((template, translated) in entries) {
            val arguments = match(template, english) ?: continue
            return placeholder.replace(translated) { arguments[it.groupValues[1].toInt()] }
        }
        return null
    }

    private fun match(template: String, english: String): List<String>? {
        if (!placeholder.containsMatchIn(template)) return null
        val pattern = StringBuilder("^")
        var last = 0
        for (found in placeholder.findAll(template)) {
            pattern.append(Regex.escape(template.substring(last, found.range.first)))
            pattern.append("(.+?)")
            last = found.range.last + 1
        }
        pattern.append(Regex.escape(template.substring(last))).append("$")
        return Regex(pattern.toString()).matchEntire(english)?.groupValues?.drop(1)
    }"""


def render_swift():
    lines = [
        "// Generated by scripts/mobile_locales.py from mobile/locales/*.json; do not edit.",
        "import Foundation",
        "",
        "enum Locales {",
        "  /// Language code and its own name, in menu order.",
        "  static let names: [(code: String, name: String)] = [",
    ]
    lines += [f"    ({swift_string(c)}, {swift_string(n)})," for c, n in LANGUAGES.items()]
    lines += ["  ]", ""]
    for code in TRANSLATED:
        lines.append(f"  private static let {ident(code)}: [String: String] = [")
        for key, value in load(code).items():
            lines.append(f"    {swift_string(key)}: {swift_string(value)},")
        lines += ["  ]", ""]
    lines += ["  private static let catalogues: [String: [String: String]] = ["]
    lines += [f"    {swift_string(c)}: {ident(c)}," for c in TRANSLATED]
    lines += ["  ]", ""]
    lines += SWIFT_LOOKUP.splitlines()
    lines.append("}")
    return "\n".join(lines) + "\n"


SWIFT_LOOKUP = """\
  /// English and Russian come from the call site; other languages from the catalogues.
  static func text(_ language: String, _ english: String, _ russian: String) -> String {
    switch language {
    case "en": return english
    case "ru": return russian
    default: return translate(language, english) ?? english
    }
  }

  private static func translate(_ language: String, _ english: String) -> String? {
    guard let entries = catalogues[language] else { return nil }
    if let exact = entries[english] { return exact }
    // Text with numbers is looked up by its template: "Meanings (3)" -> "Meanings ({0})".
    for (template, translated) in entries {
      guard let arguments = match(template, english) else { continue }
      var result = translated
      for (index, value) in arguments.enumerated() {
        result = result.replacingOccurrences(of: "{\\(index)}", with: value)
      }
      return result
    }
    return nil
  }

  private static func match(_ template: String, _ english: String) -> [String]? {
    guard template.contains("{0}"),
      let placeholder = try? NSRegularExpression(pattern: "\\\\{(\\\\d+)\\\\}")
    else { return nil }
    let whole = NSRange(template.startIndex..., in: template)
    var pattern = "^"
    var last = template.startIndex
    for found in placeholder.matches(in: template, range: whole) {
      let range = Range(found.range, in: template)!
      pattern += NSRegularExpression.escapedPattern(for: String(template[last..<range.lowerBound]))
      pattern += "(.+?)"
      last = range.upperBound
    }
    pattern += NSRegularExpression.escapedPattern(for: String(template[last...])) + "$"
    guard let expression = try? NSRegularExpression(pattern: pattern),
      let result = expression.firstMatch(
        in: english, range: NSRange(english.startIndex..., in: english))
    else { return nil }
    return (1..<result.numberOfRanges).compactMap {
      Range(result.range(at: $0), in: english).map { String(english[$0]) }
    }
  }"""


def render(target):
    return render_kotlin() if target == KOTLIN_TARGET else render_swift()


if __name__ == "__main__":
    found = problems()
    if found:
        raise SystemExit("\n".join(found))
    if "--check" in sys.argv:
        for target in GENERATED:
            if target.read_text(encoding="utf-8") != render(target):
                raise SystemExit(f"{target.name} is stale; run scripts/mobile_locales.py")
    else:
        for target in GENERATED:
            target.write_text(render(target), encoding="utf-8")
