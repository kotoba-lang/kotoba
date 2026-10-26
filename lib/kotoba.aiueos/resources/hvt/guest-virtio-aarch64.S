// aiueos.hvt V1 virtio-mmio transport-handshake test guest (aarch64).
//
// Probes and negotiates the virtio-console device the tender emulates at the
// virtio-mmio window 0x0a000000, then -- only if the whole handshake succeeds
// -- writes "HI\n" to the plain serial MMIO port 0x09000000 and halts via the
// poweroff port 0x09000008. On any check failure it writes 'E' instead, so a
// receipt serial of exactly "HI\n" proves the full transport handshake ran:
// magic/version/device-id probe, feature offer+accept, and the
// ACKNOWLEDGE -> DRIVER -> FEATURES_OK -> DRIVER_OK status sequence.
//
// The virtqueue data path (rings/descriptors) is the next milestone; this
// guest programs no queue, it only drives the transport registers.
.text
.global _start
_start:
    movz    x2, #0x0a00, lsl #16      // x2 = 0x0a000000 (virtio-mmio base)
    movz    x1, #0x0900, lsl #16      // x1 = 0x09000000 (serial base)

    // --- device identity probe ---
    ldr     w3, [x2, #0x000]          // MagicValue
    movz    w4, #0x6976
    movk    w4, #0x7472, lsl #16      // w4 = 0x74726976 ("virt")
    cmp     w3, w4
    b.ne    fail
    ldr     w3, [x2, #0x004]          // Version
    cmp     w3, #2
    b.ne    fail
    ldr     w3, [x2, #0x008]          // DeviceID
    cmp     w3, #3                    // 3 = console
    b.ne    fail

    // --- status handshake: reset -> ACKNOWLEDGE -> DRIVER ---
    str     wzr, [x2, #0x070]         // Status = 0
    mov     w3, #1
    str     w3, [x2, #0x070]          // ACKNOWLEDGE
    mov     w3, #3
    str     w3, [x2, #0x070]          // ACKNOWLEDGE | DRIVER

    // --- feature negotiation: read offered, accept all ---
    str     wzr, [x2, #0x014]         // DeviceFeaturesSel = 0
    ldr     w3, [x2, #0x010]          // DeviceFeatures (low)
    str     wzr, [x2, #0x024]         // DriverFeaturesSel = 0
    str     w3, [x2, #0x020]          // DriverFeatures (low)
    mov     w4, #1
    str     w4, [x2, #0x014]          // DeviceFeaturesSel = 1
    ldr     w3, [x2, #0x010]          // DeviceFeatures (high)
    mov     w4, #1
    str     w4, [x2, #0x024]          // DriverFeaturesSel = 1
    str     w3, [x2, #0x020]          // DriverFeatures (high)

    // --- FEATURES_OK, then verify the device left it set ---
    mov     w3, #0xb                  // ACKNOWLEDGE | DRIVER | FEATURES_OK
    str     w3, [x2, #0x070]
    ldr     w3, [x2, #0x070]          // read Status back
    tst     w3, #0x8                  // FEATURES_OK still set?
    b.eq    fail
    // --- DRIVER_OK ---
    mov     w3, #0xf                  // ACKNOWLEDGE | DRIVER | FEATURES_OK | DRIVER_OK
    str     w3, [x2, #0x070]

    // --- success: emit "HI\n" via the serial port ---
    mov     w0, #0x48
    strb    w0, [x1]                  // 'H'
    mov     w0, #0x49
    strb    w0, [x1]                  // 'I'
    mov     w0, #0x0a
    strb    w0, [x1]                  // '\n'
    b       off
fail:
    mov     w0, #0x45
    strb    w0, [x1]                  // 'E' (handshake failed)
off:
    mov     w0, #1
    strb    w0, [x1, #8]              // 0x09000008 poweroff -> VMM halts
1:  b       1b
