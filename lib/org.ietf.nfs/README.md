# org-ietf-nfs

**NFS version 3 (IETF RFC 1813) and the MOUNT protocol, as a pure `.cljc`
program over an injected filesystem — a volume macOS mounts, browses, reads
and writes, with no kernel extension, no third-party install, no code
signing and no root.**

```clojure
(require '[nfs.tcp :as tcp] '[nfs.memory :as memory])

(def server (tcp/start! {:fs (memory/filesystem) :dir "/kotoba" :port 12049}))
```

```bash
mkdir -p /tmp/mnt
mount_nfs -o vers=3,tcp,port=12049,mountport=12049,nolocks,soft \
  127.0.0.1:/kotoba /tmp/mnt
open /tmp/mnt          # a volume in Finder
```

## Why NFS, measured rather than assumed

macOS 26.4, 2026-08-17:

| | NFS | SMB | FUSE | File Provider |
|---|---|---|---|---|
| client already present | ✅ `/sbin/mount_nfs` | ✅ `mount_smbfs` | ❌ macFUSE not installed | ✅ (as an API) |
| mounts without root | ✅ **measured** | — | needs a system extension | — |
| unprivileged ports | ✅ `port=` / `mountport=` | port in URL, 445 default | — | — |
| needs code signing | ❌ | ❌ | system extension | ✅ Swift app extension |
| pure protocol | ✅ | ✅ but far larger | ❌ device I/O | ❌ |

The mount above ran as an ordinary user and produced
`127.0.0.1:/kotoba on /private/tmp/nfs-mnt (nfs, nodev, nosuid, mounted by
junkawasaki)`. Finder showed it as a volume named `kotoba`.

**What does *not* work unprivileged: the `nfs://host:port/path` URL.**
Finder's Connect to Server and AppleScript `mount volume` both fail with
NetFS error −5014 and — measured with a listener on the URL's port — never
open a connection at all. `com.apple.rpcbind` exists as a LaunchDaemon and
is not running, and this server deliberately does not implement the
portmapper (program 100000 would have to bind port 111, which needs root).
The command-line mount carries the ports explicitly and so needs no
portmapper.

## Who is allowed, and as whom

NFSv3 has no authentication. `AUTH_SYS` carries a uid and gid the *client*
chose, which makes it a hint and never a boundary. Two optional seams answer
that here, and neither knows what supplies them:

```clojure
(tcp/start!
 {:dir "/kotoba" :port 12049
  :authorize      (fn [peer] principal-or-nil)   ; once, at accept
  :filesystem-for (fn [principal] fs)})          ; a tree per principal
```

`nil` from `:authorize` closes the connection before a byte is read — the one
place where closing beats replying, because there is no RPC call yet to
answer. With neither seam supplied the server is open to anything that
reaches the socket, which is why the default bind is loopback.

`kotoba-lang/kekkai` is the intended supplier: `kekkai.acl/edge-allowed?` is
pure, deny-by-default and port-granular, and returns the ports one node may
reach another on. This repository deliberately does not depend on it —
whoever depends on both is the application.

## The filesystem is injected

`nfs.v3/IFilesystem` is the whole seam: root, attrs, lookup, readdir, read,
write, create, mkdir, remove, rmdir, rename, setattr, fsstat. A Drive, a
directory and a test double are all the same to it. `nfs.memory` is the
reference implementation and the double the round-trip suite runs against.

A handle is opaque bytes of the implementation's choosing and must keep
meaning the same file for as long as a client might hold it — across server
restarts, because the client does not know the server restarted.

## Four details that decide whether a mount works at all

- **`FSINFO` is asked before anything is trusted.** `rtmax`, `wtmax` and
  `dtpref` are what the client sizes every later call by.
- **`ACCESS` is not advisory.** macOS calls it and believes it. Return
  success with an empty mask and you get a volume that mounts, lists, and
  refuses to open anything.
- **macOS lists with `READDIRPLUS` (17), not `READDIR` (16).** Measured: a
  server implementing only 16 mounts successfully and then answers `ls`
  with `Bad procedure for program`.
- **An unimplemented procedure must answer `NFS3ERR_NOTSUPP`, not be
  absent.** A missing entry becomes RPC `PROC_UNAVAIL`, which a filesystem
  client does not recover from. `READLINK`, `SYMLINK`, `MKNOD` and `LINK`
  are answered, not omitted.

## What is implemented

NULL, GETATTR, SETATTR, LOOKUP, ACCESS, READ, WRITE, CREATE, MKDIR, REMOVE,
RMDIR, RENAME, READDIR, READDIRPLUS, FSSTAT, FSINFO, PATHCONF, COMMIT —
plus MOUNT v3 NULL/MNT/UMNT/EXPORT.

Not implemented, and answered as `NFS3ERR_NOTSUPP`: READLINK, SYMLINK,
MKNOD, LINK. Not implemented at all: NLM locking (mount with `nolocks`),
the portmapper, NFSv4, RPCSEC_GSS.

## Test

```bash
kbb -M:test
```

The round-trip suite starts a real listener and drives it with a client of
its own over a TCP socket, because unit tests over the codec prove the bytes
are shaped right and only a socket proves the three layers compose.

## License

Apache-2.0.
