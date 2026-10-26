// Browser-side port of kotoba-lang/kotoba's src/kotoba/kgraph.clj (the pure
// in-memory EAVT datom store backing the kgraph-* host-import surface) plus
// just enough of an EDN reader/writer to round-trip the two shapes the
// kgraph-* wire ABI actually carries: a `[e a v]` datom vector and a
// `{:find [...] :where [...]}` query map. This is NOT a general EDN
// implementation — no sets, no reader macros, no arbitrary nesting beyond
// what kgraph_assert/kgraph_query need. See README.md for scope.

// ---------------------------------------------------------------------------
// Minimal EDN reader

function isWhitespace(ch) {
  return ch === ' ' || ch === '\t' || ch === '\n' || ch === '\r' || ch === ',';
}

function isSymbolChar(ch) {
  return /[A-Za-z0-9_?!*+/<>=.\-]/.test(ch);
}

class EdnReader {
  constructor(s) {
    this.s = s;
    this.i = 0;
  }

  skipWs() {
    while (this.i < this.s.length && isWhitespace(this.s[this.i])) this.i++;
  }

  peek() {
    return this.s[this.i];
  }

  readValue() {
    this.skipWs();
    const ch = this.peek();
    if (ch === '[') return this.readVector();
    if (ch === '{') return this.readMap();
    if (ch === '"') return this.readString();
    if (ch === ':') return this.readKeyword();
    if (/[0-9]/.test(ch) || (ch === '-' && /[0-9]/.test(this.s[this.i + 1]))) return this.readNumber();
    return this.readSymbol();
  }

  readVector() {
    this.i++; // '['
    const out = [];
    for (;;) {
      this.skipWs();
      if (this.peek() === ']') { this.i++; return out; }
      out.push(this.readValue());
    }
  }

  readMap() {
    this.i++; // '{'
    const out = {};
    for (;;) {
      this.skipWs();
      if (this.peek() === '}') { this.i++; return out; }
      const k = this.readValue();
      if (typeof k !== 'object' || k.kw === undefined) {
        throw new Error('kgraph EDN reader: only keyword-keyed maps are supported');
      }
      const v = this.readValue();
      out[k.kw] = v;
    }
  }

  readString() {
    this.i++; // opening '"'
    let out = '';
    while (this.s[this.i] !== '"') {
      if (this.i >= this.s.length) throw new Error('kgraph EDN reader: unterminated string');
      if (this.s[this.i] === '\\') {
        this.i++;
        const esc = this.s[this.i];
        out += esc === 'n' ? '\n' : esc === 't' ? '\t' : esc;
      } else {
        out += this.s[this.i];
      }
      this.i++;
    }
    this.i++; // closing '"'
    return out;
  }

  readKeyword() {
    this.i++; // ':'
    let out = '';
    while (this.i < this.s.length && isSymbolChar(this.s[this.i])) {
      out += this.s[this.i];
      this.i++;
    }
    return { kw: out };
  }

  readNumber() {
    let out = '';
    while (this.i < this.s.length && /[0-9.\-]/.test(this.s[this.i])) {
      out += this.s[this.i];
      this.i++;
    }
    return out.includes('.') ? parseFloat(out) : parseInt(out, 10);
  }

  readSymbol() {
    let out = '';
    while (this.i < this.s.length && isSymbolChar(this.s[this.i])) {
      out += this.s[this.i];
      this.i++;
    }
    if (out.length === 0) throw new Error(`kgraph EDN reader: unexpected character "${this.s[this.i]}" at ${this.i}`);
    return { sym: out };
  }
}

export function readEdn(s) {
  return new EdnReader(s).readValue();
}

// ---------------------------------------------------------------------------
// Minimal EDN writer (only the shapes kgraph-query ever returns: vectors of
// vectors of strings/numbers/keywords — mirrors Clojure's `pr-str`).

export function writeEdn(v) {
  if (Array.isArray(v)) return '[' + v.map(writeEdn).join(' ') + ']';
  if (typeof v === 'string') return '"' + v.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
  if (typeof v === 'number') return String(v);
  if (v && v.kw !== undefined) return ':' + v.kw;
  if (v && v.sym !== undefined) return v.sym;
  throw new Error(`kgraph EDN writer: cannot print ${JSON.stringify(v)}`);
}

