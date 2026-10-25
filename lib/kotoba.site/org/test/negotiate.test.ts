import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { COOKIE_NAME, localeFromCountry } from "../src/locales.ts";
import { cookieHeader, matchAcceptLanguage, negotiate, parseCookie } from "../src/negotiate.ts";

describe("negotiate order: path > cookie > Accept-Language > country > en", () => {
  it("prefers path over everything", () => {
    assert.deepEqual(
      negotiate({
        pathname: "/he/",
        cookieHeader: `${COOKIE_NAME}=it`,
        acceptLanguage: "id",
        country: "DE",
      }),
      { tag: "he", source: "path" },
    );
  });

  it("uses cookie when the path is unprefixed", () => {
    assert.deepEqual(
      negotiate({
        pathname: "/",
        cookieHeader: cookieHeader("ko"),
        acceptLanguage: "de",
        country: "IT",
      }),
      { tag: "ko", source: "cookie" },
    );
  });

  it("uses Accept-Language before country, including jv/su", () => {
    assert.deepEqual(
      negotiate({
        pathname: "/",
        acceptLanguage: "jv, su;q=0.8, id;q=0.1",
        country: "ID",
      }),
      { tag: "jv", source: "accept-language" },
    );
    assert.deepEqual(
      negotiate({
        pathname: "/",
        acceptLanguage: "su-ID;q=0.9, en;q=0.1",
        country: "ID",
      }),
      { tag: "su", source: "accept-language" },
    );
  });

  it("uses country when no path, cookie, or language match", () => {
    const cases: Array<[string, string]> = [
      ["ID", "id"],
      ["IL", "he"],
      ["KR", "ko"],
      ["ES", "es"],
      ["IT", "it"],
      ["DE", "de"],
      ["MA", "ar-MA"],
      ["EG", "arz"],
    ];
    for (const [country, tag] of cases) {
      assert.deepEqual(negotiate({ pathname: "/", country }), { tag, source: "country" }, country);
    }
  });

  it("never selects jv or su from country", () => {
    assert.equal(localeFromCountry("ID"), "id");
    assert.notEqual(negotiate({ pathname: "/", country: "ID" }).tag, "jv");
    assert.notEqual(negotiate({ pathname: "/", country: "ID" }).tag, "su");
    assert.equal(negotiate({ pathname: "/", country: "JP" }).tag, "en");
  });

  it("falls back to en", () => {
    assert.deepEqual(negotiate({ pathname: "/" }), { tag: "en", source: "default" });
  });

  it("matches regional Accept-Language prefixes", () => {
    assert.equal(matchAcceptLanguage("it-IT,en;q=0.8"), "it");
    assert.equal(matchAcceptLanguage("he-IL"), "he");
    assert.equal(matchAcceptLanguage("id-ID,id;q=0.9"), "id");
    assert.equal(matchAcceptLanguage("ar-MA,ar;q=0.8"), "ar-MA");
    assert.equal(matchAcceptLanguage("arz,ar;q=0.5"), "arz");
    assert.equal(matchAcceptLanguage("zh-CN,en;q=0.5"), "zh-Hans");
  });

  it("ignores unknown cookies", () => {
    assert.equal(parseCookie("other=id"), undefined);
    assert.equal(negotiate({ pathname: "/", cookieHeader: "kotoba_lang=xx" }).source, "default");
  });
});
