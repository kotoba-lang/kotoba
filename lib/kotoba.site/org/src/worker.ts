/**
 * kotoba-lang-org Worker.
 *
 * Negotiate locale on the origin BEFORE the static asset cache can pin
 * English on `/`. Locale-prefixed paths stay cacheable; `/` is Vary'd and
 * not stored on the CDN.
 *
 * Default English stays on the apex (200, never Location: /). Non-default
 * locales 307 to `/{tag}/`. Do not ASSETS.fetch `/index.html` — wrangler
 * html_handling=auto-trailing-slash 307s that to `/` and loops.
 */

import { DEFAULT_LOCALE, localeFromPath, localePath } from "./locales.ts";
import { cookieHeader, negotiate } from "./negotiate.ts";

export interface Env {
  ASSETS: { fetch(input: Request | URL | string, init?: RequestInit): Promise<Response> };
}

type IncomingRequest = Request & { cf?: { country?: string } };

const NEGOTIATED_PATHS = new Set(["/", "/index.html"]);

const ASSET_PREFIXES = [
  "/favicon",
  "/kotoba-",
  "/assets/",
  "/play/",
  "/benchmarks/",
  "/llms",
  "/agent-quickstart",
  "/robots.txt",
  "/sitemap.xml",
  "/dependencies.edn",
];

function isPassthroughAsset(pathname: string): boolean {
  return ASSET_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(prefix));
}

function varyHeaders(negotiated: boolean): HeadersInit {
  if (!negotiated) {
    return {
      "Cache-Control": "public, max-age=0, must-revalidate",
      "Content-Language": "",
    };
  }
  return {
    "Cache-Control": "private, no-cache",
    "CDN-Cache-Control": "no-store",
    "Cloudflare-CDN-Cache-Control": "no-store",
    Vary: "Accept-Language, Cookie, CF-IPCountry",
  };
}

function withLocale(response: Response, tag: string, negotiated: boolean, setCookie: boolean): Response {
  const headers = new Headers(response.headers);
  const extra = varyHeaders(negotiated);
  for (const [key, value] of Object.entries(extra)) {
    if (value) headers.set(key, value);
  }
  headers.set("Content-Language", tag);
  if (setCookie) headers.append("Set-Cookie", cookieHeader(tag));
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

/** True when Location would send the client back to the request path (loop). */
export function isSelfLocation(location: string, requestUrl: URL): boolean {
  try {
    const dest = new URL(location, requestUrl);
    const destPath = dest.pathname || "/";
    const requestPath = requestUrl.pathname || "/";
    return dest.origin === requestUrl.origin && destPath === requestPath;
  } catch {
    return location === requestUrl.pathname;
  }
}

function negotiatedRedirect(destPath: string, tag: string, setCookie: boolean): Response {
  const headers = new Headers(varyHeaders(true));
  headers.set("Location", destPath);
  headers.set("Content-Language", tag);
  if (setCookie) headers.append("Set-Cookie", cookieHeader(tag));
  return new Response(null, { status: 307, headers });
}

export async function handleRequest(request: IncomingRequest, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const { pathname } = url;

  if (pathname === "/play") {
    return new Response(null, {
      status: 308,
      headers: {
        Location: "/play/",
        "Cache-Control": "public, max-age=86400",
      },
    });
  }

  if (isPassthroughAsset(pathname)) {
    return env.ASSETS.fetch(request);
  }

  const pathLocale = localeFromPath(pathname);
  if (pathLocale && (pathname === `/${pathLocale}` || pathname === `/${pathLocale}/index.html`)) {
    const dest = new URL(localePath(pathLocale, "/"), url);
    return new Response(null, {
      status: 308,
      headers: {
        Location: dest.pathname,
        "Cache-Control": "public, max-age=86400",
        "Set-Cookie": cookieHeader(pathLocale),
        "Content-Language": pathLocale,
      },
    });
  }

  if (pathLocale) {
    const asset = await env.ASSETS.fetch(request);
    return withLocale(asset, pathLocale, false, true);
  }

  if (!NEGOTIATED_PATHS.has(pathname)) {
    return env.ASSETS.fetch(request);
  }

  const decided = negotiate({
    pathname,
    cookieHeader: request.headers.get("Cookie"),
    acceptLanguage: request.headers.get("Accept-Language"),
    country: request.cf?.country,
  });

  const destPath = localePath(decided.tag, "/");
  const setCookie = decided.tag !== DEFAULT_LOCALE || decided.source !== "default";

  // English is the apex document at `/`. localePath("en") is `/` (or `/en/`
  // collapsing to `/`). Redirecting GET / there 307-loops: CF assets
  // html_handling=auto-trailing-slash turns `/index.html` into Location: /.
  // Only redirect when the negotiated tag has a distinct prefix path.
  if (
    decided.tag !== DEFAULT_LOCALE &&
    destPath !== pathname &&
    destPath !== "/" &&
    !isSelfLocation(destPath, url)
  ) {
    return negotiatedRedirect(destPath, decided.tag, setCookie);
  }

  // Fetch `/`, never `/index.html`, so ASSETS cannot 307 Location: /.
  const assetRequest = pathname === "/" ? request : new Request(new URL("/", url), request);
  const asset = await env.ASSETS.fetch(assetRequest);
  return withLocale(asset, decided.tag, true, setCookie);
}

export default {
  fetch(request: IncomingRequest, env: Env): Promise<Response> {
    return handleRequest(request, env);
  },
};
