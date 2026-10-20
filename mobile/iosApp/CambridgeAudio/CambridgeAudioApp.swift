import SwiftUI
import UniformTypeIdentifiers

private struct OLEDBackground: ViewModifier {
  @Environment(\.colorScheme) private var colorScheme
  let enabled: Bool
  @ViewBuilder func body(content: Content) -> some View {
    if enabled && colorScheme == .dark {
      content.scrollContentBackground(.hidden).background(Color.black)
        .toolbarBackground(Color.black, for: .navigationBar, .tabBar)
        .toolbarBackground(.visible, for: .navigationBar, .tabBar)
    } else {
      content
    }
  }
}
private struct OLEDRowBackground: ViewModifier {
  @Environment(\.colorScheme) private var colorScheme
  let enabled: Bool
  func body(content: Content) -> some View {
    content.listRowBackground(enabled && colorScheme == .dark ? Color.black : nil)
  }
}
extension View {
  fileprivate func oledBackground(_ enabled: Bool) -> some View {
    modifier(OLEDBackground(enabled: enabled))
  }
  fileprivate func oledRowBackground(_ enabled: Bool) -> some View {
    modifier(OLEDRowBackground(enabled: enabled))
  }
}

@main
struct CambridgeAudioApp: App {
  @StateObject private var model = AppModel()
  @Environment(\.scenePhase) private var scenePhase
  var body: some Scene {
    WindowGroup {
      RootView(model: model)
        .preferredColorScheme(
          model.theme == "system" ? nil : model.theme == "dark" ? .dark : .light
        )
        .tint(tint)
        .onChange(of: scenePhase) { _, phase in if phase == .background { model.background() } }
        .onOpenURL { model.importFile($0) }
    }
  }
  private var tint: Color {
    let colors: (UInt32, UInt32)
    switch model.color {
    case "green": colors = (0x386a20, 0xa0d685)
    case "purple": colors = (0x6750a4, 0xd0bcff)
    case "orange": colors = (0x8b5000, 0xffbd7a)
    case "red": colors = (0xaf3448, 0xe38494)
    default: colors = (0x215fa6, 0x9bc5fa)
    }
    return Color(
      uiColor: UIColor { traits in
        let rgb = traits.userInterfaceStyle == .dark ? colors.1 : colors.0
        return UIColor(
          red: CGFloat((rgb >> 16) & 0xff) / 255,
          green: CGFloat((rgb >> 8) & 0xff) / 255,
          blue: CGFloat(rgb & 0xff) / 255, alpha: 1)
      })
  }
}

