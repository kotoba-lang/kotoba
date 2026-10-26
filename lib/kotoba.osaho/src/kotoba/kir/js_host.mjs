// Static JS-host primitive for the interpreted CLJK reference runtime.
// Never evaluate source or inspect user-controlled properties.
// Boolean observation uses intrinsic truthiness without user coercion hooks.
export function typeOf(value) {
  return typeof value;
}

export function arrayBrand(value) {
  return !!Array.isArray(value);
}

// Internal trampoline controls are identified by allocation, not by properties
// of an arbitrary opaque result. Weak membership does not read Proxy targets,
// and consumed controls cannot be replayed as a fresh internal tail call.
const trampolineControls = new WeakSet();
const weakAdd = WeakSet.prototype.add;
const weakHas = WeakSet.prototype.has;
const weakDelete = WeakSet.prototype.delete;
const invoke = Reflect.apply;

export function registerTrampoline(control) {
  invoke(weakAdd, trampolineControls, [control]);
  return control;
}

export function consumeTrampoline(value) {
  if (!invoke(weakHas, trampolineControls, [value])) return false;
  invoke(weakDelete, trampolineControls, [value]);
  return true;
}
