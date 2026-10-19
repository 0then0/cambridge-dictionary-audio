import AVFoundation
import CambridgeCore
import SwiftUI

typealias Document = [String: Any]
extension Dictionary where Key == String, Value == Any {
  func text(_ key: String) -> String { self[key] as? String ?? "" }
  func flag(_ key: String) -> Bool { self[key] as? Bool ?? false }
  func documents(_ key: String) -> [Document] { self[key] as? [Document] ?? [] }
}
struct AppFailure: Identifiable {
  let id = UUID()
  let message: String
  let details: String
}
struct ShareFile: Identifiable {
  let id = UUID()
  let url: URL
}
struct SelectionState {
  let entries: [Document]
  let selected: Document?
  let translation: Document?
  let audio: [String: String]
}

final class AppModel: NSObject, ObservableObject, AVAudioPlayerDelegate {
  @Published var query = UserDefaults.standard.string(forKey: "query") ?? ""
  @Published var entries: [Document] = []
  @Published var selected: Document?
  @Published var records: [Document] = []
  @Published var translation: Document?
  @Published var selectedAudio: [String: String] = [:]
  @Published var busy = false
  @Published var playing = false
  @Published var preparingAudio = false
  @Published var dictionaryStatus = "checking"
  @Published var checkingDictionary = false
  @Published var wikdictPrompt: String?
  @Published var message = ""
  @Published var failure: AppFailure?
  @Published var preview: Document?
  @Published var shared: ShareFile?
  @Published var language: String = UserDefaults.standard.string(forKey: "language") ?? "en" {
    didSet { UserDefaults.standard.set(language, forKey: "language") }
  }
  @Published var theme: String = {
    let stored = UserDefaults.standard.string(forKey: "theme") ?? "system"
    return stored == "black" ? "dark" : stored
  }()
  {
    didSet { UserDefaults.standard.set(theme, forKey: "theme") }
  }
  @Published var pureBlack: Bool =
    UserDefaults.standard.object(forKey: "pureBlack") as? Bool
    ?? (UserDefaults.standard.string(forKey: "theme") == "black")
  {
    didSet { UserDefaults.standard.set(pureBlack, forKey: "pureBlack") }
  }
  @Published var accent: String = UserDefaults.standard.string(forKey: "accent") ?? "us" {
    didSet { UserDefaults.standard.set(accent, forKey: "accent") }
  }
  @Published var color: String = UserDefaults.standard.string(forKey: "color") ?? "blue" {
    didSet { UserDefaults.standard.set(color, forKey: "color") }
  }
  @Published var showTranslation = UserDefaults.standard.bool(forKey: "translation") {
    didSet {
      UserDefaults.standard.set(showTranslation, forKey: "translation")
      if showTranslation { translate() }
    }
  }
  @Published var offline = false
  let platform = IOSPlatform()
  let bridge = MobileJson()
  let engine: Engine
  private let worker = DispatchQueue(label: "org.cambridgeaudio.operations", qos: .userInitiated)
  private var operation = 0
  private var selection = 0
  private var editRevision = 0
  private var player: AVAudioPlayer?
  private var observers: [NSObjectProtocol] = []
  override init() {
    let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[
      0
    ].appendingPathComponent("CambridgeAudio", isDirectory: true)
    let cache = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
      .appendingPathComponent("CambridgeAudio", isDirectory: true)
    engine = Engine(
      collectionPath: support.appendingPathComponent("collection").path, cachePath: cache.path,
      platform: platform)
    super.init()
    if UserDefaults.standard.string(forKey: "theme") == "black" {
      UserDefaults.standard.set(pureBlack, forKey: "pureBlack")
      UserDefaults.standard.set(theme, forKey: "theme")
    }
    observers.append(
      NotificationCenter.default.addObserver(
        forName: AVAudioSession.interruptionNotification, object: nil, queue: .main
      ) { [weak self] _ in self?.stop() })
    observers.append(
      NotificationCenter.default.addObserver(
        forName: AVAudioSession.routeChangeNotification, object: nil, queue: .main
      ) { [weak self] note in
        if let reason = note.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt,
          reason == AVAudioSession.RouteChangeReason.oldDeviceUnavailable.rawValue
        {
          self?.stop()
        }
      })
    perform {
      try CollectionTransfer(engine: self.engine).recover()
      try self.refreshWorker()
    }
  }
  deinit { observers.forEach(NotificationCenter.default.removeObserver) }
  func t(_ en: String, _ ru: String) -> String { language == "ru" ? ru : en }
  func json(_ document: Document) throws -> String { try encodeJSON(document) }
  func cached(_ document: Document) -> Document? {
    guard let input = try? json(document),
      let result = try? decodeObject(bridge.cachedTranslationJson(metadataJson: input))
    else { return nil }
    return result
  }
  func texts(_ translation: Document?) -> [String] {
    guard let translation = translation, let input = try? json(translation),
      let data = bridge.translationTexts(resultJson: input).data(using: .utf8),
      let texts = try? JSONSerialization.jsonObject(with: data) as? [String]
    else { return [] }
    return texts
  }
  func cancel() {
    operation += 1
    platform.cancel()
    busy = false
    stop()
  }
  private func perform(showProgress: Bool = true, _ work: @escaping () throws -> Void) {
    platform.cancel()
    operation += 1
    let serial = operation
    busy = showProgress
    preparingAudio = false
    failure = nil
    if showProgress { message = "" }
    worker.async {
      // Wait for a cancelled previous operation to unwind before resetting.
      guard serial == self.operation else { return }
      self.platform.reset()
      do { try work() } catch {
        DispatchQueue.main.async {
          if serial == self.operation {
            self.preparingAudio = false
            self.report(error)
          }
        }
      }
      DispatchQueue.main.async { if serial == self.operation { self.busy = false } }
    }
  }
  func report(_ error: Error) {
    let details = String(describing: error)
    let lower = details.lowercased()
    let message: String
    if lower.contains("cancelled") { return }
    if lower.contains("blocked") {
      message = t(
        "Cambridge blocked the request. Try later.",
        "Cambridge заблокировал запрос. Повторите позже.")
    } else if lower.contains("parser") {
      message = t(
        "Dictionary markup is not recognized. See technical details.",
        "Разметка словаря не распознана. Откройте технические сведения.")
    } else if lower.contains("dictionary_missing") {
      message = t(
        "Install WikDict in Settings to translate offline.",
        "Установите WikDict в настройках для перевода без сети.")
    } else if lower.contains("dictionary_corrupt") {
      message = t("WikDict is damaged. Reinstall it.", "WikDict повреждён. Переустановите его.")
    } else if lower.contains("translation_choice") {
      message = t(
        "Choose or edit the translation before export.",
        "Выберите или отредактируйте перевод перед экспортом.")
    } else if lower.contains("accent") {
      message = t(
        "The selected accent is unavailable. Choose another explicitly.",
        "Выбранный акцент недоступен. Выберите другой явно.")
    } else if lower.contains("absent") {
      message = t(
        "No dictionary result. Check the spelling.", "Результат не найден. Проверьте написание.")
    } else if lower.contains("network") {
      message = t(
        "Network request failed. Check your connection and retry.",
        "Ошибка сети. Проверьте подключение и повторите.")
    } else if lower.contains("schema") {
      message = t(
        "Unsupported data version. Keep a backup and update the app.",
        "Неподдерживаемая версия данных. Сохраните резервную копию и обновите приложение.")
    } else {
      message = t(
        "Operation failed. Check free space and technical details, then retry.",
        "Операция не выполнена. Проверьте свободное место и технические сведения, затем повторите.")
    }
    failure = AppFailure(message: message, details: details)
  }
  private func refreshWorker() throws {
    let value = try engine.records()
    let records = try JSONSerialization.jsonObject(with: Data(value.utf8)) as! [Document]
    DispatchQueue.main.async {
      self.records = records
      if let id = self.selected?.text("variant_id"), !id.isEmpty {
        self.selected = records.first { $0.text("variant_id") == id }
      }
    }
  }
  func refresh() { perform { try self.refreshWorker() } }
  func search() {
    let input = query
    UserDefaults.standard.set(input, forKey: "query")
    selection += 1
    editRevision += 1
    let key = selection
    entries = []
    selected = nil
    translation = nil
    perform {
      let value = try self.engine.lookup(input: input)
      let results = try JSONSerialization.jsonObject(with: Data(value.utf8)) as! [Document]
      DispatchQueue.main.async {
        if self.selection == key {
          self.entries = results
          if let first = results.first { self.select(first) }
        }
      }
    }
  }
  func select(_ entry: Document) {
    cancel()
    selection += 1
    editRevision += 1
    selected = entry
    translation = nil
    selectedAudio = [:]
    for audio in entry.documents("pronunciations") where selectedAudio[audio.text("accent")] == nil
    {
      selectedAudio[audio.text("accent")] = bridge.audioId(
        accent: audio.text("accent"), url: audio.text("url"))
    }
    if showTranslation { translate() }
  }
  func open(_ record: Document) {
    cancel()
    selection += 1
    editRevision += 1
    selected = record
    entries = []
    selectedAudio = [:]
    translation = cached(record)
  }
  func captureSelection() -> SelectionState {
    SelectionState(
      entries: entries, selected: selected, translation: translation, audio: selectedAudio)
  }
  func restoreSelection(_ state: SelectionState) {
    cancel()
    selection += 1
    editRevision += 1
    entries = state.entries
    let id = state.selected?.text("variant_id") ?? ""
    selected = id.isEmpty ? state.selected : records.first { $0.text("variant_id") == id }
    selectedAudio = state.audio
    translation = !id.isEmpty ? selected.flatMap(cached) : state.translation
  }
  func translate() {
    guard var item = selected else { return }
    if item.text("variant_id").isEmpty {
      item["translation_cache"] = translation.map { [$0] } ?? []
    }
    let input = item
    let key = selection
    let revision = editRevision
    let local = offline
    perform {
      let result = try decodeObject(
        self.engine.translation(metadataJson: self.json(input), offline: local))
      guard key == self.selection, revision == self.editRevision else { return }
      if !input.text("variant_id").isEmpty {
        _ = try self.engine.persistTranslation(
          identity: input.text("variant_id"), resultJson: self.json(result))
      }
      DispatchQueue.main.async {
        if key == self.selection && revision == self.editRevision { self.translation = result }
      }
    }
  }
  func edit(_ text: String, reset: Bool) {
    guard let item = selected else { return }
    editRevision += 1
    if item.text("variant_id").isEmpty {
      translation =
        reset || text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        ? nil
        : try? decodeObject(bridge.personalTranslation(senseId: item.text("sense_id"), text: text))
      return
    }
    perform {
      let updated = try decodeObject(
        self.engine.editTranslation(identity: item.text("variant_id"), text: text, reset: reset))
      DispatchQueue.main.async {
        self.selected = updated
        self.translation = self.cached(updated)
      }
      try self.refreshWorker()
    }
  }
  func chooseTranslation(_ id: String) {
    guard let item = selected, var result = translation else { return }
    editRevision += 1
    if item.text("variant_id").isEmpty {
      result["selected_id"] = id
      translation = result
      return
    }
    let input = result
    perform {
      let updated = try decodeObject(
        self.engine.chooseTranslation(
          identity: item.text("variant_id"), resultJson: self.json(input), optionId: id))
      DispatchQueue.main.async {
        self.selected = updated
        self.translation = self.cached(updated)
      }
      try self.refreshWorker()
    }
  }
  func save(overwrite: Bool = false) {
    guard let item = selected else { return }
    let choices = selectedAudio
    let accents = accent == "both" ? ["us", "uk"] : [accent]
    let prepared = translation
    perform {
      if !item.text("variant_id").isEmpty {
        _ = try self.engine.repair(identity: item.text("variant_id"))
      } else {
        for region in accents {
          guard let audio = choices[region] else { throw self.platform.fail("accent", region) }
          _ = try self.engine.save(
            entryJson: self.json(item), audioId: audio, overwrite: overwrite,
            translationJson: prepared.map { try self.json($0) } ?? "")
        }
      }
      try self.refreshWorker()
      DispatchQueue.main.async { self.message = self.t("Saved", "Сохранено") }
    }
  }
  func play(_ region: String? = nil) {
    guard let item = selected else { return }
    let chosen = selectedAudio[region ?? (accent == "uk" ? "uk" : "us")]
    let key = selection
    stop()
    perform(showProgress: false) {
      let path: String
      if !item.text("variant_id").isEmpty {
        path = try self.engine.audioPath(identity: item.text("variant_id"))
      } else {
        guard let audio = chosen else { throw self.platform.fail("accent") }
        path = try self.engine.preview(entryJson: self.json(item), audioId: audio)
      }
      DispatchQueue.main.async {
        if key == self.selection && !self.platform.cancelled() {
          do { try self.startPlayback(path) } catch { self.report(error) }
        }
      }
    }
    preparingAudio = true
  }
  private func startPlayback(_ path: String) throws {
    stop()
    let session = AVAudioSession.sharedInstance()
    try session.setCategory(.playback, mode: .spokenAudio, options: [])
    try session.setActive(true)
    player = try AVAudioPlayer(contentsOf: URL(fileURLWithPath: path))
    player?.delegate = self
    guard player?.play() == true else { throw platform.fail("audio", "Playback failed") }
    playing = true
  }
  func stop() {
    player?.stop()
    player = nil
    playing = false
    preparingAudio = false
    try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
  }
  func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) { stop() }
  func delete() {
    guard let item = selected, !item.text("variant_id").isEmpty else { return }
    stop()
    perform {
      try self.engine.deleteRecord(identity: item.text("variant_id"))
      DispatchQueue.main.async { self.selected = nil }
      try self.refreshWorker()
    }
  }
  @Published var phrasePlans: [Document] = []
  func synthesize() {
    let input = query
    let accents = accent == "both" ? ["us", "uk"] : [accent]
    perform {
      let plans = try accents.map {
        try decodeObject(self.engine.planPhrase(input: input, accent: $0))
      }
      DispatchQueue.main.async { self.phrasePlans = plans }
    }
  }
  func applyPhrase(_ selections: [[String]]) {
    let plans = phrasePlans
    guard plans.count == selections.count else { return }
    perform {
      let saved =
        try JSONSerialization.jsonObject(with: Data(self.engine.records().utf8)) as! [Document]
      for (index, plan) in plans.enumerated() {
        let existing = saved.first {
          $0.flag("combined") && $0.text("word") == plan.text("word")
            && $0.text("accent") == plan.text("accent")
        }
        _ = try self.engine.synthesizeChosen(
          planJson: self.json(plan), selectionsJson: encodeJSON(selections[index]),
          replacingIdentity: existing?.text("variant_id") ?? "")
      }
      try self.refreshWorker()
      DispatchQueue.main.async {
        self.phrasePlans = []
        self.message = self.t("Phrase saved", "Фраза сохранена")
      }
    }
  }
  func refreshWikdictStatus(prompt: Bool = false) {
    guard !checkingDictionary && (!prompt || !busy) else { return }
    checkingDictionary = true
    worker.async {
      do {
        let status = try self.engine.wikdictStatus()
        DispatchQueue.main.async {
          self.checkingDictionary = false
          self.dictionaryStatus = status
          if prompt { self.wikdictPrompt = status }
        }
      } catch {
        DispatchQueue.main.async {
          self.checkingDictionary = false
          self.dictionaryStatus = "unavailable"
          if prompt { self.report(error) }
        }
      }
    }
  }
  func requestWikdict() { refreshWikdictStatus(prompt: true) }
  func installWikdict() {
    wikdictPrompt = nil
    perform {
      _ = try self.engine.installWikdict()
      DispatchQueue.main.async {
        self.dictionaryStatus = "ready"
        self.message = self.t("WikDict installed", "WikDict установлен")
      }
    }
  }
  func export(_ kind: String, all: Bool) {
    let id = selected?.text("variant_id") ?? ""
    perform {
      let suffix = kind == "bundle" ? "cda" : kind == "apkg" ? "apkg" : "zip"
      let file = URL(fileURLWithPath: self.engine.cachePath).appendingPathComponent(
        "cambridge-\(UUID().uuidString).\(suffix)")
      let ids = try encodeJSON(!all && !id.isEmpty ? [id] : [])
      if kind == "bundle" {
        _ = try CollectionTransfer(engine: self.engine).exportBundle(destination: file.path)
      } else if kind == "apkg" {
        _ = try AnkiExporter(engine: self.engine).exportApkg(destination: file.path, idsJson: ids)
      } else {
        _ = try AnkiExporter(engine: self.engine).exportTsv(destination: file.path, idsJson: ids)
      }
      DispatchQueue.main.async { self.shared = ShareFile(url: file) }
    }
  }
  func importFile(_ url: URL) {
    perform {
      let access = url.startAccessingSecurityScopedResource()
      defer { if access { url.stopAccessingSecurityScopedResource() } }
      let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? Int.max
      guard size <= 2 * 1024 * 1024 * 1024 else {
        throw self.platform.fail("archive", "Bundle exceeds 2 GiB")
      }
      let file = URL(fileURLWithPath: self.engine.cachePath).appendingPathComponent(
        "import-\(UUID().uuidString).cda")
      let input = try FileHandle(forReadingFrom: url)
      defer { try? input.close() }
      guard FileManager.default.createFile(atPath: file.path, contents: nil) else {
        throw self.platform.fail("storage", "Cannot create import staging file")
      }
      let output = try FileHandle(forWritingTo: file)
      defer { try? output.close() }
      do {
        var total = 0
        while let data = try input.read(upToCount: 65536), !data.isEmpty {
          if self.platform.cancelled() { throw self.platform.fail("cancelled") }
          total += data.count
          guard total <= 2 * 1024 * 1024 * 1024 else {
            throw self.platform.fail("archive", "Bundle exceeds 2 GiB")
          }
          try output.write(contentsOf: data)
        }
        try output.synchronize()
      } catch {
        try? FileManager.default.removeItem(at: file)
        throw error
      }
      let preview = try decodeObject(
        CollectionTransfer(engine: self.engine).previewImport(source: file.path))
      DispatchQueue.main.async { self.preview = preview }
    }
  }
  func applyImport(_ decisions: [String: String]) {
    guard let preview = preview else { return }
    perform {
      _ = try CollectionTransfer(engine: self.engine).applyImport(
        previewJson: self.json(preview), decisionsJson: encodeJSON(decisions))
      try self.refreshWorker()
      DispatchQueue.main.async {
        self.preview = nil
        self.message = self.t(
          "Collection imported. Previous data backed up.",
          "Коллекция импортирована. Прежние данные сохранены в резервной копии.")
      }
    }
  }
  func background() {
    cancel()
    stop()
  }
}
