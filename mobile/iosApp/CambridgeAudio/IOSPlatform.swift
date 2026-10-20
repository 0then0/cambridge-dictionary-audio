import AVFoundation
import CambridgeCore
import Foundation
import SQLite3
import ZIPFoundation

final class IOSPlatform: NSObject, Platform {
  private let lock = NSLock()
  private var stopped = false
  func cancel() {
    lock.lock()
    stopped = true
    lock.unlock()
  }
  func reset() {
    lock.lock()
    stopped = false
    lock.unlock()
  }
  func cancelled() -> Bool {
    lock.lock()
    defer { lock.unlock() }
    return stopped
  }
  func randomId() -> String {
    UUID().uuidString.lowercased().replacingOccurrences(of: "-", with: "")
  }
  func nowSeconds() -> Int64 { Int64(Date().timeIntervalSince1970) }
  func pause(milliseconds: Int64) { Thread.sleep(forTimeInterval: Double(milliseconds) / 1000) }
  func syncFile(path: String) throws {
    let handle = try FileHandle(forWritingTo: URL(fileURLWithPath: path))
    defer { try? handle.close() }
    try handle.synchronize()
  }
  func fail(_ code: String, _ details: String = "") -> NSError {
    NSError(
      domain: "CambridgeAudio.\(code)", code: 1, userInfo: [NSLocalizedDescriptionKey: details])
  }
  func fetch(url: String, maxBytes: Int64) throws -> HttpResult {
    // Delegate bounds the body while streaming, rather than after URLSession
    // has already buffered an unbounded response. No main-thread semaphore.
    let transfer = BoundedDownload(
      limit: maxBytes, cancelled: { [weak self] in self?.cancelled() ?? true })
    let result = try transfer.get(URL(string: url)!)
    return HttpResult(
      status: Int32(result.0.statusCode), url: result.0.url?.absoluteString ?? url,
      body: result.1.kotlinBytes(),
      retryAfter: result.0.value(forHTTPHeaderField: "Retry-After") ?? "")
  }
  func archiveList(path: String) throws -> String {
    let archive = try Archive(url: URL(fileURLWithPath: path), accessMode: .read)
    let entries: [[String: Any]] = archive.map { entry in
      [
        "name": entry.path, "size": entry.uncompressedSize, "directory": entry.type == .directory,
        "symlink": entry.type == .symlink, "encrypted": false,
      ]
    }
    return try encodeJSON(entries)
  }
  func archiveRead(path: String, member: String, maxBytes: Int64) throws -> KotlinByteArray {
    let archive = try Archive(url: URL(fileURLWithPath: path), accessMode: .read)
    guard let entry = archive[member], entry.uncompressedSize <= maxBytes else {
      throw fail("archive", "Missing or oversized ZIP member")
    }
    var data = Data()
    _ = try archive.extract(entry) { chunk in
      if self.cancelled() { throw self.fail("cancelled") }
      guard data.count + chunk.count <= maxBytes else {
        throw self.fail("archive", "Oversized ZIP member")
      }
      data.append(chunk)
    }
    return data.kotlinBytes()
  }
  func archiveWrite(path: String, names: [String], files: [String]) throws {
    guard names.count == files.count else { throw fail("archive") }
    let archive = try Archive(url: URL(fileURLWithPath: path), accessMode: .create)
    for (name, source) in zip(names, files) {
      if cancelled() { throw fail("cancelled") }
      try archive.addEntry(
        with: name, fileURL: URL(fileURLWithPath: source), compressionMethod: .deflate)
    }
  }
  func sqliteQuery(path: String, sql: String, arguments: [String]) throws -> String {
    var database: OpaquePointer?
    guard
      sqlite3_open_v2(path, &database, SQLITE_OPEN_READONLY | SQLITE_OPEN_NOMUTEX, nil)
        == SQLITE_OK, let db = database
    else {
      if database != nil { sqlite3_close(database) }
      throw fail("dictionary_corrupt", "Cannot open SQLite")
    }
    defer { sqlite3_close(db) }
    var statement: OpaquePointer?
    guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK, let stmt = statement else {
      throw fail("sqlite", String(cString: sqlite3_errmsg(db)))
    }
    defer { sqlite3_finalize(stmt) }
    let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
    for (index, value) in arguments.enumerated() {
      guard sqlite3_bind_text(stmt, Int32(index + 1), value, -1, transient) == SQLITE_OK else {
        throw fail("sqlite", "Bind failed")
      }
    }
    var rows: [[Any]] = []
    while true {
      let status = sqlite3_step(stmt)
      if status == SQLITE_DONE { break }
      guard status == SQLITE_ROW else { throw fail("sqlite", String(cString: sqlite3_errmsg(db))) }
      rows.append(
        (0..<sqlite3_column_count(stmt)).map { i in
          sqlite3_column_type(stmt, i) == SQLITE_NULL
            ? NSNull() : String(cString: sqlite3_column_text(stmt, i)) as Any
        })
    }
    return try encodeJSON(rows)
  }
  func sqliteCreate(path: String, statements: [String]) throws {
    var database: OpaquePointer?
    guard sqlite3_open(path, &database) == SQLITE_OK, let db = database else {
      if database != nil { sqlite3_close(database) }
      throw fail("sqlite")
    }
    defer { sqlite3_close(db) }
    guard sqlite3_exec(db, "BEGIN IMMEDIATE", nil, nil, nil) == SQLITE_OK else {
      throw fail("sqlite")
    }
    do {
      for statement in statements {
        if cancelled() { throw fail("cancelled") }
        guard sqlite3_exec(db, statement, nil, nil, nil) == SQLITE_OK else {
          throw fail("sqlite", String(cString: sqlite3_errmsg(db)))
        }
      }
      guard sqlite3_exec(db, "COMMIT", nil, nil, nil) == SQLITE_OK else { throw fail("sqlite") }
    } catch {
      sqlite3_exec(db, "ROLLBACK", nil, nil, nil)
      throw error
    }
  }
  func validateAudio(path: String) throws {
    let file = try AVAudioFile(forReading: URL(fileURLWithPath: path))
    guard file.fileFormat.streamDescription.pointee.mFormatID == kAudioFormatMPEGLayer3 else {
      throw fail("audio", "File is not MP3")
    }
    let buffer = AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: 16384)!
    var frames: AVAudioFramePosition = 0
    while file.framePosition < file.length {
      if cancelled() { throw fail("cancelled") }
      try file.read(into: buffer)
      if buffer.frameLength == 0 { throw fail("audio", "MP3 cannot be decoded") }
      frames += AVAudioFramePosition(buffer.frameLength)
    }
    guard frames > 0 else { throw fail("audio", "MP3 contains no audio frames") }
  }

  func synthesize(segments: [String], destination: String) throws {
    let format = AVAudioFormat(
      commonFormat: .pcmFormatFloat32, sampleRate: 44100, channels: 1, interleaved: false)!
    var samples = [Float]()
    for segment in segments {
      if cancelled() { throw fail("cancelled") }
      let file = try AVAudioFile(forReading: URL(fileURLWithPath: segment))
      guard let converter = AVAudioConverter(from: file.processingFormat, to: format) else {
        throw fail("audio", "PCM converter unavailable")
      }
      var finished = false
      while !finished {
        if cancelled() { throw fail("cancelled") }
        let output = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 16384)!
        var conversionError: NSError?
        var readFailure: Error?
        let status = converter.convert(to: output, error: &conversionError) { frames, inputStatus in
          if file.framePosition >= file.length {
            inputStatus.pointee = .endOfStream
            return nil
          }
          let input = AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: frames)!
          do {
            try file.read(into: input)
            inputStatus.pointee = .haveData
            return input
          } catch {
            readFailure = error
            inputStatus.pointee = .endOfStream
            return nil
          }
        }
        if let error = readFailure { throw error }
        if let error = conversionError { throw error }
        if let pointer = output.floatChannelData?[0] {
          samples.append(
            contentsOf: UnsafeBufferPointer(start: pointer, count: Int(output.frameLength)))
        }
        guard samples.count <= 44100 * 600 else { throw fail("audio", "Phrase exceeds 10 minutes") }
        if status == .endOfStream { finished = true }
        if status == .error { throw fail("audio", "PCM conversion failed") }
      }
    }
    if cancelled() { throw fail("cancelled") }
    let status = samples.withUnsafeBufferPointer { buffer in
      destination.withCString { cda_encode_phrase(buffer.baseAddress, buffer.count, $0) }
    }
    guard status == 0 else { throw fail("audio", "LAME error \(status)") }
    if cancelled() {
      try? FileManager.default.removeItem(atPath: destination)
      throw fail("cancelled")
    }
  }
}
extension Data {
  func kotlinBytes() -> KotlinByteArray {
    let array = KotlinByteArray(size: Int32(count))
    for (index, byte) in enumerated() {
      array.set(index: Int32(index), value: Int8(bitPattern: byte))
    }
    return array
  }
}
func encodeJSON(_ value: Any) throws -> String {
  String(
    data: try JSONSerialization.data(
      withJSONObject: value, options: [.sortedKeys, .fragmentsAllowed]), encoding: .utf8)!
}
func decodeObject(_ value: String) throws -> [String: Any] {
  guard let result = try JSONSerialization.jsonObject(with: Data(value.utf8)) as? [String: Any]
  else { throw NSError(domain: "CambridgeAudio.json", code: 1) }
  return result
}