// ---------------------------------------------------------------------------
// Pure datom store logic — a faithful port of kotoba.kgraph.clj's
// assert-datom/retract-datom/get-objects/query (unify + match-clause +
// left-to-right join), operating over the `readEdn`-shaped values above
// (keywords as `{kw}`, logic vars as `{sym}` starting with "?").

function ednEqual(a, b) {
  if (a && typeof a === 'object' && b && typeof b === 'object') {
    if (a.kw !== undefined || b.kw !== undefined) return a.kw === b.kw;
    if (a.sym !== undefined || b.sym !== undefined) return a.sym === b.sym;
  }
  return a === b;
}

function isLogicVar(x) {
  return !!(x && typeof x === 'object' && typeof x.sym === 'string' && x.sym.startsWith('?'));
}

function unify(bindings, pat, val) {
  if (bindings === null) return null;
  if (isLogicVar(pat)) {
    if (Object.prototype.hasOwnProperty.call(bindings, pat.sym)) {
      return ednEqual(bindings[pat.sym], val) ? bindings : null;
    }
    return { ...bindings, [pat.sym]: val };
  }
  return ednEqual(pat, val) ? bindings : null;
}

function matchClause(datoms, bindings, clause) {
  const [ep, ap, vp] = clause;
  const out = [];
  for (const [e, a, v] of datoms) {
    const b = unify(unify(unify(bindings, ep, e), ap, a), vp, v);
    if (b !== null) out.push(b);
  }
  return out;
}

export function assertDatom(datoms, datom) {
  datoms.push(datom);
  return datoms;
}

export function retractDatom(datoms, datom) {
  const key = writeEdn(datom);
  return datoms.filter((d) => writeEdn(d) !== key);
}

export function getObjects(datoms, e) {
  return datoms.filter(([de]) => ednEqual(de, e));
}

export function query(datoms, { find, where }) {
  let bindingsSeq = [{}];
  for (const clause of where) {
    bindingsSeq = bindingsSeq.flatMap((b) => matchClause(datoms, b, clause));
  }
  const rows = bindingsSeq.map((b) => find.map((v) => b[v.sym]));
  const seen = new Set();
  const out = [];
  for (const row of rows) {
    const key = writeEdn(row);
    if (!seen.has(key)) {
      seen.add(key);
      out.push(row);
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// The (module "kotoba") host-import ABI kotoba.wasm-exec/kgraph-host-functions
// implements on the JVM side, ported byte-for-byte to the browser's WASM JS
// API: same (ptr, len[, out-ptr, out-cap]) convention, same wire format
// (guest memory holds a UTF-8 EDN string; kgraph_query/kgraph_get_objects
// write a UTF-8 EDN string back and return the byte count, or -1 on
// overflow). `memoryBox` is a mutable `{memory}` holder populated with
// `instance.exports.memory` AFTER `WebAssembly.instantiate` resolves — the
// import functions below are only ever called later, when the guest's own
// exported functions run, so the box is always populated by then.
export function kgraphHostImports(store, memoryBox) {
  const readStr = (ptr, len) => {
    const bytes = new Uint8Array(memoryBox.memory.buffer, ptr, len);
    return new TextDecoder('utf-8').decode(bytes);
  };
  const writeBytes = (ptr, cap, bytes) => {
    if (bytes.length > cap) return -1;
    new Uint8Array(memoryBox.memory.buffer, ptr, bytes.length).set(bytes);
    return bytes.length;
  };

  return {
    kgraph_assert: (ptr, len) => {
      assertDatom(store, readEdn(readStr(ptr, len)));
      return 0;
    },
    kgraph_retract: (ptr, len) => {
      const remaining = retractDatom(store, readEdn(readStr(ptr, len)));
      store.length = 0;
      store.push(...remaining);
      return 0;
    },
    kgraph_get_objects: (ePtr, eLen, outPtr, outCap) => {
      const e = readEdn(readStr(ePtr, eLen));
      const bytes = new TextEncoder().encode(writeEdn(getObjects(store, e)));
      return writeBytes(outPtr, outCap, bytes);
    },
    kgraph_query: (qPtr, qLen, outPtr, outCap) => {
      const q = readEdn(readStr(qPtr, qLen));
      const bytes = new TextEncoder().encode(writeEdn(query(store, q)));
      return writeBytes(outPtr, outCap, bytes);
    },
  };
}
