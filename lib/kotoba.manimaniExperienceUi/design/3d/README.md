# Manimani-kun 3D

`manimani-wheel-reference.svg` is the vector master for image-to-3D generation.
The checked-in PNG is the deterministic 2048 px raster input sent to
`api.murakumo.cloud`. The target is a toy-like Manimani-kun cow running inside
a large prayer/hamster wheel; wheel rotation and the cow run cycle remain
separate animation channels at runtime.

`generation-request.json` records the public, non-secret Murakumo request. The
resulting `manimani-wheel.glb` and its receipt are added only after artifact
hash and GLB magic validation pass.
