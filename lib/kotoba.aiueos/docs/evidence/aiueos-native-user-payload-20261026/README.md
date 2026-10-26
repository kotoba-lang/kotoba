# Native user ELF boot-slot diagnostic

The Kotoba kernel entry reads a bounded 512 KiB boot region, checks its
header and the pinned SHA-256 of one 8,280-byte ELF, checks the expected
entry and two segment addresses, copies the two segments into sealed user
pages, and enters CPL3. This is a deliberately fixed diagnostic image, not
a general ELF loader or signed application installer.

The [Mac native build receipt](build-state.json) binds the 27-module AIUEOS
kernel source graph, Amu compiler, slot, reproducible kernel ELF and EFI.
The [private QMP receipt](qmp.json) records three fresh QEMU boots. The first
reaches CPL3 at `0x220015`, returns `42`, and has code bytes identical to the
selfhost-produced ELF. The second changes one code byte in the EFI-embedded
slot: the guest remains in its kernel refusal loop at CPL0 and leaves the
result zero. The third changes the slot header magic and is likewise refused
at CPL0 with result zero. QEMU has no network, display listener or VNC
password, and the observer needs no person to press keys.

With a new scratch output directory under `github/workspaces`, repeat the
VM check using the matching build, ELF and slot:

```sh
python3 os/aiueos/scripts/check-native-user-payload-qemu.py \
  --kernel "$BUILD/KERNEL.ELF" --efi "$BUILD/BOOTX64.EFI" \
  --elf "$AMU_BUILD/scalar.elf" --slot "$AMU_BUILD/scalar-slot.bin" \
  --source os/aiueos/native/user-elf-payload-entry.kotoba \
  --qemu /opt/homebrew/bin/qemu-system-x86_64 \
  --firmware /opt/homebrew/share/qemu/edk2-x86_64-code.fd \
  --output "$NEW_PRIVATE_OBSERVATION"
```

The exact Mac compiler image for this build is SHA-256
`012bfb77a364b3b68cb5e2c406ae49535784fa2b851dfdbbe1bd10efffcb950a`;
the slot is
`97a475c0f9ca521b14033c6e214c6cba7de390c161c96ffd36008c72b9f44520`.
The build used Amu's selfhost Mac route with no Linux, JVM, Node or C compiler
in the image closure. It does not establish signed release admission,
registered Itonami app/agent execution, normal desktop coexistence or
physical hardware operation.
