//! Generated declarations for the authoritative typed capability world.
//!
//! This module deliberately has no hand-copied WIT. Cargo receives the path
//! from `kotoba-abi-wit`'s build metadata, pinned in Cargo.lock. The concrete
//! linker registration is enabled only for Components that declare this world.

wasmtime::component::bindgen!({
    path: "wit/aiueos-capability-v2",
    world: "application",
    imports: { default: trappable },
    // The opaque WIT resource is backed by the native-only record below;
    // generated provider traits therefore cannot manufacture a grant.
    with: {
        "aiueos:capability/capability.grant": crate::Grant,
        "aiueos:capability/capability.bytes-task": crate::BytesTask,
        "aiueos:capability/capability.bytes-stream": crate::BytesStream,
    },
});
