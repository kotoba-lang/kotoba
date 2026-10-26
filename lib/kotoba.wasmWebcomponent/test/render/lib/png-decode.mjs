// Minimal, dependency-free PNG decoder — enough to read back a pixel buffer
// from a Playwright `elementHandle.screenshot()` buffer, which is always
// 8-bit-depth, non-interlaced, color type 2 (RGB) or 6 (RGBA) in practice
// (Chromium's screenshot encoder doesn't emit palette/interlaced PNGs).
// Uses only Node's built-in `zlib` (PNG's IDAT chunks are zlib/deflate
// streams per the spec) — no image-decoding npm package needed, keeping
// this repo's "zero extra runtime dependency for the logic itself" ethos
// even though the *browser driver* (`playwright`) is a new dependency this
// change accepts (see README's "Automated render verification" section).
//
// Deliberately narrow: throws on anything this repo's own screenshots never
// produce (interlaced, palette/grayscale, <8-bit depth) rather than silently
// mis-decoding — a wrong pixel readback would be worse than a loud failure.
import { inflateSync } from 'node:zlib';

const PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

function paeth(a, b, c) {
  const p = a + b - c;
  const pa = Math.abs(p - a);
  const pb = Math.abs(p - b);
  const pc = Math.abs(p - c);
  if (pa <= pb && pa <= pc) return a;
  if (pb <= pc) return b;
  return c;
}

/** Decode an 8-bit, non-interlaced RGB/RGBA PNG buffer into
 * `{ width, height, channels, data }` where `data` is a flat Buffer of
 * `width*height*channels` unfiltered bytes, row-major, top-to-bottom. */
export function decodePNG(buf) {
  if (!buf.subarray(0, 8).equals(PNG_SIGNATURE)) {
    throw new Error('decodePNG: not a PNG (bad signature)');
  }
  let pos = 8;
  let width, height, bitDepth, colorType, interlace;
  const idatChunks = [];
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos);
    const type = buf.toString('ascii', pos + 4, pos + 8);
    const data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
      interlace = data[12];
    } else if (type === 'IDAT') {
      idatChunks.push(data);
    } else if (type === 'IEND') {
      break;
    }
    pos += 8 + len + 4; // length + type + data + CRC
  }
  if (width === undefined) throw new Error('decodePNG: missing IHDR');
  if (bitDepth !== 8) throw new Error(`decodePNG: only 8-bit depth supported, got ${bitDepth}`);
  if (interlace !== 0) throw new Error('decodePNG: interlaced PNG not supported');
  const channels = { 0: 1, 2: 3, 4: 2, 6: 4 }[colorType];
  if (!channels) throw new Error(`decodePNG: unsupported color type ${colorType}`);

  const raw = inflateSync(Buffer.concat(idatChunks));
  const stride = width * channels;
  const out = Buffer.alloc(height * stride);
  let rawPos = 0;
  let prevRow = Buffer.alloc(stride);
  for (let y = 0; y < height; y++) {
    const filter = raw[rawPos];
    rawPos += 1;
    const row = raw.subarray(rawPos, rawPos + stride);
    rawPos += stride;
    const outRow = Buffer.alloc(stride);
    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? outRow[x - channels] : 0;
      const b = prevRow[x];
      const c = x >= channels ? prevRow[x - channels] : 0;
      let val = row[x];
      switch (filter) {
        case 0: break; // None
        case 1: val = (val + a) & 0xff; break; // Sub
        case 2: val = (val + b) & 0xff; break; // Up
        case 3: val = (val + Math.floor((a + b) / 2)) & 0xff; break; // Average
        case 4: val = (val + paeth(a, b, c)) & 0xff; break; // Paeth
        default: throw new Error(`decodePNG: unknown filter type ${filter} on row ${y}`);
      }
      outRow[x] = val;
    }
    outRow.copy(out, y * stride);
    prevRow = outRow;
  }
  return { width, height, channels, data: out };
}

/** Read pixel `(x, y)` from a decoded image as `[r, g, b, a]` (a=255 if the
 * image has no alpha channel). */
export function getPixel(img, x, y) {
  const i = (y * img.width + x) * img.channels;
  const r = img.data[i];
  const g = img.data[i + 1];
  const b = img.data[i + 2];
  const a = img.channels === 4 ? img.data[i + 3] : 255;
  return [r, g, b, a];
}
