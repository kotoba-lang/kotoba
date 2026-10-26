const exactKeys = (value, keys) =>
  value !== null &&
  typeof value === "object" &&
  Object.keys(value).sort().join("\0") === [...keys].sort().join("\0");

const reject = (reason) => {
  throw new Error(`kototama workerd admission rejected: ${reason}`);
};

export const createKototamaCoreHost = ({
  module,
  manifest,
  providers,
  authorize,
}) => {
  if (!(module instanceof WebAssembly.Module) ||
      !exactKeys(manifest, ["format", "imports", "grants"]) ||
      manifest.format !== "kototama.workerd-core/v1" ||
      !Array.isArray(manifest.imports) ||
      !Array.isArray(manifest.grants) ||
      typeof authorize !== "function" ||
      providers === null ||
      typeof providers !== "object") {
    reject("invalid-manifest");
  }

  const grants = new Set(manifest.grants);
  const imports = {};
  const capabilities = new Set();
  const declaredImports = new Set();
  for (const entry of manifest.imports) {
    if (!exactKeys(entry, ["module", "name", "capability", "ability"]) ||
        typeof entry.module !== "string" ||
        typeof entry.name !== "string" ||
        typeof entry.capability !== "string" ||
        capabilities.has(entry.capability) ||
        !grants.has(entry.capability) ||
        typeof providers[entry.capability] !== "function") {
      reject("unbound-import");
    }
    capabilities.add(entry.capability);
    declaredImports.add(`${entry.module}\0${entry.name}`);
    imports[entry.module] ??= {};
    if (Object.hasOwn(imports[entry.module], entry.name)) {
      reject("duplicate-import");
    }
    imports[entry.module][entry.name] = (...args) => {
      if (authorize(entry.capability, entry.ability, args) !== true) {
        reject("provider-call-denied");
      }
      return providers[entry.capability]({
        capability: entry.capability,
        ability: entry.ability,
        args,
      });
    };
  }
  if (grants.size !== capabilities.size ||
      [...grants].some((grant) => !capabilities.has(grant))) {
    reject("grant-import-mismatch");
  }
  const actualImports = WebAssembly.Module.imports(module);
  if (actualImports.length !== declaredImports.size ||
      actualImports.some(({ module: namespace, name, kind }) =>
        kind !== "function" ||
        !declaredImports.has(`${namespace}\0${name}`))) {
    reject("module-import-mismatch");
  }

  const instance = new WebAssembly.Instance(module, imports);
  return Object.freeze({
    invoke(exportName, ...args) {
      const fn = instance.exports[exportName];
      if (typeof fn !== "function") reject("unknown-export");
      return fn(...args);
    },
  });
};
