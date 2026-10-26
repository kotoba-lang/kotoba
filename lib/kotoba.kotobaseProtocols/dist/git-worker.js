var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// node_modules/@noble/curves/node_modules/@noble/hashes/_u64.js
var fromNumH = /* @__PURE__ */ __name((n) => n / 2 ** 32 | 0, "fromNumH");
var fromNumL = /* @__PURE__ */ __name((n) => n >>> 0, "fromNumL");
function setU64FromNum(view, byteOffset, n, isLE2) {
  const h = fromNumH(n);
  const l = fromNumL(n);
  view.setUint32(byteOffset, isLE2 ? l : h, isLE2);
  view.setUint32(byteOffset + 4, isLE2 ? h : l, isLE2);
}
__name(setU64FromNum, "setU64FromNum");

// node_modules/@noble/curves/node_modules/@noble/hashes/utils.js
function isBytes(a) {
  return a instanceof Uint8Array || ArrayBuffer.isView(a) && a.constructor.name === "Uint8Array" && "BYTES_PER_ELEMENT" in a && a.BYTES_PER_ELEMENT === 1;
}
__name(isBytes, "isBytes");
var atitle = /* @__PURE__ */ __name((title) => title ? `"${title}" ` : "", "atitle");
function anumber(n, title = "") {
  if (typeof n !== "number")
    throw new TypeError(atitle(title) + "expected number, got " + typeof n);
  if (!Number.isSafeInteger(n) || n < 0)
    throw new RangeError(atitle(title) + "expected integer >= 0, got " + n);
  return n;
}
__name(anumber, "anumber");
function abytes(value, length, title = "") {
  if (isBytes(value) && (length === void 0 || value.length === length))
    return value;
  if (length !== void 0)
    anumber(length, "length");
  const bytes = isBytes(value);
  const ofLen = length !== void 0 ? ` of length ${length}` : "";
  const got = bytes ? `length=${value.length}` : `type=${typeof value}`;
  const message = atitle(title) + "expected Uint8Array" + ofLen + ", got " + got;
  if (!bytes)
    throw new TypeError(message);
  throw new RangeError(message);
}
__name(abytes, "abytes");
function ahash(h) {
  if (typeof h !== "function" || typeof h.create !== "function")
    throw new TypeError("expected hash wrapped by utils.createHasher");
  anumber(h.outputLen);
  anumber(h.blockLen);
  if (h.outputLen < 1 || h.blockLen < 1)
    throw new Error("hash blockLen / outputLen must be >= 1");
}
__name(ahash, "ahash");
var aobject = /* @__PURE__ */ __name((value, label) => {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    throw new TypeError((label === "object" ? "" : `"${label}" `) + "expected object, got type=" + typeof value);
}, "aobject");
function aexists(instance, checkFinished = true) {
  if (instance.destroyed)
    throw new Error("hash was destroyed");
  if (checkFinished && instance.finished)
    throw new Error("digest() was already called");
}
__name(aexists, "aexists");
function aoutput(out, instance) {
  abytes(out, void 0, "output");
  const min = instance.outputLen;
  if (!(out.length >= min)) {
    throw new RangeError('"output" expected length >= ' + min);
  }
}
__name(aoutput, "aoutput");
function clean(...arrays) {
  for (let i = 0; i < arrays.length; i++) {
    arrays[i].fill(0);
  }
}
__name(clean, "clean");
function createView(arr) {
  return new DataView(arr.buffer, arr.byteOffset, arr.byteLength);
}
__name(createView, "createView");
function rotr(word, shift) {
  return word << 32 - shift | word >>> shift;
}
__name(rotr, "rotr");
var hasHexBuiltin = /* @__PURE__ */ (() => (
  // @ts-ignore
  typeof Uint8Array.from([]).toHex === "function" && typeof Uint8Array.fromHex === "function"
))();
var hexes = /* @__PURE__ */ Array.from({ length: 256 }, (_, i) => i.toString(16).padStart(2, "0"));
function bytesToHex(bytes) {
  abytes(bytes);
  if (hasHexBuiltin)
    return bytes.toHex();
  let hex2 = "";
  for (let i = 0; i < bytes.length; i++) {
    hex2 += hexes[bytes[i]];
  }
  return hex2;
}
__name(bytesToHex, "bytesToHex");
function asciiToBase16(ch) {
  return ch >= 48 && ch <= 57 ? ch - 48 : ch >= 65 && ch <= 70 ? ch - (65 - 10) : ch >= 97 && ch <= 102 ? ch - (97 - 10) : void 0;
}
__name(asciiToBase16, "asciiToBase16");
function hexToBytes(hex2) {
  if (typeof hex2 !== "string")
    throw new TypeError("hex string expected, got " + typeof hex2);
  if (hasHexBuiltin) {
    try {
      return Uint8Array.fromHex(hex2);
    } catch (error) {
      if (error instanceof SyntaxError)
        throw new RangeError(error.message);
      throw error;
    }
  }
  const hl = hex2.length;
  const al = hl / 2;
  if (hl % 2)
    throw new RangeError("hex string expected, got unpadded hex of length " + hl);
  const array = new Uint8Array(al);
  for (let ai = 0, hi = 0; ai < al; ai++, hi += 2) {
    const n1 = asciiToBase16(hex2.charCodeAt(hi));
    const n2 = asciiToBase16(hex2.charCodeAt(hi + 1));
    if (n1 === void 0 || n2 === void 0) {
      const char = hex2[hi] + hex2[hi + 1];
      throw new RangeError('hex string expected, got non-hex character "' + char + '" at index ' + hi);
    }
    array[ai] = n1 * 16 + n2;
  }
  return array;
}
__name(hexToBytes, "hexToBytes");
function concatBytes(...arrays) {
  let sum = 0;
  for (let i = 0; i < arrays.length; i++) {
    const a = arrays[i];
    abytes(a);
    sum += a.length;
  }
  const res = new Uint8Array(sum);
  for (let i = 0, pad = 0; i < arrays.length; i++) {
    const a = arrays[i];
    res.set(a, pad);
    pad += a.length;
  }
  return res;
}
__name(concatBytes, "concatBytes");
function checkOpts(defaults, opts, title = "opts") {
  aobject(defaults, "defaults");
  if (opts !== void 0)
    aobject(opts, title);
  const merged = Object.assign(defaults, opts);
  return merged;
}
__name(checkOpts, "checkOpts");
function createHasher(hashCons, info = {}) {
  if (typeof hashCons !== "function")
    throw new TypeError('"hashCons" expected function, got type=' + typeof hashCons);
  info = checkOpts({}, info, "info");
  const hashC = /* @__PURE__ */ __name((msg, opts) => hashCons(opts).update(msg).digest(), "hashC");
  const tmp = hashCons(void 0);
  hashC.outputLen = tmp.outputLen;
  hashC.blockLen = tmp.blockLen;
  hashC.canXOF = tmp.canXOF;
  hashC.create = (opts) => hashCons(opts);
  Object.assign(hashC, info);
  return Object.freeze(hashC);
}
__name(createHasher, "createHasher");
function randomBytes(bytesLength = 32) {
  anumber(bytesLength, "bytesLength");
  const cr = typeof globalThis === "object" ? globalThis.crypto : null;
  if (typeof cr?.getRandomValues !== "function")
    throw new Error("crypto.getRandomValues must be defined");
  if (bytesLength > 65536)
    throw new RangeError(`"bytesLength" expected <= 65536, got ${bytesLength}`);
  return cr.getRandomValues(new Uint8Array(bytesLength));
}
__name(randomBytes, "randomBytes");
var oidNist = /* @__PURE__ */ __name((suffix) => ({
  // Current NIST hashAlgs suffixes used here fit in one DER subidentifier octet.
  // Larger suffix values would need base-128 OID encoding and a different length byte.
  oid: Uint8Array.from([6, 9, 96, 134, 72, 1, 101, 3, 4, 2, suffix])
}), "oidNist");

// node_modules/@noble/curves/node_modules/@noble/hashes/_md.js
function Chi(a, b, c) {
  return a & b ^ ~a & c;
}
__name(Chi, "Chi");
function Maj(a, b, c) {
  return a & b ^ a & c ^ b & c;
}
__name(Maj, "Maj");
var HashMD = class {
  static {
    __name(this, "HashMD");
  }
  blockLen;
  outputLen;
  canXOF = false;
  padOffset;
  isLE;
  // For partial updates less than block size
  buffer;
  view;
  finished = false;
  length = 0;
  pos = 0;
  destroyed = false;
  constructor(blockLen, outputLen, padOffset, isLE2) {
    this.blockLen = blockLen;
    this.outputLen = outputLen;
    this.padOffset = padOffset;
    this.isLE = isLE2;
    this.buffer = new Uint8Array(blockLen);
    this.view = createView(this.buffer);
  }
  update(data) {
    aexists(this);
    abytes(data);
    const { view, buffer, blockLen } = this;
    const len = data.length;
    let processed = false;
    for (let pos = 0; pos < len; ) {
      const take = Math.min(blockLen - this.pos, len - pos);
      if (take === blockLen) {
        const dataView = createView(data);
        for (; blockLen <= len - pos; pos += blockLen)
          this.process(dataView, pos);
        processed = true;
        continue;
      }
      buffer.set(pos === 0 && take === len ? data : data.subarray(pos, pos + take), this.pos);
      this.pos += take;
      pos += take;
      if (this.pos === blockLen) {
        this.process(view, 0);
        this.pos = 0;
        processed = true;
      }
    }
    this.length += data.length;
    if (processed)
      this.roundClean();
    return this;
  }
  digestInto(out) {
    aexists(this);
    aoutput(out, this);
    this.finished = true;
    const { buffer, view, blockLen, isLE: isLE2 } = this;
    let { pos } = this;
    buffer[pos++] = 128;
    buffer.fill(0, pos);
    if (this.padOffset > blockLen - pos) {
      this.process(view, 0);
      buffer.fill(0);
    }
    setU64FromNum(view, blockLen - 8, this.length * 8, isLE2);
    this.process(view, 0);
    this.roundClean();
    const oview = out === buffer ? view : createView(out);
    const len = this.outputLen;
    const outLen = len / 4;
    const state = this.get();
    if (len % 4 || outLen > state.length)
      throw new Error("invalid outputLen");
    for (let i = 0; i < outLen; i++)
      oview.setUint32(4 * i, state[i], isLE2);
  }
  digest() {
    const { buffer, outputLen } = this;
    this.digestInto(buffer);
    const res = buffer.slice(0, outputLen);
    this.destroy();
    return res;
  }
  _cloneIntoMeta(to) {
    const { buffer, length, finished, destroyed, pos } = this;
    to.destroyed = destroyed;
    to.finished = finished;
    to.length = length;
    to.pos = pos;
    if (pos)
      to.buffer.set(buffer);
    return to;
  }
  clone() {
    return this._cloneInto();
  }
};
var SHA256_IV = /* @__PURE__ */ Uint32Array.from([
  1779033703,
  3144134277,
  1013904242,
  2773480762,
  1359893119,
  2600822924,
  528734635,
  1541459225
]);

// node_modules/@noble/curves/node_modules/@noble/hashes/sha2.js
var SHA256_K = /* @__PURE__ */ Uint32Array.from([
  1116352408,
  1899447441,
  3049323471,
  3921009573,
  961987163,
  1508970993,
  2453635748,
  2870763221,
  3624381080,
  310598401,
  607225278,
  1426881987,
  1925078388,
  2162078206,
  2614888103,
  3248222580,
  3835390401,
  4022224774,
  264347078,
  604807628,
  770255983,
  1249150122,
  1555081692,
  1996064986,
  2554220882,
  2821834349,
  2952996808,
  3210313671,
  3336571891,
  3584528711,
  113926993,
  338241895,
  666307205,
  773529912,
  1294757372,
  1396182291,
  1695183700,
  1986661051,
  2177026350,
  2456956037,
  2730485921,
  2820302411,
  3259730800,
  3345764771,
  3516065817,
  3600352804,
  4094571909,
  275423344,
  430227734,
  506948616,
  659060556,
  883997877,
  958139571,
  1322822218,
  1537002063,
  1747873779,
  1955562222,
  2024104815,
  2227730452,
  2361852424,
  2428436474,
  2756734187,
  3204031479,
  3329325298
]);
var SHA256_W = /* @__PURE__ */ new Uint32Array(64);
var SHA2_32B = class extends HashMD {
  static {
    __name(this, "SHA2_32B");
  }
  // We cannot use array here since array allows indexing by variable
  // which means optimizer/compiler cannot use registers.
  // Numeric initializers matter: starting the fields as `undefined` changes
  // V8's field representation and makes sha256 3x slower (measured).
  A = 0;
  B = 0;
  C = 0;
  D = 0;
  E = 0;
  F = 0;
  G = 0;
  H = 0;
  constructor(outputLen, IV) {
    super(64, outputLen, 8, false);
    this.A = IV[0] | 0;
    this.B = IV[1] | 0;
    this.C = IV[2] | 0;
    this.D = IV[3] | 0;
    this.E = IV[4] | 0;
    this.F = IV[5] | 0;
    this.G = IV[6] | 0;
    this.H = IV[7] | 0;
  }
  get() {
    const { A, B, C, D, E, F, G, H } = this;
    return [A, B, C, D, E, F, G, H];
  }
  // prettier-ignore
  set(A, B, C, D, E, F, G, H) {
    this.A = A | 0;
    this.B = B | 0;
    this.C = C | 0;
    this.D = D | 0;
    this.E = E | 0;
    this.F = F | 0;
    this.G = G | 0;
    this.H = H | 0;
  }
  _cloneInto(to) {
    (to ||= new this.constructor()).set(...this.get());
    return this._cloneIntoMeta(to);
  }
  process(view, offset) {
    for (let i = 0; i < 16; i++, offset += 4)
      SHA256_W[i] = view.getUint32(offset, false);
    for (let i = 16; i < 64; i++) {
      const W15 = SHA256_W[i - 15];
      const W2 = SHA256_W[i - 2];
      const s0 = rotr(W15, 7) ^ rotr(W15, 18) ^ W15 >>> 3;
      const s1 = rotr(W2, 17) ^ rotr(W2, 19) ^ W2 >>> 10;
      SHA256_W[i] = s1 + SHA256_W[i - 7] + s0 + SHA256_W[i - 16] | 0;
    }
    let { A, B, C, D, E, F, G, H } = this;
    for (let i = 0; i < 64; i++) {
      const sigma1 = rotr(E, 6) ^ rotr(E, 11) ^ rotr(E, 25);
      const T1 = H + sigma1 + Chi(E, F, G) + SHA256_K[i] + SHA256_W[i] | 0;
      const sigma0 = rotr(A, 2) ^ rotr(A, 13) ^ rotr(A, 22);
      const T2 = sigma0 + Maj(A, B, C) | 0;
      H = G;
      G = F;
      F = E;
      E = D + T1 | 0;
      D = C;
      C = B;
      B = A;
      A = T1 + T2 | 0;
    }
    A = A + this.A | 0;
    B = B + this.B | 0;
    C = C + this.C | 0;
    D = D + this.D | 0;
    E = E + this.E | 0;
    F = F + this.F | 0;
    G = G + this.G | 0;
    H = H + this.H | 0;
    this.set(A, B, C, D, E, F, G, H);
  }
  roundClean() {
    clean(SHA256_W);
  }
  destroy() {
    this.destroyed = true;
    this.set(0, 0, 0, 0, 0, 0, 0, 0);
    clean(this.buffer);
  }
};
var _SHA256 = class extends SHA2_32B {
  static {
    __name(this, "_SHA256");
  }
  constructor() {
    super(32, SHA256_IV);
  }
};
var sha256 = /* @__PURE__ */ createHasher(
  () => new _SHA256(),
  /* @__PURE__ */ oidNist(1)
);

// node_modules/@noble/curves/utils.js
function aarray(item, title, inner = () => {
}) {
  if (!Array.isArray(item))
    throw new TypeError(`"${title}" expected array, got type=${typeof item}`);
  for (let i = 0; i < item.length; i++)
    inner(item[i], `${title}[${i}]`);
  return item;
}
__name(aarray, "aarray");
var abytes2 = /* @__PURE__ */ __name((value, length, title) => abytes(value, length, title), "abytes");
var anumber2 = anumber;
function astring(value, title = "") {
  if (typeof value !== "string") {
    const prefix = title && `"${title}" `;
    throw new TypeError(prefix + "expected string, got type=" + typeof value);
  }
  return value;
}
__name(astring, "astring");
function aobject2(value, title = "object") {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    throw new TypeError(title === "object" ? "expected valid options object" : `"${title}" expected object, got type=${typeof value}`);
  return value;
}
__name(aobject2, "aobject");
function afunction(value, title) {
  if (typeof value !== "function")
    throw new TypeError(`"${title}" is invalid: expected function, got ${typeof value}`);
  return value;
}
__name(afunction, "afunction");
var bytesToHex2 = bytesToHex;
var concatBytes2 = /* @__PURE__ */ __name((...arrays) => concatBytes(...arrays), "concatBytes");
var hexToBytes2 = /* @__PURE__ */ __name((hex2) => hexToBytes(hex2), "hexToBytes");
var isBytes2 = isBytes;
var randomBytes2 = /* @__PURE__ */ __name((bytesLength) => randomBytes(bytesLength), "randomBytes");
var _0n = /* @__PURE__ */ BigInt(0);
var _1n = /* @__PURE__ */ BigInt(1);
var atitle2 = /* @__PURE__ */ __name((title) => title ? `"${title}" ` : "", "atitle");
function abool(value, title = "") {
  if (typeof value !== "boolean")
    throw new TypeError(atitle2(title) + "expected boolean, got type=" + typeof value);
  return value;
}
__name(abool, "abool");
function abignumber(n) {
  if (typeof n === "bigint") {
    if (!isPosBig(n))
      throw new RangeError("positive bigint expected, got " + n);
  } else
    anumber2(n);
  return n;
}
__name(abignumber, "abignumber");
function asafenumber(value, title = "") {
  if (typeof value !== "number") {
    const prefix = title && `"${title}" `;
    throw new TypeError(prefix + "expected number, got type=" + typeof value);
  }
  if (!Number.isSafeInteger(value)) {
    const prefix = title && `"${title}" `;
    throw new RangeError(prefix + "expected safe integer, got " + value);
  }
}
__name(asafenumber, "asafenumber");
function numberToHexUnpadded(num) {
  const hex2 = abignumber(num).toString(16);
  return hex2.length & 1 ? "0" + hex2 : hex2;
}
__name(numberToHexUnpadded, "numberToHexUnpadded");
function hexToNumber(hex2) {
  if (typeof hex2 !== "string")
    throw new TypeError("hex string expected, got " + typeof hex2);
  return hex2 === "" ? _0n : BigInt("0x" + hex2);
}
__name(hexToNumber, "hexToNumber");
function bytesToNumberBE(bytes) {
  return hexToNumber(bytesToHex(bytes));
}
__name(bytesToNumberBE, "bytesToNumberBE");
function bytesToNumberLE(bytes) {
  return hexToNumber(bytesToHex(copyBytes(abytes(bytes)).reverse()));
}
__name(bytesToNumberLE, "bytesToNumberLE");
function numberToBytesBE(n, len) {
  anumber(len);
  if (len === 0)
    throw new Error("zero output length is invalid");
  n = abignumber(n);
  const expectedLen = len * 2;
  const hex2 = n.toString(16);
  if (hex2.length > expectedLen)
    throw new RangeError("number is too large");
  return hexToBytes(hex2.padStart(expectedLen, "0"));
}
__name(numberToBytesBE, "numberToBytesBE");
function numberToBytesLE(n, len) {
  return numberToBytesBE(n, len).reverse();
}
__name(numberToBytesLE, "numberToBytesLE");
function copyBytes(bytes) {
  return Uint8Array.from(abytes2(bytes));
}
__name(copyBytes, "copyBytes");
function isPosBig(n) {
  return typeof n === "bigint" && _0n <= n;
}
__name(isPosBig, "isPosBig");
function inRange(n, min, max) {
  return isPosBig(n) && isPosBig(min) && isPosBig(max) && min <= n && n < max;
}
__name(inRange, "inRange");
function aInRange(title, n, min, max) {
  if (!inRange(n, min, max))
    throw new RangeError("expected valid " + title + ": " + min + " <= n < " + max + ", got " + n);
}
__name(aInRange, "aInRange");
function bitLen(n) {
  if (n < _0n)
    throw new Error("expected non-negative bigint, got " + n);
  return n === _0n ? 0 : n.toString(2).length;
}
__name(bitLen, "bitLen");
var bitMask = /* @__PURE__ */ __name((n) => {
  asafenumber(n, "n");
  return (_1n << BigInt(n)) - _1n;
}, "bitMask");
function createHmacDrbg(hashLen, qByteLen, hmacFn) {
  anumber(hashLen, "hashLen");
  anumber(qByteLen, "qByteLen");
  if (typeof hmacFn !== "function")
    throw new TypeError("hmacFn must be a function");
  const u8n = /* @__PURE__ */ __name((len) => new Uint8Array(len), "u8n");
  const NULL = Uint8Array.of();
  const byte0 = Uint8Array.of(0);
  const byte1 = Uint8Array.of(1);
  const _maxDrbgIters = 1e3;
  let v = u8n(hashLen);
  let k = u8n(hashLen);
  let i = 0;
  const reset = /* @__PURE__ */ __name(() => {
    v.fill(1);
    k.fill(0);
    i = 0;
  }, "reset");
  const h = /* @__PURE__ */ __name((...msgs) => hmacFn(k, concatBytes2(v, ...msgs)), "h");
  const reseed = /* @__PURE__ */ __name((seed = NULL) => {
    k = h(byte0, seed);
    v = h();
    if (seed.length === 0)
      return;
    k = h(byte1, seed);
    v = h();
  }, "reseed");
  const gen = /* @__PURE__ */ __name(() => {
    if (i++ >= _maxDrbgIters)
      throw new Error("drbg: tried max amount of iterations");
    let len = 0;
    const out = [];
    while (len < qByteLen) {
      v = h();
      const sl = v.slice();
      out.push(sl);
      len += v.length;
    }
    return concatBytes2(...out);
  }, "gen");
  const genUntil = /* @__PURE__ */ __name((seed, pred) => {
    reset();
    reseed(seed);
    let res = void 0;
    while ((res = pred(gen())) === void 0)
      reseed();
    reset();
    return res;
  }, "genUntil");
  return genUntil;
}
__name(createHmacDrbg, "createHmacDrbg");
function validateObject(object, fields = {}, optFields = {}, title = "object") {
  aobject2(object, title);
  aobject2(fields, "fields");
  aobject2(optFields, "optFields");
  function checkField(fieldName, expectedType, isOpt) {
    const label = title === "object" ? `param "${String(fieldName)}"` : `"${title}.${String(fieldName)}"`;
    const val = object[fieldName];
    if (!Object.hasOwn(object, fieldName) && (isOpt ? val !== void 0 : expectedType !== "function")) {
      throw new TypeError(`${label} is invalid: expected own property`);
    }
    if (isOpt && val === void 0)
      return;
    const current = typeof val;
    if (current !== expectedType || val === null)
      throw new TypeError(`${label} is invalid: expected ${expectedType}, got ${current}`);
  }
  __name(checkField, "checkField");
  const iter = /* @__PURE__ */ __name((f, isOpt) => Object.entries(f).forEach(([k, v]) => checkField(k, v, isOpt)), "iter");
  iter(fields, false);
  iter(optFields, true);
}
__name(validateObject, "validateObject");

