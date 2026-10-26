// aiueos.hvt V1 ELF-loader test guest (aarch64).
// Writes "HI\n" to the MMIO serial port 0x09000000 (each strb traps out as
// KVM_EXIT_MMIO), then writes the poweroff MMIO port 0x09000008 (VMM halt),
// then parks. Same behavior as guest-program-words, but delivered as a real
// ELF so the tender's ELF64 loader is exercised end-to-end.
.text
.global _start
_start:
    movz    x1, #0x0900, lsl #16     // x1 = 0x09000000 (MMIO serial base)
    movz    w0, #0x48
    strb    w0, [x1]                 // 'H'
    movz    w0, #0x49
    strb    w0, [x1]                 // 'I'
    movz    w0, #0x0a
    strb    w0, [x1]                 // '\n'
    movz    w0, #0x01
    strb    w0, [x1, #8]             // 0x09000008 poweroff -> VMM halts
1:  b       1b                       // park