struct RootView: View {
  @ObservedObject var model: AppModel
  @State private var tab = 0
  @State private var importFile = false
  @State private var editing = false
  @State private var draft = ""
  @State private var replace = false
  @State private var deleting = false
  @State private var allMeanings = false
  @State private var collectionDetail = false
  @State private var searchSelection: SelectionState?
  var body: some View {
    TabView(selection: $tab) {
      NavigationStack {
        List {
          Section {
            TextField(
              model.t("English word or phrase", "Английское слово или фраза"), text: $model.query
            )
            .textInputAutocapitalization(.never).autocorrectionDisabled().submitLabel(.search)
            .onSubmit(model.search)
            .accessibilityIdentifier("searchInput")
            Button(model.t("Find", "Найти"), action: model.search).disabled(
              model.query.trimmingCharacters(in: .whitespaces).isEmpty
            ).accessibilityIdentifier("findButton")
            Picker(model.t("Pronunciation", "Произношение"), selection: $model.accent) {
              Text("US").tag("us")
              Text("UK").tag("uk")
              Text(model.t("Both", "Оба")).tag("both")
            }
            Button(
              model.t(
                "Build phrase from Cambridge recordings", "Собрать фразу из записей Cambridge"),
              action: model.synthesize
            ).disabled(!model.query.trimmingCharacters(in: .whitespaces).contains(" "))
          }.oledRowBackground(model.pureBlack)
          status
          if model.entries.isEmpty && model.selected == nil && !model.busy {
            Section {
              Text(
                model.t(
                  "Find a word, choose a meaning, preview and save its recording.",
                  "Найдите слово, выберите значение, прослушайте и сохраните запись.")
              ).foregroundStyle(.secondary)
            }.oledRowBackground(model.pureBlack)
          }
          if !model.entries.isEmpty {
            Section(model.t("Meanings", "Значения")) {
              ForEach(Array(model.entries.prefix(3).enumerated()), id: \.offset) { _, entry in
                meaningRow(entry)
              }
              if model.entries.count > 3 {
                DisclosureGroup(
                  model.t(
                    "All meanings (\(model.entries.count))", "Все значения (\(model.entries.count))"
                  ),
                  isExpanded: $allMeanings
                ) {
                  ForEach(Array(model.entries.dropFirst(3).enumerated()), id: \.offset) {
                    _, entry in
                    meaningRow(entry)
                  }
                }.accessibilityIdentifier("allMeanings")
              }
            }.oledRowBackground(model.pureBlack)
          }
          if let item = model.selected { detail(item) }
        }
        .navigationTitle(model.t("Cambridge Audio", "Cambridge Audio"))
        .oledBackground(model.pureBlack)
        .onChange(of: model.entries.map { $0.text("sense_id") }) { _, _ in allMeanings = false }
        .toolbar {
          if model.busy {
            ToolbarItem(placement: .topBarTrailing) {
              Button(model.t("Cancel", "Отмена"), action: model.cancel)
            }
          }
        }
      }.tabItem { Label(model.t("Search", "Поиск"), systemImage: "magnifyingglass") }.tag(0)
      NavigationStack {
        CollectionView(model: model) { record in
          searchSelection = model.captureSelection()
          model.open(record)
          collectionDetail = true
        }
        .navigationDestination(isPresented: $collectionDetail) {
          List {
            status
            if let item = model.selected { detail(item) }
          }
          .navigationTitle(model.selected?.text("word") ?? "")
          .navigationBarTitleDisplayMode(.inline)
          .oledBackground(model.pureBlack)
          .toolbar {
            if model.busy {
              ToolbarItem(placement: .topBarTrailing) {
                Button(model.t("Cancel", "Отмена"), action: model.cancel)
              }
            }
          }
        }
      }
      .tabItem { Label(model.t("Collection", "Коллекция"), systemImage: "books.vertical") }.tag(1)
      NavigationStack {
        SettingsView(model: model, importFile: { importFile = true }, install: model.requestWikdict)
      }
      .tabItem { Label(model.t("Settings", "Настройки"), systemImage: "gear") }.tag(2)
    }
    .onChange(of: collectionDetail) { _, shown in
      if !shown { restoreSearch() }
    }
    .onChange(of: tab) { _, selected in
      if selected == 0 && collectionDetail {
        collectionDetail = false
        restoreSearch()
      }
    }
    .onChange(of: model.selected?.text("variant_id")) { _, id in
      if collectionDetail && (id == nil || id == "") {
        collectionDetail = false
        restoreSearch()
      }
    }
    .fileImporter(
      isPresented: $importFile,
      allowedContentTypes: [UTType(importedAs: "org.cambridgeaudio.collection"), .zip, .data],
      allowsMultipleSelection: false
    ) { result in
      do { if let url = try result.get().first { model.importFile(url) } } catch {
        model.report(error)
      }
    }
    .sheet(item: $model.shared) { file in NativeShareSheet(url: file.url) }
    .sheet(
      isPresented: Binding(
        get: { !model.phrasePlans.isEmpty }, set: { if !$0 { model.phrasePlans = [] } })
    ) {
      PhrasePlanView(model: model, plans: model.phrasePlans)
    }
    .sheet(
      isPresented: Binding(get: { model.preview != nil }, set: { if !$0 { model.preview = nil } })
    ) { if let preview = model.preview { ImportPreviewView(model: model, preview: preview) } }
    .sheet(isPresented: $editing) {
      NavigationStack {
        Form {
          TextEditor(text: $draft).frame(minHeight: 160).accessibilityLabel(
            model.t("Personal Russian translation", "Личный перевод на русский")
          )
          .oledRowBackground(model.pureBlack)
          Button(
            model.t("Reset personal translation", "Сбросить личный перевод"), role: .destructive
          ) {
            model.edit("", reset: true)
            editing = false
          }.oledRowBackground(model.pureBlack)
        }.oledBackground(model.pureBlack).navigationTitle(model.t("Translation", "Перевод"))
          .toolbar {
            ToolbarItem(placement: .cancellationAction) {
              Button(model.t("Cancel", "Отмена")) { editing = false }
            }
            ToolbarItem(placement: .confirmationAction) {
              Button(model.t("Save", "Сохранить")) {
                model.edit(draft, reset: false)
                editing = false
              }
            }
          }
      }
    }
    .confirmationDialog(
      model.t(
        "Replace shared recording? Your translations are kept.",
        "Заменить общую запись? Ваши переводы сохранятся."), isPresented: $replace,
      titleVisibility: .visible
    ) { Button(model.t("Replace", "Заменить"), role: .destructive) { model.save(overwrite: true) } }
    .confirmationDialog(
      model.t(
        "Delete this meaning? Other meanings keep shared audio.",
        "Удалить это значение? Общее аудио сохранится для других значений."),
      isPresented: $deleting, titleVisibility: .visible
    ) { Button(model.t("Delete", "Удалить"), role: .destructive, action: model.delete) }
    .alert(
      model.wikdictPrompt == "missing"
        ? model.t("Install WikDict", "Установить WikDict")
        : model.t("Download WikDict again", "Скачать WikDict заново"),
      isPresented: Binding(
        get: { model.wikdictPrompt != nil }, set: { if !$0 { model.wikdictPrompt = nil } })
    ) {
      Button(
        model.wikdictPrompt == "missing"
          ? model.t("Install", "Установить") : model.t("Download again", "Скачать заново"),
        action: model.installWikdict)
      Button(model.t("Cancel", "Отмена"), role: .cancel) { model.wikdictPrompt = nil }
    } message: {
      Text(
        (model.wikdictPrompt == "ready"
          ? model.t(
            "WikDict is already installed and verified. Download it again?",
            "WikDict уже установлен и проверен. Скачать его заново?"
          )
          : model.wikdictPrompt == "corrupt"
            ? model.t(
              "The installed WikDict is damaged. Download it again?",
              "Установленный WikDict повреждён. Скачать его заново?"
            )
            : model.t(
              "Install the English–Russian WikDict package?",
              "Установить англо-русский словарь WikDict?")) + "\n\n"
          + model.t(
            "2_2026-06 · 20.9 MB · CC BY-SA 4.0. WikDict by Karl Bartel; Wiktionary via DBnary. The download is verified before replacement.",
            "2_2026-06 · 20,9 МБ · CC BY-SA 4.0. WikDict: Карл Бартель; Wiktionary через DBnary. Загрузка проверяется до замены словаря."
          ))
    }
  }
  private func restoreSearch() {
    guard let saved = searchSelection else { return }
    searchSelection = nil
    model.restoreSelection(saved)
  }
  private func meaningRow(_ entry: Document) -> some View {
    Button {
      model.select(entry)
      allMeanings = false
    } label: {
      VStack(alignment: .leading, spacing: 6) {
        Text(entry.text("part_of_speech")).font(.caption).foregroundStyle(.secondary)
        Text(entry.text("definition")).foregroundStyle(.primary).lineLimit(2)
          .multilineTextAlignment(.leading)
        if model.selected?.text("sense_id") == entry.text("sense_id") {
          Label(model.t("Selected", "Выбрано"), systemImage: "checkmark").font(.caption)
        }
      }.frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
    }
    .accessibilityAddTraits(
      model.selected?.text("sense_id") == entry.text("sense_id") ? .isSelected : [])
  }
  @ViewBuilder private var status: some View {
    if model.busy {
      Section { ProgressView(model.t("Working…", "Выполнение…")) }
        .oledRowBackground(model.pureBlack)
    }
    if !model.message.isEmpty {
      Section { Text(model.message) }
        .oledRowBackground(model.pureBlack)
    }
    if let failure = model.failure {
      Section {
        Text(failure.message).foregroundStyle(.red)
        DisclosureGroup(model.t("Technical details", "Технические сведения")) {
          Text(failure.details).font(.caption).textSelection(.enabled)
          ShareLink(item: failure.details) {
            Label(
              model.t("Share details", "Поделиться сведениями"), systemImage: "square.and.arrow.up")
          }
        }
        Button(model.t("Dismiss", "Закрыть")) { model.failure = nil }
      }.oledRowBackground(model.pureBlack)
    }
  }
  @ViewBuilder private func detail(_ item: Document) -> some View {
    let saved = !item.text("variant_id").isEmpty
    Section {
      Text(item.text("word")).font(.title).accessibilityAddTraits(.isHeader)
      if !item.text("part_of_speech").isEmpty {
        Text(item.text("part_of_speech")).foregroundStyle(.secondary)
      }
      Text(item.text("definition")).textSelection(.enabled)
      if saved {
        Text("\(item.text("accent").uppercased()) · /\(item.text("ipa"))/")
        if item["media_valid"] != nil && !item.flag("media_valid") {
          Label(
            model.t(
              "Audio missing or damaged; repair required",
              "Аудио отсутствует или повреждено; требуется восстановление"),
            systemImage: "exclamationmark.triangle"
          ).foregroundStyle(.red)
        }
      } else {
        ForEach(model.accent == "both" ? ["us", "uk"] : [model.accent], id: \.self) { accent in
          let audio = item.documents("pronunciations").filter { $0.text("accent") == accent }
          if audio.isEmpty {
            Text(
              model.t("No \(accent.uppercased()) recording", "Нет записи \(accent.uppercased())")
            ).foregroundStyle(.secondary)
          } else {
            Picker(
              accent.uppercased(),
              selection: Binding(
                get: { model.selectedAudio[accent] ?? "" },
                set: {
                  model.selectedAudio[accent] = $0
                  model.stop()
                })
            ) {
              ForEach(Array(audio.enumerated()), id: \.offset) { index, pronunciation in
                Text("/\(pronunciation.text("ipa"))/ · \(index + 1)").tag(
                  model.bridge.audioId(accent: accent, url: pronunciation.text("url")))
              }
            }
          }
        }
      }
      if model.preparingAudio {
        Button(action: model.cancel) {
          HStack {
            ProgressView()
            Text(model.t("Cancel audio", "Отменить загрузку аудио"))
          }
        }.accessibilityIdentifier("preparingAudio")
      } else if model.playing {
        Button(model.t("Stop", "Остановить"), systemImage: "stop.fill", action: model.stop)
      } else if !saved && model.accent == "both" {
        Button(model.t("Play US", "Слушать US"), systemImage: "play.fill") { model.play("us") }
        Button(model.t("Play UK", "Слушать UK"), systemImage: "play.fill") { model.play("uk") }
      } else {
        Button(model.t("Play", "Слушать"), systemImage: "play.fill") { model.play() }
      }
      if saved {
        Button(model.t("Repair / download again", "Восстановить / загрузить заново")) {
          replace = true
        }
        Button(model.t("Delete meaning", "Удалить значение"), role: .destructive) {
          deleting = true
        }
      } else {
        Button(model.t("Save meaning", "Сохранить значение"), systemImage: "square.and.arrow.down")
        { model.save() }
      }
    }.oledRowBackground(model.pureBlack)
    Section {
      Toggle(model.t("Russian translation", "Русский перевод"), isOn: $model.showTranslation)
      if model.showTranslation {
        let texts = model.texts(model.translation)
        Text(
          texts.isEmpty
            ? model.t(
              "No confirmed translation for this meaning",
              "Нет подтверждённого перевода этого значения") : texts.joined(separator: "; ")
        ).textSelection(.enabled)
        if let result = model.translation {
          Text(result.text("source")).font(.caption).foregroundStyle(.secondary)
          TranslationChoices(model: model, result: result)
            .id(item.text("variant_id") + item.text("sense_id") + result.text("source"))
          if !result.text("error").isEmpty {
            DisclosureGroup(model.t("Translation details", "Сведения о переводе")) {
              Text(result.text("error")).font(.caption).textSelection(.enabled)
            }
          }
        }
        Button(model.t("Find translation", "Найти перевод"), action: model.translate)
        Button(model.t("Edit translation", "Изменить перевод")) {
          draft = model.texts(model.translation).joined(separator: "; ")
          editing = true
        }
      }
    }
    .oledRowBackground(model.pureBlack)
    if saved {
      Section(model.t("Export this meaning", "Экспорт значения")) {
        Button("Anki APKG") { model.export("apkg", all: false) }
        Button("TSV + media") { model.export("tsv", all: false) }
      }.oledRowBackground(model.pureBlack)
    }
  }
}