private final class BoundedDownload: NSObject, URLSessionDataDelegate {
  let limit: Int64
  let cancelled: () -> Bool
  private var data = Data()
  private var response: HTTPURLResponse?
  private var failure: Error?
  private let completed = DispatchSemaphore(value: 0)
  init(limit: Int64, cancelled: @escaping () -> Bool) {
    self.limit = limit
    self.cancelled = cancelled
  }
  func get(_ url: URL) throws -> (HTTPURLResponse, Data) {
    let config = URLSessionConfiguration.ephemeral
    config.timeoutIntervalForRequest = 15
    config.timeoutIntervalForResource = 120
    let session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
    var request = URLRequest(url: url)
    request.setValue(
      "Mozilla/5.0 CambridgeDictionaryAudio/1.0.0-dev", forHTTPHeaderField: "User-Agent")
    let task = session.dataTask(with: request)
    task.resume()
    while completed.wait(timeout: .now() + .milliseconds(100)) == .timedOut {
      if cancelled() { task.cancel() }
    }
    session.invalidateAndCancel()
    if let error = failure { throw error }
    guard let response = response else { throw URLError(.badServerResponse) }
    return (response, data)
  }
  func urlSession(
    _ session: URLSession, task: URLSessionTask,
    willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
    completionHandler: @escaping (URLRequest?) -> Void
  ) {
    guard let url = request.url, url.scheme == "https", url.user == nil,
      url.port == nil || url.port == 443,
      ["dictionary.cambridge.org", "download.wikdict.com"].contains(url.host ?? "")
    else {
      failure = URLError(.redirectToNonExistentLocation)
      completionHandler(nil)
      return
    }
    completionHandler(request)
  }
  func urlSession(
    _ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse,
    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void
  ) {
    self.response = response as? HTTPURLResponse
    if response.expectedContentLength > limit {
      failure = URLError(.dataLengthExceedsMaximum)
      completionHandler(.cancel)
    } else {
      completionHandler(.allow)
    }
  }
  func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
    if cancelled() || self.data.count + data.count > limit {
      failure = URLError(cancelled() ? .cancelled : .dataLengthExceedsMaximum)
      dataTask.cancel()
    } else {
      self.data.append(data)
    }
  }
  func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
    if failure == nil { failure = error }
    completed.signal()
  }
}