// node_modules/@noble/curves/abstract/modular.js
var _0n2 = /* @__PURE__ */ BigInt(0);
var _1n2 = /* @__PURE__ */ BigInt(1);
var _2n = /* @__PURE__ */ BigInt(2);
var _3n = /* @__PURE__ */ BigInt(3);
var _4n = /* @__PURE__ */ BigInt(4);
var _5n = /* @__PURE__ */ BigInt(5);
var _7n = /* @__PURE__ */ BigInt(7);
var _8n = /* @__PURE__ */ BigInt(8);
var _9n = /* @__PURE__ */ BigInt(9);
var _15n = /* @__PURE__ */ BigInt(15);
var _16n = /* @__PURE__ */ BigInt(16);
var POW_WINDOWED_MIN = /* @__PURE__ */ BigInt("0x10000000000000000");
function mod(a, b) {
  if (b <= _0n2)
    throw new Error("mod: expected positive modulus, got " + b);
  const result = a % b;
  return result >= _0n2 ? result : b + result;
}
__name(mod, "mod");
function pow(num, power, modulo) {
  if (modulo <= _1n2)
    throw new Error("pow: expected modulus > 1, got " + modulo);
  if (typeof power !== "bigint")
    throw new TypeError("invalid exponent: expected bigint, got " + typeof power);
  if (power < _0n2)
    throw new Error("invalid exponent, negatives unsupported");
  if (power === _0n2)
    return _1n2;
  if (power === _1n2)
    return num;
  let d = num % modulo;
  if (d < _0n2)
    d += modulo;
  if (power < POW_WINDOWED_MIN) {
    let p2 = _1n2;
    while (power > _0n2) {
      if (power & _1n2)
        p2 = p2 * d % modulo;
      d = d * d % modulo;
      power >>= _1n2;
    }
    return p2;
  }
  const digits = [];
  while (power > _0n2) {
    digits.push(Number(power & _15n));
    power >>= _4n;
  }
  const table = new Array(16);
  table[0] = _1n2;
  table[1] = d;
  for (let i = 2; i < 16; i++)
    table[i] = table[i - 1] * d % modulo;
  let p = table[digits[digits.length - 1]];
  for (let w = digits.length - 2; w >= 0; w--) {
    p = p * p % modulo;
    p = p * p % modulo;
    p = p * p % modulo;
    p = p * p % modulo;
    const digit = digits[w];
    if (digit !== 0)
      p = p * table[digit] % modulo;
  }
  return p;
}
__name(pow, "pow");
function pow2(x, power, modulo) {
  if (modulo <= _1n2)
    throw new Error("pow2: expected modulus > 1, got " + modulo);
  if (power < _0n2)
    throw new Error("pow2: expected non-negative exponent, got " + power);
  let res = x;
  while (power-- > _0n2) {
    res *= res;
    res %= modulo;
  }
  return res;
}
__name(pow2, "pow2");
function invert(number, modulo) {
  if (number === _0n2)
    throw new Error("invert: expected non-zero number");
  if (modulo <= _1n2)
    throw new Error("invert: expected modulus > 1, got " + modulo);
  let a = mod(number, modulo);
  let b = modulo;
  let x = _0n2, u = _1n2;
  while (a !== _0n2) {
    const q = b / a;
    const r = b - a * q;
    const m = x - u * q;
    b = a, a = r, x = u, u = m;
  }
  const gcd = b;
  if (gcd !== _1n2)
    throw new Error("invert: does not exist");
  return mod(x, modulo);
}
__name(invert, "invert");
function invertCt(a, prime) {
  if (prime <= _1n2)
    throw new Error("invertCt: expected prime modulus > 1, got " + prime);
  const an = mod(a, prime);
  if (an === _0n2)
    throw new Error("invertCt: expected non-zero number");
  const inverse = pow(an, prime - _2n, prime);
  if (mod(an * inverse, prime) !== _1n2)
    throw new Error("invertCt: does not exist");
  return inverse;
}
__name(invertCt, "invertCt");
function assertIsSquare(Fp, root, n) {
  const F = Fp;
  if (!F.eql(F.sqr(root), n))
    throw new Error("Cannot find square root");
}
__name(assertIsSquare, "assertIsSquare");
function aoddModulus(order, fnName) {
  if ((order & _1n2) === _0n2)
    throw new Error(fnName + ": expected odd modulus, got " + order);
}
__name(aoddModulus, "aoddModulus");
function sqrt3mod4(Fp, n) {
  const F = Fp;
  const p1div4 = (F.ORDER + _1n2) / _4n;
  const root = F.pow(n, p1div4);
  assertIsSquare(F, root, n);
  return root;
}
__name(sqrt3mod4, "sqrt3mod4");
function sqrt5mod8(Fp, n) {
  const F = Fp;
  const p5div8 = (F.ORDER - _5n) / _8n;
  const n2 = F.mul(n, _2n);
  const v = F.pow(n2, p5div8);
  const nv = F.mul(n, v);
  const i = F.mul(F.mul(nv, _2n), v);
  const root = F.mul(nv, F.sub(i, F.ONE));
  assertIsSquare(F, root, n);
  return root;
}
__name(sqrt5mod8, "sqrt5mod8");
function sqrt9mod16(P) {
  const Fp_ = Field(P);
  const tn = tonelliShanks(P);
  const c1 = tn(Fp_, Fp_.neg(Fp_.ONE));
  const c2 = tn(Fp_, c1);
  const c3 = tn(Fp_, Fp_.neg(c1));
  const c4 = (P + _7n) / _16n;
  return ((Fp, n) => {
    const F = Fp;
    let tv1 = F.pow(n, c4);
    let tv2 = F.mul(tv1, c1);
    const tv3 = F.mul(tv1, c2);
    const tv4 = F.mul(tv1, c3);
    const e1 = F.eql(F.sqr(tv2), n);
    const e2 = F.eql(F.sqr(tv3), n);
    tv1 = F.cmov(tv1, tv2, e1);
    tv2 = F.cmov(tv4, tv3, e2);
    const e3 = F.eql(F.sqr(tv2), n);
    const root = F.cmov(tv1, tv2, e3);
    assertIsSquare(F, root, n);
    return root;
  });
}
__name(sqrt9mod16, "sqrt9mod16");
function tonelliShanks(P) {
  if (P < _3n)
    throw new Error("sqrt is not defined for small field");
  aoddModulus(P, "tonelliShanks");
  let Q = P - _1n2;
  let S = 0;
  while (Q % _2n === _0n2) {
    Q /= _2n;
    S++;
  }
  let Z = _2n;
  const _Fp = Field(P);
  while (FpLegendre(_Fp, Z) === 1) {
    if (Z++ > 1e3)
      throw new Error("Cannot find square root: probably non-prime P");
  }
  if (S === 1)
    return sqrt3mod4;
  let cc = _Fp.pow(Z, Q);
  const Q1div2 = (Q + _1n2) / _2n;
  return /* @__PURE__ */ __name(function tonelliSlow(Fp, n) {
    const F = Fp;
    if (F.is0(n))
      return n;
    if (FpLegendre(F, n) !== 1)
      throw new Error("Cannot find square root");
    let M = S;
    let c = F.mul(F.ONE, cc);
    let t = F.pow(n, Q);
    let R = F.pow(n, Q1div2);
    while (!F.eql(t, F.ONE)) {
      if (F.is0(t))
        throw new Error("Cannot find square root: probably non-prime P");
      let i = 1;
      let t_tmp = F.sqr(t);
      while (!F.eql(t_tmp, F.ONE)) {
        i++;
        t_tmp = F.sqr(t_tmp);
        if (i === M)
          throw new Error("Cannot find square root");
      }
      const exponent = _1n2 << BigInt(M - i - 1);
      const b = F.pow(c, exponent);
      M = i;
      c = F.sqr(b);
      t = F.mul(t, c);
      R = F.mul(R, b);
    }
    return R;
  }, "tonelliSlow");
}
__name(tonelliShanks, "tonelliShanks");
function FpSqrt(P) {
  aoddModulus(P, "Fp.sqrt");
  if (P % _4n === _3n)
    return sqrt3mod4;
  if (P % _8n === _5n)
    return sqrt5mod8;
  if (P % _16n === _9n)
    return sqrt9mod16(P);
  return tonelliShanks(P);
}
__name(FpSqrt, "FpSqrt");
var FIELD_FIELDS = [
  "create",
  "isValid",
  "is0",
  "neg",
  "inv",
  "sqrt",
  "sqr",
  "eql",
  "add",
  "sub",
  "mul",
  "pow",
  "div",
  "addN",
  "subN",
  "mulN",
  "sqrN"
];
function validateField(field) {
  aobject2(field, "field");
  if (typeof field.ORDER !== "bigint")
    throw new TypeError('param "ORDER" is invalid: expected bigint, got ' + typeof field.ORDER);
  asafenumber(field.BYTES, "BYTES");
  asafenumber(field.BITS, "BITS");
  for (const name of FIELD_FIELDS)
    afunction(field[name], "field." + name);
  if (field.BYTES < 1 || field.BITS < 1)
    throw new Error("invalid field: expected BYTES/BITS > 0");
  if (field.ORDER <= _1n2)
    throw new Error("invalid field: expected ORDER > 1, got " + field.ORDER);
  return field;
}
__name(validateField, "validateField");
function FpInvertBatch(Fp, nums, passZero = false) {
  validateField(Fp);
  aarray(nums, "nums");
  abool(passZero, "passZero");
  const F = Fp;
  const inverted = new Array(nums.length).fill(passZero ? F.ZERO : void 0);
  const multipliedAcc = nums.reduce((acc, num, i) => {
    if (F.is0(num))
      return acc;
    inverted[i] = acc;
    return F.mul(acc, num);
  }, F.ONE);
  const invertedAcc = F.inv(multipliedAcc);
  nums.reduceRight((acc, num, i) => {
    if (F.is0(num))
      return acc;
    inverted[i] = F.mul(acc, inverted[i]);
    return F.mul(acc, num);
  }, invertedAcc);
  return inverted;
}
__name(FpInvertBatch, "FpInvertBatch");
function FpLegendre(Fp, n) {
  validateField(Fp);
  const F = Fp;
  aoddModulus(F.ORDER, "FpLegendre");
  const p1mod2 = (F.ORDER - _1n2) / _2n;
  const powered = F.pow(n, p1mod2);
  const yes = F.eql(powered, F.ONE);
  const zero = F.eql(powered, F.ZERO);
  const no = F.eql(powered, F.neg(F.ONE));
  if (!yes && !zero && !no)
    throw new Error("invalid Legendre symbol result");
  return yes ? 1 : zero ? 0 : -1;
}
__name(FpLegendre, "FpLegendre");
function nLength(n, nBitLength) {
  if (nBitLength !== void 0)
    anumber2(nBitLength);
  if (n <= _0n2)
    throw new Error("invalid n length: expected positive n, got " + n);
  if (nBitLength !== void 0 && nBitLength < 1)
    throw new Error("invalid n length: expected positive bit length, got " + nBitLength);
  const bits = bitLen(n);
  if (nBitLength !== void 0 && nBitLength < bits)
    throw new Error(`invalid n length: expected nBitLength (${nBitLength}) >= bitLen(n) (${bits})`);
  const _nBitLength = nBitLength !== void 0 ? nBitLength : bits;
  const nByteLength = Math.ceil(_nBitLength / 8);
  return { nBitLength: _nBitLength, nByteLength };
}
__name(nLength, "nLength");
var FIELD_SQRT = /* @__PURE__ */ new WeakMap();
var _Field = class {
  static {
    __name(this, "_Field");
  }
  ORDER;
  BITS;
  BYTES;
  isLE;
  ZERO = _0n2;
  ONE = _1n2;
  _lengths;
  _mod;
  constructor(ORDER, opts = {}) {
    if (ORDER <= _1n2)
      throw new Error("invalid field: expected ORDER > 1, got " + ORDER);
    let _nbitLength = void 0;
    this.isLE = false;
    if (opts != null && typeof opts === "object") {
      if (typeof opts.BITS === "number")
        _nbitLength = opts.BITS;
      if (typeof opts.sqrt === "function")
        Object.defineProperty(this, "sqrt", { value: opts.sqrt, enumerable: true });
      if (typeof opts.isLE === "boolean")
        this.isLE = opts.isLE;
      if (opts.allowedLengths)
        this._lengths = Object.freeze(opts.allowedLengths.slice());
      if (typeof opts.modFromBytes === "boolean")
        this._mod = opts.modFromBytes;
    }
    const { nBitLength, nByteLength } = nLength(ORDER, _nbitLength);
    if (nByteLength > 2048)
      throw new Error("invalid field: expected ORDER of <= 2048 bytes");
    this.ORDER = ORDER;
    this.BITS = nBitLength;
    this.BYTES = nByteLength;
    Object.freeze(this);
  }
  create(num) {
    return mod(num, this.ORDER);
  }
  isValid(num) {
    if (typeof num !== "bigint")
      throw new TypeError("invalid field element: expected bigint, got " + typeof num);
    return _0n2 <= num && num < this.ORDER;
  }
  is0(num) {
    return num === _0n2;
  }
  // is valid and invertible
  isValidNot0(num) {
    return !this.is0(num) && this.isValid(num);
  }
  isOdd(num) {
    return (num & _1n2) === _1n2;
  }
  neg(num) {
    return mod(-num, this.ORDER);
  }
  eql(lhs, rhs) {
    return lhs === rhs;
  }
  sqr(num) {
    return mod(num * num, this.ORDER);
  }
  add(lhs, rhs) {
    return mod(lhs + rhs, this.ORDER);
  }
  sub(lhs, rhs) {
    return mod(lhs - rhs, this.ORDER);
  }
  mul(lhs, rhs) {
    return mod(lhs * rhs, this.ORDER);
  }
  pow(num, power) {
    return pow(num, power, this.ORDER);
  }
  div(lhs, rhs) {
    return mod(lhs * invert(rhs, this.ORDER), this.ORDER);
  }
  // Same as above, but doesn't normalize
  sqrN(num) {
    return num * num;
  }
  addN(lhs, rhs) {
    return lhs + rhs;
  }
  subN(lhs, rhs) {
    return lhs - rhs;
  }
  mulN(lhs, rhs) {
    return lhs * rhs;
  }
  inv(num) {
    return invert(num, this.ORDER);
  }
  sqrt(num) {
    let sqrt = FIELD_SQRT.get(this);
    if (!sqrt)
      FIELD_SQRT.set(this, sqrt = FpSqrt(this.ORDER));
    return sqrt(this, num);
  }
  toBytes(num) {
    return this.isLE ? numberToBytesLE(num, this.BYTES) : numberToBytesBE(num, this.BYTES);
  }
  fromBytes(bytes, skipValidation = false) {
    abytes2(bytes);
    const { _lengths: allowedLengths, BYTES, isLE: isLE2, ORDER, _mod: modFromBytes } = this;
    if (allowedLengths) {
      if (bytes.length < 1 || !allowedLengths.includes(bytes.length) || bytes.length > BYTES) {
        throw new Error("Field.fromBytes: expected " + allowedLengths + " bytes, got " + bytes.length);
      }
      const padded = new Uint8Array(BYTES);
      padded.set(bytes, isLE2 ? 0 : padded.length - bytes.length);
      bytes = padded;
    }
    if (bytes.length !== BYTES)
      throw new Error("Field.fromBytes: expected " + BYTES + " bytes, got " + bytes.length);
    let scalar = isLE2 ? bytesToNumberLE(bytes) : bytesToNumberBE(bytes);
    if (modFromBytes)
      scalar = mod(scalar, ORDER);
    if (!skipValidation) {
      if (!this.isValid(scalar))
        throw new Error("invalid field element: outside of range 0..ORDER");
    }
    return scalar;
  }
  // TODO: we don't need it here, move out to separate fn
  invertBatch(lst) {
    return FpInvertBatch(this, lst, true);
  }
  // We can't move this out because Fp6, Fp12 implement it
  // and it's unclear what to return in there.
  cmov(a, b, condition) {
    abool(condition, "condition");
    return condition ? b : a;
  }
};
function Field(ORDER, opts = {}) {
  Object.freeze(_Field.prototype);
  return new _Field(ORDER, opts);
}
__name(Field, "Field");
function getFieldBytesLength(fieldOrder) {
  if (typeof fieldOrder !== "bigint")
    throw new Error("field order must be bigint");
  if (fieldOrder <= _1n2)
    throw new Error("field order must be greater than 1");
  const bitLength = bitLen(fieldOrder - _1n2);
  return Math.ceil(bitLength / 8);
}
__name(getFieldBytesLength, "getFieldBytesLength");
function getMinHashLength(fieldOrder) {
  const length = getFieldBytesLength(fieldOrder);
  return length + Math.ceil(length / 2);
}
__name(getMinHashLength, "getMinHashLength");
function mapHashToField(key, fieldOrder, isLE2 = false) {
  abytes2(key);
  const len = key.length;
  const fieldLen = getFieldBytesLength(fieldOrder);
  const minLen = Math.max(getMinHashLength(fieldOrder), 16);
  if (len < minLen || len > 1024)
    throw new Error("expected " + minLen + "-1024 bytes of input, got " + len);
  const num = isLE2 ? bytesToNumberLE(key) : bytesToNumberBE(key);
  const reduced = mod(num, fieldOrder - _1n2) + _1n2;
  return isLE2 ? numberToBytesLE(reduced, fieldLen) : numberToBytesBE(reduced, fieldLen);
}
__name(mapHashToField, "mapHashToField");