private struct TranslationChoices: View {
  @ObservedObject var model: AppModel
  let result: Document
  @State private var expanded = false
  private var options: [Document] { result.documents("options") }
  var body: some View {
    if !options.isEmpty {
      Text(
        model.t("Translation choices (\(options.count))", "Варианты перевода (\(options.count))")
      )
      .font(.headline)
      ForEach(Array(options.prefix(3).enumerated()), id: \.offset) { _, option in row(option) }
      if options.count > 3 {
        DisclosureGroup(
          model.t("All translations (\(options.count))", "Все переводы (\(options.count))"),
          isExpanded: $expanded
        ) {
          ForEach(Array(options.dropFirst(3).enumerated()), id: \.offset) { _, option in row(option)
          }
        }.accessibilityIdentifier("allTranslations")
      }
    }
  }
  private func row(_ option: Document) -> some View {
    Button {
      model.chooseTranslation(option.text("id"))
      expanded = false
    } label: {
      VStack(alignment: .leading, spacing: 6) {
        Text((option["texts"] as? [String] ?? []).joined(separator: "; ")).lineLimit(2)
        if !option.text("definition").isEmpty {
          Text(option.text("definition")).font(.caption).foregroundStyle(.secondary).lineLimit(2)
        }
        if result.text("selected_id") == option.text("id") {
          Label(model.t("Selected", "Выбрано"), systemImage: "checkmark").font(.caption)
        }
      }.frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
        .multilineTextAlignment(.leading)
    }
  }
}

