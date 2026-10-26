const ARTIFACT_SCHEMA = "kotoba-js-artifact/v1";

function bytesToBase64(bytes) {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

async function sha256Hex(text) {
  const bytes = new TextEncoder().encode(text);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return [...digest].map(b => b.toString(16).padStart(2, "0")).join("");
}

async function verifiedModule(moduleUrl, verification = {}) {
  const sourceText = verification.sourceText ?? await fetch(moduleUrl).then(response => {
    if (!response.ok) throw new Error(`kotoba-artifact-fetch-failed:${response.status}`);
    return response.text();
  });
  const manifest = verification.manifest ?? await fetch(`${moduleUrl}.manifest.json`).then(response => {
    if (!response.ok) throw new Error(`kotoba-manifest-fetch-failed:${response.status}`);
    return response.json();
  });
  if (manifest["kotoba.artifact/schema"] !== ARTIFACT_SCHEMA) {
    throw new Error("kotoba-manifest-schema-rejected");
  }
  const actual = await sha256Hex(sourceText);
  if (actual !== manifest["kotoba.artifact/output-digest"]) {
    throw new Error("kotoba-output-digest-mismatch");
  }
  const encoded = bytesToBase64(new TextEncoder().encode(sourceText));
  return { module: await import(`data:text/javascript;base64,${encoded}`), manifest };
}

function assertArtifact(module) {
  const artifact = module?.kotobaArtifact;
  if (!Object.isFrozen(artifact) || artifact.schema !== ARTIFACT_SCHEMA) {
    throw new Error("kotoba-artifact-rejected");
  }
  if (!Array.isArray(artifact.requiredCapabilities) ||
      !Object.isFrozen(artifact.requiredCapabilities) ||
      !artifact.requiredCapabilities.every(Number.isInteger)) {
    throw new Error("kotoba-capability-manifest-rejected");
  }
  if (typeof module.instantiateKotoba !== "function") {
    throw new Error("kotoba-instantiator-missing");
  }
  return artifact;
}

export async function loadKotobaScript(moduleUrl, providers = new Map(), verification = {}) {
  const { module, manifest } = await verifiedModule(moduleUrl, verification);
  const artifact = assertArtifact(module);
  if (artifact.sourceDigest !== manifest["kotoba.artifact/source-digest"] ||
      artifact.kirDigest !== manifest["kotoba.artifact/kir-digest"] ||
      artifact.compilerVersion !== manifest["kotoba.artifact/compiler-version"]) {
    throw new Error("kotoba-embedded-metadata-mismatch");
  }
  const required = [...artifact.requiredCapabilities].sort((a, b) => a - b);
  const supplied = [...providers.keys()].sort((a, b) => a - b);
  if (required.length !== supplied.length || required.some((id, i) => id !== supplied[i])) {
    throw new Error("kotoba-capability-grant-mismatch");
  }
  const grants = Object.create(null);
  for (const id of required) {
    const provider = providers.get(id);
    if (typeof provider !== "function") throw new Error(`kotoba-provider-invalid:${id}`);
    Object.defineProperty(grants, id, { value: provider, enumerable: true });
  }
  const instance = module.instantiateKotoba(Object.freeze(grants));
  if (!Object.isFrozen(instance)) throw new Error("kotoba-instance-not-frozen");
  return Object.freeze({ artifact, manifest: Object.freeze(manifest), instance });
}

export async function runKotobaScript(moduleUrl, options = {}) {
  const { providers = new Map(), exportName = "main", args = [], verification = {} } = options;
  const loaded = await loadKotobaScript(moduleUrl, providers, verification);
  const entry = loaded.instance[exportName];
  if (typeof entry !== "function") throw new Error(`kotoba-export-missing:${exportName}`);
  return Object.freeze({ artifact: loaded.artifact, value: entry(...args) });
}
