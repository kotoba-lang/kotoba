# Itonami OS remote management progress

AWAI-119 / AWAI-122, 2026-11-02. The Mac loopback OpenSSH management bridge
is distinct from the unimplemented OS-native SSH listener. `ssh
itonami-6600h status` performs a fresh signed ping against the physical OS;
`help` lists the finite commands, `key 3` opens Itonami, and `screenshot`
writes a PNG to SSH stdout. Other commands include supported ASCII `type`,
explicit `usb-select BDF` and `reboot`. Unknown commands are refused before
any signed operation. It is not a general Mac shell or an app-consent grant.

The installed loopback listener uses port22077, a dedicated client identity,
a pinned dedicated host key, public-key-only authentication, ForceCommand,
no TTY, no user rc/environment and no forwarding. Keys stay in the Mac's
existing SSH application directory. The additive client Include preserves
the previous SSH configuration. Two user LaunchAgents retain the listener
and a boot-nonce observer; only public0xc000 identities enter that cache.
The running workspace configuration and private-key paths stay outside Git.
No existing Remote Login, Tailscale, device membership or ACL is changed.

`aiueos-management.py` is a host adapter around the existing signed debug
client. It uses the board's existing pinned key; nonce/counter/signature
admission is still performed on the board. Commands serialize locally and
ping/key responses must match their sent counter/value. This debug path is
Ed25519 only, below the product's post-quantum qualification floor.

Physical verification: fresh SSH ping, key3 and a complete800x600 PNG
readback pass. Wrong client key, unknown `uname -a`, and TCP forwarding fail.
The plain SSH alias also reaches the board. The bridge receipt does not
qualify a TCP/SSH stack in the OS, encrypted desktop streaming, general shell,
Kekkai overlay connectivity, automatic update, or a released product.

Next: native USB-safe update maintenance, signed release/version checks,
macOS-style update choices/notification, OS-native SSH, and Kekkai app
installation on both the Mac and6600H (JUN-757). The source-bound native
input-maintenance candidate is still under verification; no NVMe OS update
or new physical candidate has been installed by this unit.


2026-11-02 native update maintenance candidate: run-update stops the active
non-radio xHCI and observes HCHalted before borrowing scratchpad14. Context
3072..3711 is copied into stopped USB memory0..639, restored before selecting
the same host again. Pending modals/missing or failed hosts/radio refuse the
borrow. Public key/fixture constants are word-packed without byte changes.
Standard USB/NVMe12 and exact PXE hub smoke pass. The native component'sff
mask exercises8 controls, including changed signature/digest, all1024 public
key/app-pattern bytes retained and actual keyboard/mouse input after USB
reinitialization. The fixture needs the complete ValueRuntime root/caller
region anchors and a real524KiB font payload; early refused roots and the
no-payload boot failure remain recorded. Final source reproduces the exact
tested product ELF/EFI. Version floor remains>=1 in this unit: automatic
installation is not enabled yet. No physical ESP update in this unit.