// node_modules/@noble/curves/abstract/curve.js
var _0n3 = /* @__PURE__ */ BigInt(0);
var _1n3 = /* @__PURE__ */ BigInt(1);
var _4n2 = /* @__PURE__ */ BigInt(4);
var BLIND_BYTES = 16;
var BLIND_BITS = 128;
var FW_WINDOW = 5;
var TABLE_BYTES_MAX = /* @__PURE__ */ (() => 2 ** 31)();
function validatePointCons(Point) {
  const pc = Point;
  if (typeof pc !== "function")
    throw new TypeError('"Point" expected constructor, got type=' + typeof Point);
  afunction(pc.fromAffine, "Point.fromAffine");
  afunction(pc.fromBytes, "Point.fromBytes");
  afunction(pc.fromHex, "Point.fromHex");
  aobject2(pc.BASE, "Point.BASE");
  aobject2(pc.ZERO, "Point.ZERO");
  validateField(pc.Fp);
  validateField(pc.Fn);
}
__name(validatePointCons, "validatePointCons");
function normalizeZ(c, points) {
  validatePointCons(c);
  validateMSMPoints(points, c);
  const invertedZs = FpInvertBatch(c.Fp, points.map((p) => p.Z));
  return points.map((p, i) => c.fromAffine(p.toAffine(invertedZs[i])));
}
__name(normalizeZ, "normalizeZ");
function validateW(W, bits, min = 1) {
  if (!Number.isSafeInteger(W) || W < min || W > bits)
    throw new Error("invalid window size, expected [" + min + ".." + bits + "], got W=" + W);
}
__name(validateW, "validateW");
function validateTableBytes(numPoints, fpBytes) {
  const bytes = numPoints * (4 * fpBytes + 128);
  if (bytes > TABLE_BYTES_MAX)
    throw new Error("invalid window size: table would need ~" + Math.ceil(bytes / 2 ** 20) + " MiB, max " + TABLE_BYTES_MAX / 2 ** 20 + " MiB");
}
__name(validateTableBytes, "validateTableBytes");
function probeRandomBytes(randomBytes3, length) {
  if (randomBytes3 === void 0)
    return void 0;
  afunction(randomBytes3, "randomBytes");
  try {
    const probe = randomBytes3(length);
    if (!isBytes2(probe) || probe.length !== length)
      return void 0;
  } catch {
    return void 0;
  }
  return randomBytes3;
}
__name(probeRandomBytes, "probeRandomBytes");
function validateMSMPoints(points, c) {
  aarray(points, "points");
  points.forEach((p, i) => {
    if (!(p instanceof c))
      throw new Error("invalid point at index " + i);
  });
}
__name(validateMSMPoints, "validateMSMPoints");
function validateMSMScalars(scalars, field, maxScalar) {
  if (!Array.isArray(scalars))
    throw new Error("array of scalars expected");
  scalars.forEach((s, i) => {
    const ok = maxScalar === void 0 ? field.isValid(s) : isPosBig(s) && s < maxScalar;
    if (!ok)
      throw new Error("invalid scalar at index " + i);
  });
}
__name(validateMSMScalars, "validateMSMScalars");
var pointWindowSizes = /* @__PURE__ */ new WeakMap();
function getWindowSize(P) {
  return pointWindowSizes.get(P) || 1;
}
__name(getWindowSize, "getWindowSize");
function oddMultiples(p, size) {
  const dbl = p.double();
  const t = [p];
  for (let j = 1; j < size; j++)
    t.push(t[j - 1].add(dbl));
  return t;
}
__name(oddMultiples, "oddMultiples");
function wnafDigits(n, W) {
  const size = 2 ** W;
  const half = size / 2;
  const mask = BigInt(size - 1);
  const d = [];
  while (n > _0n3) {
    let w = 0;
    if (n & _1n3) {
      w = Number(n & mask);
      if (w >= half)
        w -= size;
      n -= BigInt(w);
    }
    d.push(w);
    n >>= _1n3;
  }
  return d;
}
__name(wnafDigits, "wnafDigits");
function signedWindowDigits(n, W, windows) {
  const size = 2 ** W;
  const half = size / 2;
  const mask = BigInt(size - 1);
  const shiftBy = BigInt(W);
  const d = [];
  for (let w = 0; w < windows; w++) {
    let v = Number(n & mask);
    n >>= shiftBy;
    if (v > half) {
      v -= size;
      n += _1n3;
    }
    d.push(v);
  }
  if (n !== _0n3)
    throw new Error("invalid wnaf");
  return d;
}
__name(signedWindowDigits, "signedWindowDigits");
function wnafWalk(zero, tables, digits) {
  let max = 0;
  for (const d of digits)
    max = Math.max(max, d.length);
  let acc = zero;
  for (let bit = max - 1; bit >= 0; bit--) {
    if (bit !== max - 1)
      acc = acc.double();
    for (let i = 0; i < digits.length; i++) {
      const w = digits[i][bit];
      if (w) {
        const item = tables[i][Math.abs(w) - 1 >> 1];
        acc = acc.add(w < 0 ? item.negate() : item);
      }
    }
  }
  return acc;
}
__name(wnafWalk, "wnafWalk");
var ScalarMultiplier = class {
  static {
    __name(this, "ScalarMultiplier");
  }
  Point;
  BASE;
  ZERO;
  randomBytes;
  wnafPrecomputes = /* @__PURE__ */ new WeakMap();
  baseCanBeBlinded;
  bits;
  // Parametrized with a given Point class (not individual point)
  constructor(Point, randomBytes3) {
    validatePointCons(Point);
    this.randomBytes = probeRandomBytes(randomBytes3, BLIND_BYTES);
    this.Point = Point;
    this.BASE = Point.BASE;
    this.ZERO = Point.ZERO;
    this.bits = Point.Fn.BITS;
  }
  /**
   * Creates a signed fixed-window wNAF precomputation table: for every window w, the
   * multiples `[1..2^(W−1)]⋅2^(w⋅W)⋅P`, flattened. All doublings are baked into the table,
   * so cached multiplication is additions-only. `windows = ceil(bits/W) + 1`: the extra
   * window absorbs the final carry of signed-digit recoding.
   * For a 256-bit curve and W=6, the table is 44⋅32 = 1408 points.
   * @param point - Point instance
   * @param W - window size
   * @param bits - scalar bitlength the table must cover
   */
  buildWnafTable(point, W, bits) {
    const windows = Math.ceil(bits / W) + 1;
    const half = 2 ** (W - 1);
    const comp = [];
    let base = point;
    for (let w = 0; w < windows; w++) {
      let acc = base;
      for (let i = 0; i < half; i++) {
        comp.push(acc);
        acc = acc.add(base);
      }
      base = comp[comp.length - 1].double();
    }
    return { W, bits, windows, comp };
  }
  /**
   * Implements ec multiplication using precomputed signed fixed-window wNAF tables.
   * Constant-time: fixed window count with one table addition per window — zero digits feed
   * the fake accumulator — and no doublings; the lookup scans the whole window slice.
   * Scalar bounds are validated by the public entry points ({@link ScalarMultiplier.mulCT},
   * {@link ScalarMultiplier.mulCTBlinded}, {@link ScalarMultiplier.mulUnsafe});
   * signedWindowDigits throws if `n` exceeds the table.
   * @returns real and fake (for const-time) points
   */
  wnafCachedCT(precomputes, n) {
    const { W, windows, comp } = precomputes;
    const half = 2 ** (W - 1);
    const digits = signedWindowDigits(n, W, windows);
    let p = this.ZERO;
    let f = this.BASE;
    for (let w = 0; w < windows; w++) {
      const digit = digits[w];
      const start = w * half;
      const idx = Math.abs(digit) - 1;
      let sel = comp[start];
      for (let i = 1; i < half; i++)
        sel = i === idx ? comp[start + i] : sel;
      const neg = sel.negate();
      if (digit === 0)
        f = f.add(comp[start]);
      else
        p = p.add(digit < 0 ? neg : sel);
    }
    return { p, f };
  }
  // Cache key is point identity plus (W, bits); at most two entries exist per point (public-width
  // `Fn.BITS` and blinded `Fn.BITS + BLIND_BITS`). Callers must not reuse the same point with
  // incompatible `transform(...)` layouts and expect a separate cache entry.
  getWnafPrecomputes(W, point, bits, transform) {
    let entries = this.wnafPrecomputes.get(point);
    let comp = entries?.find((entry) => entry.W === W && entry.bits === bits);
    if (!comp) {
      comp = this.buildWnafTable(point, W, bits);
      if (typeof transform === "function")
        comp = { ...comp, comp: transform(comp.comp) };
      if (!entries) {
        entries = [];
        this.wnafPrecomputes.set(point, entries);
      }
      entries.push(comp);
    }
    return comp;
  }
  assertPoint(point) {
    if (!(point instanceof this.Point))
      throw new TypeError('"point" expected Point instance, got type=' + typeof point);
  }
  // Shared prologue of the constant-time entry points. Rejects scalar 0: in key/signature-style
  // callers a zero scalar means broken upstream plumbing, and concrete Points already reject it.
  // Uses inRange instead of Fn.isValidNot0: validateField() only certifies the arithmetic subset.
  validateMulInput(point, scalar) {
    this.assertPoint(point);
    if (!inRange(scalar, _1n3, this.Point.Fn.ORDER))
      throw new Error("invalid scalar");
  }
  // Constant-time dispatch shared by mulCT / mulCTBlinded. Un-precomputed points (W===1, e.g.
  // ECDH peer keys) skip building a throwaway cached table in favor of a small fixed-window
  // multiply. `n` must be < 2^bits.
  runCT(point, n, bits, transform) {
    const W = getWindowSize(point);
    if (W === 1)
      return this.fixedWindowCT(point, n, bits);
    return this.wnafCachedCT(this.getWnafPrecomputes(W, point, bits, transform), n);
  }
  mulCT(point, scalar, transform) {
    this.validateMulInput(point, scalar);
    return this.runCT(point, scalar, this.bits, transform);
  }
  mulCTBlinded(point, scalar, transform) {
    this.validateMulInput(point, scalar);
    if (this.randomBytes === void 0)
      throw new Error("randomBytes is required for scalar blinding");
    const bits = this.Point.Fn.BITS + BLIND_BITS;
    const blind = this.randomBytes(BLIND_BYTES);
    if (!isBytes2(blind) || blind.length !== BLIND_BYTES)
      throw new Error("randomBytes returned invalid byte array");
    blind[0] = blind[0] & 63 | 128;
    const n = scalar + bytesToNumberBE(blind) * this.Point.Fn.ORDER;
    return this.runCT(point, n, bits, transform);
  }
  /**
   * Constant-time multiplication `n*point` for an un-precomputed point, via a small fixed window.
   * A cached wNAF table only pays off when reused; a flat 2^FW_WINDOW table (`size-1` adds) is
   * far cheaper to build for a single use. The point-operation sequence is independent of `n`:
   * build the table, then per window exactly FW_WINDOW doublings, a data-oblivious scan over
   * every table entry, and one addition (adds the identity when the window digit is 0 — never
   * skipped).
   *
   * `n` must be `< 2^bits`. Assumes complete addition (adding the identity costs the same as any
   * add), which holds for the Weierstrass/Edwards point types used here. The table is left in
   * projective form (no normalizeZ): normalizing this small a table costs more than the
   * mixed-add savings it would buy for a single multiply.
   * @returns real point `p`; `f` duplicates it only to match {@link wnafCachedCT}'s return shape
   * (this path needs no fake accumulator — its op-count is already scalar-independent).
   */
  fixedWindowCT(point, n, bits) {
    const W = FW_WINDOW;
    const size = 1 << W;
    const mask = bitMask(W);
    const table = new Array(size);
    table[0] = this.ZERO;
    for (let i = 1; i < size; i++)
      table[i] = table[i - 1].add(point);
    const windows = Math.ceil(bits / W);
    let acc = this.ZERO;
    for (let window = windows - 1; window >= 0; window--) {
      if (window !== windows - 1)
        for (let d = 0; d < W; d++)
          acc = acc.double();
      const digit = Number(n >> BigInt(window * W) & mask);
      let sel = table[0];
      for (let i = 1; i < size; i++)
        sel = i === digit ? table[i] : sel;
      acc = acc.add(sel);
    }
    return { p: acc, f: acc };
  }
  shouldBlind(point, cofactor) {
    if (this.randomBytes === void 0)
      return false;
    if (cofactor === _1n3)
      return true;
    if (point !== this.BASE)
      return false;
    if (this.baseCanBeBlinded === void 0)
      this.baseCanBeBlinded = this.mulUnsafe(this.BASE, this.Point.Fn.ORDER).is0();
    return this.baseCanBeBlinded;
  }
  mulSecret(point, scalar, cofactor, transform) {
    return this.shouldBlind(point, cofactor) ? this.mulCTBlinded(point, scalar, transform) : this.mulCT(point, scalar, transform);
  }
  mulUnsafe(point, scalar, transform) {
    this.assertPoint(point);
    if (!isPosBig(scalar))
      throw new Error("invalid scalar");
    const W = getWindowSize(point);
    if (W === 1 || scalar >= this.Point.Fn.ORDER)
      return mulAddUnsafe(this.Point, [point], [scalar], true);
    const precomputes = this.getWnafPrecomputes(W, point, this.bits, transform);
    return this.wnafCachedCT(precomputes, scalar).p;
  }
  // Remembers the window size used for precomputed wNAF multiplication of the given point
  // and drops any previously built tables. Usually only the base point is precomputed.
  // W=1 resets the point to the un-precomputed (table-less) paths.
  // W is additionally capped so tables stay under ~2 GiB ({@link TABLE_BYTES_MAX}).
  setWindowSize(point, W) {
    this.assertPoint(point);
    validateW(W, this.bits);
    const windows = Math.ceil((this.bits + BLIND_BITS) / W) + 1;
    validateTableBytes(windows * 2 ** (W - 1), this.Point.Fp.BYTES);
    pointWindowSizes.set(point, W);
    this.wnafPrecomputes.delete(point);
  }
  // True when a window size is set: tables themselves are built lazily on first multiply.
  hasWindowSize(point) {
    return getWindowSize(point) !== 1;
  }
};
function mulAddUnsafe(c, points, scalars, allowOversized = false) {
  validatePointCons(c);
  validateMSMPoints(points, c);
  abool(allowOversized, "allowOversized");
  validateMSMScalars(scalars, c.Fn, allowOversized ? c.Fn.ORDER ** _4n2 : void 0);
  if (points.length !== scalars.length)
    throw new Error("arrays of points and scalars must have equal length");
  const tables = points.map((p) => oddMultiples(p, 4));
  const digits = scalars.map((n) => wnafDigits(n, 4));
  return wnafWalk(c.ZERO, tables, digits);
}
__name(mulAddUnsafe, "mulAddUnsafe");
function createField(order, field, isLE2) {
  if (field) {
    if (field.ORDER !== order)
      throw new Error("Field.ORDER must match order: Fp == p, Fn == n");
    validateField(field);
    return field;
  } else {
    return Field(order, { isLE: isLE2 });
  }
}
__name(createField, "createField");
function createCurveFields(type, CURVE, curveOpts = {}, FpFnLE) {
  if (type !== "weierstrass" && type !== "edwards")
    throw new Error('expected curve type "weierstrass" or "edwards"');
  if (FpFnLE === void 0)
    FpFnLE = type === "edwards";
  if (!CURVE || typeof CURVE !== "object")
    throw new Error(`expected valid ${type} CURVE object`);
  validateObject(curveOpts);
  for (const p of ["p", "n", "h"]) {
    const val = CURVE[p];
    if (!(isPosBig(val) && val !== _0n3))
      throw new Error(`CURVE.${p} must be positive bigint`);
  }
  const Fp = createField(CURVE.p, curveOpts.Fp, FpFnLE);
  const Fn = createField(CURVE.n, curveOpts.Fn, FpFnLE);
  const _b = type === "weierstrass" ? "b" : "d";
  const params = ["Gx", "Gy", "a", _b];
  for (const p of params) {
    if (!Fp.isValid(CURVE[p]))
      throw new Error(`CURVE.${p} must be valid field element of CURVE.Fp`);
  }
  CURVE = Object.freeze(Object.assign({}, CURVE));
  return { CURVE, Fp, Fn };
}
__name(createCurveFields, "createCurveFields");
function createKeygen(randomSecretKey, getPublicKey) {
  return /* @__PURE__ */ __name(function keygen(seed) {
    const secretKey = randomSecretKey(seed);
    return { secretKey, publicKey: getPublicKey(secretKey) };
  }, "keygen");
}
__name(createKeygen, "createKeygen");

// node_modules/@noble/curves/node_modules/@noble/hashes/hmac.js
var _HMAC = class {
  static {
    __name(this, "_HMAC");
  }
  oHash;
  iHash;
  blockLen;
  outputLen;
  canXOF = false;
  finished = false;
  destroyed = false;
  constructor(hash, key) {
    ahash(hash);
    abytes(key, void 0, "key");
    this.iHash = hash.create();
    if (typeof this.iHash.update !== "function")
      throw new Error("expected Hash instance");
    this.blockLen = this.iHash.blockLen;
    this.outputLen = this.iHash.outputLen;
    const blockLen = this.blockLen;
    const pad = new Uint8Array(blockLen);
    pad.set(key.length > blockLen ? hash.create().update(key).digest() : key);
    for (let i = 0; i < pad.length; i++)
      pad[i] ^= 54;
    this.iHash.update(pad);
    this.oHash = hash.create();
    for (let i = 0; i < pad.length; i++)
      pad[i] ^= 54 ^ 92;
    this.oHash.update(pad);
    clean(pad);
  }
  update(buf) {
    aexists(this);
    this.iHash.update(buf);
    return this;
  }
  digestInto(out) {
    aexists(this);
    aoutput(out, this);
    this.finished = true;
    const buf = out.subarray(0, this.outputLen);
    this.iHash.digestInto(buf);
    this.oHash.update(buf);
    this.oHash.digestInto(buf);
    this.destroy();
  }
  digest() {
    const out = new Uint8Array(this.oHash.outputLen);
    this.digestInto(out);
    return out;
  }
  _cloneInto(to) {
    to ||= Object.create(Object.getPrototypeOf(this), {});
    const { oHash, iHash, finished, destroyed, blockLen, outputLen, canXOF } = this;
    to = to;
    to.finished = finished;
    to.destroyed = destroyed;
    to.blockLen = blockLen;
    to.outputLen = outputLen;
    to.canXOF = canXOF;
    to.oHash = oHash._cloneInto(to.oHash);
    to.iHash = iHash._cloneInto(to.iHash);
    return to;
  }
  clone() {
    return this._cloneInto();
  }
  destroy() {
    this.destroyed = true;
    this.oHash.destroy();
    this.iHash.destroy();
  }
};
var hmac = /* @__PURE__ */ (() => {
  const hmac_ = /* @__PURE__ */ __name(((hash, key, message) => new _HMAC(hash, key).update(message).digest()), "hmac_");
  hmac_.create = (hash, key) => new _HMAC(hash, key);
  return hmac_;
})();

// node_modules/@noble/curves/abstract/der.js
var _0n4 = /* @__PURE__ */ BigInt(0);
var DERErr = class extends Error {
  static {
    __name(this, "DERErr");
  }
  constructor(m = "") {
    super(m);
  }
};
var _DER = {
  // asn.1 DER encoding utils
  Err: DERErr,
  // Basic building block is TLV (Tag-Length-Value)
  _tlv: {
    encode: /* @__PURE__ */ __name((tag, data) => {
      const { Err: E } = _DER;
      asafenumber(tag, "tag");
      if (tag < 0 || tag > 255)
        throw new E("tlv.encode: wrong tag");
      astring(data, "data");
      if (data.length & 1)
        throw new E("tlv.encode: unpadded data");
      const dataLen = data.length / 2;
      const len = numberToHexUnpadded(dataLen);
      if (len.length / 2 & 128)
        throw new E("tlv.encode: long form length too big");
      const lenLen = dataLen > 127 ? numberToHexUnpadded(len.length / 2 | 128) : "";
      const t = numberToHexUnpadded(tag);
      return t + lenLen + len + data;
    }, "encode"),
    // v - value, l - left bytes (unparsed)
    decode(tag, data) {
      const { Err: E } = _DER;
      data = abytes2(data, void 0, "DER data");
      let pos = 0;
      if (tag < 0 || tag > 255)
        throw new E("tlv.decode: wrong tag");
      if (data.length < 2 || data[pos++] !== tag)
        throw new E("tlv.decode: wrong tlv");
      const first = data[pos++];
      const isLong = !!(first & 128);
      let length = 0;
      if (!isLong)
        length = first;
      else {
        const lenLen = first & 127;
        if (!lenLen)
          throw new E("tlv.decode(long): indefinite length not supported");
        if (lenLen > 4)
          throw new E("tlv.decode(long): byte length is too big");
        const lengthBytes = data.subarray(pos, pos + lenLen);
        if (lengthBytes.length !== lenLen)
          throw new E("tlv.decode: length bytes not complete");
        if (lengthBytes[0] === 0)
          throw new E("tlv.decode(long): zero leftmost byte");
        for (const b of lengthBytes)
          length = length << 8 | b;
        pos += lenLen;
        if (length < 128)
          throw new E("tlv.decode(long): not minimal encoding");
      }
      const v = data.subarray(pos, pos + length);
      if (v.length !== length)
        throw new E("tlv.decode: wrong value length");
      return { v, l: data.subarray(pos + length) };
    }
  },
  // https://crypto.stackexchange.com/a/57734 Leftmost bit of first byte is 'negative' flag,
  // since we always use positive integers here. It must always be empty:
  // - add zero byte if exists
  // - if next byte doesn't have a flag, leading zero is not allowed (minimal encoding)
  _int: {
    encode(num) {
      const { Err: E } = _DER;
      abignumber(num);
      if (num < _0n4)
        throw new E("integer: negative integers are not allowed");
      let hex2 = numberToHexUnpadded(num);
      if (Number.parseInt(hex2[0], 16) & 8)
        hex2 = "00" + hex2;
      if (hex2.length & 1)
        throw new E("unexpected DER parsing assertion: unpadded hex");
      return hex2;
    },
    decode(data) {
      const { Err: E } = _DER;
      if (data.length < 1)
        throw new E("invalid signature integer: empty");
      if (data[0] & 128)
        throw new E("invalid signature integer: negative");
      if (data.length > 1 && data[0] === 0 && !(data[1] & 128))
        throw new E("invalid signature integer: unnecessary leading zero");
      return bytesToNumberBE(data);
    }
  },
  toSig(bytes) {
    const { Err: E, _int: int, _tlv: tlv } = _DER;
    const data = abytes2(bytes, void 0, "signature");
    const { v: seqBytes, l: seqLeftBytes } = tlv.decode(48, data);
    if (seqLeftBytes.length)
      throw new E("invalid signature: left bytes after parsing");
    const { v: rBytes, l: rLeftBytes } = tlv.decode(2, seqBytes);
    const { v: sBytes, l: sLeftBytes } = tlv.decode(2, rLeftBytes);
    if (sLeftBytes.length)
      throw new E("invalid signature: left bytes after parsing");
    return { r: int.decode(rBytes), s: int.decode(sBytes) };
  },
  hexFromSig(sig) {
    const { _tlv: tlv, _int: int } = _DER;
    validateObject(sig, { r: "bigint", s: "bigint" }, {}, "sig");
    const rs = tlv.encode(2, int.encode(sig.r));
    const ss = tlv.encode(2, int.encode(sig.s));
    const seq = rs + ss;
    return tlv.encode(48, seq);
  }
};
var DER = /* @__PURE__ */ (() => {
  Object.freeze(_DER._tlv);
  Object.freeze(_DER._int);
  return Object.freeze(_DER);
})();

