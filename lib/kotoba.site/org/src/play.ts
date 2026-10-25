import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/** Existing kotoba-lang.org Play artifact — not a new runtime. */
export const PLAY_WASM_URL = "/play/double-21.wasm";
export const PLAY_WASM_SHA256 = "99d43eb26371891bcca2f1fc8a48b3ad47f3350e50c50a3b7ae95b2daeafc214";
export const PLAY_SOURCE_SHA256 = "0471d55d668ed5f9887f9d2520ced9098d03dbbd57086dd3449e98dfb95f2e6b";
export const PLAY_ELEMENT_SHA256 = "1770e33def81380e0d91da9610f3ddee8132d22ef437743505f63efe855c645d";
export const INSTALL_COMMAND =
  "brew tap kotoba-lang/kotoba && brew trust kotoba-lang/kotoba && brew install kotoba";
export const DOCS_HREF = "https://github.com/kotoba-lang/kotoba-lang/tree/main/docs";
export const GITHUB_HREF = "https://github.com/kotoba-lang/kotoba-lang";
export const PLAY_HREF = "/play/";
export const PLAY_BOOT_URL = "/play/play-boot.js";

/** Existing wasm-webcomponent GitHub Pages demos — not a new compiler. */
export const WASM_WEBCOMPONENT_DEMOS = [
  {
    href: "https://kotoba-lang.github.io/wasm-webcomponent/examples/solar-helix/",
    label: "solar-helix",
  },
  {
    href: "https://kotoba-lang.github.io/wasm-webcomponent/examples/kami-survivors/",
    label: "kami-survivors",
  },
  {
    href: "https://kotoba-lang.github.io/wasm-webcomponent/examples/gpu-clear/",
    label: "gpu-clear",
  },
] as const;

export function playDir(): string {
  return join(dirname(fileURLToPath(import.meta.url)), "..", "play");
}

export function playSource(): string {
  return readFileSync(join(playDir(), "double-21.kotoba"), "utf8");
}

export const PLAY_FILES = [
  "double-21.kotoba",
  "double-21.wasm",
  "double-21.wasm.provenance.edn",
  "double-21.wasm.publication.edn",
  "kotoba-wasm-element.js",
  "play-boot.js",
  "NOTICE",
] as const;

/** Load Freebuff only when an attributed ad click (`bfcid`) is present. */
export const FREEBUFF_BOOTSTRAP =
  "(function(){try{var clickId=new URLSearchParams(location.search).get('bfcid');if(!clickId)return;window.freebuff=window.freebuff||function(){(window.freebuff.q=window.freebuff.q||[]).push(arguments);};var script=document.createElement('script');script.async=true;script.src='https://freebuff.com/freebuff-tag.js';document.head.appendChild(script);}catch(error){}})();";
