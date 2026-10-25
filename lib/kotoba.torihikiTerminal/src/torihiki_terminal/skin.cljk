(ns torihiki-terminal.skin
  "The DADS skin: デジタル庁 colours and type under the terminal's own layout.

  ## What a skin is here, and what it is not

  `jp-go-dds.tokens/hig->dads` maps the `--hig-*` CONTRACT onto DADS
  primitives, and it maps colours and font families — not spacing, not radius,
  not the eleven text sizes. That is not an omission: DADS has no spacing or
  radius scale to map onto, and the bridge's own rule is that a mapping is
  always `var(--dads-primitive)` rather than a value written here.

  So the bridge is designed to be layered OVER a page that already defines the
  structural half of the contract, which `kotoba-ui.theme` does. Replacing the
  page builder instead of skinning it would leave `--hig-spacing-*` and
  `--hig-radius-*` undefined — and an undefined custom property makes the whole
  declaration invalid rather than falling back, so the layout would collapse
  quietly, with no error anywhere.

  That is why this app still requires `kotoba-ui.core` (agent-guide rule 1),
  and why the swap the owner asked for is a skin: every colour and typeface on
  the page comes from デジタル庁, and the geometry keeps coming from HIG.

  ## The accent is deliberately not DADS

  `brand-tokens` excludes `--hig-color-tint`, so the terminal keeps its teal.
  The bridge would otherwise repaint it デジタル庁 key blue — correct for a
  government design system, whose purpose is that every site looks the same,
  and wrong for a product that is not a government site.

  ## Dark is forced, not offered

  The terminal is dark. `kotoba-ui.shell/page` stamps `data-appearance` on
  `<html>`, so `jp-go-dds.dark/dark-css`'s `[data-theme]` selector never
  matches and its `@media` gate would leave a light-OS visitor with DADS light
  primitives under a dark layout. `forced-dark-css` is the unconditional form."
  (:require [jp-go-dds.dark :as dark]
            [jp-go-dds.tokens :as dds-tokens]))

(defn skin-css
  "The whole skin, in cascade order: DADS primitives, the dark mirror of them,
  then the `--hig-*` bridge that reads them.

  The bridge last because it references the primitives through `var()` — it
  resolves at use, so order between it and the dark layer does not matter for
  correctness, only for reading.

  `dds-css` is passed in rather than read here: this namespace has to compile
  under ClojureScript too, where there is no resource to slurp."
  [dds-css]
  (str (dds-tokens/root-css dds-css) "\n"
       (dark/forced-dark-css dds-css) "\n"
       (dds-tokens/bridge-css-except dds-tokens/brand-tokens)))