private struct CollectionView: View {
  @ObservedObject var model: AppModel
  let select: (Document) -> Void
  @State private var filter = ""
  var body: some View {
    List {
      if model.records.isEmpty {
        ContentUnavailableView(
          model.t("No saved entries", "Нет сохранённых записей"), systemImage: "books.vertical",
          description: Text(
            model.t("Search and save a meaning first.", "Найдите и сохраните значение.")))
      }
      ForEach(
        model.records.filter {
          filter.isEmpty || $0.text("word").localizedCaseInsensitiveContains(filter)
            || $0.text("definition").localizedCaseInsensitiveContains(filter)
        }.map { CollectionRow(data: $0) }
      ) { row in
        let record = row.data
        Button {
          select(record)
        } label: {
          VStack(alignment: .leading, spacing: 6) {
            Text(record.text("word")).font(.headline)
            Text(record.text("definition")).foregroundStyle(.primary)
            Text(record.text("accent").uppercased()).font(.caption)
            if !record.flag("media_valid") {
              Label(
                model.t("Needs repair", "Требуется восстановление"),
                systemImage: "exclamationmark.triangle"
              ).font(.caption)
            }
          }.frame(minHeight: 44)
        }
        .oledRowBackground(model.pureBlack)
      }
    }.oledBackground(model.pureBlack)
      .searchable(text: $filter, prompt: model.t("Search saved entries", "Поиск в коллекции"))
      .navigationTitle(model.t("Collection", "Коллекция")).refreshable { model.refresh() }
      .toolbar {
        Button(
          model.t("Refresh", "Обновить"), systemImage: "arrow.clockwise", action: model.refresh)
      }
  }
}
private struct CollectionRow: Identifiable {
  let data: Document
  var id: String { data.text("variant_id") }
}

