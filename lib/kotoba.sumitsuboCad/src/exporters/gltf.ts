/**
 * sumitsubo 墨壺 — glTF 2.0 exporter (Khronos open spec).
 * ADR-2606033600. All mesh entities → one glTF doc with a single embedded
 * (base64 data-URI) binary buffer of f32 positions + u32 indices.
 */

import { Drawing, MeshEntity } from "../geometry/types.js";

function toBase64(bytes: Uint8Array): string {
  // Works in Node (Buffer) and browsers (btoa).
  const g = globalThis as { Buffer?: { from(b: Uint8Array): { toString(enc: string): string } } };
  if (g.Buffer) return g.Buffer.from(bytes).toString("base64");
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return (globalThis as unknown as { btoa(s: string): string }).btoa(bin);
}

export function exportGltf(d: Drawing): string {
  const meshes = d.entities.filter((e): e is MeshEntity => e.kind === "mesh");

  // Build layout: [positions f32][indices u32].
  const posChunks: number[][] = [];
  const idxChunks: number[][] = [];
  let posCount = 0;
  let idxCount = 0;
  for (const m of meshes) {
    const pos: number[] = [];
    for (const v of m.vertices) pos.push(v.x, v.y, v.z);
    const idx: number[] = [];
    for (const t of m.triangles) idx.push(t[0], t[1], t[2]);
    posChunks.push(pos);
    idxChunks.push(idx);
    posCount += pos.length;
    idxCount += idx.length;
  }

  const posBytes = posCount * 4;
  const idxBytes = idxCount * 4;
  const totalLen = posBytes + idxBytes;
  const buf = new ArrayBuffer(totalLen);
  const f32 = new Float32Array(buf, 0, posCount);
  const u32 = new Uint32Array(buf, posBytes, idxCount);

  const accessors: Record<string, unknown>[] = [];
  const bufferViews: Record<string, unknown>[] = [];
  const gltfMeshes: Record<string, unknown>[] = [];
  const nodes: Record<string, unknown>[] = [];

  let posOff = 0;
  let idxOff = 0;
  let fCursor = 0;
  let uCursor = 0;

  meshes.forEach((m, mi) => {
    const pos = posChunks[mi];
    const idx = idxChunks[mi];
    const min = [Infinity, Infinity, Infinity];
    const max = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < pos.length; i += 3) {
      for (let c = 0; c < 3; c++) {
        min[c] = Math.min(min[c], pos[i + c]);
        max[c] = Math.max(max[c], pos[i + c]);
      }
    }
    for (const x of pos) f32[fCursor++] = x;
    for (const x of idx) u32[uCursor++] = x;

    const posView = bufferViews.length;
    bufferViews.push({ buffer: 0, byteOffset: posOff, byteLength: pos.length * 4, target: 34962 });
    const idxView = bufferViews.length;
    bufferViews.push({ buffer: 0, byteOffset: posBytes + idxOff, byteLength: idx.length * 4, target: 34963 });

    const posAcc = accessors.length;
    accessors.push({ bufferView: posView, componentType: 5126, count: pos.length / 3, type: "VEC3", min, max });
    const idxAcc = accessors.length;
    accessors.push({ bufferView: idxView, componentType: 5125, count: idx.length, type: "SCALAR" });

    gltfMeshes.push({
      name: m.id,
      primitives: [{ attributes: { POSITION: posAcc }, indices: idxAcc, mode: 4 }],
    });
    nodes.push({ mesh: mi, name: m.id });
    posOff += pos.length * 4;
    idxOff += idx.length * 4;
  });

  const gltf = {
    asset: { version: "2.0", generator: "sumitsubo (ADR-2606033600)" },
    scene: 0,
    scenes: [{ nodes: nodes.map((_, i) => i) }],
    nodes,
    meshes: gltfMeshes,
    accessors,
    bufferViews,
    buffers: [
      {
        byteLength: totalLen,
        uri: `data:application/octet-stream;base64,${toBase64(new Uint8Array(buf))}`,
      },
    ],
  };

  return JSON.stringify(gltf, null, 2);
}
