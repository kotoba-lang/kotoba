# Kotodama Inference Moved

The inference runtime has moved out of the deep `kotoba` crate tree.

Canonical repository:

```text
https://github.com/kotoba-lang/inference
```

Local sibling checkout:

```text
../inference
```

`kotoba` keeps Kotoba language, host, and capability integration code. The
portable CLJC/Rust inference runtime, browser worker, WGSL shaders, and real
model verification now live in `kotoba-lang/inference`.
