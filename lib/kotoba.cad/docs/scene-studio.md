# Kami Scene Studio UI contract

`kotoba-lang/cad` is the Rhino/CAD-side workbench. Its GitHub Pages surface,
Kami Scene Studio, gives it the visual-authoring loop associated with tools
such as Twinmotion while keeping the boundaries appropriate for an OSS web
application.

## Product split

| Layer | Responsibility |
| --- | --- |
| `cad` | EDN domain model, artifact intake, browser authoring state, and GitHub Pages UI |
| Kami Scene Studio | scene graph, camera, environment, asset placement, preview, and EDN export |
| `kami-engine` | scene/WIT contracts and adapter registry |
| native or WASM adapter | WebGPU rendering, importers, physics, and file-system integrations |

The page never executes a host runner and never claims that an SVG preview is
a geometry kernel. It creates portable state that a renderer can consume.

## Interaction model

The primary view uses the spatial-editor pattern:

1. Choose a node in the scene graph or directly in the scene preview.
2. Set the camera mode and art direction (time and weather).
3. Place a high-level asset from the lower shelf.
4. Inspect the selected node and export `kotoba-cad-state.edn`.

Presentation mode removes authoring chrome so a review can happen directly
from the same URL. The layout collapses the scene tree and inspector on small
screens; the preview and asset shelf remain usable.

## GitHub Pages delivery

`amu compile --target wasm32-browser app` writes the static bundle to `docs/js`. The Pages
workflow tests and lints the CLJ sources, builds the CLJS bundle, and deploys
the `docs/` directory. The resulting site has no runtime secrets, server, or
vendor SDK requirement.