private struct SettingsView: View {
  @ObservedObject var model: AppModel
  let importFile: () -> Void
  let install: () -> Void
  var body: some View {
    Form {
      Section {
        Picker(model.t("Language", "Язык"), selection: $model.language) {
          Text("English").tag("en")
          Text("Русский").tag("ru")
        }
        Picker(model.t("Appearance", "Оформление"), selection: $model.theme) {
          Text(model.t("System", "Системное")).tag("system")
          Text(model.t("Light", "Светлое")).tag("light")
          Text(model.t("Dark", "Тёмное")).tag("dark")
        }
        Toggle(isOn: $model.pureBlack) {
          VStack(alignment: .leading, spacing: 4) {
            Text(model.t("Pure black (OLED)", "Чистый чёрный (OLED)"))
            Text(
              model.t(
                "Use a pure black background when the dark theme is active.",
                "Чёрный фон при активной тёмной теме, в том числе системной."
              )
            ).font(.caption).foregroundStyle(.secondary)
          }
        }.accessibilityIdentifier("pureBlack")
        Picker(model.t("Accent colour", "Цвет акцента"), selection: $model.color) {
          Text(model.t("Blue", "Синий")).tag("blue")
          Text(model.t("Green", "Зелёный")).tag("green")
          Text(model.t("Purple", "Фиолетовый")).tag("purple")
          Text(model.t("Orange", "Оранжевый")).tag("orange")
          Text(model.t("Red", "Красный")).tag("red")
        }
        Picker(
          model.t("Default pronunciation", "Произношение по умолчанию"), selection: $model.accent
        ) {
          Text("US").tag("us")
          Text("UK").tag("uk")
          Text(model.t("Both", "Оба")).tag("both")
        }
      }.oledRowBackground(model.pureBlack)
      Section("WikDict") {
        Toggle(model.t("Offline translation lookup", "Перевод без сети"), isOn: $model.offline)
        Text(
          model.checkingDictionary
            ? model.t("Checking WikDict…", "Проверка WikDict…") : dictionaryStatusText
        )
        .accessibilityIdentifier("wikdictStatus")
        Button(
          ["ready", "corrupt"].contains(model.dictionaryStatus)
            ? model.t("Download WikDict again", "Скачать WikDict заново")
            : model.dictionaryStatus == "unavailable"
              ? model.t("Check WikDict", "Проверить WikDict")
              : model.t("Install en → ru", "Установить en → ru"), action: install
        ).disabled(model.busy || model.checkingDictionary)
        Text("2_2026-06 · 20.9 MB · CC BY-SA 4.0").font(.caption)
        Link(
          "WikDict / Wiktionary / DBnary",
          destination: URL(string: "https://www.wikdict.com/page/download")!)
      }.oledRowBackground(model.pureBlack)
      Section(model.t("Collection transfer", "Перенос коллекции")) {
        Button(model.t("Back up / export bundle", "Резервная копия / экспорт")) {
          model.export("bundle", all: true)
        }
        Button(model.t("Import bundle", "Импорт коллекции"), action: importFile)
        Text(
          model.t(
            "Files transfer only. Updates preserve data. Deleting the app removes its local collection; export a backup first.",
            "Перенос через файлы. Обновления сохраняют данные. Удаление приложения удаляет локальную коллекцию; сначала экспортируйте резервную копию."
          )
        ).font(.caption)
      }.oledRowBackground(model.pureBlack)
      Section(model.t("Anki export", "Экспорт Anki")) {
        Button(model.t("Collection APKG", "Коллекция APKG")) { model.export("apkg", all: true) }
        Button(model.t("Collection TSV + media", "Коллекция TSV + аудио")) {
          model.export("tsv", all: true)
        }
      }.oledRowBackground(model.pureBlack)
      Section(model.t("About", "О приложении")) {
        Text("1.0.0 (1000002) · storage 3 · bundle 1")
        Link(
          model.t("Repository", "Репозиторий"),
          destination: URL(string: "https://github.com/0then0/cambridge-dictionary-audio")!)
        NavigationLink(model.t("Licenses and sources", "Лицензии и источники")) {
          LicensesView(model: model)
        }
      }.oledRowBackground(model.pureBlack)
    }.oledBackground(model.pureBlack)
      .navigationTitle(model.t("Settings", "Настройки"))
      .onAppear { model.refreshWikdictStatus() }
  }

