# org-kernel-fuse

**Design only. No implementation.** The blocker here is not effort, it is a
dependency on software the user has to install.

FUSE (the Linux kernel's userspace filesystem interface,
`include/uapi/linux/fuse.h`) lets a userspace process serve a mount point
directly.

## What is actually in the way

Measured on this machine, 2026-08-17:

- `/Library/Filesystems/macfuse.fs` — **absent**. macFUSE is not installed.
- `libfuse` — **absent** under `/usr/local/lib` and `/opt/homebrew/lib`.

macFUSE is a third-party system extension. Requiring a user to install one,
approve it in System Settings and reboot is a strictly worse first
experience than `org-ietf-nfs`, which needs nothing.

## And it is not a wire protocol

FUSE is not TCP. It is a message protocol over a **device file** —
`/dev/macfuse*` on macOS, `/dev/fuse` on Linux — which portable `.cljc`
cannot reach. On the JVM, Panama's FFM API (`java.lang.foreign`) can open
and ioctl a device without writing JNI or any C, so this could be built
without violating the no-new-native rule (ADR-2607072000) — but only on the
JVM, and only with the extension installed.

## The condition for starting

Serving a mount on **Linux**, where FUSE is in the kernel and nothing has to
be installed. On macOS it stays behind NFS.

## Layering, when it is built

```
org-kernel-fuse         the FUSE message protocol (portable .cljc)
  <fuse device>         :clj-only, Panama FFM, opens the device and nothing else
  nfs.v3/IFilesystem    the same injected filesystem NFS uses
```

## License

Apache-2.0.