// node_modules/@noble/curves/abstract/weierstrass.js
var divNearest = /* @__PURE__ */ __name((num, den) => (num + (num >= 0 ? den : -den) / _2n2) / den, "divNearest");
function _splitEndoScalar(k, basis, n) {
  aInRange("scalar", k, _0n5, n);
  const [[a1, b1], [a2, b2]] = basis;
  const c1 = divNearest(b2 * k, n);
  const c2 = divNearest(-b1 * k, n);
  let k1 = k - c1 * a1 - c2 * a2;
  let k2 = -c1 * b1 - c2 * b2;
  const k1neg = k1 < _0n5;
  const k2neg = k2 < _0n5;
  if (k1neg)
    k1 = -k1;
  if (k2neg)
    k2 = -k2;
  const MAX_NUM = bitMask(Math.ceil(bitLen(n) / 2)) + _1n4;
  if (k1 < _0n5 || k1 >= MAX_NUM || k2 < _0n5 || k2 >= MAX_NUM) {
    throw new Error("splitScalar (endomorphism): failed for k");
  }
  return { k1neg, k1, k2neg, k2 };
}
__name(_splitEndoScalar, "_splitEndoScalar");
function validateSigFormat(format) {
  if (!["compact", "recovered", "der"].includes(format))
    throw new Error('Signature format must be "compact", "recovered", or "der"');
  return format;
}
__name(validateSigFormat, "validateSigFormat");
function validateSigOpts(opts, def) {
  validateObject(opts);
  const optsn = {};
  for (let optName of Object.keys(def)) {
    optsn[optName] = opts[optName] === void 0 ? def[optName] : opts[optName];
  }
  abool(optsn.lowS, "lowS");
  abool(optsn.prehash, "prehash");
  if (optsn.format !== void 0)
    validateSigFormat(optsn.format);
  return optsn;
}
__name(validateSigOpts, "validateSigOpts");
var _0n5 = /* @__PURE__ */ BigInt(0);
var _1n4 = /* @__PURE__ */ BigInt(1);
var _2n2 = /* @__PURE__ */ BigInt(2);
var _3n2 = /* @__PURE__ */ BigInt(3);
var _4n3 = /* @__PURE__ */ BigInt(4);
function weierstrass(params, extraOpts = {}) {
  const validated = createCurveFields("weierstrass", params, extraOpts);
  const Fp = validated.Fp;
  const Fn = validated.Fn;
  let CURVE = validated.CURVE;
  const { h: cofactor, n: CURVE_ORDER } = CURVE;
  validateObject(extraOpts, {}, {
    allowInfinityPoint: "boolean",
    clearCofactor: "function",
    isTorsionFree: "function",
    fromBytes: "function",
    toBytes: "function",
    endo: "object",
    randomBytes: "function"
  });
  const { endo, allowInfinityPoint } = extraOpts;
  const randomBytes3 = extraOpts.randomBytes === void 0 ? randomBytes2 : extraOpts.randomBytes;
  if (endo) {
    if (!Fp.is0(CURVE.a) || typeof endo.beta !== "bigint" || !Array.isArray(endo.basises)) {
      throw new Error('invalid endo: expected "beta": bigint and "basises": array');
    }
  }
  const lengths = getWLengths(Fp, Fn);
  function assertCompressionIsSupported() {
    if (!Fp.isOdd)
      throw new Error("compression is not supported: Field does not have .isOdd()");
  }
  __name(assertCompressionIsSupported, "assertCompressionIsSupported");
  function pointToBytes(_c, point, isCompressed) {
    if (allowInfinityPoint && point.is0())
      return Uint8Array.of(0);
    const { x, y } = point.toAffine();
    const bx = Fp.toBytes(x);
    abool(isCompressed, "isCompressed");
    if (isCompressed) {
      assertCompressionIsSupported();
      const hasEvenY = !Fp.isOdd(y);
      return concatBytes2(pprefix(hasEvenY), bx);
    } else {
      return concatBytes2(Uint8Array.of(4), bx, Fp.toBytes(y));
    }
  }
  __name(pointToBytes, "pointToBytes");
  function pointFromBytes(bytes) {
    abytes2(bytes, void 0, "Point");
    const { publicKey: comp, publicKeyUncompressed: uncomp } = lengths;
    const length = bytes.length;
    const head = bytes[0];
    const tail = bytes.subarray(1);
    if (allowInfinityPoint && length === 1 && head === 0)
      return { x: Fp.ZERO, y: Fp.ZERO };
    if (length === comp && (head === 2 || head === 3)) {
      const x = Fp.fromBytes(tail);
      if (!Fp.isValid(x))
        throw new Error("bad point: is not on curve, wrong x");
      const y2 = weierstrassEquation(x);
      let y;
      try {
        y = Fp.sqrt(y2);
      } catch (sqrtError) {
        const err = sqrtError instanceof Error ? ": " + sqrtError.message : "";
        throw new Error("bad point: is not on curve, sqrt error" + err);
      }
      assertCompressionIsSupported();
      const evenY = Fp.isOdd(y);
      const evenH = (head & 1) === 1;
      if (evenH !== evenY)
        y = Fp.neg(y);
      return { x, y };
    } else if (length === uncomp && head === 4) {
      const L = Fp.BYTES;
      const x = Fp.fromBytes(tail.subarray(0, L));
      const y = Fp.fromBytes(tail.subarray(L, L * 2));
      if (!isValidXY(x, y))
        throw new Error("bad point: is not on curve");
      return { x, y };
    } else {
      throw new Error(`bad point: got length ${length}, expected compressed=${comp} or uncompressed=${uncomp}`);
    }
  }
  __name(pointFromBytes, "pointFromBytes");
  const encodePoint = extraOpts.toBytes === void 0 ? pointToBytes : extraOpts.toBytes;
  const decodePoint = extraOpts.fromBytes === void 0 ? pointFromBytes : extraOpts.fromBytes;
  const b3 = Fp.mul(CURVE.b, _3n2);
  const mulA = Fp.is0(CURVE.a) ? (_) => Fp.ZERO : (x) => Fp.mul(CURVE.a, x);
  function weierstrassEquation(x) {
    const x2 = Fp.sqr(x);
    const x3 = Fp.mul(x2, x);
    return Fp.add(Fp.add(x3, Fp.mul(x, CURVE.a)), CURVE.b);
  }
  __name(weierstrassEquation, "weierstrassEquation");
  function isValidXY(x, y) {
    const left = Fp.sqr(y);
    const right = weierstrassEquation(x);
    return Fp.eql(left, right);
  }
  __name(isValidXY, "isValidXY");
  if (!isValidXY(CURVE.Gx, CURVE.Gy))
    throw new Error("bad curve params: generator point");
  const _4a3 = Fp.mul(Fp.pow(CURVE.a, _3n2), _4n3);
  const _27b2 = Fp.mul(Fp.sqr(CURVE.b), BigInt(27));
  if (Fp.is0(Fp.add(_4a3, _27b2)))
    throw new Error("bad curve params: a or b");
  function acoord(title, n, banZero = false) {
    if (!Fp.isValid(n) || banZero && Fp.is0(n))
      throw new Error(`bad point coordinate ${title}`);
    return n;
  }
  __name(acoord, "acoord");
  function aprjpoint(other) {
    if (!(other instanceof Point))
      throw new Error("Weierstrass Point expected");
  }
  __name(aprjpoint, "aprjpoint");
  function splitEndoScalarN(k) {
    if (!endo || !endo.basises)
      throw new Error("no endo");
    return _splitEndoScalar(k, endo.basises, Fn.ORDER);
  }
  __name(splitEndoScalarN, "splitEndoScalarN");
  function pushWnafPair(points, scalars, p, k) {
    if (!Fn.isValid(k))
      throw new RangeError("invalid scalar: out of range");
    if (endo) {
      const { k1neg, k1, k2neg, k2 } = splitEndoScalarN(k);
      const psi = new Point(Fp.mul(p.X, endo.beta), p.Y, p.Z);
      points.push(k1neg ? p.negate() : p, k2neg ? psi.negate() : psi);
      scalars.push(k1, k2);
    } else {
      points.push(p);
      scalars.push(k);
    }
  }
  __name(pushWnafPair, "pushWnafPair");
  const validityCache = /* @__PURE__ */ new WeakSet();
  class Point {
    static {
      __name(this, "Point");
    }
    static BASE = new Point(CURVE.Gx, CURVE.Gy, Fp.ONE);
    static ZERO = new Point(Fp.ZERO, Fp.ONE, Fp.ZERO);
    static Fp = Fp;
    static Fn = Fn;
    X;
    Y;
    Z;
    /** Does NOT validate if the point is valid. Use `.assertValidity()`. */
    constructor(X, Y, Z) {
      this.X = acoord("x", X);
      this.Y = acoord("y", Y, true);
      this.Z = acoord("z", Z);
      Object.freeze(this);
    }
    static CURVE() {
      return CURVE;
    }
    /** Does NOT validate if the point is valid. Use `.assertValidity()`. */
    static fromAffine(p) {
      const { x, y } = p || {};
      if (!p || !Fp.isValid(x) || !Fp.isValid(y))
        throw new Error("invalid affine point");
      if (p instanceof Point)
        throw new Error("projective point not allowed");
      if (Fp.is0(x) && Fp.is0(y))
        return Point.ZERO;
      return new Point(x, y, Fp.ONE);
    }
    static fromBytes(bytes) {
      const P = Point.fromAffine(decodePoint(abytes2(bytes, void 0, "point")));
      P.assertValidity();
      return P;
    }
    static fromHex(hex2) {
      return Point.fromBytes(hexToBytes2(hex2));
    }
    get x() {
      return this.toAffine().x;
    }
    get y() {
      return this.toAffine().y;
    }
    /**
     * @param isLazy - true will defer table computation until the first multiplication
     */
    precompute(windowSize = 6, isLazy = true) {
      wnaf.setWindowSize(this, windowSize);
      if (!isLazy)
        this.multiply(_3n2);
      return this;
    }
    // TODO: return `this`
    /** A point on curve is valid if it conforms to equation. */
    assertValidity() {
      const p = this;
      if (p.is0()) {
        if (extraOpts.allowInfinityPoint && Fp.is0(p.X) && Fp.eql(p.Y, Fp.ONE) && Fp.is0(p.Z))
          return;
        throw new Error("bad point: ZERO");
      }
      if (validityCache.has(p))
        return;
      const { x, y } = p.toAffine();
      if (!Fp.isValid(x) || !Fp.isValid(y))
        throw new Error("bad point: x or y not field elements");
      if (!isValidXY(x, y))
        throw new Error("bad point: equation left != right");
      if (!p.isTorsionFree())
        throw new Error("bad point: not in prime-order subgroup");
      validityCache.add(p);
    }
    hasEvenY() {
      const { y } = this.toAffine();
      if (!Fp.isOdd)
        throw new Error("Field doesn't support isOdd");
      return !Fp.isOdd(y);
    }
    /** Compare one point to another. */
    equals(other) {
      aprjpoint(other);
      const { X: X1, Y: Y1, Z: Z1 } = this;
      const { X: X2, Y: Y2, Z: Z2 } = other;
      const U1 = Fp.eql(Fp.mul(X1, Z2), Fp.mul(X2, Z1));
      const U2 = Fp.eql(Fp.mul(Y1, Z2), Fp.mul(Y2, Z1));
      return U1 && U2;
    }
    /** Flips point to one corresponding to (x, -y) in Affine coordinates. */
    negate() {
      return new Point(this.X, Fp.neg(this.Y), this.Z);
    }
    // Renes-Costello-Batina exception-free doubling formula.
    // There is 30% faster Jacobian formula, but it is not complete.
    // https://eprint.iacr.org/2015/1060, algorithm 3
    // Cost: 8M + 3S + 3*a + 2*b3 + 15add.
    double() {
      const { X: X1, Y: Y1, Z: Z1 } = this;
      let X3 = Fp.ZERO, Y3 = Fp.ZERO, Z3 = Fp.ZERO;
      let t0 = Fp.mul(X1, X1);
      let t1 = Fp.mul(Y1, Y1);
      let t2 = Fp.mul(Z1, Z1);
      let t3 = Fp.mul(X1, Y1);
      t3 = Fp.add(t3, t3);
      Z3 = Fp.mul(X1, Z1);
      Z3 = Fp.add(Z3, Z3);
      X3 = mulA(Z3);
      Y3 = Fp.mul(b3, t2);
      Y3 = Fp.add(X3, Y3);
      X3 = Fp.sub(t1, Y3);
      Y3 = Fp.add(t1, Y3);
      Y3 = Fp.mul(X3, Y3);
      X3 = Fp.mul(t3, X3);
      Z3 = Fp.mul(b3, Z3);
      t2 = mulA(t2);
      t3 = Fp.sub(t0, t2);
      t3 = mulA(t3);
      t3 = Fp.add(t3, Z3);
      Z3 = Fp.add(t0, t0);
      t0 = Fp.add(Z3, t0);
      t0 = Fp.add(t0, t2);
      t0 = Fp.mul(t0, t3);
      Y3 = Fp.add(Y3, t0);
      t2 = Fp.mul(Y1, Z1);
      t2 = Fp.add(t2, t2);
      t0 = Fp.mul(t2, t3);
      X3 = Fp.sub(X3, t0);
      Z3 = Fp.mul(t2, t1);
      Z3 = Fp.add(Z3, Z3);
      Z3 = Fp.add(Z3, Z3);
      return new Point(X3, Y3, Z3);
    }
    // Renes-Costello-Batina exception-free addition formula.
    // There is 30% faster Jacobian formula, but it is not complete.
    // https://eprint.iacr.org/2015/1060, algorithm 1
    // Cost: 12M + 0S + 3*a + 3*b3 + 23add.
    add(other) {
      aprjpoint(other);
      const { X: X1, Y: Y1, Z: Z1 } = this;
      const { X: X2, Y: Y2, Z: Z2 } = other;
      let X3 = Fp.ZERO, Y3 = Fp.ZERO, Z3 = Fp.ZERO;
      let t0 = Fp.mul(X1, X2);
      let t1 = Fp.mul(Y1, Y2);
      let t2 = Fp.mul(Z1, Z2);
      let t3 = Fp.add(X1, Y1);
      let t4 = Fp.add(X2, Y2);
      t3 = Fp.mul(t3, t4);
      t4 = Fp.add(t0, t1);
      t3 = Fp.sub(t3, t4);
      t4 = Fp.add(X1, Z1);
      let t5 = Fp.add(X2, Z2);
      t4 = Fp.mul(t4, t5);
      t5 = Fp.add(t0, t2);
      t4 = Fp.sub(t4, t5);
      t5 = Fp.add(Y1, Z1);
      X3 = Fp.add(Y2, Z2);
      t5 = Fp.mul(t5, X3);
      X3 = Fp.add(t1, t2);
      t5 = Fp.sub(t5, X3);
      Z3 = mulA(t4);
      X3 = Fp.mul(b3, t2);
      Z3 = Fp.add(X3, Z3);
      X3 = Fp.sub(t1, Z3);
      Z3 = Fp.add(t1, Z3);
      Y3 = Fp.mul(X3, Z3);
      t1 = Fp.add(t0, t0);
      t1 = Fp.add(t1, t0);
      t2 = mulA(t2);
      t4 = Fp.mul(b3, t4);
      t1 = Fp.add(t1, t2);
      t2 = Fp.sub(t0, t2);
      t2 = mulA(t2);
      t4 = Fp.add(t4, t2);
      t0 = Fp.mul(t1, t4);
      Y3 = Fp.add(Y3, t0);
      t0 = Fp.mul(t5, t4);
      X3 = Fp.mul(t3, X3);
      X3 = Fp.sub(X3, t0);
      t0 = Fp.mul(t3, t1);
      Z3 = Fp.mul(t5, Z3);
      Z3 = Fp.add(Z3, t0);
      return new Point(X3, Y3, Z3);
    }
    subtract(other) {
      aprjpoint(other);
      return this.add(other.negate());
    }
    is0() {
      return this.equals(Point.ZERO);
    }
    /**
     * Constant time multiplication.
     * Uses precomputed tables (signed fixed-window wNAF) when available.
     * Uses scalar blinding and avoids endomorphism splitting in the secret-scalar path.
     * @param scalar - by which the point would be multiplied
     * @returns New point
     */
    multiply(scalar) {
      if (!Fn.isValidNot0(scalar))
        throw new RangeError("invalid scalar: out of range");
      const { p, f } = wnaf.mulSecret(this, scalar, cofactor, normalize);
      return normalize([p, f])[0];
    }
    /**
     * Non-constant-time multiplication. Uses width-4 wNAF with GLV endomorphism splitting
     * when available (two half-width scalars sharing one halved doubling chain).
     * It's faster, but should only be used when you don't care about
     * an exposed secret key e.g. sig verification, which works over *public* keys.
     */
    multiplyUnsafe(scalar) {
      const p = this;
      const sc = scalar;
      if (!Fn.isValid(sc))
        throw new RangeError("invalid scalar: out of range");
      if (sc === _0n5 || p.is0())
        return Point.ZERO;
      if (sc === _1n4)
        return p;
      if (wnaf.hasWindowSize(this))
        return wnaf.mulUnsafe(p, sc, normalize);
      const points = [];
      const scalars = [];
      pushWnafPair(points, scalars, p, sc);
      return mulAddUnsafe(Point, points, scalars);
    }
    /**
     * Non-constant-time double-scalar multiplication `a⋅this + b⋅other` (Strauss–Shamir).
     * Both walks share one doubling chain via {@link mulAddUnsafe}, and GLV endomorphism
     * (when available) halves the chain again by splitting each scalar into two half-width
     * parts. Used by ECDSA verification and public-key recovery for `R = u1⋅G + u2⋅P`.
     * Only for public scalars.
     */
    mulAddUnsafe(a, other, b) {
      aprjpoint(other);
      const points = [];
      const scalars = [];
      pushWnafPair(points, scalars, this, a);
      pushWnafPair(points, scalars, other, b);
      return mulAddUnsafe(Point, points, scalars);
    }
    /**
     * Converts Projective point to affine (x, y) coordinates.
     * (X, Y, Z) ∋ (x=X/Z, y=Y/Z).
     * @param invertedZ - Z^-1 (inverted zero) - optional, precomputation is useful for invertBatch
     */
    toAffine(invertedZ) {
      const p = this;
      let iz = invertedZ;
      if (iz != null && !Fp.isValid(iz))
        throw new RangeError('"invertedZ" expected valid field element');
      const { X, Y, Z } = p;
      if (Fp.eql(Z, Fp.ONE))
        return { x: X, y: Y };
      const is0 = p.is0();
      if (iz == null)
        iz = is0 ? Fp.ONE : Fp.inv(Z);
      const x = Fp.mul(X, iz);
      const y = Fp.mul(Y, iz);
      const zz = Fp.mul(Z, iz);
      if (is0)
        return { x: Fp.ZERO, y: Fp.ZERO };
      if (!Fp.eql(zz, Fp.ONE))
        throw new Error("invZ was invalid");
      return { x, y };
    }
    /**
     * Checks whether Point is free of torsion elements (is in prime subgroup).
     * Always torsion-free for cofactor=1 curves.
     */
    isTorsionFree() {
      const { isTorsionFree } = extraOpts;
      if (cofactor === _1n4)
        return true;
      if (isTorsionFree)
        return isTorsionFree(Point, this);
      return wnaf.mulUnsafe(this, CURVE_ORDER).is0();
    }
    clearCofactor() {
      const { clearCofactor } = extraOpts;
      if (cofactor === _1n4)
        return this;
      if (clearCofactor)
        return clearCofactor(Point, this);
      return this.multiplyUnsafe(cofactor);
    }
    isSmallOrder() {
      if (cofactor === _1n4)
        return this.is0();
      return this.clearCofactor().is0();
    }
    toBytes(isCompressed = true) {
      abool(isCompressed, "isCompressed");
      this.assertValidity();
      return encodePoint(Point, this, isCompressed);
    }
    toHex(isCompressed = true) {
      return bytesToHex2(this.toBytes(isCompressed));
    }
    toString() {
      return `<Point ${this.is0() ? "ZERO" : this.toHex()}>`;
    }
  }
  const normalize = /* @__PURE__ */ __name((points) => normalizeZ(Point, points), "normalize");
  const wnaf = new ScalarMultiplier(Point, randomBytes3);
  if (wnaf.bits >= 6)
    Point.BASE.precompute(6);
  Object.freeze(Point.prototype);
  Object.freeze(Point);
  return Point;
}
__name(weierstrass, "weierstrass");
function pprefix(hasEvenY) {
  return Uint8Array.of(hasEvenY ? 2 : 3);
}
__name(pprefix, "pprefix");
function getWLengths(Fp, Fn) {
  return {
    secretKey: Fn.BYTES,
    publicKey: 1 + Fp.BYTES,
    publicKeyUncompressed: 1 + 2 * Fp.BYTES,
    publicKeyHasPrefix: true,
    // Raw compact `(r || s)` signature width; DER and recovered signatures use
    // different lengths outside this helper.
    signature: 2 * Fn.BYTES
  };
}
__name(getWLengths, "getWLengths");
function ecdh(Point, ecdhOpts = {}) {
  validatePointCons(Point);
  const { Fn } = Point;
  const randomBytes_ = ecdhOpts.randomBytes === void 0 ? randomBytes2 : ecdhOpts.randomBytes;
  const lengths = Object.assign(getWLengths(Point.Fp, Fn), {
    seed: Math.max(getMinHashLength(Fn.ORDER), 16)
  });
  function isValidSecretKey(secretKey) {
    try {
      const num = Fn.fromBytes(secretKey);
      return Fn.isValidNot0(num);
    } catch (error) {
      return false;
    }
  }
  __name(isValidSecretKey, "isValidSecretKey");
  function isValidPublicKey(publicKey, isCompressed) {
    const { publicKey: comp, publicKeyUncompressed } = lengths;
    try {
      const l = publicKey.length;
      if (isCompressed === true && l !== comp)
        return false;
      if (isCompressed === false && l !== publicKeyUncompressed)
        return false;
      return !!Point.fromBytes(publicKey);
    } catch (error) {
      return false;
    }
  }
  __name(isValidPublicKey, "isValidPublicKey");
  function randomSecretKey(seed) {
    seed = seed === void 0 ? randomBytes_(lengths.seed) : seed;
    return mapHashToField(abytes2(seed, lengths.seed, "seed"), Fn.ORDER);
  }
  __name(randomSecretKey, "randomSecretKey");
  function getPublicKey(secretKey, isCompressed = true) {
    return Point.BASE.multiply(Fn.fromBytes(secretKey)).toBytes(isCompressed);
  }
  __name(getPublicKey, "getPublicKey");
  function isProbPub(item) {
    const { secretKey, publicKey, publicKeyUncompressed } = lengths;
    const allowedLengths = Fn._lengths;
    if (!isBytes2(item))
      return void 0;
    const l = abytes2(item, void 0, "key").length;
    const isPub = l === publicKey || l === publicKeyUncompressed;
    const isSec = l === secretKey || !!allowedLengths?.includes(l);
    if (isPub && isSec)
      return void 0;
    return isPub;
  }
  __name(isProbPub, "isProbPub");
  function getSharedSecret(secretKeyA, publicKeyB, isCompressed = true) {
    if (isProbPub(secretKeyA) === true)
      throw new Error("first arg must be private key");
    if (isProbPub(publicKeyB) === false)
      throw new Error("second arg must be public key");
    const s = Fn.fromBytes(secretKeyA);
    const b = Point.fromBytes(publicKeyB);
    return b.multiply(s).toBytes(isCompressed);
  }
  __name(getSharedSecret, "getSharedSecret");
  const utils = {
    isValidSecretKey,
    isValidPublicKey,
    randomSecretKey
  };
  const keygen = createKeygen(randomSecretKey, getPublicKey);
  Object.freeze(utils);
  Object.freeze(lengths);
  return Object.freeze({ getPublicKey, getSharedSecret, keygen, Point, utils, lengths });
}
__name(ecdh, "ecdh");
function ecdsa(Point, hash, ecdsaOpts = {}) {
  validatePointCons(Point);
  const hash_ = hash;
  ahash(hash_);
  validateObject(ecdsaOpts, {}, {
    hmac: "function",
    lowS: "boolean",
    randomBytes: "function",
    bits2int: "function",
    bits2int_modN: "function"
  });
  const opts = Object.assign({}, ecdsaOpts);
  const randomBytes3 = opts.randomBytes === void 0 ? randomBytes2 : opts.randomBytes;
  const hmac2 = opts.hmac === void 0 ? (key, msg) => hmac(hash_, key, msg) : opts.hmac;
  const { Fp, Fn } = Point;
  const { ORDER: CURVE_ORDER, BITS: fnBits } = Fn;
  const blindLength = getMinHashLength(CURVE_ORDER);
  const csprng = probeRandomBytes(randomBytes3, blindLength);
  const { keygen, getPublicKey, getSharedSecret, utils, lengths } = ecdh(Point, opts);
  const defaultSigOpts = {
    prehash: true,
    lowS: typeof opts.lowS === "boolean" ? opts.lowS : true,
    format: "compact",
    extraEntropy: false
  };
  const hasLargeRecoveryLifts = CURVE_ORDER * _2n2 + _1n4 < Fp.ORDER;
  function isBiggerThanHalfOrder(number) {
    const HALF = CURVE_ORDER >> _1n4;
    return number > HALF;
  }
  __name(isBiggerThanHalfOrder, "isBiggerThanHalfOrder");
  function validateRS(title, num) {
    if (!Fn.isValidNot0(num))
      throw new Error(`invalid signature ${title}: out of range 1..Point.Fn.ORDER`);
    return num;
  }
  __name(validateRS, "validateRS");
  function assertFieldSignIsSupported() {
    if (!Fp.isOdd)
      throw new Error("Field doesn't support isOdd");
  }
  __name(assertFieldSignIsSupported, "assertFieldSignIsSupported");
  function getRecoveryBit(x, y, r) {
    assertFieldSignIsSupported();
    return (x === r ? 0 : 2) | Number(Fp.isOdd(y));
  }
  __name(getRecoveryBit, "getRecoveryBit");
  function assertRecoverableCurve() {
    if (hasLargeRecoveryLifts)
      throw new Error('"recovered" sig type is not supported for cofactor >2 curves');
  }
  __name(assertRecoverableCurve, "assertRecoverableCurve");
  function validateSigLength(bytes, format) {
    validateSigFormat(format);
    const size = lengths.signature;
    const sizer = format === "compact" ? size : format === "recovered" ? size + 1 : void 0;
    return abytes2(bytes, sizer);
  }
  __name(validateSigLength, "validateSigLength");
  class Signature {
    static {
      __name(this, "Signature");
    }
    r;
    s;
    recovery;
    constructor(r, s, recovery) {
      this.r = validateRS("r", r);
      this.s = validateRS("s", s);
      if (recovery != null) {
        assertRecoverableCurve();
        if (![0, 1, 2, 3].includes(recovery))
          throw new Error("invalid recovery id");
        this.recovery = recovery;
      }
      Object.freeze(this);
    }
    static fromBytes(bytes, format = defaultSigOpts.format) {
      validateSigLength(bytes, format);
      let recid;
      if (format === "der") {
        const { r: r2, s: s2 } = DER.toSig(abytes2(bytes));
        return new Signature(r2, s2);
      }
      if (format === "recovered") {
        recid = bytes[0];
        format = "compact";
        bytes = bytes.subarray(1);
      }
      const L = lengths.signature / 2;
      const r = bytes.subarray(0, L);
      const s = bytes.subarray(L, L * 2);
      return new Signature(Fn.fromBytes(r), Fn.fromBytes(s), recid);
    }
    static fromHex(hex2, format) {
      return this.fromBytes(hexToBytes2(hex2), format);
    }
    assertRecovery() {
      const { recovery } = this;
      if (recovery == null)
        throw new Error("invalid recovery id: must be present");
      return recovery;
    }
    addRecoveryBit(recovery) {
      return new Signature(this.r, this.s, recovery);
    }
    // Unlike the top-level helper below, this method expects a digest that has
    // already been hashed to the curve's message representative.
    recoverPublicKey(messageHash) {
      const { r, s } = this;
      const recovery = this.assertRecovery();
      const radj = recovery === 2 || recovery === 3 ? r + CURVE_ORDER : r;
      if (!Fp.isValid(radj))
        throw new Error("invalid recovery id: sig.r+curve.n != R.x");
      const x = Fp.toBytes(radj);
      const R = Point.fromBytes(concatBytes2(pprefix((recovery & 1) === 0), x));
      const ir = Fn.inv(radj);
      const h = bits2int_modN(abytes2(messageHash, void 0, "msgHash"));
      const u1 = Fn.create(-h * ir);
      const u2 = Fn.create(s * ir);
      const Q = Point.BASE.mulAddUnsafe(u1, R, u2);
      if (Q.is0())
        throw new Error("invalid recovery: point at infinify");
      Q.assertValidity();
      return Q;
    }
    // Signatures should be low-s, to prevent malleability.
    hasHighS() {
      return isBiggerThanHalfOrder(this.s);
    }
    toBytes(format = defaultSigOpts.format) {
      validateSigFormat(format);
      if (format === "der")
        return hexToBytes2(DER.hexFromSig(this));
      const { r, s } = this;
      const rb = Fn.toBytes(r);
      const sb = Fn.toBytes(s);
      if (format === "recovered") {
        assertRecoverableCurve();
        return concatBytes2(Uint8Array.of(this.assertRecovery()), rb, sb);
      }
      return concatBytes2(rb, sb);
    }
    toHex(format) {
      return bytesToHex2(this.toBytes(format));
    }
  }
  Object.freeze(Signature.prototype);
  Object.freeze(Signature);
  const bits2int = opts.bits2int === void 0 ? /* @__PURE__ */ __name(function bits2int_def(bytes) {
    if (bytes.length > 8192)
      throw new Error("input is too large");
    const num = bytesToNumberBE(bytes);
    const delta = bytes.length * 8 - fnBits;
    return delta > 0 ? num >> BigInt(delta) : num;
  }, "bits2int_def") : opts.bits2int;
  const bits2int_modN = opts.bits2int_modN === void 0 ? /* @__PURE__ */ __name(function bits2int_modN_def(bytes) {
    return Fn.create(bits2int(bytes));
  }, "bits2int_modN_def") : opts.bits2int_modN;
  const ORDER_MASK = bitMask(fnBits);
  function int2octets(num) {
    aInRange("num < 2^" + fnBits, num, _0n5, ORDER_MASK);
    return Fn.toBytes(num);
  }
  __name(int2octets, "int2octets");
  function validateMsgAndHash(message, prehash) {
    abytes2(message, void 0, "message");
    return prehash ? abytes2(hash_(message), void 0, "prehashed message") : message;
  }
  __name(validateMsgAndHash, "validateMsgAndHash");
  function prepSig(message, secretKey, opts2) {
    const { lowS, prehash, extraEntropy } = validateSigOpts(opts2, defaultSigOpts);
    message = validateMsgAndHash(message, prehash);
    const h1int = bits2int_modN(message);
    const d = Fn.fromBytes(secretKey);
    if (!Fn.isValidNot0(d))
      throw new Error("invalid private key");
    const seedArgs = [int2octets(d), int2octets(h1int)];
    if (extraEntropy != null && extraEntropy !== false) {
      const e = extraEntropy === true ? randomBytes3(lengths.secretKey) : extraEntropy;
      seedArgs.push(abytes2(e, void 0, "extraEntropy"));
    }
    const seed = concatBytes2(...seedArgs);
    const m = h1int;
    function k2sig(kBytes) {
      const k = bits2int(kBytes);
      if (!Fn.isValidNot0(k))
        return;
      const q = Point.BASE.multiply(k).toAffine();
      const r = Fn.create(q.x);
      if (r === _0n5)
        return;
      let s;
      if (csprng !== void 0) {
        const b = bytesToNumberBE(mapHashToField(csprng(blindLength), CURVE_ORDER));
        const ibk = Fn.inv(Fn.mul(b, k));
        const bm = Fn.mul(b, m);
        const bd = Fn.mul(b, d);
        s = Fn.create(ibk * Fn.create(bm + bd * r));
      } else {
        const ik = invertCt(k, CURVE_ORDER);
        s = Fn.create(ik * Fn.create(m + r * d));
      }
      if (s === _0n5)
        return;
      let recovery = getRecoveryBit(q.x, q.y, r);
      let normS = s;
      if (lowS && isBiggerThanHalfOrder(s)) {
        normS = Fn.neg(s);
        recovery ^= 1;
      }
      return new Signature(r, normS, hasLargeRecoveryLifts ? void 0 : recovery);
    }
    __name(k2sig, "k2sig");
    return { seed, k2sig };
  }
  __name(prepSig, "prepSig");
  function sign(message, secretKey, opts2 = {}) {
    const { seed, k2sig } = prepSig(message, secretKey, opts2);
    const drbg = createHmacDrbg(hash_.outputLen, Fn.BYTES, hmac2);
    const sig = drbg(seed, k2sig);
    return sig.toBytes(opts2.format);
  }
  __name(sign, "sign");
  function verify(signature, message, publicKey, opts2 = {}) {
    const { lowS, prehash, format } = validateSigOpts(opts2, defaultSigOpts);
    publicKey = abytes2(publicKey, void 0, "publicKey");
    message = validateMsgAndHash(message, prehash);
    if (!isBytes2(signature)) {
      const end = signature instanceof Signature ? ", use sig.toBytes()" : "";
      throw new Error("verify expects Uint8Array signature" + end);
    }
    validateSigLength(signature, format);
    try {
      const sig = Signature.fromBytes(signature, format);
      const P = Point.fromBytes(publicKey);
      if (lowS && sig.hasHighS())
        return false;
      const { r, s } = sig;
      const h = bits2int_modN(message);
      const is = Fn.inv(s);
      const u1 = Fn.create(h * is);
      const u2 = Fn.create(r * is);
      const R = Point.BASE.mulAddUnsafe(u1, P, u2);
      if (R.is0())
        return false;
      const q = R.toAffine();
      const v = Fn.create(q.x);
      if (v !== r)
        return false;
      if (format === "recovered" && sig.recovery !== getRecoveryBit(q.x, q.y, r))
        return false;
      return true;
    } catch (e) {
      return false;
    }
  }
  __name(verify, "verify");
  function recoverPublicKey(signature, message, opts2 = {}) {
    const { prehash } = validateSigOpts(opts2, defaultSigOpts);
    message = validateMsgAndHash(message, prehash);
    return Signature.fromBytes(signature, "recovered").recoverPublicKey(message).toBytes();
  }
  __name(recoverPublicKey, "recoverPublicKey");
  return Object.freeze({
    keygen,
    getPublicKey,
    getSharedSecret,
    utils,
    lengths,
    Point,
    sign,
    verify,
    recoverPublicKey,
    Signature,
    hash: hash_
  });
}
__name(ecdsa, "ecdsa");