  private var dictionaryStatusText: String {
    switch model.dictionaryStatus {
    case "ready":
      return model.t("WikDict: installed and verified", "WikDict: установлен и проверен")
    case "missing": return model.t("WikDict: not installed", "WikDict: не установлен")
    case "corrupt": return model.t("WikDict: damaged", "WikDict: повреждён")
    default: return model.t("WikDict: unavailable", "WikDict: недоступен")
    }
  }

}

private struct LicensesView: View {
  @ObservedObject var model: AppModel
  private let documents = ["LICENSE", "LICENSE-MIT", "NOTICE"]
  var body: some View {
    List {
      Section("Cambridge Dictionary Audio") {
        Text(
          model.t(
            "Application: Apache-2.0. Inherited code: MIT.",
            "Приложение: Apache-2.0. Унаследованный код: MIT."))
      }.oledRowBackground(model.pureBlack)
      Section(model.t("Libraries", "Библиотеки")) {
        Text("Kotlin, Okio · Apache-2.0")
        Text("Ksoup, ZIPFoundation · MIT")
        Text("LAME · LGPL-2.0-or-later")
        Text(
          model.t(
            "Source, build and relinking materials accompany releases.",
            "Исходники и материалы для сборки и перелинковки поставляются с релизами."))
        Link(
          model.t("LAME sources", "Исходники LAME"),
          destination: URL(string: "https://lame.sourceforge.io/")!)
      }.oledRowBackground(model.pureBlack)
      Section("Cambridge Dictionary") {
        Text(
          model.t(
            "Audio, IPA and definitions retain their owners’ rights.",
            "Права на аудио, транскрипции и определения принадлежат правообладателям."))
        Link(
          model.t("Terms of use", "Условия использования"),
          destination: URL(string: "https://dictionary.cambridge.org/terms-of-use")!)
      }.oledRowBackground(model.pureBlack)
      Section("WikDict / Wiktionary / DBnary") {
        Text(
          model.t(
            "WikDict by Karl Bartel · CC BY-SA 4.0. Wiki markup and duplicate translations are removed.",
            "WikDict: Карл Бартель · CC BY-SA 4.0. Вики-разметка и повторяющиеся переводы удалены.")
        )
        Link(
          model.t("CC BY-SA 4.0 license", "Лицензия CC BY-SA 4.0"),
          destination: URL(string: "https://creativecommons.org/licenses/by-sa/4.0/")!)
      }.oledRowBackground(model.pureBlack)
      Section(model.t("Full texts", "Полные тексты")) {
        ForEach(documents, id: \.self) { file in
          DisclosureGroup(
            file == "LICENSE"
              ? "Apache License 2.0"
              : file == "LICENSE-MIT"
                ? "MIT License" : model.t("Attribution (NOTICE)", "Авторство (NOTICE)")
          ) {
            ForEach(Array(paragraphs(file).enumerated()), id: \.offset) { _, paragraph in
              Text(paragraph).frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
            }
          }
        }
      }.oledRowBackground(model.pureBlack)
    }.oledBackground(model.pureBlack)
      .navigationTitle(model.t("Licenses", "Лицензии"))
      .navigationBarTitleDisplayMode(.inline)
  }
  private func paragraphs(_ file: String) -> [String] {
    guard let url = Bundle.main.url(forResource: file, withExtension: nil),
      let text = try? String(contentsOf: url, encoding: .utf8)
    else { return [] }
    return text.components(separatedBy: "\n\n").map {
      $0.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
    }.filter { !$0.isEmpty }
  }
}

