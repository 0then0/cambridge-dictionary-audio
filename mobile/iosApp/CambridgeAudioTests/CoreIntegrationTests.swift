import AVFoundation
import CambridgeCore
import XCTest

@testable import CambridgeAudio

final class CoreIntegrationTests: XCTestCase {
  func testPersistentLegacyCollectionAndFileTransfer() throws {
    let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
    defer { try? FileManager.default.removeItem(at: folder) }
    let collection = folder.appendingPathComponent("collection")
    try FileManager.default.createDirectory(at: collection, withIntermediateDirectories: true)
    let audio = collection.appendingPathComponent("hello.us.mp3")
    try Data("ID3test fixture".utf8).write(to: audio)
    let platform = IOSPlatform()
    let engine = Engine(
      collectionPath: collection.path, cachePath: folder.appendingPathComponent("cache").path,
      platform: platform)
    let rows = try JSONSerialization.jsonObject(with: Data(engine.records().utf8)) as! [Document]
    XCTAssertEqual(rows.count, 1)
    let id = rows[0].text("variant_id")
    _ = try engine.editTranslation(identity: id, text: "привет", reset: false)
    let bundle = folder.appendingPathComponent("backup.cda")
    _ = try CollectionTransfer(engine: engine).exportBundle(destination: bundle.path)
    let second = Engine(
      collectionPath: folder.appendingPathComponent("second").path,
      cachePath: folder.appendingPathComponent("second-cache").path, platform: platform)
    let transfer = CollectionTransfer(engine: second)
    let preview = try transfer.previewImport(source: bundle.path)
    _ = try transfer.applyImport(previewJson: preview, decisionsJson: "{}")
    let imported =
      try JSONSerialization.jsonObject(with: Data(second.records().utf8)) as! [Document]
    XCTAssertEqual(imported[0].text("variant_id"), id)
    let exporter = AnkiExporter(engine: second)
    let apkg = folder.appendingPathComponent("ios.apkg")
    _ = try exporter.exportApkg(destination: apkg.path, idsJson: "[]")
    XCTAssertTrue(FileManager.default.fileExists(atPath: apkg.path))
    let fresh = Engine(
      collectionPath: folder.appendingPathComponent("second").path,
      cachePath: folder.appendingPathComponent("second-cache").path, platform: platform)
    XCTAssertEqual(try fresh.audioPath(identity: id), try second.audioPath(identity: id))
  }
  func testNativePhraseAndAndroidCollectionHandoff() throws {
    let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
    try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: folder) }
    let fixtures = try XCTUnwrap(Bundle(for: Self.self).resourceURL).appendingPathComponent(
      "Fixtures")
    let platform = IOSPlatform()
    let phrase = folder.appendingPathComponent("phrase.mp3")
    try platform.synthesize(
      segments: ["segment-a.mp3", "segment-b.mp3"].map {
        fixtures.appendingPathComponent($0).path
      }, destination: phrase.path)
    XCTAssertTrue(try platform.validateAudio(path: phrase.path))
    let decoded = try AVAudioFile(forReading: phrase)
    XCTAssertEqual(Double(decoded.length) / decoded.processingFormat.sampleRate, 1, accuracy: 0.1)
    let engine = Engine(
      collectionPath: folder.appendingPathComponent("collection").path,
      cachePath: folder.appendingPathComponent("cache").path, platform: platform)
    let transfer = CollectionTransfer(engine: engine)
    _ = try transfer.applyImport(
      previewJson: transfer.previewImport(
        source: fixtures.appendingPathComponent("android.cda").path), decisionsJson: "{}")
    let rows = try JSONSerialization.jsonObject(with: Data(engine.records().utf8)) as! [Document]
    XCTAssertEqual(rows.count, 3)
    let ids = Set(rows.map { $0.text("variant_id") })
    let id = try XCTUnwrap(rows.first { $0.text("word") == "bay" }).text("variant_id")
    _ = try engine.editTranslation(identity: id, text: "iOS personal translation", reset: false)
    let apkg = folder.appendingPathComponent("ios.apkg")
    _ = try AnkiExporter(engine: engine).exportApkg(destination: apkg.path, idsJson: "[]")
    let bundle = folder.appendingPathComponent("ios.cda")
    _ = try transfer.exportBundle(destination: bundle.path)
    let reopened = Engine(
      collectionPath: engine.collectionPath, cachePath: engine.cachePath, platform: platform)
    let restored =
      try JSONSerialization.jsonObject(with: Data(reopened.records().utf8)) as! [Document]
    XCTAssertEqual(ids, Set(restored.map { $0.text("variant_id") }))
    XCTAssertEqual(try platform.archiveList(path: apkg.path).contains("collection.anki2"), true)
    if let output = ProcessInfo.processInfo.environment["CDA_IOS_ACCEPTANCE_OUTPUT"] {
      try FileManager.default.createDirectory(atPath: output, withIntermediateDirectories: true)
      for file in [apkg, bundle] {
        try FileManager.default.copyItem(
          at: file, to: URL(fileURLWithPath: output).appendingPathComponent(file.lastPathComponent))
      }
    }
  }
  func testGuidContract() {
    let bridge = MobileJson()
    XCTAssertFalse(
      bridge.audioId(accent: "us", url: "https://dictionary.cambridge.org/media/hello.mp3").isEmpty)
  }

  func testImportReplacementAndMissingMediaRestoreKeepPermanentIdentity() throws {
    let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
    defer { try? FileManager.default.removeItem(at: folder) }
    let root = folder.appendingPathComponent("collection")
    try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    let fixture = try XCTUnwrap(Bundle(for: Self.self).resourceURL)
      .appendingPathComponent("Fixtures/segment-a.mp3")
    let original = root.appendingPathComponent("hello.us.mp3")
    try FileManager.default.copyItem(at: fixture, to: original)
    let engine = Engine(
      collectionPath: root.path,
      cachePath: folder.appendingPathComponent("cache").path, platform: IOSPlatform())
    let rows = try JSONSerialization.jsonObject(with: Data(engine.records().utf8)) as! [Document]
    let id = try XCTUnwrap(rows.first).text("variant_id")
    _ = try engine.editTranslation(identity: id, text: "backup translation", reset: false)
    let archive = folder.appendingPathComponent("backup.cda")
    let transfer = CollectionTransfer(engine: engine)
    _ = try transfer.exportBundle(destination: archive.path)
    _ = try engine.editTranslation(identity: id, text: "local edit", reset: false)
    let decisions = try encodeJSON([id: "incoming"])
    _ = try transfer.applyImport(
      previewJson: transfer.previewImport(source: archive.path),
      decisionsJson: decisions)
    XCTAssertFalse(FileManager.default.fileExists(atPath: original.path))
    for missing in [true, false] {
      let audio = URL(fileURLWithPath: try engine.audioPath(identity: id))
      if missing {
        try FileManager.default.removeItem(at: audio)
      } else {
        try Data("corrupt".utf8).write(to: audio)
      }
      _ = try transfer.applyImport(
        previewJson: transfer.previewImport(source: archive.path),
        decisionsJson: decisions)
      let restored =
        try JSONSerialization.jsonObject(with: Data(engine.records().utf8)) as! [Document]
      XCTAssertEqual(restored.count, 1)
      XCTAssertEqual(restored.first?.text("variant_id"), id)
      XCTAssertTrue(try IOSPlatform().validateAudio(path: engine.audioPath(identity: id)))
      XCTAssertTrue(
        MobileJson().cachedTranslationJson(metadataJson: try encodeJSON(restored[0]))
          .contains("backup translation"))
    }
  }
}