// node_modules/@noble/curves/secp256k1.js
var secp256k1_CURVE = {
  p: BigInt("0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f"),
  n: BigInt("0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141"),
  h: BigInt(1),
  a: BigInt(0),
  b: BigInt(7),
  Gx: BigInt("0x79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"),
  Gy: BigInt("0x483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8")
};
var secp256k1_ENDO = {
  beta: BigInt("0x7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee"),
  basises: [
    [BigInt("0x3086d221a7d46bcde86c90e49284eb15"), -BigInt("0xe4437ed6010e88286f547fa90abfe4c3")],
    [BigInt("0x114ca50f7a8e2f3f657c1108d9d44cfd8"), BigInt("0x3086d221a7d46bcde86c90e49284eb15")]
  ]
};
var _2n3 = /* @__PURE__ */ BigInt(2);
function sqrtMod(y) {
  const P = secp256k1_CURVE.p;
  const _3n3 = BigInt(3), _6n = BigInt(6), _11n = BigInt(11), _22n = BigInt(22);
  const _23n = BigInt(23), _44n = BigInt(44), _88n = BigInt(88);
  const b2 = y * y * y % P;
  const b3 = b2 * b2 * y % P;
  const b6 = pow2(b3, _3n3, P) * b3 % P;
  const b9 = pow2(b6, _3n3, P) * b3 % P;
  const b11 = pow2(b9, _2n3, P) * b2 % P;
  const b22 = pow2(b11, _11n, P) * b11 % P;
  const b44 = pow2(b22, _22n, P) * b22 % P;
  const b88 = pow2(b44, _44n, P) * b44 % P;
  const b176 = pow2(b88, _88n, P) * b88 % P;
  const b220 = pow2(b176, _44n, P) * b44 % P;
  const b223 = pow2(b220, _3n3, P) * b3 % P;
  const t1 = pow2(b223, _23n, P) * b22 % P;
  const t2 = pow2(t1, _6n, P) * b2 % P;
  const root = pow2(t2, _2n3, P);
  if (!Fpk1.eql(Fpk1.sqr(root), y))
    throw new Error("Cannot find square root");
  return root;
}
__name(sqrtMod, "sqrtMod");
var Fpk1 = /* @__PURE__ */ Field(secp256k1_CURVE.p, { sqrt: sqrtMod });
var Pointk1 = /* @__PURE__ */ weierstrass(secp256k1_CURVE, {
  Fp: Fpk1,
  endo: secp256k1_ENDO
});
var secp256k1 = /* @__PURE__ */ ecdsa(Pointk1, sha256);

// node_modules/@noble/hashes/_u64.js
var U32_MASK64 = /* @__PURE__ */ BigInt(2 ** 32 - 1);
var _32n = /* @__PURE__ */ BigInt(32);
function fromBig(n, le = false) {
  if (le)
    return { h: Number(n & U32_MASK64), l: Number(n >> _32n & U32_MASK64) };
  return { h: Number(n >> _32n & U32_MASK64) | 0, l: Number(n & U32_MASK64) | 0 };
}
__name(fromBig, "fromBig");
function split(lst, le = false) {
  const len = lst.length;
  let Ah = new Uint32Array(len);
  let Al = new Uint32Array(len);
  for (let i = 0; i < len; i++) {
    const { h, l } = fromBig(lst[i], le);
    [Ah[i], Al[i]] = [h, l];
  }
  return [Ah, Al];
}
__name(split, "split");
var rotlSH = /* @__PURE__ */ __name((h, l, s) => h << s | l >>> 32 - s, "rotlSH");
var rotlSL = /* @__PURE__ */ __name((h, l, s) => l << s | h >>> 32 - s, "rotlSL");
var rotlBH = /* @__PURE__ */ __name((h, l, s) => l << s - 32 | h >>> 64 - s, "rotlBH");
var rotlBL = /* @__PURE__ */ __name((h, l, s) => h << s - 32 | l >>> 64 - s, "rotlBL");