private struct ImportPreviewView: View {
  @ObservedObject var model: AppModel
  let preview: Document
  @State private var decisions: [String: String] = [:]
  private var conflicts: [String] { preview["conflicts"] as? [String] ?? [] }
  var body: some View {
    NavigationStack {
      Form {
        Section {
          Text(
            model.t(
              "New: \((preview["added"] as? [String] ?? []).count), unchanged: \((preview["unchanged"] as? [String] ?? []).count), conflicts: \(conflicts.count)",
              "Новых: \((preview["added"] as? [String] ?? []).count), без изменений: \((preview["unchanged"] as? [String] ?? []).count), конфликтов: \(conflicts.count)"
            ))
        }
        ForEach(conflicts, id: \.self) { id in
          let incoming = (preview["entries"] as? [String: Document])?[id] ?? [:]
          let current = model.records.first { $0.text("variant_id") == id } ?? [:]
          Section(incoming.text("word").isEmpty ? id : incoming.text("word")) {
            Text(incoming.text("definition"))
            Text(
              model.t("Current: ", "Текущий: ")
                + model.texts(model.cached(current)).joined(separator: "; "))
            Text(
              model.t("Incoming: ", "Входящий: ")
                + model.texts(model.cached(incoming)).joined(separator: "; "))
            Picker(
              model.t("Resolve conflict", "Решение конфликта"),
              selection: Binding(get: { decisions[id] ?? "" }, set: { decisions[id] = $0 })
            ) {
              Text(model.t("Choose…", "Выберите…")).tag("")
              Text(model.t("Keep current", "Оставить текущий")).tag("existing")
              Text(model.t("Use incoming", "Принять входящий")).tag("incoming")
            }
          }
        }
        Section {
          Text(
            model.t(
              "A backup is retained before replacement. Device timestamps never decide conflicts.",
              "Перед заменой сохраняется резервная копия. Время устройства не определяет решение конфликтов."
            ))
        }
      }.oledBackground(model.pureBlack).navigationTitle(
        model.t("Import preview", "Предварительный импорт")
      ).toolbar {
        ToolbarItem(placement: .cancellationAction) {
          Button(model.t("Cancel", "Отмена")) { model.preview = nil }
        }
        ToolbarItem(placement: .confirmationAction) {
          Button(model.t("Import", "Импортировать")) { model.applyImport(decisions) }.disabled(
            !conflicts.allSatisfy { decisions[$0] != nil && decisions[$0] != "" })
        }
      }
    }
  }
}
private struct NativeShareSheet: UIViewControllerRepresentable {
  let url: URL
  func makeUIViewController(context: Context) -> UIActivityViewController {
    UIActivityViewController(activityItems: [url], applicationActivities: nil)
  }
  func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}

