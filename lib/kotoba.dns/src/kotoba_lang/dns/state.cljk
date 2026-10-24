(ns kotoba-lang.dns.state
  "UI state for the dns (etzhayyim-project-dns) appview. Ported from the
  former appview/etzhayyim-wasm-dns-scndu0rf/svelte/src/routes/+page.svelte
  template shell — a single static screen describing the app surface (title
  / project / routes / bindings / source path). The shell's placeholder
  facts (0 routes, no vars, path into the deleted svelte tree) are replaced
  with the truth served by appview/etzhayyim-wasm-dns-scndu0rf/src/app.ts +
  wrangler.jsonc. Single reagent atom, murakumo-studio構成."
  (:require [reagent.core :as r]))

(defonce state
  (r/atom
   {:app {:title "DNS / Cloudflare Registrar"
          :project "etzhayyim-project-dns"
          :name "etzhayyim-wasm-dns-scndu0rf"
          :kind "appview"
          :route-count 2
          :routes ["/xrpc/com.etzhayyim.dns.*" "/_app/meta"]
          :vars ["APP_NANOID" "APP_CAPABILITIES" "APP_FRAMEWORK"
                 "AGENTGATEWAY_MCP_ROUTER_URL"]
          :xrpc? true
          :relative-path "appview/etzhayyim-wasm-dns-scndu0rf/src/app.ts"}}))
