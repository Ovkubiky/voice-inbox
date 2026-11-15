import AppKit
import Foundation

struct InboxItem: Codable, Identifiable {
    let id: Int?
    let type: String
    let title: String
    let start: String?
    let people: [String]
    let project: String?
    let question: String?
    let is_incomplete: Bool
    let duplicate_of: Int?

    var icon: String {
        ["task": "checkmark.circle", "event": "calendar", "note": "note.text", "idea": "lightbulb"][type] ?? "circle"
    }
}

struct NoteResponse: Codable {
    let clean_text: String
    let items: [InboxItem]
    let timings: [String: Double]
}

@MainActor
final class InboxModel: ObservableObject {
    static let baseURL = URL(string: "http://127.0.0.1:8777")!

    @Published var isRecording = false
    @Published var isBusy = false
    @Published var transcript = ""
    @Published var items: [InboxItem] = []
    @Published var error: String?
    @Published var answers: [Int: String] = [:]
    @Published var serverUp = false

    private let recorder = Recorder()
    private var hotKey: HotKey?

    init() {
        // ⌃⌥Space anywhere: start / stop a voice note without opening the popover.
        hotKey = HotKey { [weak self] in
            Task { @MainActor in await self?.toggleRecording() }
        }
    }

    private func sound(_ name: String) { NSSound(named: NSSound.Name(name))?.play() }

    func checkServer() async {
        let url = Self.baseURL.appendingPathComponent("health")
        serverUp = (try? await URLSession.shared.data(from: url)) != nil
    }

    func toggleRecording() async {
        error = nil
        if isRecording {
            isRecording = false
            sound("Pop")
            guard let url = recorder.stop() else { return }
            await upload(url)
        } else {
            guard await recorder.requestPermission() else {
                error = "No microphone access (System Settings → Privacy → Microphone)"
                return
            }
            do {
                try recorder.start()
                isRecording = true
                sound("Tink")
            } catch {
                self.error = error.localizedDescription
            }
        }
    }

    private func upload(_ fileURL: URL) async {
        isBusy = true
        defer { isBusy = false }
        var request = URLRequest(url: Self.baseURL.appendingPathComponent("notes"))
        request.httpMethod = "POST"
        request.timeoutInterval = 300
        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        guard let audio = try? Data(contentsOf: fileURL) else { return }
        var body = Data()
        body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"note.wav\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: audio/wav\r\n\r\n".data(using: .utf8)!)
        body.append(audio)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        do {
            let (data, resp) = try await URLSession.shared.upload(for: request, from: body)
            guard (resp as? HTTPURLResponse)?.statusCode == 200 else {
                error = "Server error: \(String(data: data, encoding: .utf8) ?? "")"
                return
            }
            let note = try JSONDecoder().decode(NoteResponse.self, from: data)
            transcript = note.clean_text
            items = note.items
            sound("Glass")
        } catch {
            self.error = "Server is offline. Run: uv run inbox-server"
        }
        try? FileManager.default.removeItem(at: fileURL)
    }

    func answer(_ item: InboxItem) async {
        guard let id = item.id, let text = answers[id], !text.isEmpty else { return }
        var request = URLRequest(url: Self.baseURL.appendingPathComponent("items/\(id)/answer"))
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        let encoded = text.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? ""
        request.httpBody = "answer=\(encoded)".data(using: .utf8)
        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            let updated = try JSONDecoder().decode(InboxItem.self, from: data)
            items = items.map { $0.id == id ? updated : $0 }
            answers[id] = nil
        } catch {
            self.error = "Couldn't save the answer"
        }
    }

    func openICS(_ item: InboxItem) {
        guard let id = item.id else { return }
        NSWorkspace.shared.open(Self.baseURL.appendingPathComponent("items/\(id).ics"))
    }

    func openDashboard() {
        NSWorkspace.shared.open(Self.baseURL)
    }
}
