import SwiftUI

@main
struct VoiceInboxApp: App {
    @StateObject private var model = InboxModel()

    var body: some Scene {
        MenuBarExtra {
            ContentView()
                .environmentObject(model)
                .frame(width: 380)
        } label: {
            Image(systemName: model.isRecording ? "record.circle.fill" : (model.isBusy ? "hourglass" : "waveform"))
        }
        .menuBarExtraStyle(.window)
    }
}
