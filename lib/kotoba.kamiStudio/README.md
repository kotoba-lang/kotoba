# kami-studio

The **Kami Studio hub page** — a static, link-out landing page for the separate
`kami-app-*` 3D editors. It is *not* an editor itself and holds no scene,
geometry, or document state; every card on the page is an external link.

## What this repo actually contains

| Path | Role |
|---|---|
| `src/kami/studio/ui.cljk` | The whole page: the `apps` link table, a `css/css` stylesheet, and `page` returning hiccup |
| `build.cljk` | Two forms — `(spit "public/index.html" (ui/page))` |
| `public/index.html` | **Committed generated output.** Do not hand-edit; regenerate from `ui.cljc` |
| `deps.edn` | `kotoba-lang/html` + `kotoba-lang/css`, pinned by `:git/sha` |

There is no reagent, no bundler, and no runtime JavaScript — `page` renders to a
single HTML document at build time.

## The links

Seven cards resolve to six apps: Modeler, Animator, BIM Editor, CAD, Sculpt, and
Amenominaka. **Vehicle Physics is not a seventh app** — it is `kami-app-modeler`
opened at `?workspace=vehicle-physics`. All seven point at
`kotoba-lang.github.io/kami-app-*`.

To add or move a card, edit the `apps` vector in `src/kami/studio/ui.cljk` and
**rebuild** (see below). Nothing else reads that table.

## Build and deploy — the generated file is the deployed file

```
kbb -M build.cljk      # rewrites public/index.html from src/kami/studio/ui.cljk
```

`.github/workflows/pages.yml` **does not run this build.** It runs
`upload-pages-artifact` with `path: public` and publishes whatever `public/` is
committed on `main`. So the deploy step cannot notice that `index.html` is stale:

> Editing `ui.cljc` without rebuilding changes nothing about the live site, and
> nothing fails. The page still renders — it just renders the older link table.

This has already happened once. `5192750` added the Vehicle Physics card to
`ui.cljc`; `public/index.html` was last written by `2ef356b`, before it. The live
page served six cards while the source described seven, and no check was in a
position to say so. Regenerating is what fixed it.

**Therefore: any commit touching `ui.cljc` must include the regenerated
`public/index.html` in the same commit.** Reviewing the source alone is not
enough to know what is deployed.

## Boundary

Per the kami stack rule (`com-junkawasaki/root` AGENTS.md, 3D section), the
authority for geometry, scene, animation, and rendering lives in `kami-engine-*`
and the `webgpu` / `webgl` libraries — never in an app or in this hub. This repo
owns exactly one thing: which apps exist and how to reach them.

Styling is hand-written CSS in `ui.cljc` predating the `jp-go-dds` design-system
rule; new UI in this workspace starts from `jp-go-dds`, so treat this stylesheet
as legacy rather than as a pattern to copy.

## Test

```
kbb -M:test        # from the repo root
```

`test/kami/studio/staleness_test.cljk` renders `ui/page` and compares it byte for
byte against the committed `public/index.html` — the check whose absence let
`5192750` ship a source with seven cards and a deployed page with six. It also
asserts, separately, that `ui/apps` and the committed page agree on the card
count and that every app URL appears in the file, so the failure message names
the regression rather than only reporting a byte difference.

`test/run.cljk` reports the **number** of failures and distinguishes three
outcomes: exit 0 = passed, exit 1 = a real failure, exit 2 = the check refused to
answer (run from the wrong directory, or no tests ran). Exit 2 is not a pass.

It runs on the JVM deliberately. `deps.edn` pins `kotoba-lang/html` and
`kotoba-lang/css` by `:git/sha` and `build.cljk` renders against those exact shas;
a runner reaching the sibling west checkouts instead would render against
different versions than the build does, and its verdict about staleness would not
be about the deployed file.

Still not covered: nothing fetches the `kami-app-*` URLs, so a card can point at
a page that 404s and this test stays green.

## License

Apache-2.0 (see `LICENSE`).
