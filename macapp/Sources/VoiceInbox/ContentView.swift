import SwiftUI

extension Color {
    static let amber1 = Color(red: 0.99, green: 0.88, blue: 0.28)   // #fde047
    static let amber2 = Color(red: 0.98, green: 0.75, blue: 0.14)   // #fbbf24
    static let amber3 = Color(red: 0.96, green: 0.62, blue: 0.04)   // #f59e0b
    static let cream = Color(red: 0.969, green: 0.969, blue: 0.961) // #f7f7f5 page
    static let panel = Color(red: 0.937, green: 0.937, blue: 0.925) // #efefec
    static let sun = Color(red: 1.0, green: 0.882, blue: 0.302)     // #ffe14d
    static let grey = Color(red: 0.54, green: 0.54, blue: 0.52)
    static let ink = Color(red: 0.11, green: 0.10, blue: 0.09)
    static let brown = Color(red: 0.47, green: 0.21, blue: 0.06)
}

let amberGradient = LinearGradient(colors: [.amber1, .amber2, .amber3], startPoint: .topLeading, endPoint: .bottomTrailing)

/// Yellow starburst sticker, same as the web page's record button.
struct Starburst: Shape {
    var points = 16
    func path(in rect: CGRect) -> Path {
        let c = CGPoint(x: rect.midX, y: rect.midY), outer = min(rect.width, rect.height) / 2, inner = outer * 0.8
        var p = Path()
        for i in 0..<(points * 2) {
            let r = i.isMultiple(of: 2) ? outer : inner, a = Double(i) * .pi / Double(points)
            let pt = CGPoint(x: c.x + r * sin(a), y: c.y - r * cos(a))
            i == 0 ? p.move(to: pt) : p.addLine(to: pt)
        }
        p.closeSubpath()
        return p
    }
}

extension Font {
    static func serifItalic(_ size: CGFloat) -> Font { .system(size: size, design: .serif).italic() }
}

struct ContentView: View {
    @EnvironmentObject var model: InboxModel

    var body: some View {
        VStack(spacing: 0) {
            header
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    if let error = model.error {
                        Label(error, systemImage: "exclamationmark.triangle.fill")
                            .font(.caption).foregroundStyle(.red)
                    }
                    if !model.transcript.isEmpty {
                        Text("“\(model.transcript)”")
                            .font(.serifItalic(14)).foregroundStyle(Color.grey).textSelection(.enabled)
                    }
                    ForEach(Array(model.items.enumerated()), id: \.offset) { _, item in
                        ItemCard(item: item)
                    }
                    if model.items.isEmpty && !model.isBusy && model.transcript.isEmpty {
                        Text("Your items will appear here.")
                            .font(.serifItalic(15)).foregroundStyle(Color.grey)
                            .frame(maxWidth: .infinity).padding(.vertical, 12)
                    }
                }
                .padding(14)
            }
            .frame(maxHeight: 360)
            footer
        }
        .background(Color.cream)
        .task { await model.checkServer() }
    }

    private var header: some View {
        HStack(alignment: .center, spacing: 16) {
            Button {
                Task { await model.toggleRecording() }
            } label: {
                ZStack {
                    Starburst().fill(model.isRecording ? Color(red: 1, green: 0.82, blue: 0.12) : Color.sun)
                        .frame(width: 92, height: 92)
                        .rotationEffect(.degrees(model.isRecording ? 10 : 0))
                        .animation(model.isRecording ? .easeInOut(duration: 0.8).repeatForever(autoreverses: true) : .default,
                                   value: model.isRecording)
                    if model.isBusy {
                        ProgressView().controlSize(.small)
                    } else {
                        Text(model.isRecording ? "Stop" : "Speak\nnow →")
                            .font(.serifItalic(17)).multilineTextAlignment(.center)
                            .foregroundStyle(Color.ink).rotationEffect(.degrees(-9))
                    }
                }
            }
            .buttonStyle(.plain)
            .disabled(model.isBusy)
            .keyboardShortcut("r")

            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("Voice Inbox").font(.serifItalic(24)).foregroundStyle(Color.ink)
                    Spacer()
                    Circle().fill(model.serverUp ? Color.green : Color.red).frame(width: 6, height: 6)
                        .help(model.serverUp ? "Server is running" : "Start the server: uv run inbox-server")
                }
                Text(model.isRecording ? "Listening. Talk like you would to a friend."
                     : model.isBusy ? "Reading your note…"
                     : "Say it out loud. Tasks, events and ideas sort themselves out.")
                    .font(.system(size: 12)).foregroundStyle(Color.grey).fixedSize(horizontal: false, vertical: true)
                Text("⌃⌥Space from any app").font(.system(size: 10, design: .monospaced)).foregroundStyle(Color.grey)
            }
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.panel)
    }

    private var footer: some View {
        HStack {
            Button { model.openDashboard() } label: {
                Label("Open board", systemImage: "square.grid.3x2")
            }
            .buttonStyle(.plain).font(.serifItalic(15)).foregroundStyle(Color.ink)
            Spacer()
            Button("Quit") { NSApplication.shared.terminate(nil) }
                .buttonStyle(.plain).font(.callout).foregroundStyle(.secondary)
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .background(Color.cream)
        .overlay(Rectangle().frame(height: 1).foregroundStyle(Color.black.opacity(0.06)), alignment: .top)
    }
}

struct ItemCard: View {
    @EnvironmentObject var model: InboxModel
    let item: InboxItem

    private var typeColor: Color {
        ["task": .amber3, "event": .orange, "idea": Color(red: 0.79, green: 0.54, blue: 0.02), "note": .gray][item.type] ?? .gray
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .top) {
                Text(item.type + (item.project.map { " · \($0)" } ?? ""))
                    .font(.serifItalic(13)).foregroundStyle(Color.grey)
                Spacer()
                if item.start != nil {
                    Button { model.openICS(item) } label: { Image(systemName: "calendar.badge.plus") }
                        .buttonStyle(.borderless).help("Add to calendar")
                }
            }
            Text(item.title).font(.system(size: 14, weight: .semibold)).foregroundStyle(Color.ink)
            HStack(spacing: 8) {
                if let start = item.start { Label(start.replacingOccurrences(of: "T", with: " "), systemImage: "clock") }
                if !item.people.isEmpty { Label(item.people.joined(separator: ", "), systemImage: "person") }
            }
            .font(.caption).foregroundStyle(.secondary)
            if item.duplicate_of != nil {
                Text("Looks like an item you already have").font(.caption).foregroundStyle(.orange)
            }
            if let question = item.question, let id = item.id {
                VStack(alignment: .leading, spacing: 6) {
                    Text("— " + question).font(.serifItalic(14)).foregroundStyle(Color.ink)
                    HStack {
                        TextField("Answer…", text: Binding(
                            get: { model.answers[id] ?? "" },
                            set: { model.answers[id] = $0 }))
                            .textFieldStyle(.roundedBorder)
                            .onSubmit { Task { await model.answer(item) } }
                        Button("OK") { Task { await model.answer(item) } }
                    }
                }
                .padding(8)
                .background(RoundedRectangle(cornerRadius: 10).fill(Color.sun.opacity(0.35)))
            }
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 14).fill(.white).shadow(color: .black.opacity(0.06), radius: 4, y: 2))
    }
}
