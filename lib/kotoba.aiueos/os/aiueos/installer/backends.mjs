import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { constants, createReadStream, lstatSync } from "node:fs";
import { open, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

function run(command, args) {
  return execFileSync(command, args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}

function macPlist(commandArgs) {
  const [verb, ...rest] = commandArgs;
  const plist = execFileSync("diskutil", [verb, "-plist", ...rest], { encoding: "buffer", stdio: ["ignore", "pipe", "pipe"] });
  return JSON.parse(execFileSync("plutil", ["-convert", "json", "-o", "-", "-"], { input: plist, encoding: "utf8" }));
}

function macDiskInfo(device) {
  const value = macPlist(["info", device]);
  const list = macPlist(["list", device]);
  const partitions = list?.AllDisksAndPartitions?.[0]?.Partitions ?? [];
  const canonical = value.DeviceNode;
  const systemDisks = new Set();
  const collectPhysicalWholeDisks = (entry, seen = new Set()) => {
    const identifier = entry?.DeviceIdentifier;
    if (!identifier || seen.has(identifier)) return;
    seen.add(identifier);
    if (entry.WholeDisk === true && entry.Internal === true && entry.VirtualOrPhysical !== "Virtual") {
      systemDisks.add(entry.DeviceNode ?? `/dev/${identifier}`);
    }
    const related = [];
    if (entry.ParentWholeDisk) related.push(entry.ParentWholeDisk);
    for (const store of entry.APFSPhysicalStores ?? []) {
      const storeIdentifier = store.DeviceIdentifier ?? store.APFSPhysicalStore;
      if (storeIdentifier) related.push(storeIdentifier);
    }
    for (const next of related) {
      try { collectPhysicalWholeDisks(macPlist(["info", next]), seen); } catch { /* unresolved means the final empty set fails closed */ }
    }
  };
  for (const mount of ["/", "/System/Volumes/Data"]) {
    try {
      const mounted = macPlist(["info", mount]);
      collectPhysicalWholeDisks(mounted);
    } catch { /* one successful system-volume lookup is sufficient */ }
  }
  return {
    info: {
      path: canonical,
      type: value.WholeDisk ? "disk" : "partition",
      whole: value.WholeDisk === true,
      internal: value.Internal === true,
      empty: partitions.length === 0 && !value.Content,
      mounted: Boolean(value.Mounted || partitions.some((p) => p.MountPoint)),
      boot: value.Bootable === true && systemDisks.has(canonical),
      system: systemDisks.has(canonical),
      bytes: value.TotalSize,
      model: value.MediaName ?? "unknown",
      nodeIdentity: deviceNodeIdentity(canonical),
    },
    systemDisks: [...systemDisks],
  };
}

function linuxDiskInfo(device) {
  const tree = JSON.parse(run("lsblk", ["--json", "--bytes", "--output", "PATH,TYPE,SIZE,MODEL,RM,HOTPLUG,TRAN,SERIAL,WWN,MOUNTPOINTS,FSTYPE,PTTYPE", device]));
  const root = tree.blockdevices?.[0];
  if (!root) throw new Error(`lsblk did not return ${device}`);
  const systemPaths = linuxSystemDiskPaths(run);
  const children = root.children ?? [];
  return {
    info: {
      path: root.path,
      type: root.type,
      whole: root.type === "disk",
      internal: (root.rm === false || root.rm === 0) && (root.hotplug === false || root.hotplug === 0) && root.tran !== "usb",
      empty: children.length === 0 && !root.fstype && !root.pttype,
      mounted: (root.mountpoints ?? []).some(Boolean) || children.some((c) => (c.mountpoints ?? []).some(Boolean)),
      boot: systemPaths.includes(root.path),
      system: systemPaths.includes(root.path),
      bytes: root.size,
      model: root.model ?? "unknown",
      transport: root.tran ?? "unknown",
      serial: root.serial ?? null,
      wwn: root.wwn ?? null,
      nodeIdentity: deviceNodeIdentity(root.path),
    },
    systemDisks: systemPaths,
  };
}

export function linuxSystemDiskPaths(runCommand, mountTargets = ["/", "/cdrom", "/isodevice", "/run/live/medium"]) {
  const disks = new Set();
  const flatten = (nodes) => nodes.flatMap((node) => [node, ...flatten(node.children ?? [])]);
  for (const target of mountTargets) {
    try {
      const source = runCommand("findmnt", ["--noheadings", "--output", "SOURCE", "--target", target]).trim();
      if (!source.startsWith("/dev/")) continue;
      const tree = JSON.parse(runCommand("lsblk", ["--json", "--inverse", "--paths", "--output", "PATH,TYPE", source]));
      for (const node of flatten(tree.blockdevices ?? [])) if (node.type === "disk") disks.add(node.path);
    } catch { /* absent live-media mount is normal; an empty final set fails closed */ }
  }
  return [...disks].sort();
}

function deviceNodeIdentity(path) {
  const value = lstatSync(path);
  return { dev: value.dev, ino: value.ino, rdev: value.rdev, mode: value.mode };
}

function sameNodeIdentity(actual, expected) {
  return expected && actual.dev === expected.dev && actual.ino === expected.ino && actual.rdev === expected.rdev && actual.mode === expected.mode;
}

async function hashOpenedExtent(handle, bytes) {
  const hash = createHash("sha256");
  const chunk = Buffer.allocUnsafe(Math.min(4 * 1024 * 1024, Math.max(1, bytes)));
  let offset = 0;
  while (offset < bytes) {
    const wanted = Math.min(chunk.length, bytes - offset);
    const { bytesRead } = await handle.read(chunk, 0, wanted, offset);
    if (bytesRead === 0) break;
    hash.update(chunk.subarray(0, bytesRead));
    offset += bytesRead;
  }
  return { bytes: offset, sha256: hash.digest("hex") };
}

async function copyAndVerify(imagePath, device, expected, expectedTarget = undefined, binding = undefined) {
  const source = await open(imagePath, "r");
  let clear;
  try {
    clear = await source.readFile();
  } finally {
    await source.close();
  }
  const digest = createHash("sha256").update(clear).digest("hex");
  if (clear.length !== expected.bytes || digest !== expected.sha256) {
    throw new Error("release image changed after receipt validation; target was not opened");
  }
  const targetFlags = binding?.exclusive
    ? constants.O_RDWR | constants.O_EXCL | (constants.O_NOFOLLOW ?? 0)
    : "r+";
  const target = await open(device, targetFlags);
  try {
    const openedIdentity = await target.stat();
    if (expectedTarget && !sameNodeIdentity(openedIdentity, expectedTarget.nodeIdentity)) {
      throw new Error("target device identity changed between inspection and open; nothing was written");
    }
    if (expectedTarget && !openedIdentity.isBlockDevice()) {
      throw new Error("opened target is not the inspected block device; nothing was written");
    }
    if (binding?.reinspect) {
      const boundInspection = binding.reinspect();
      if (JSON.stringify(boundInspection) !== JSON.stringify(binding.expectedInspection)) {
        throw new Error("target safety state changed after exclusive open; nothing was written");
      }
    }
    let offset = 0;
    while (offset < expected.bytes) {
      const bytesRead = Math.min(4 * 1024 * 1024, expected.bytes - offset);
      let written = 0;
      while (written < bytesRead) {
        const result = await target.write(clear, offset + written, bytesRead - written, offset + written);
        if (result.bytesWritten === 0) throw new Error("target accepted a zero-byte write");
        written += result.bytesWritten;
      }
      offset += bytesRead;
    }
    await target.sync();
    const readback = await hashOpenedExtent(target, expected.bytes);
    if (readback.bytes !== expected.bytes || readback.sha256 !== expected.sha256) throw new Error("installed image readback does not match the validated release image");
    return readback;
  } finally {
    await target.close();
  }
}

export function realBackend(platform = process.platform) {
  const inspect = (device) => {
    if (platform === "darwin") return macDiskInfo(device);
    if (platform === "linux") return linuxDiskInfo(device);
    throw new Error(`unsupported installer platform: ${platform}`);
  };
  return {
    kind: "real",
    inspect,
    writeImage(imagePath, device, expected, expectedTarget, expectedInspection) {
      if (platform !== "linux") {
        throw new Error("real internal-disk writes are supported only from Linux, where an exclusive block-device open can be required");
      }
      return copyAndVerify(imagePath, device, expected, expectedTarget, {
        exclusive: true,
        expectedInspection,
        reinspect: () => inspect(device),
      });
    },
  };
}

export async function fakeBackend(configPath) {
  if (process.env.NODE_ENV !== "test" || process.env.AIUEOS_INSTALLER_ALLOW_FAKE !== "1") {
    throw new Error("fake-device backend is only available with NODE_ENV=test and AIUEOS_INSTALLER_ALLOW_FAKE=1");
  }
  const config = JSON.parse(await readFile(configPath, "utf8"));
  return {
    kind: "fake",
    inspect(device) {
      if (device !== config.info?.path) throw new Error(`fake backend has no device ${device}`);
      return { info: config.info, systemDisks: config.systemDisks };
    },
    async writeImage(imagePath, _device, expected) {
      if (!config.outputPath) throw new Error("fake backend requires outputPath");
      const outputPath = resolve(config.outputPath);
      if (outputPath === "/dev" || outputPath.startsWith("/dev/")) throw new Error("fake backend refuses device paths");
      await writeFile(outputPath, Buffer.alloc(expected.bytes), { flag: "wx" });
      return copyAndVerify(imagePath, outputPath, expected);
    },
  };
}