private struct PhrasePlanView: View {
  @ObservedObject var model: AppModel
  let plans: [Document]
  @State private var choices: [String: String] = [:]
  var body: some View {
    NavigationStack {
      Form {
        Section {
          Text(
            model.t(
              "Review the recordings in phrase order. Confirming replaces an existing synthesized phrase with the same words and accent, retaining personal translations.",
              "Проверьте записи в порядке слов. Подтверждение заменит уже собранную фразу с теми же словами и акцентом; личные переводы сохранятся."
            ))
        }
        ForEach(Array(plans.enumerated()), id: \.offset) { planIndex, plan in
          Section(plan.text("accent").uppercased()) {
            ForEach(Array(plan.documents("segments").enumerated()), id: \.offset) {
              segmentIndex, segment in
              let key = "\(planIndex):\(segmentIndex)"
              let options = segment.documents("options")
              Picker(
                segment.text("word"),
                selection: Binding(
                  get: { choices[key] ?? options.first?.text("id") ?? "" },
                  set: { choices[key] = $0 })
              ) {
                ForEach(Array(options.enumerated()), id: \.offset) { index, audio in
                  Text("/\(audio.text("ipa"))/ · \(index + 1)").tag(audio.text("id"))
                }
              }
            }
          }
        }
      }.oledBackground(model.pureBlack).navigationTitle(
        model.t("Phrase recordings", "Записи для фразы")
      )
      .toolbar {
        ToolbarItem(placement: .cancellationAction) {
          Button(model.t("Cancel", "Отмена")) { model.phrasePlans = [] }
        }
        ToolbarItem(placement: .confirmationAction) {
          Button(model.t("Build and save", "Собрать и сохранить")) {
            let selected = plans.enumerated().map { planIndex, plan in
              plan.documents("segments").enumerated().map { segmentIndex, segment in
                choices["\(planIndex):\(segmentIndex)"] ?? segment.documents("options").first?
                  .text("id") ?? ""
              }
            }
            model.applyPhrase(selected)
          }
        }
      }
    }
  }
}
