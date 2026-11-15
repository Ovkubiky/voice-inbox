import AVFoundation

/// Records 16 kHz mono WAV to a temp file.
final class Recorder {
    private var recorder: AVAudioRecorder?
    private(set) var url: URL?

    func requestPermission() async -> Bool {
        await AVCaptureDevice.requestAccess(for: .audio)
    }

    func start() throws {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("voice-inbox-\(UUID().uuidString).wav")
        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: 16_000,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
        ]
        let rec = try AVAudioRecorder(url: url, settings: settings)
        guard rec.record() else { throw NSError(domain: "VoiceInbox", code: 1,
                                                 userInfo: [NSLocalizedDescriptionKey: "Couldn't start recording"]) }
        recorder = rec
        self.url = url
    }

    func stop() -> URL? {
        recorder?.stop()
        recorder = nil
        return url
    }
}
