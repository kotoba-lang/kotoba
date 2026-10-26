# Native user entry v3: implemented mechanism and remaining qualification

Status: local native mechanism proofs pass. The v2 queue/typed gate and v3
CPL3/SYSCALL have separate positive/refusal receipts; public x86/controller
adoption of the final compiler is still required before merge qualification.

The implemented version owns its page tables instead of trusting canonical
addresses or inherited firmware user bits. Its private RW size is
0x240000 bytes; the kernel stack remains context+0x10000..0x20000. Four
domain windows at context+0x20000, stride0x4000, contain code, request,
an unmapped guard and stack, in that order. Only the current domain receives user
permissions. Kernel text is RX; private state/stack is supervisor RW/NX;
user code is RO/X and user request/stack are RW/NX. CR0.WP is enabled.

Tables are PML4 at0x30000, PDPT at0x31000 and512 PD pages at
0x32000..0x232000. They identity-map the low512GiB with supervisor/NX huge
pages. Four small-page tables at0x232000..0x236000 refine low8MiB for image
text and domain permissions. A private IDT and descriptor follow them;
the final chosen image size must cover those structures without overlap.
LA57, missing NX/SYSCALL support or unsupported mappings must refuse.

The native SYSCALL handler must save user RSP/RIP/RFLAGS/request/number/RBP
through RIP-relative stores before using user R9, then switch to the fixed
kernel stack and reload private context. Only syscall5 is public. Validate
the return RIP against the current code page, RSP against its stack page,
and the complete104-byte envelope against its request page before calling
the existing typed entry. An invalid request with valid return state may
return0; invalid return state must stop without SYSRET. Return flags must
exclude IOPL/NT/RF/VM/AC/TF/DF, and private scratch registers are cleared.

STAR uses kernelCS8 and user base0x10 (SYSRET CS0x23/SS0x1b); LSTAR names
native-produced code. A private fault entry records actual CR2/error/CPL
for controlled forbidden-read, NX and guard-page probes. No C/reference
kernel, foreign object or hosted packager may supply this mechanism.

The positive QEMU proof must reach CPL3, execute the actual SYSCALL/entry,
return the expected value at the declared user loop and keep kernel state
private. Negative probes must distinguish wrong request, forged R9,
forbidden supervisor access, NX and guard faults. Full kernel scheduling,
canonical value/token binding and physical hardware remain separate gates.

The native media gate now emits/reproduces an8MiB GPT/FAT16 diagnostic ESP.
Independent GPT/FAT/CRC/EFI readback and11 negative controls pass. Raw-media
boot and desktop/input are measured on QEMU q35 SATA with a temporary
overlay; virtio block boot is not qualified. General release/installer and
physical-hardware compatibility still require their own evidence.