// node_modules/@noble/hashes/utils.js
function isBytes3(a) {
  return a instanceof Uint8Array || ArrayBuffer.isView(a) && a.constructor.name === "Uint8Array";
}
__name(isBytes3, "isBytes");
function anumber3(n, title = "") {
  if (!Number.isSafeInteger(n) || n < 0) {
    const prefix = title && `"${title}" `;
    throw new Error(`${prefix}expected integer >= 0, got ${n}`);
  }
}
__name(anumber3, "anumber");
function abytes3(value, length, title = "") {
  const bytes = isBytes3(value);
  const len = value?.length;
  const needsLen = length !== void 0;
  if (!bytes || needsLen && len !== length) {
    const prefix = title && `"${title}" `;
    const ofLen = needsLen ? ` of length ${length}` : "";
    const got = bytes ? `length=${len}` : `type=${typeof value}`;
    throw new Error(prefix + "expected Uint8Array" + ofLen + ", got " + got);
  }
  return value;
}
__name(abytes3, "abytes");
function aexists2(instance, checkFinished = true) {
  if (instance.destroyed)
    throw new Error("Hash instance has been destroyed");
  if (checkFinished && instance.finished)
    throw new Error("Hash#digest() has already been called");
}
__name(aexists2, "aexists");
function aoutput2(out, instance) {
  abytes3(out, void 0, "digestInto() output");
  const min = instance.outputLen;
  if (out.length < min) {
    throw new Error('"digestInto() output" expected to be of length >=' + min);
  }
}
__name(aoutput2, "aoutput");
function u32(arr) {
  return new Uint32Array(arr.buffer, arr.byteOffset, Math.floor(arr.byteLength / 4));
}
__name(u32, "u32");
function clean2(...arrays) {
  for (let i = 0; i < arrays.length; i++) {
    arrays[i].fill(0);
  }
}
__name(clean2, "clean");
var isLE = /* @__PURE__ */ (() => new Uint8Array(new Uint32Array([287454020]).buffer)[0] === 68)();
function byteSwap(word) {
  return word << 24 & 4278190080 | word << 8 & 16711680 | word >>> 8 & 65280 | word >>> 24 & 255;
}
__name(byteSwap, "byteSwap");
function byteSwap32(arr) {
  for (let i = 0; i < arr.length; i++) {
    arr[i] = byteSwap(arr[i]);
  }
  return arr;
}
__name(byteSwap32, "byteSwap32");
var swap32IfBE = isLE ? (u) => u : byteSwap32;
function createHasher2(hashCons, info = {}) {
  const hashC = /* @__PURE__ */ __name((msg, opts) => hashCons(opts).update(msg).digest(), "hashC");
  const tmp = hashCons(void 0);
  hashC.outputLen = tmp.outputLen;
  hashC.blockLen = tmp.blockLen;
  hashC.create = (opts) => hashCons(opts);
  Object.assign(hashC, info);
  return Object.freeze(hashC);
}
__name(createHasher2, "createHasher");

// node_modules/@noble/hashes/sha3.js
var _0n6 = BigInt(0);
var _1n5 = BigInt(1);
var _2n4 = BigInt(2);
var _7n2 = BigInt(7);
var _256n = BigInt(256);
var _0x71n = BigInt(113);
var SHA3_PI = [];
var SHA3_ROTL = [];
var _SHA3_IOTA = [];
for (let round = 0, R = _1n5, x = 1, y = 0; round < 24; round++) {
  [x, y] = [y, (2 * x + 3 * y) % 5];
  SHA3_PI.push(2 * (5 * y + x));
  SHA3_ROTL.push((round + 1) * (round + 2) / 2 % 64);
  let t = _0n6;
  for (let j = 0; j < 7; j++) {
    R = (R << _1n5 ^ (R >> _7n2) * _0x71n) % _256n;
    if (R & _2n4)
      t ^= _1n5 << (_1n5 << BigInt(j)) - _1n5;
  }
  _SHA3_IOTA.push(t);
}
var IOTAS = split(_SHA3_IOTA, true);
var SHA3_IOTA_H = IOTAS[0];
var SHA3_IOTA_L = IOTAS[1];
var rotlH = /* @__PURE__ */ __name((h, l, s) => s > 32 ? rotlBH(h, l, s) : rotlSH(h, l, s), "rotlH");
var rotlL = /* @__PURE__ */ __name((h, l, s) => s > 32 ? rotlBL(h, l, s) : rotlSL(h, l, s), "rotlL");
function keccakP(s, rounds = 24) {
  const B = new Uint32Array(5 * 2);
  for (let round = 24 - rounds; round < 24; round++) {
    for (let x = 0; x < 10; x++)
      B[x] = s[x] ^ s[x + 10] ^ s[x + 20] ^ s[x + 30] ^ s[x + 40];
    for (let x = 0; x < 10; x += 2) {
      const idx1 = (x + 8) % 10;
      const idx0 = (x + 2) % 10;
      const B0 = B[idx0];
      const B1 = B[idx0 + 1];
      const Th = rotlH(B0, B1, 1) ^ B[idx1];
      const Tl = rotlL(B0, B1, 1) ^ B[idx1 + 1];
      for (let y = 0; y < 50; y += 10) {
        s[x + y] ^= Th;
        s[x + y + 1] ^= Tl;
      }
    }
    let curH = s[2];
    let curL = s[3];
    for (let t = 0; t < 24; t++) {
      const shift = SHA3_ROTL[t];
      const Th = rotlH(curH, curL, shift);
      const Tl = rotlL(curH, curL, shift);
      const PI = SHA3_PI[t];
      curH = s[PI];
      curL = s[PI + 1];
      s[PI] = Th;
      s[PI + 1] = Tl;
    }
    for (let y = 0; y < 50; y += 10) {
      for (let x = 0; x < 10; x++)
        B[x] = s[y + x];
      for (let x = 0; x < 10; x++)
        s[y + x] ^= ~B[(x + 2) % 10] & B[(x + 4) % 10];
    }
    s[0] ^= SHA3_IOTA_H[round];
    s[1] ^= SHA3_IOTA_L[round];
  }
  clean2(B);
}
__name(keccakP, "keccakP");
var Keccak = class _Keccak {
  static {
    __name(this, "Keccak");
  }
  state;
  pos = 0;
  posOut = 0;
  finished = false;
  state32;
  destroyed = false;
  blockLen;
  suffix;
  outputLen;
  enableXOF = false;
  rounds;
  // NOTE: we accept arguments in bytes instead of bits here.
  constructor(blockLen, suffix, outputLen, enableXOF = false, rounds = 24) {
    this.blockLen = blockLen;
    this.suffix = suffix;
    this.outputLen = outputLen;
    this.enableXOF = enableXOF;
    this.rounds = rounds;
    anumber3(outputLen, "outputLen");
    if (!(0 < blockLen && blockLen < 200))
      throw new Error("only keccak-f1600 function is supported");
    this.state = new Uint8Array(200);
    this.state32 = u32(this.state);
  }
  clone() {
    return this._cloneInto();
  }
  keccak() {
    swap32IfBE(this.state32);
    keccakP(this.state32, this.rounds);
    swap32IfBE(this.state32);
    this.posOut = 0;
    this.pos = 0;
  }
  update(data) {
    aexists2(this);
    abytes3(data);
    const { blockLen, state } = this;
    const len = data.length;
    for (let pos = 0; pos < len; ) {
      const take = Math.min(blockLen - this.pos, len - pos);
      for (let i = 0; i < take; i++)
        state[this.pos++] ^= data[pos++];
      if (this.pos === blockLen)
        this.keccak();
    }
    return this;
  }
  finish() {
    if (this.finished)
      return;
    this.finished = true;
    const { state, suffix, pos, blockLen } = this;
    state[pos] ^= suffix;
    if ((suffix & 128) !== 0 && pos === blockLen - 1)
      this.keccak();
    state[blockLen - 1] ^= 128;
    this.keccak();
  }
  writeInto(out) {
    aexists2(this, false);
    abytes3(out);
    this.finish();
    const bufferOut = this.state;
    const { blockLen } = this;
    for (let pos = 0, len = out.length; pos < len; ) {
      if (this.posOut >= blockLen)
        this.keccak();
      const take = Math.min(blockLen - this.posOut, len - pos);
      out.set(bufferOut.subarray(this.posOut, this.posOut + take), pos);
      this.posOut += take;
      pos += take;
    }
    return out;
  }
  xofInto(out) {
    if (!this.enableXOF)
      throw new Error("XOF is not possible for this instance");
    return this.writeInto(out);
  }
  xof(bytes) {
    anumber3(bytes);
    return this.xofInto(new Uint8Array(bytes));
  }
  digestInto(out) {
    aoutput2(out, this);
    if (this.finished)
      throw new Error("digest() was already called");
    this.writeInto(out);
    this.destroy();
    return out;
  }
  digest() {
    return this.digestInto(new Uint8Array(this.outputLen));
  }
  destroy() {
    this.destroyed = true;
    clean2(this.state);
  }
  _cloneInto(to) {
    const { blockLen, suffix, outputLen, rounds, enableXOF } = this;
    to ||= new _Keccak(blockLen, suffix, outputLen, enableXOF, rounds);
    to.state32.set(this.state32);
    to.pos = this.pos;
    to.posOut = this.posOut;
    to.finished = this.finished;
    to.rounds = rounds;
    to.suffix = suffix;
    to.outputLen = outputLen;
    to.enableXOF = enableXOF;
    to.destroyed = this.destroyed;
    return to;
  }
};
var genKeccak = /* @__PURE__ */ __name((suffix, blockLen, outputLen, info = {}) => createHasher2(() => new Keccak(blockLen, suffix, outputLen), info), "genKeccak");
var keccak_256 = /* @__PURE__ */ genKeccak(1, 136, 32);

// worker/git-base-auth.mjs
var USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
var USDC_BASE_SEPOLIA = "0x036CbD5886E7d24Dd49DaFb5968bA0C771E4d7b9";
var TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef";
var ERC1271_MAGIC = "0x1626ba7e";
var MIN_CONFIRMATIONS = 3;
var BASE_CHAIN_ID = 8453;
var BASE_SEPOLIA_CHAIN_ID = 84532;
var X402_VERSION = 1;
var enc = new TextEncoder();
var lc = /* @__PURE__ */ __name((s) => String(s || "").toLowerCase(), "lc");
var usdcFor = /* @__PURE__ */ __name((net) => net === "base-sepolia" ? USDC_BASE_SEPOLIA : USDC_BASE, "usdcFor");
var canonNet = /* @__PURE__ */ __name((n) => n === "eip155:8453" ? "base" : n === "eip155:84532" ? "base-sepolia" : n, "canonNet");
function rpcUrls(env, net) {
  const configured = [env.KOTOBASE_EVM_RPC_BASE, env.KOTOBASE_EVM_RPC].filter(Boolean);
  const keyless = canonNet(net) === "base-sepolia" ? ["https://base-sepolia.gateway.tenderly.co", "https://sepolia.base.org"] : [
    "https://base.gateway.tenderly.co",
    "https://gateway.tenderly.co/public/base",
    "https://base.drpc.org",
    "https://base-rpc.publicnode.com",
    "https://mainnet.base.org"
  ];
  return [...configured, ...keyless];
}
__name(rpcUrls, "rpcUrls");
async function rpcCall(env, net, method, params) {
  let lastErr = new Error("no rpc configured");
  for (const url of rpcUrls(env, net)) {
    try {
      const r = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params })
      });
      if (!r.ok) {
        lastErr = new Error("rpc status " + r.status);
        continue;
      }
      const j = await r.json();
      if (j.error) {
        lastErr = new Error("rpc error: " + (j.error.message || j.error.code));
        continue;
      }
      return j.result;
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr;
}
__name(rpcCall, "rpcCall");
var hexToLong = /* @__PURE__ */ __name((h) => {
  if (typeof h !== "string" || !/^0x[0-9a-f]+$/i.test(h)) return null;
  try {
    return Number(BigInt(h));
  } catch (_) {
    return null;
  }
}, "hexToLong");
var hexToBytes3 = /* @__PURE__ */ __name((h) => {
  const s = h.startsWith("0x") ? h.slice(2) : h;
  if (s.length % 2 !== 0 || /[^0-9a-f]/i.test(s)) return null;
  return Uint8Array.from((s.match(/../g) || []).map((x) => parseInt(x, 16)));
}, "hexToBytes");
var bytesToHex3 = /* @__PURE__ */ __name((b) => [...b].map((x) => x.toString(16).padStart(2, "0")).join(""), "bytesToHex");
function eip191Digest(message) {
  const payload = enc.encode(message);
  const prefix = enc.encode(`Ethereum Signed Message:
${payload.length}`);
  const buf = new Uint8Array(prefix.length + payload.length);
  buf.set(prefix, 0);
  buf.set(payload, prefix.length);
  return keccak_256(buf);
}
__name(eip191Digest, "eip191Digest");
function siweMessage(p) {
  const lines = [
    `${p.domain} wants you to sign in with your Ethereum account:`,
    String(p.iss || "").split(":").at(-1),
    "",
    `URI: ${p.aud}`,
    `Version: ${p.version}`,
    `Chain ID: ${p.chainId}`,
    `Nonce: ${p.nonce}`,
    `Issued At: ${p.iat}`
  ];
  if (p.exp) lines.push(`Expiration Time: ${p.exp}`);
  if (p.resources?.length) lines.push("Resources:", ...p.resources.map((r) => `- ${r}`));
  return lines.join("\n");
}
__name(siweMessage, "siweMessage");
function recoverAddress(message, sigHex) {
  try {
    const sig = hexToBytes3(sigHex);
    if (!sig || sig.length !== 65) return null;
    const v = sig[64];
    if (v !== 27 && v !== 28) return null;
    const digest = eip191Digest(message);
    const noble = new Uint8Array(65);
    noble[0] = v - 27;
    noble.set(sig.slice(0, 64), 1);
    const pub = secp256k1.Signature.fromBytes(noble, "recovered").recoverPublicKey(digest).toBytes(false);
    return "0x" + bytesToHex3(keccak_256(pub.slice(1)).slice(12));
  } catch (_) {
    return null;
  }
}
__name(recoverAddress, "recoverAddress");
var PKH_RE = /^did:pkh:eip155:(\d+):0x[0-9a-fA-F]{40}$/;
function parsePkh(did) {
  const m = PKH_RE.exec(did || "");
  if (!m) return null;
  return { chainId: Number(m[1]), address: lc(did.slice(did.lastIndexOf(":") + 1)) };
}
__name(parsePkh, "parsePkh");
var netForChainId = /* @__PURE__ */ __name((cid) => cid === BASE_CHAIN_ID ? "base" : cid === BASE_SEPOLIA_CHAIN_ID ? "base-sepolia" : null, "netForChainId");
async function erc1271Valid(env, net, contract, digest32, sigHex) {
  const data = "0x1626ba7e" + bytesToHex3(digest32).padStart(64, "0") + "000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000" + (sigHex.startsWith("0x") ? (sigHex.length - 2) / 2 : sigHex.length / 2).toString(16).padStart(64, "0") + (sigHex.startsWith("0x") ? sigHex.slice(2) : sigHex);
  try {
    const out = await rpcCall(
      env,
      net,
      "eth_call",
      [{ to: contract, data }, "latest"]
    );
    return out && lc(out).startsWith(ERC1271_MAGIC);
  } catch (_) {
    return false;
  }
}
__name(erc1271Valid, "erc1271Valid");
async function verifyPkhCacao(env, payload, signature) {
  const pkh = parsePkh(payload.iss);
  if (!pkh) return { ok: false, reason: "not-a-pkh-issuer" };
  const net = netForChainId(pkh.chainId);
  if (!net) return { ok: false, reason: "chain-not-allowed" };
  if (!payload.domain || !payload.aud || !payload.nonce) return { ok: false, reason: "incomplete-siwe" };
  const iat = Date.parse(payload.iat);
  const exp = payload.exp ? Date.parse(payload.exp) : NaN;
  const now = Date.now();
  if (!Number.isFinite(iat) || iat > now + 3e5) return { ok: false, reason: "bad-iat" };
  if (Number.isFinite(exp) && now >= exp) return { ok: false, reason: "expired" };
  const message = siweMessage({ ...payload, chainId: pkh.chainId });
  const sigHex = typeof signature === "string" && signature.length === 130 + 2 ? signature.startsWith("0x") ? signature : "0x" + signature : null;
  if (sigHex) {
    const recovered = recoverAddress(message, sigHex);
    if (recovered && lc(recovered) === pkh.address) return { ok: true, address: pkh.address, signer: "eoa", net };
    return { ok: false, reason: "eoa-signature-mismatch" };
  }
  const code = await rpcCall(env, net, "eth_getCode", [pkh.address, "latest"]).catch(() => null);
  if (!code || code === "0x") {
    return { ok: false, reason: sigHex ? "eoa-signature-mismatch" : "no-code-and-not-65b-sig" };
  }
  const digest = keccak_256(enc.encode(message));
  const okSig = typeof signature === "string" ? await erc1271Valid(env, net, pkh.address, digest, signature.startsWith("0x") ? signature : "0x" + signature) : false;
  return okSig ? { ok: true, address: pkh.address, signer: "erc1271", net } : { ok: false, reason: "erc1271-invalid" };
}
__name(verifyPkhCacao, "verifyPkhCacao");
var MICRO = 1e6;
var DEFAULT_USD = 1e-3;
function quotedUsd(declared, floor) {
  const d = Number.parseFloat(declared || "");
  const f = Number(floor ?? DEFAULT_USD);
  if (!Number.isFinite(d) || d <= 0) return f;
  return Math.max(d, f);
}
__name(quotedUsd, "quotedUsd");
var usdToMicros = /* @__PURE__ */ __name((usd) => BigInt(Math.ceil(usd * MICRO)).toString(), "usdToMicros");
function requirement({ payTo, usd, resource, net, scheme, facilitator }) {
  const canonical = canonNet(net);
  const req = {
    scheme,
    network: canonical,
    maxAmountRequired: usdToMicros(usd),
    resource,
    description: "kotobase git read: " + resource,
    mimeType: "application/json",
    payTo,
    maxTimeoutSeconds: 60,
    asset: usdcFor(canonical)
  };
  if (scheme === "exact") {
    req.extra = canonical === "base-sepolia" ? { name: "USDC", version: "2" } : { name: "USD Coin", version: "2" };
    if (facilitator) req.facilitator = facilitator;
  }
  return req;
}
__name(requirement, "requirement");
function challenge(accepts, error) {
  return { x402Version: X402_VERSION, accepts, error: error || "" };
}
__name(challenge, "challenge");
var b64decode = /* @__PURE__ */ __name((s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(s.length / 4) * 4, "=")), (c) => c.charCodeAt(0)), "b64decode");
function decodePayment(header) {
  try {
    const j = JSON.parse(new TextDecoder().decode(b64decode(header)));
    if (typeof j !== "object" || !j || typeof j.scheme !== "string") return null;
    j.network = canonNet(j.network);
    return j;
  } catch (_) {
    return null;
  }
}
__name(decodePayment, "decodePayment");
function payloadErrors(payment, req, nowSec) {
  const errs = [];
  if (payment.scheme !== req.scheme) errs.push("scheme-mismatch");
  if (payment.network !== req.network) errs.push("network-mismatch");
  const p = payment.payload || {};
  if (req.scheme === "exact") {
    const auth = p.authorization || {};
    if (lc(auth.to) !== lc(req.payTo)) errs.push("wrong-recipient");
    const value = Number.parseInt(String(auth.value), 10);
    if (!Number.isFinite(value) || value < Number(req.maxAmountRequired)) errs.push("underpaid");
    if (auth.validBefore && Number.parseInt(auth.validBefore, 10) <= nowSec) errs.push("authorization-expired");
    if (auth.validAfter && Number.parseInt(auth.validAfter, 10) > nowSec) errs.push("authorization-not-yet-valid");
    if (typeof p.signature !== "string" || !p.signature) errs.push("missing-signature");
  } else if (req.scheme === "transaction") {
    if (typeof p.txHash !== "string" || !/^0x[0-9a-fA-F]{64}$/.test(p.txHash)) errs.push("missing-tx-hash");
    if (typeof p.from !== "string" || !/^0x[0-9a-fA-F]{40}$/.test(p.from)) errs.push("missing-payer");
  }
  return errs;
}
__name(payloadErrors, "payloadErrors");
async function verifyTxPayment(env, req, payment) {
  const net = req.network;
  const treasury = env.KOTOBASE_TREASURY_ADDR;
  if (!treasury) return { ok: false, reason: "treasury-not-configured" };
  const txHash = payment.payload.txHash;
  const payer = lc(payment.payload.from);
  const requiredMicros = BigInt(req.maxAmountRequired);
  let receipt, headHex;
  try {
    [receipt, headHex] = await Promise.all([
      rpcCall(env, net, "eth_getTransactionReceipt", [txHash]),
      rpcCall(env, net, "eth_blockNumber", [])
    ]);
  } catch (_) {
    return { ok: false, reason: "rpc-unavailable" };
  }
  if (!receipt) return { ok: false, reason: "tx-not-found" };
  if (lc(receipt.status) !== "0x1") return { ok: false, reason: "tx-reverted" };
  const head = hexToLong(headHex);
  const txBlock = hexToLong(receipt.blockNumber);
  if (head === null || txBlock === null) return { ok: false, reason: "bad-block-number" };
  const confirmations = head - txBlock + 1;
  if (confirmations < MIN_CONFIRMATIONS) return { ok: false, reason: "insufficient-confirmations" };
  const usdc = lc(usdcFor(net));
  const transfer = (receipt.logs || []).find((l) => l.address && lc(l.address) === usdc && Array.isArray(l.topics) && l.topics.length >= 3 && lc(l.topics[0]) === TRANSFER_TOPIC);
  if (!transfer) return { ok: false, reason: "no-usdc-transfer" };
  const to = "0x" + lc(transfer.topics[2]).slice(-40);
  if (to !== lc(treasury)) return { ok: false, reason: "wrong-recipient" };
  const paidMicros = BigInt(hexToLong(transfer.data) ?? 0);
  if (paidMicros < requiredMicros) return { ok: false, reason: "underpaid" };
  return { ok: true, payer, paidMicros: paidMicros.toString() };
}
__name(verifyTxPayment, "verifyTxPayment");
async function spendReserve(env, req, verification, ttlHours = 72) {
  const store = env.GIT_STORE;
  if (!store) return { allow: false, reason: "spend-store-unavailable" };
  const k = "x402-spend:" + req.network + ":" + (verification.txHash || verification.payer + ":" + verification.paidMicros);
  const existing = await store.get(k);
  if (existing) return { allow: false, reason: "tx-already-spent" };
  await store.put(
    k,
    JSON.stringify({ paidMicros: verification.paidMicros, payer: verification.payer, at: Date.now() }),
    { expirationTtl: Math.max(3600, ttlHours * 3600) }
  );
  return { allow: true };
}
__name(spendReserve, "spendReserve");
async function settleExact(env, payment, req) {
  const facilitator = env.KOTOBASE_X402_FACILITATOR;
  if (!facilitator) return null;
  const r = await fetch(facilitator.replace(/\/+$/, "") + "/settle", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ x402Version: X402_VERSION, paymentPayload: payment, paymentRequirements: req })
  });
  const j = await r.json();
  const value = payment?.payload?.authorization?.value;
  return {
    included: Boolean(j.success),
    reason: j.errorReason || j.error || null,
    tx: j.transaction || null,
    payer: j.payer || payment?.payload?.authorization?.from || null,
    paidMicros: value != null && !Number.isNaN(Number.parseInt(value, 10)) ? String(value) : null,
    txHash: j.transaction || null
  };
}
__name(settleExact, "settleExact");
function paymentRequiredResponse(accepts, error) {
  return new Response(JSON.stringify(challenge(accepts, error), null, 2), {
    status: 402,
    headers: { "content-type": "application/json; charset=utf-8" }
  });
}
__name(paymentRequiredResponse, "paymentRequiredResponse");

