import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { loadAllCatalogs } from "../src/catalog.ts";
import {
  LOCALES,
  NEW_LOCALES,
  STILL_EMIT,
  getLocale,
  hreflangHref,
  hreflangTags,
  localeFromCountry,
  localeFromPath,
  localePath,
} from "../src/locales.ts";
import { INSTALL_COMMAND, PLAY_WASM_SHA256, PLAY_WASM_URL } from "../src/play.ts";
import { emitTags, escapeHtml, hreflangLinks, renderPage } from "../src/render.ts";

describe("locale registry (ADR-2609091700 + expansion)", () => {
  it("keeps the shipped public-site tags and adds jv, su, he, it, ar-MA", () => {
    assert.deepEqual(
      LOCALES.map((item) => item.tag),
      [
        "en",
        "zh-Hans",
        "hi",
        "es",
        "ar",
        "fr",
        "bn",
        "pt",
        "id",
        "ur",
        "ru",
        "de",
        "ja",
        "ko",
        "pcm",
        "arz",
        "mr",
        "jv",
        "su",
        "he",
        "it",
        "ar-MA",
      ],
    );
  });

  it("marks jv and su never-country", () => {
    assert.equal(getLocale("jv").neverCountry, true);
    assert.equal(getLocale("su").neverCountry, true);
    assert.deepEqual(getLocale("jv").countries, []);
    assert.deepEqual(getLocale("su").countries, []);
  });

  it("uses rtl for Arabic family, Urdu, and Hebrew", () => {
    assert.deepEqual(
      LOCALES.filter((item) => item.dir === "rtl").map((item) => item.tag),
      ["ar", "ur", "arz", "he", "ar-MA"],
    );
  });
});

describe("country map", () => {
  it("maps the allowed countries and never jv/su", () => {
    assert.equal(localeFromCountry("ID"), "id");
    assert.equal(localeFromCountry("IL"), "he");
    assert.equal(localeFromCountry("KR"), "ko");
    assert.equal(localeFromCountry("ES"), "es");
    assert.equal(localeFromCountry("IT"), "it");
    assert.equal(localeFromCountry("DE"), "de");
    assert.equal(localeFromCountry("MA"), "ar-MA");
    assert.equal(localeFromCountry("EG"), "arz");
    assert.equal(localeFromCountry("JP"), undefined);
    assert.equal(localeFromCountry("US"), undefined);
  });
});

describe("path + catalogs + hreflang emit", () => {
  const catalogs = loadAllCatalogs();

  it("has a catalog for every registry tag including new codes", () => {
    for (const tag of [...STILL_EMIT, ...NEW_LOCALES, "en"]) {
      assert.ok(catalogs[tag]?.title, tag);
    }
  });

  it("still emits id, es, de, ko, arz on every page plus new codes", () => {
    for (const tag of LOCALES.map((item) => item.tag)) {
      const html = renderPage(tag, catalogs[tag]);
      const tags = emitTags(html);
      for (const required of STILL_EMIT) {
        assert.ok(tags.includes(required), `${tag} missing ${required}`);
        assert.ok(html.includes(`hreflang="${required}" href="${hreflangHref(required)}"`), `${tag} href ${required}`);
      }
      for (const required of NEW_LOCALES) {
        assert.ok(tags.includes(required), `${tag} missing ${required}`);
      }
      assert.ok(tags.includes("x-default"), tag);
      assert.ok(html.includes(`<html lang="${tag}"`), tag);
      if (getLocale(tag).dir === "rtl") {
        assert.ok(html.includes(`<html lang="${tag}" dir="rtl"`), tag);
      }
      assert.ok(html.includes(`data-language-selector-current>${getLocale(tag).label}`), tag);
      assert.equal(/GMV \$/.test(html), false);
      assert.equal(/Kawasaki/.test(html), false);
    }
  });

  it("exposes switcher links for every registry locale", () => {
    const html = renderPage("jv", catalogs.jv);
    assert.ok(html.includes('href="/jv/"'));
    assert.ok(html.includes('href="/su/"'));
    assert.ok(html.includes('href="/he/"'));
    assert.ok(html.includes('href="/it/"'));
    assert.ok(html.includes('href="/ar-MA/"'));
    assert.ok(html.includes('href="/id/"'));
    assert.ok(html.includes('href="/"'));
  });

  it("parses locale prefixes and leaves non-locale paths alone", () => {
    assert.equal(localeFromPath("/jv/"), "jv");
    assert.equal(localeFromPath("/ar-MA"), "ar-MA");
    assert.equal(localeFromPath("/blog/"), undefined);
    assert.equal(localePath("en"), "/");
    assert.equal(localePath("id"), "/id/");
  });

  it("lists the same hreflang set the pages emit", () => {
    const head = hreflangLinks("id");
    assert.ok(hreflangTags().every((tag) => head.includes(`hreflang="${tag}"`)));
  });

  it("puts one-line install and digest-bound Play above the fold on every locale", () => {
    for (const tag of LOCALES.map((item) => item.tag)) {
      const html = renderPage(tag, catalogs[tag]);
      const installAt = html.indexOf('id="install"');
      const playAt = html.indexOf('class="play" id="play"');
      const titleAt = html.indexOf("<h1>");
      const leadAt = html.indexOf('class="lead"');
      assert.ok(
        installAt > 0 && playAt > installAt && titleAt > playAt && leadAt > titleAt,
        `${tag} install=${installAt} play=${playAt} title=${titleAt} lead=${leadAt}`,
      );
      assert.ok(html.includes(escapeHtml(INSTALL_COMMAND)), tag);
      assert.ok(html.includes('id="kot-install-copy"'), tag);
      assert.ok(html.includes(PLAY_WASM_URL), tag);
      assert.ok(html.includes(PLAY_WASM_SHA256), tag);
      assert.ok(html.includes("wasm-webcomponent"), tag);
      assert.ok(html.includes("/play/"), tag);
      assert.ok(html.includes("defn double"), tag);
      assert.ok(html.includes("freebuff-tag.js"), tag);
      assert.ok(html.includes('type="module" src="/play/play-boot.js"'), tag);
      assert.ok(html.includes('data-sha="'), tag);
      assert.ok(html.includes('id="kot-play-host"'), tag);
      assert.equal(/GMV \$/.test(html), false, tag);
      assert.ok(html.includes("Not an in-browser compiler") || html.includes("digest") || html.includes("SHA-256"), tag);
    }
  });
});
