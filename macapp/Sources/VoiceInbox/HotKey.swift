import Carbon.HIToolbox

/// System-wide hotkey (works in any app) via Carbon RegisterEventHotKey. No accessibility permission needed.
final class HotKey {
    private var ref: EventHotKeyRef?
    private static var handlers: [UInt32: () -> Void] = [:]
    private static var installed = false

    /// Default: ⌃⌥Space.
    init(keyCode: UInt32 = UInt32(kVK_Space), modifiers: UInt32 = UInt32(controlKey | optionKey), id: UInt32 = 1,
         handler: @escaping () -> Void) {
        HotKey.handlers[id] = handler
        HotKey.installHandlerOnce()
        let hotKeyID = EventHotKeyID(signature: OSType(0x5649_4E42), id: id)  // 'VINB'
        RegisterEventHotKey(keyCode, modifiers, hotKeyID, GetApplicationEventTarget(), 0, &ref)
    }

    deinit {
        if let ref { UnregisterEventHotKey(ref) }
    }

    private static func installHandlerOnce() {
        guard !installed else { return }
        installed = true
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, event, _ in
            var hkID = EventHotKeyID()
            GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID),
                              nil, MemoryLayout<EventHotKeyID>.size, nil, &hkID)
            DispatchQueue.main.async { HotKey.handlers[hkID.id]?() }
            return noErr
        }, 1, &spec, nil, nil)
    }
}
