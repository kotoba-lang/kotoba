// request-cache.ts — No-op compatibility stub.
// Historical read-through caching was removed; callers now either hit Kysely directly
// or return defaults when no backing query path exists.

export class RequestCache {
  get(_key: string): string | null { return null; }
  getBinary(_key: string): Uint8Array | null { return null; }
  set(_key: string, _value: string): void {}
  setBinary(_key: string, _value: Uint8Array): void {}
  static graphKey(_l: string, _m: string, _r: string, _n: number): string { return ""; }
  static sqlKey(_c: string, _p: string): string { return ""; }
  clear(): void {}
}
