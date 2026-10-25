# models/

Drop the VRM avatar referenced by `:dance/avatar :vrm` in `../scene.edn` here
(e.g. `mitama.vrm`). VRM/GLB assets are host-supplied and not checked in.
The host loads them via `kami-vrm` (`kami-web::run_embed_vrm`, ADR-0031).