// worker/git-worker.mjs
var json = /* @__PURE__ */ __name((value, status = 200, headers = {}) => new Response(JSON.stringify(value), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", ...headers }
}), "json");
var text = /* @__PURE__ */ __name((value, status = 200, headers = {}) => new Response(value, {
  status,
  headers: { "content-type": "text/plain; charset=utf-8", ...headers }
}), "text");
var validRepo = /* @__PURE__ */ __name((s) => /^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/.test(s), "validRepo");
var privateRepoPrefixes = /* @__PURE__ */ __name((env) => (env.PRIVATE_GIT_REPO_PREFIXES || "").split(",").map((s) => s.trim()).filter(Boolean), "privateRepoPrefixes");
var isPrivateRepo = /* @__PURE__ */ __name((env, repo) => privateRepoPrefixes(env).some((prefix) => repo === prefix || repo.startsWith(`${prefix}/`)), "isPrivateRepo");
var paidRepoNames = /* @__PURE__ */ __name((env) => (env.PAID_GIT_REPOS || "").split(",").map((s) => s.trim()).filter(Boolean), "paidRepoNames");
var isPaidRepo = /* @__PURE__ */ __name((env, repo) => paidRepoNames(env).some((n) => n === repo), "isPaidRepo");
async function walletCacaoAuthorized(request, env, repo) {
  const header = request.headers.get("x-git-cacao") || "";
  if (!header || header.length > 16384) return { ok: false };
  let wire;
  try {
    wire = decodeCbor(Uint8Array.from(atob(header), (c) => c.charCodeAt(0)));
  } catch (_) {
    return { ok: false };
  }
  const payload = wire?.p;
  if (!payload || typeof payload.iss !== "string" || !payload.iss.startsWith("did:pkh:")) return { ok: false };
  const checked = await verifyPkhCacao(env, payload, wire?.s?.s);
  if (!checked.ok) return { ok: false };
  if (!payload.nonce) return { ok: false };
  try {
    await env.GIT_DB.prepare("INSERT INTO nonces(did,nonce,created_at) VALUES(?,?,?)").bind(payload.iss, payload.nonce, (/* @__PURE__ */ new Date()).toISOString()).run();
  } catch (_) {
    return { ok: false };
  }
  const wanted = `urn:kotobase:git:${repo}`;
  const granted = (payload.resources || []).some((r) => r === wanted || r === `${wanted}/*` || r.endsWith("*") && wanted.startsWith(r.slice(0, -1)));
  if (!granted) return { ok: false };
  return { ok: true, address: checked.address, signer: checked.signer };
}
__name(walletCacaoAuthorized, "walletCacaoAuthorized");
function x402Accepts(env, repo, usd, path) {
  const addr = env.KOTOBASE_TREASURY_ADDR;
  if (!addr) return null;
  const resource = `https://git.kotobase.net/${path}`;
  const facilitator = env.KOTOBASE_X402_FACILITATOR;
  const opts = [requirement({ payTo: addr, usd, resource, net: "base", scheme: "transaction" })];
  if (facilitator) opts.unshift(requirement({ payTo: addr, usd, resource, net: "base", scheme: "exact", facilitator }));
  return opts;
}
__name(x402Accepts, "x402Accepts");
async function x402Gate(request, env, repo, path, serve) {
  const usd = quotedUsd(new URL(request.url).searchParams.get("usd"), DEFAULT_USD);
  const accepts = x402Accepts(env, repo, usd, path);
  if (!accepts) return json({ ok: false, error: "crypto rail not configured (KOTOBASE_TREASURY_ADDR unset)" }, 503);
  const header = request.headers.get("x-payment");
  if (!header) return paymentRequiredResponse(accepts);
  const payment = decodePayment(header);
  const req = payment && accepts.find((a) => a.scheme === payment.scheme && a.network === payment.network);
  if (!payment || !req) return paymentRequiredResponse(accepts, "unsupported scheme/network");
  const errs = payloadErrors(payment, req, Math.floor(Date.now() / 1e3));
  if (errs.length) return paymentRequiredResponse(accepts, "invalid payment: " + errs.join(","));
  let verification;
  if (req.scheme === "exact") {
    verification = await settleExact(env, payment, req);
    if (!verification) return paymentRequiredResponse(accepts, "no facilitator configured");
  } else {
    verification = await verifyTxPayment(env, req, payment);
  }
  if (!verification.ok) return paymentRequiredResponse(accepts, "payment not confirmed: " + verification.reason);
  const spend = await spendReserve(env, req, verification);
  if (!spend.allow) return paymentRequiredResponse(accepts, spend.reason);
  const response = await serve();
  const settlement = {
    success: true,
    network: req.network,
    payer: verification.payer,
    amount: verification.paidMicros,
    tx: verification.txHash || null
  };
  const headers = new Headers(response.headers);
  headers.set("x-payment-response", btoa(JSON.stringify(settlement)));
  return new Response(response.body, { status: response.status, headers });
}
__name(x402Gate, "x402Gate");
async function readGate(request, env, repo, path, serve) {
  const paid = isPaidRepo(env, repo);
  const priv = isPrivateRepo(env, repo);
  if (!paid && !priv) return null;
  if (await adminAuthorized(request, env)) return null;
  const wallet = await walletCacaoAuthorized(request, env, repo);
  if (wallet.ok) return null;
  if (paid) return x402Gate(request, env, repo, path, serve);
  return json({ ok: false, error: "Unauthorized" }, 401);
}
__name(readGate, "readGate");
var validSha = /* @__PURE__ */ __name((s) => /^[0-9a-f]{40}$/.test(s), "validSha");
var validRef = /* @__PURE__ */ __name((s) => /^refs\/(heads|tags)\/[A-Za-z0-9._/-]+$/.test(s) && !s.includes("..") && !s.endsWith("/"), "validRef");
var validDid = /* @__PURE__ */ __name((s) => /^did:key:z[1-9A-HJ-NP-Za-km-z]{40,}$/.test(s), "validDid");
var enc2 = new TextEncoder();
var hex = /* @__PURE__ */ __name((bytes) => [...new Uint8Array(bytes)].map((x) => x.toString(16).padStart(2, "0")).join(""), "hex");
var b64urlBytes = /* @__PURE__ */ __name((s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(s.length / 4) * 4, "=")), (c) => c.charCodeAt(0)), "b64urlBytes");
var unhex = /* @__PURE__ */ __name((s) => Uint8Array.from(s.match(/../g) || [], (x) => Number.parseInt(x, 16)), "unhex");
async function adminAuthorized(request, env) {
  if (!env.ADMIN_TOKEN) return false;
  const header = request.headers.get("authorization") || "";
  if (!header.startsWith("Bearer ")) return false;
  const [presented, expected] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc2.encode(header.slice(7))),
    crypto.subtle.digest("SHA-256", enc2.encode(env.ADMIN_TOKEN))
  ]);
  const a = new Uint8Array(presented), b = new Uint8Array(expected);
  let mismatch = a.length ^ b.length;
  for (let i = 0; i < Math.min(a.length, b.length); i += 1) mismatch |= a[i] ^ b[i];
  return mismatch === 0;
}
__name(adminAuthorized, "adminAuthorized");
function decodeCbor(bytes) {
  let offset = 0;
  const readLength = /* @__PURE__ */ __name((additional) => {
    if (additional < 24) return additional;
    if (additional === 24) return bytes[offset++];
    if (additional === 25) return bytes[offset++] << 8 | bytes[offset++];
    if (additional === 26) return bytes[offset++] * 16777216 + (bytes[offset++] << 16) + (bytes[offset++] << 8) + bytes[offset++];
    throw new Error("unsupported CBOR length");
  }, "readLength");
  const read = /* @__PURE__ */ __name(() => {
    if (offset >= bytes.length) throw new Error("truncated CBOR");
    const first = bytes[offset++];
    const major = first >> 5;
    const length = readLength(first & 31);
    if (major === 0) return length;
    if (major === 2) {
      const value2 = bytes.slice(offset, offset + length);
      offset += length;
      return value2;
    }
    if (major === 3) {
      const value2 = new TextDecoder().decode(bytes.slice(offset, offset + length));
      offset += length;
      return value2;
    }
    if (major === 4) return Array.from({ length }, read);
    if (major === 5) {
      const value2 = {};
      for (let i = 0; i < length; i += 1) value2[read()] = read();
      return value2;
    }
    if (major === 7 && first === 244) return false;
    if (major === 7 && first === 245) return true;
    if (major === 7 && first === 246) return null;
    throw new Error("unsupported CBOR type");
  }, "read");
  const value = read();
  if (offset !== bytes.length) throw new Error("trailing CBOR bytes");
  return value;
}
__name(decodeCbor, "decodeCbor");
function siweMessage2(payload) {
  const lines = [
    `${payload.domain} wants you to sign in with your Ethereum account:`,
    String(payload.iss || "").split(":").at(-1),
    "",
    `URI: ${payload.aud}`,
    `Version: ${payload.version}`,
    "Chain ID: 1",
    `Nonce: ${payload.nonce}`,
    `Issued At: ${payload.iat}`
  ];
  if (payload.exp) lines.push(`Expiration Time: ${payload.exp}`);
  if (payload.resources?.length) lines.push("Resources:", ...payload.resources.map((r) => `- ${r}`));
  return lines.join("\n");
}
__name(siweMessage2, "siweMessage");
var covers = /* @__PURE__ */ __name((parent, child) => typeof parent === "string" && typeof child === "string" && (parent.endsWith("*") ? child.startsWith(parent.slice(0, -1)) : parent === child), "covers");
async function verifyCacao(value, now = Date.now()) {
  try {
    if (typeof value !== "string" || value.length > 16384) return null;
    const wire = decodeCbor(Uint8Array.from(atob(value), (c) => c.charCodeAt(0)));
    const payload = wire.p;
    const signature = wire.s?.s;
    if (!payload || !signature || !validDid(payload.iss) || !Array.isArray(payload.resources) || payload.resources.some((r) => typeof r !== "string" || r.includes("\n")) || !payload.nonce) return null;
    const iat = Date.parse(payload.iat);
    const exp = Date.parse(payload.exp);
    if (!Number.isFinite(iat) || iat > now + 3e5 || !Number.isFinite(exp) || now >= exp) return null;
    const pub = b58decode(payload.iss.slice("did:key:z".length));
    if (pub.length !== 34 || pub[0] !== 237 || pub[1] !== 1) return null;
    const key = await crypto.subtle.importKey("raw", pub.slice(2), { name: "Ed25519" }, false, ["verify"]);
    const sig = b64urlBytes(signature);
    if (sig.length !== 64 || !await crypto.subtle.verify("Ed25519", key, sig, enc2.encode(siweMessage2(payload)))) return null;
    return payload;
  } catch (_) {
    return null;
  }
}
__name(verifyCacao, "verifyCacao");
function b58decode(value) {
  let n = 0n;
  for (const ch of value) {
    const i = b58alphabet.indexOf(ch);
    if (i < 0) throw new Error("invalid base58");
    n = n * 58n + BigInt(i);
  }
  const out = [];
  while (n > 0n) {
    out.unshift(Number(n & 255n));
    n >>= 8n;
  }
  for (const ch of value) {
    if (ch !== "1") break;
    out.unshift(0);
  }
  return Uint8Array.from(out);
}
__name(b58decode, "b58decode");
async function verifyCacaoChain(chain, ownerDid, signerDid, wanted, now = Date.now()) {
  if (!Array.isArray(chain) || chain.length < 1 || chain.length > 8) return null;
  const payloads = [];
  for (const link of chain) {
    const payload = await verifyCacao(link, now);
    if (!payload) return null;
    payloads.push(payload);
  }
  if (payloads[0].iss !== ownerDid || payloads.at(-1).aud !== signerDid) return null;
  for (let i = 1; i < payloads.length; i += 1) {
    const parent = payloads[i - 1];
    const child = payloads[i];
    if (child.iss !== parent.aud || Date.parse(child.exp) > Date.parse(parent.exp) || child.resources.some((resource) => !parent.resources.some((grant) => covers(grant, resource)))) return null;
  }
  if (!payloads.at(-1).resources.some((grant) => covers(grant, wanted))) return null;
  return payloads;
}
__name(verifyCacaoChain, "verifyCacaoChain");
var b58alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
function base58(bytes) {
  let n = 0n;
  for (const b of bytes) n = (n << 8n) + BigInt(b);
  let out = "";
  while (n > 0n) {
    out = b58alphabet[Number(n % 58n)] + out;
    n /= 58n;
  }
  for (const b of bytes) {
    if (b !== 0) break;
    out = `1${out}`;
  }
  return out || "1";
}
__name(base58, "base58");
var didFromPublicKey = /* @__PURE__ */ __name((pk) => `did:key:z${base58(new Uint8Array([237, 1, ...pk]))}`, "didFromPublicKey");
function cborText(value) {
  const bytes = enc2.encode(value);
  if (bytes.length < 24) return new Uint8Array([96 + bytes.length, ...bytes]);
  if (bytes.length < 256) return new Uint8Array([120, bytes.length, ...bytes]);
  return new Uint8Array([121, bytes.length >> 8, bytes.length & 255, ...bytes]);
}
__name(cborText, "cborText");
function sigrefPayload(sigref) {
  const entries = ["rid", "ref", "commit", "ts"].map((key) => [cborText(key), cborText(sigref[key])]);
  entries.sort((a, b) => {
    if (a[0].length !== b[0].length) return a[0].length - b[0].length;
    for (let i = 0; i < a[0].length; i += 1) if (a[0][i] !== b[0][i]) return a[0][i] - b[0][i];
    return 0;
  });
  const size = entries.reduce((n, [k, v]) => n + k.length + v.length, 1);
  const out = new Uint8Array(size);
  out[0] = 164;
  let offset = 1;
  for (const [k, v] of entries) {
    out.set(k, offset);
    offset += k.length;
    out.set(v, offset);
    offset += v.length;
  }
  return out;
}
__name(sigrefPayload, "sigrefPayload");
var digestHex = /* @__PURE__ */ __name(async (bytes, algorithm = "SHA-256") => hex(await crypto.subtle.digest(algorithm, bytes)), "digestHex");
function base32(bytes) {
  const alphabet = "abcdefghijklmnopqrstuvwxyz234567";
  let bits = 0;
  let value = 0;
  let out = "";
  for (const byte of bytes) {
    value = value << 8 | byte;
    bits += 8;
    while (bits >= 5) {
      out += alphabet[value >>> bits - 5 & 31];
      bits -= 5;
    }
  }
  if (bits) out += alphabet[value << 5 - bits & 31];
  return out;
}
__name(base32, "base32");
async function rawCid(bytes) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return `b${base32(new Uint8Array([1, 85, 18, 32, ...digest]))}`;
}
__name(rawCid, "rawCid");
async function deflate(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream("deflate"));
  return new Response(stream).arrayBuffer();
}
__name(deflate, "deflate");
var audit = /* @__PURE__ */ __name((env, op, repo, subject, signer, evidence = {}) => env.GIT_DB.prepare(
  "INSERT INTO audit(id,op,repo,subject,signer_did,evidence_json,created_at) VALUES(?,?,?,?,?,?,?)"
).bind(crypto.randomUUID(), op, repo || null, subject || null, signer || null, JSON.stringify(evidence), (/* @__PURE__ */ new Date()).toISOString()).run(), "audit");
async function verifySignedRequest(request, env, body) {
  const did = request.headers.get("x-nekko-did") || "";
  const pub64 = request.headers.get("x-nekko-public-key") || "";
  const sig64 = request.headers.get("x-nekko-signature") || "";
  const timestamp = request.headers.get("x-nekko-timestamp") || "";
  const nonce = request.headers.get("x-nekko-nonce") || "";
  if (!validDid(did) || !pub64 || !sig64 || !nonce || nonce.length > 160) return null;
  const at = Date.parse(timestamp);
  if (!Number.isFinite(at) || Math.abs(Date.now() - at) > 3e5) return null;
  const pub = b64urlBytes(pub64);
  if (pub.length !== 32 || didFromPublicKey(pub) !== did) return null;
  const url = new URL(request.url);
  const bodyHash = await digestHex(body);
  const sigrefHeader = request.headers.get("x-nekko-sigref") || "";
  const projectionGraph = request.headers.get("x-kotobase-graph") || "";
  const projectionCommit = request.headers.get("x-kotobase-commit-cid") || "";
  const cacaoHash = await digestHex(enc2.encode(request.headers.get("x-kotobase-cacao") || ""));
  const approvalsHeader = request.headers.get("x-nekko-approvals") || "";
  const approvalSuffix = approvalsHeader ? `
${await digestHex(enc2.encode(approvalsHeader))}` : "";
  const authorizationHash = await digestHex(enc2.encode(`${sigrefHeader}
${projectionGraph}
${projectionCommit}
${cacaoHash}${approvalSuffix}`));
  if (request.headers.get("x-nekko-authorization-hash") !== authorizationHash) return { error: "AuthorizationHashMismatch" };
  const message = `${request.method}
${url.pathname}${url.search}
${bodyHash}
${timestamp}
${nonce}
${authorizationHash}`;
  try {
    const key = await crypto.subtle.importKey("raw", pub, { name: "Ed25519" }, false, ["verify"]);
    if (!await crypto.subtle.verify("Ed25519", key, b64urlBytes(sig64), enc2.encode(message))) return { error: "RequestSignatureMismatch" };
    await env.GIT_DB.prepare("INSERT INTO nonces(did,nonce,created_at) VALUES(?,?,?)").bind(did, nonce, (/* @__PURE__ */ new Date()).toISOString()).run();
    return { did, bodyHash };
  } catch (_) {
    return null;
  }
}
__name(verifySignedRequest, "verifySignedRequest");
async function verifySigref(request, signed, repo, ref, sha) {
  const encoded = request.headers.get("x-nekko-sigref") || "";
  try {
    const value = JSON.parse(new TextDecoder().decode(b64urlBytes(encoded)));
    if (value.rid !== `urn:kotobase:git:${repo}` || value.ref !== ref || value.commit !== `git:sha1:${sha}` || value.signer !== signed.did || !/^[0-9a-f]{128}$/.test(value.sig || "")) return null;
    const at = Date.parse(value.ts);
    if (!Number.isFinite(at) || Math.abs(Date.now() - at) > 3e5) return null;
    const pub = b64urlBytes(request.headers.get("x-nekko-public-key") || "");
    const key = await crypto.subtle.importKey("raw", pub, { name: "Ed25519" }, false, ["verify"]);
    return await crypto.subtle.verify("Ed25519", key, unhex(value.sig), sigrefPayload(value)) ? value : null;
  } catch (_) {
    return null;
  }
}
__name(verifySigref, "verifySigref");
async function verifyApprovalSigref(value, publicKey, repo, ref, sha) {
  try {
    if (value.rid !== `urn:kotobase:git:${repo}` || value.ref !== ref || value.commit !== `git:sha1:${sha}` || !validDid(value.signer) || !/^[0-9a-f]{128}$/.test(value.sig || "")) return false;
    const at = Date.parse(value.ts);
    if (!Number.isFinite(at) || Math.abs(Date.now() - at) > 3e5) return false;
    const pub = b64urlBytes(publicKey || "");
    if (pub.length !== 32 || didFromPublicKey(pub) !== value.signer) return false;
    const key = await crypto.subtle.importKey("raw", pub, { name: "Ed25519" }, false, ["verify"]);
    return crypto.subtle.verify("Ed25519", key, unhex(value.sig), sigrefPayload(value));
  } catch (_) {
    return false;
  }
}
__name(verifyApprovalSigref, "verifyApprovalSigref");
async function verifyQuorumApprovals(request, env, repo, ref, sha, ownerDid, minimum) {
  const encoded = request.headers.get("x-nekko-approvals") || "";
  if (!encoded) return minimum <= 1 ? { ok: true, signers: [] } : { ok: false, error: "QuorumApprovalsRequired" };
  try {
    const approvals = JSON.parse(new TextDecoder().decode(b64urlBytes(encoded)));
    if (!Array.isArray(approvals) || approvals.length > 16) return { ok: false, error: "InvalidQuorumApprovals" };
    const wanted = `kotoba-rad://urn:kotobase:git:${repo}/push/${ref}`;
    const accepted = [];
    const nonceRows = [];
    for (const approval of approvals) {
      const sigref = approval?.sigref;
      if (!sigref || accepted.includes(sigref.signer) || !await verifyApprovalSigref(sigref, approval.publicKey, repo, ref, sha)) continue;
      const payloads = await verifyCacaoChain(approval.chain, ownerDid, sigref.signer, wanted);
      if (!payloads) continue;
      accepted.push(sigref.signer);
      for (const payload of payloads) nonceRows.push([payload.iss, payload.nonce]);
    }
    if (accepted.length < minimum) return { ok: false, error: "QuorumNotReached", accepted: accepted.length, required: minimum };
    const uniqueNonces = [...new Map(nonceRows.map((row) => [`${row[0]}\0${row[1]}`, row])).values()];
    try {
      await env.GIT_DB.batch(uniqueNonces.map(([issuer, nonce]) => env.GIT_DB.prepare(
        "INSERT INTO cacao_nonces(issuer_did,nonce,created_at) VALUES(?,?,?)"
      ).bind(issuer, nonce, (/* @__PURE__ */ new Date()).toISOString())));
    } catch (_) {
      return { ok: false, error: "CacaoChainReplay" };
    }
    return { ok: true, signers: accepted };
  } catch (_) {
    return { ok: false, error: "InvalidQuorumApprovals" };
  }
}
__name(verifyQuorumApprovals, "verifyQuorumApprovals");
async function isAncestor(env, repo, ancestor, descendant) {
  if (ancestor === descendant) return true;
  const seen = /* @__PURE__ */ new Set();
  const pending = [descendant];
  while (pending.length && seen.size < 1e5) {
    const sha = pending.pop();
    if (seen.has(sha)) continue;
    seen.add(sha);
    const row = await env.GIT_DB.prepare("SELECT parents_json FROM objects WHERE repo=? AND sha=?").bind(repo, sha).first();
    if (!row) continue;
    for (const parent of JSON.parse(row.parents_json)) {
      if (parent === ancestor) return true;
      if (!seen.has(parent)) pending.push(parent);
    }
  }
  return false;
}
__name(isAncestor, "isAncestor");
async function verifyKotobaseProjection(repo, ref, sha, sigref, graph, cacao, did) {
  if (!/^b[a-z2-7]{20,}$/.test(graph || "")) return false;
  if (!cacao || cacao.length > 16384) return false;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      const response = await fetch("https://kotobase.net/xrpc/ai.gftd.apps.kotobase.datomic.datoms", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "accept": "application/json",
          "authorization": `CACAO ${cacao}`,
          "x-kotoba-did": did
        },
        body: JSON.stringify({ graph, index: ":avet", components_edn: [":git.ref/sigref"], cacao_b64: cacao })
      });
      if (response.ok) {
        const result = await response.json();
        const datoms = result.datoms || [];
        if (datoms.some((datom) => datom.a === ":git.ref/sigref" && String(datom.v_edn || datom.v || "").includes(sha) && String(datom.v_edn || datom.v || "").includes(sigref.sig))) return true;
      }
    } catch (_) {
    }
    await new Promise((resolve) => setTimeout(resolve, 150 * (attempt + 1)));
  }
  return false;
}
__name(verifyKotobaseProjection, "verifyKotobaseProjection");
async function authority(env, repo, did, claim = false) {
  const row = await env.GIT_DB.prepare("SELECT owner_did FROM repos WHERE name=?").bind(repo).first();
  if (!row && claim) {
    await env.GIT_DB.prepare("INSERT INTO repos(name,owner_did,created_at) VALUES(?,?,?)").bind(repo, did, (/* @__PURE__ */ new Date()).toISOString()).run();
    return "owner";
  }
  if (row?.owner_did === did) return "owner";
  const delegated = await env.GIT_DB.prepare("SELECT active FROM delegates WHERE repo=? AND did=?").bind(repo, did).first();
  return delegated?.active === 1 ? "delegate" : null;
}
__name(authority, "authority");
async function signedWrite(request, env, url) {
  if (request.method !== "PUT") return json({ ok: false, error: "MethodNotAllowed" }, 405);
  const body = await request.arrayBuffer();
  const signed = await verifySignedRequest(request, env, body);
  if (!signed?.did) return json({ ok: false, error: signed?.error || "InvalidNekkoSignatureOrReplay" }, 401);
  const repo = url.searchParams.get("repo") || "";
  if (!validRepo(repo)) return json({ ok: false, error: "InvalidRepo" }, 400);
  const role = await authority(env, repo, signed.did, url.pathname === "/xrpc/kotobase.git.object.put");
  if (!role) return json({ ok: false, error: "NotAuthorizedForRepo" }, 403);
  const now = (/* @__PURE__ */ new Date()).toISOString();
  if (url.pathname === "/xrpc/kotobase.git.object.put") {
    const sha = url.searchParams.get("sha") || "";
    if (!validSha(sha)) return json({ ok: false, error: "InvalidSha" }, 400);
    if (body.byteLength > 100 * 1024 * 1024) return json({ ok: false, error: "ObjectTooLarge" }, 413);
    const parents = (url.searchParams.getAll("parent") || []).filter(validSha);
    if (parents.length !== url.searchParams.getAll("parent").length) return json({ ok: false, error: "InvalidParent" }, 400);
    const computedSha = await digestHex(body, "SHA-1");
    if (computedSha !== sha) return json({ ok: false, error: "GitObjectIntegrityFailed", expected: sha, computed: computedSha }, 422);
    const blockCid = await rawCid(body);
    const looseBytes = await deflate(body);
    await env.GIT_OBJECTS.put(`blocks/${blockCid}`, body, {
      customMetadata: { cid: blockCid, codec: "raw", sha1: sha, sha256: signed.bodyHash, signer: signed.did }
    });
    await env.GIT_OBJECTS.put(`${repo}/objects/${sha.slice(0, 2)}/${sha.slice(2)}`, looseBytes, {
      customMetadata: { sha1: sha, blockCid, cache: "git-loose", signer: signed.did }
    });
    await env.GIT_DB.prepare("INSERT OR REPLACE INTO objects(repo,sha,oid_sha256,size,parents_json,signer_did,created_at,block_cid) VALUES(?,?,?,?,?,?,?,?)").bind(repo, sha, signed.bodyHash, body.byteLength, JSON.stringify(parents), signed.did, now, blockCid).run();
    await audit(env, "put-object", repo, sha, signed.did, { sha256: signed.bodyHash, blockCid, size: body.byteLength, parents });
    return json({ ok: true, repo, sha, cid: blockCid }, 201);
  }
  if (url.pathname === "/xrpc/kotobase.git.ref.set") {
    const ref = url.searchParams.get("ref") || "";
    const sha = url.searchParams.get("sha") || "";
    const old = url.searchParams.get("old");
    if (!validRef(ref) || !validSha(sha) || old !== null && old !== "" && !validSha(old)) return json({ ok: false, error: "InvalidRefUpdate" }, 400);
    const sigref = await verifySigref(request, signed, repo, ref, sha);
    if (!sigref) return json({ ok: false, error: "InvalidNekkoSigref" }, 401);
    const policy = await env.GIT_DB.prepare("SELECT owner_did,min_signers FROM repos WHERE name=?").bind(repo).first();
    const quorum = await verifyQuorumApprovals(request, env, repo, ref, sha, policy.owner_did, policy.min_signers || 1);
    if (!quorum.ok) return json({ ok: false, ...quorum }, 403);
    const kotobaseGraph = request.headers.get("x-kotobase-graph") || "";
    const kotobaseCommit = request.headers.get("x-kotobase-commit-cid") || "";
    const kotobaseCacao = request.headers.get("x-kotobase-cacao") || "";
    if (!/^b[a-z2-7]{20,}$/.test(kotobaseCommit) || !await verifyKotobaseProjection(repo, ref, sha, sigref, kotobaseGraph, kotobaseCacao, signed.did))
      return json({ ok: false, error: "KotobaseProjectionNotVerified" }, 409);
    const object = await env.GIT_DB.prepare("SELECT parents_json FROM objects WHERE repo=? AND sha=?").bind(repo, sha).first();
    if (!object) return json({ ok: false, error: "UnknownObject" }, 409);
    const current = await env.GIT_DB.prepare("SELECT sha FROM refs WHERE repo=? AND ref=?").bind(repo, ref).first();
    const currentSha = current?.sha || null;
    if ((old || null) !== currentSha) return json({ ok: false, error: "CompareAndSetFailed", current: currentSha }, 409);
    if (currentSha && !await isAncestor(env, repo, currentSha, sha)) return json({ ok: false, error: "NonFastForward" }, 409);
    const event = {
      schema: 1,
      id: crypto.randomUUID(),
      type: ref === "refs/heads/main" ? "kotobase.git.ref.promoted" : "kotobase.git.canary.promoted",
      repo,
      ref,
      old: currentSha,
      sha,
      signerDid: signed.did,
      sigref,
      kotobaseGraph,
      kotobaseCommit,
      requestedAt: now,
      bounds: {
        maxFiles: 32,
        maxChangedLines: 1200,
        maxSpendUsd: "1.00",
        allowedPhases: ["observe", "propose", "test", "canary"]
      }
    };
    const evidence = {
      old: currentSha,
      sha,
      role,
      sigref,
      quorumSigners: quorum.signers,
      quorumRequired: policy.min_signers || 1,
      kotobaseGraph,
      kotobaseCommit,
      eventId: event.id
    };
    const statements = [
      env.GIT_DB.prepare("INSERT INTO refs(repo,ref,sha,updated_at,signer_did,kotobase_graph,kotobase_commit_cid) VALUES(?,?,?,?,?,?,?) ON CONFLICT(repo,ref) DO UPDATE SET sha=excluded.sha,updated_at=excluded.updated_at,signer_did=excluded.signer_did,kotobase_graph=excluded.kotobase_graph,kotobase_commit_cid=excluded.kotobase_commit_cid").bind(repo, ref, sha, now, signed.did, kotobaseGraph, kotobaseCommit),
      env.GIT_DB.prepare("INSERT INTO event_outbox(id,event_json,created_at) VALUES(?,?,?)").bind(event.id, JSON.stringify(event), now),
      env.GIT_DB.prepare("INSERT INTO audit(id,op,repo,subject,signer_did,evidence_json,created_at) VALUES(?,?,?,?,?,?,?)").bind(crypto.randomUUID(), "set-ref", repo, ref, signed.did, JSON.stringify(evidence), now)
    ];
    if (ref === "refs/heads/main") statements.push(env.GIT_DB.prepare("INSERT INTO heads(repo,ref,updated_at) VALUES(?,?,?) ON CONFLICT(repo) DO UPDATE SET ref=excluded.ref,updated_at=excluded.updated_at").bind(repo, ref, now));
    await env.GIT_DB.batch(statements);
    let eventQueued = false;
    try {
      await env.KAIZEN_EVENTS.send(event, { contentType: "json" });
      await env.GIT_DB.prepare("UPDATE event_outbox SET delivered_at=? WHERE id=?").bind((/* @__PURE__ */ new Date()).toISOString(), event.id).run();
      eventQueued = true;
    } catch (_) {
    }
    return json({
      ok: true,
      repo,
      ref,
      old: currentSha,
      sha,
      kotobaseGraph,
      kotobaseCommit,
      quorumRequired: policy.min_signers || 1,
      quorumSigners: quorum.signers,
      eventId: event.id,
      eventQueued
    });
  }
  if (url.pathname === "/xrpc/kotobase.git.delegate.set") {
    if (role !== "owner") return json({ ok: false, error: "OwnerRequired" }, 403);
    const delegate = url.searchParams.get("did") || "";
    const active = url.searchParams.get("active") !== "false";
    if (!validDid(delegate)) return json({ ok: false, error: "InvalidDelegateDid" }, 400);
    await env.GIT_DB.prepare("INSERT INTO delegates(repo,did,active,updated_at) VALUES(?,?,?,?) ON CONFLICT(repo,did) DO UPDATE SET active=excluded.active,updated_at=excluded.updated_at").bind(repo, delegate, active ? 1 : 0, now).run();
    await audit(env, active ? "delegate-add" : "delegate-remove", repo, delegate, signed.did);
    return json({ ok: true, repo, did: delegate, active });
  }
  if (url.pathname === "/xrpc/kotobase.git.quorum.set") {
    if (role !== "owner") return json({ ok: false, error: "OwnerRequired" }, 403);
    const minimum = Number(url.searchParams.get("min"));
    if (!Number.isInteger(minimum) || minimum < 1 || minimum > 16)
      return json({ ok: false, error: "InvalidQuorum" }, 400);
    const available = await env.GIT_DB.prepare("SELECT COUNT(*) AS n FROM delegates WHERE repo=? AND active=1").bind(repo).first();
    if (minimum > Number(available?.n || 0) + 1) return json({ ok: false, error: "QuorumExceedsAuthorizedSigners" }, 409);
    await env.GIT_DB.prepare("UPDATE repos SET min_signers=? WHERE name=?").bind(minimum, repo).run();
    await audit(env, "quorum-set", repo, String(minimum), signed.did, { minimum });
    return json({ ok: true, repo, minSigners: minimum });
  }
  return json({ ok: false, error: "NotFound" }, 404);
}
__name(signedWrite, "signedWrite");
async function infoRefsResponse(env, repo) {
  const rows = await env.GIT_DB.prepare("SELECT ref,sha FROM refs WHERE repo=? ORDER BY ref").bind(repo).all();
  if (!rows.results.length) return text("repository not found", 404);
  return text(rows.results.map((r) => `${r.sha}	${r.ref}
`).join(""));
}
__name(infoRefsResponse, "infoRefsResponse");
async function headResponse(env, repo) {
  const row = await env.GIT_DB.prepare("SELECT ref FROM heads WHERE repo=?").bind(repo).first();
  return row ? text(`ref: ${row.ref}
`) : text("repository not found", 404);
}
__name(headResponse, "headResponse");
async function objectResponse(request, env, repo, d2, d38) {
  const sha = `${d2}${d38}`;
  let value = await env.GIT_OBJECTS.get(`${repo}/objects/${d2}/${d38}`);
  if (!value) {
    const row = await env.GIT_DB.prepare("SELECT block_cid FROM objects WHERE repo=? AND sha=?").bind(repo, sha).first();
    const block = row?.block_cid ? await env.GIT_OBJECTS.get(`blocks/${row.block_cid}`) : null;
    if (block) {
      const raw = await block.arrayBuffer();
      const loose = await deflate(raw);
      await env.GIT_OBJECTS.put(
        `${repo}/objects/${d2}/${d38}`,
        loose,
        { customMetadata: { sha1: sha, blockCid: row.block_cid, cache: "git-loose" } }
      );
      value = await env.GIT_OBJECTS.get(`${repo}/objects/${d2}/${d38}`);
    }
  }
  return value ? new Response(request.method === "HEAD" ? null : value.body, { status: 200, headers: { "content-type": "application/x-git-loose-object", etag: value.httpEtag } }) : text("object not found", 404);
}
__name(objectResponse, "objectResponse");
async function gitRead(request, env, url) {
  if (request.method !== "GET" && request.method !== "HEAD") return text("method not allowed", 405);
  const path = url.pathname.replace(/^\/+/, "");
  let m = path.match(/^([^/]+\/[^/]+)\/info\/refs$/);
  if (m) {
    const gate = await readGate(request, env, m[1], path, () => infoRefsResponse(env, m[1]));
    return gate || infoRefsResponse(env, m[1]);
  }
  m = path.match(/^([^/]+\/[^/]+)\/HEAD$/);
  if (m) {
    const gate = await readGate(request, env, m[1], path, () => headResponse(env, m[1]));
    return gate || headResponse(env, m[1]);
  }
  m = path.match(/^([^/]+\/[^/]+)\/objects\/([0-9a-f]{2})\/([0-9a-f]{38})$/);
  if (m) {
    const gate = await readGate(request, env, m[1], path, () => objectResponse(request, env, m[1], m[2], m[3]));
    return gate || objectResponse(request, env, m[1], m[2], m[3]);
  }
  return text("not found", 404);
}
__name(gitRead, "gitRead");
async function refMetadata(env, url) {
  const repo = url.searchParams.get("repo") || "";
  const ref = url.searchParams.get("ref") || "";
  if (!validRepo(repo) || !validRef(ref)) return json({ ok: false, error: "InvalidRef" }, 400);
  const row = await env.GIT_DB.prepare("SELECT sha,kotobase_graph,kotobase_commit_cid,updated_at FROM refs WHERE repo=? AND ref=?").bind(repo, ref).first();
  return row ? json({
    ok: true,
    repo,
    ref,
    sha: row.sha,
    kotobaseGraph: row.kotobase_graph,
    kotobaseCommit: row.kotobase_commit_cid,
    updatedAt: row.updated_at
  }) : json({ ok: false, error: "RefNotFound" }, 404);
}
__name(refMetadata, "refMetadata");
async function flushOutbox(env) {
  const pending = await env.GIT_DB.prepare("SELECT id,event_json FROM event_outbox WHERE delivered_at IS NULL ORDER BY created_at LIMIT 50").all();
  for (const row of pending.results) {
    try {
      await env.KAIZEN_EVENTS.send(JSON.parse(row.event_json), { contentType: "json" });
      await env.GIT_DB.prepare("UPDATE event_outbox SET delivered_at=? WHERE id=? AND delivered_at IS NULL").bind((/* @__PURE__ */ new Date()).toISOString(), row.id).run();
    } catch (_) {
      break;
    }
  }
}
__name(flushOutbox, "flushOutbox");
var git_worker_default = { async fetch(request, env) {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === "/health") {
    return json({
      ok: true,
      service: "kotobase-git",
      version: env.SERVICE_VERSION,
      refs: "kotobase-datom-authority+d1-cas",
      objects: "kotobase-protocol-blocks-cidv1+r2-loose-cache",
      auth: "nekko-sigref+delegated-cacao-chain+distinct-signer-quorum",
      protocol: "git-dumb-http+remote-helper"
    }, 200, { "cache-control": "no-store" });
  }
  if (request.method === "GET" && url.pathname === "/xrpc/kotobase.git.ref.get") return refMetadata(env, url);
  if (url.pathname.startsWith("/xrpc/kotobase.git.")) {
    if (!await adminAuthorized(request, env))
      return json({ ok: false, error: "Unauthorized", message: "writes require a bearer token" }, 401);
    return signedWrite(request, env, url);
  }
  return gitRead(request, env, url);
}, async scheduled(_controller, env, ctx) {
  ctx.waitUntil(flushOutbox(env));
} };
export {
  adminAuthorized,
  decodeCbor,
  git_worker_default as default,
  rawCid,
  verifyCacao,
  verifyCacaoChain
};
/*! Bundled license information:

@noble/curves/utils.js:
@noble/curves/abstract/modular.js:
@noble/curves/abstract/curve.js:
@noble/curves/abstract/der.js:
@noble/curves/abstract/weierstrass.js:
@noble/curves/secp256k1.js:
  (*! noble-curves - MIT License (c) 2022 Paul Miller (paulmillr.com) *)

@noble/hashes/utils.js:
  (*! noble-hashes - MIT License (c) 2022 Paul Miller (paulmillr.com) *)
*/
//# sourceMappingURL=git-worker.js.map
