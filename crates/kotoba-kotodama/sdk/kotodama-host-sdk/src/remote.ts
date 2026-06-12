// remote.ts — Remote call utilities for component-to-component RPC.

import type { HostImports, ProviderInfo } from "./types.js";

let _host: HostImports | null = null;

export function setRemoteHost(host: HostImports): void {
  _host = host;
}

function host(): HostImports {
  if (!_host) throw new Error("kotodama-host-sdk: remote host not initialized");
  return _host;
}

export function remoteCall(pkg: string, iface: string, fn: string, paramsCbor: Uint8Array): Uint8Array {
  return (host() as any).remoteCallInvoke(pkg, iface, fn, paramsCbor);
}

export function remoteCallJson<T = unknown>(pkg: string, iface: string, fn: string, params: unknown): T {
  const encoded = new TextEncoder().encode(JSON.stringify(params));
  const result = remoteCall(pkg, iface, fn, encoded);
  return JSON.parse(new TextDecoder().decode(result)) as T;
}

export function remoteCallAsync(pkg: string, iface: string, fn: string, paramsCbor: Uint8Array): string {
  return (host() as any).remoteCallInvokeAsync(pkg, iface, fn, paramsCbor);
}

export function remoteDiscover(pkg: string, iface: string): ProviderInfo[] {
  const payload = (host() as any).remoteCallDiscover(pkg, iface);
  return JSON.parse(new TextDecoder().decode(payload)) as ProviderInfo[];
}
