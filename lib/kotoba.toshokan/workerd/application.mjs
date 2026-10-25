import { createWorkerdHandler, dispatchPortableEffect } from "./portable-effect-host.mjs";
import { instantiateKotoba as instantiatePolicy } from "./generated/portable-effect.mjs";
import { instantiateKotoba as instantiateParser } from "./generated/ndl-parser.mjs";
import { instantiateKotoba as instantiateWorkflow } from "./generated/application.mjs";
import {
  openDatabase,
  pull as kotobasePull,
  transact as kotobaseTransact
} from "./generated/kotobase/engine.js";
import {
  chunkText,
  frameXmlElements,
  persistChunkManifest
} from "./bounded-stream.mjs";

function runtimePolicy() {
  const kotoba = instantiatePolicy({});
  return Object.freeze({
    ndlScopeAdmitted: kotoba["ndl-scope-admitted"],
    ndlLimitsAdmitted: kotoba["ndl-limits-admitted"]
  });
}

function workflow() {
  const kotoba = instantiateWorkflow({});
  return Object.freeze({
    maxBytes: Number(kotoba["harvest-max-bytes"]()),
    maxRecords: Number(kotoba["harvest-max-records"]()),
    deadlineMs: Number(kotoba["harvest-deadline-ms"]()),
    fetchAdmitted: kotoba["worker-fetch-admitted"],
    scheduledAdmitted: kotoba["worker-scheduled-admitted"]
  });
}

function harvestEffect(host, id) {
  const plan = workflow();
  const configuredMax = Number.parseInt(host.config.get("NDL_MAX_RECORDS") ?? "20", 10);
  const maxItems = Math.min(configuredMax, plan.maxRecords);
  const query = host.config.get("NDL_QUERY") ?? "title=\"夏目漱石\"";
  return {
    format: "kotoba.portable-effect/v1",
    id,
    call: "toshokan/fetch",
    effects: ["host/http"],
    ability: {
      kind: "host/http",
      resource: "library:ndl",
      target: "toshokan/http",
      operation: "get",
      limits: { maxBytes: plan.maxBytes, maxItems, deadlineMs: plan.deadlineMs },
      auditId: id
    },
    input: {
      method: "GET",
      url: "https://ndlsearch.ndl.go.jp/api/sru"
        + "?operation=searchRetrieve&version=1.2"
        + `&query=${encodeURIComponent(query)}`
        + "&recordSchema=dcndl"
        + `&maximumRecords=${maxItems}`,
      headers: {
        "User-Agent": "murakumo-toshokan/0.3 (scheduled public-metadata preservation)"
      }
    }
  };
}

function titleFromRecordFrame(frame) {
  const parser = instantiateParser({});
  const record = parser["record-data"](
    `<searchRetrieveResponse>${frame}</searchRetrieveResponse>`, 0n
  );
  if (!record[1]) return null;
  const title = parser["bib-title"](record[2], 0n);
  return title[1] ? title[2] : null;
}

function parsedRecords(xml) {
  try {
    const frames = frameXmlElements(xml, "recordData");
    const records = frames.map((frame, index) => {
      try {
        return { index, ok: true, title: titleFromRecordFrame(frame) };
      } catch (error) {
        return {
          index,
          ok: false,
          title: null,
          diagnostic: {
            name: typeof error?.name === "string" ? error.name.slice(0, 64) : "Error",
            message: typeof error?.message === "string"
              ? error.message.slice(0, 256)
              : "record parser failed"
          }
        };
      }
    });
    const titles = records.filter(record => record.ok).map(record => record.title);
    return {
      recordCount: frames.length,
      title: titles[0] ?? null,
      titles,
      records,
      parserDiagnostic: null
    };
  } catch (error) {
    return {
      recordCount: 0,
      title: null,
      titles: [],
      records: [],
      parserDiagnostic: {
        name: typeof error?.name === "string" ? error.name.slice(0, 64) : "Error",
        message: typeof error?.message === "string"
          ? error.message.slice(0, 256)
          : "parser failed"
      }
    };
  }
}

function kotobaseTransaction(id, scheduledTime, parsed, chunkManifest) {
  const entity = `ndl:${id}`;
  const triples = [
    [entity, "library/source", "ndl"],
    [entity, "library/retrieved-at", new Date(scheduledTime).toISOString()],
    [entity, "library/record-count", String(parsed.recordCount)],
    [entity, "library/chunk-root", chunkManifest.rootSha256],
    [entity, "library/total-bytes", String(chunkManifest.totalBytes)]
  ];
  for (const title of parsed.titles) {
    if (typeof title === "string" && title.length > 0)
      triples.push([entity, "library/title", title]);
  }
  return { entity, triples };
}

async function persistHarvest(bucket, id, result, scheduledTime) {
  const day = new Date(scheduledTime).toISOString().slice(0, 10);
  const prefix = `ndl/${day}/${id}`;
  const parsed = result.ok ? parsedRecords(result.value) : {
    recordCount: 0,
    title: null,
    titles: [],
    records: [],
    parserDiagnostic: null
  };
  const chunkManifest = result.ok
    ? await persistChunkManifest(
      bucket, prefix, await chunkText(result.value)
    )
    : null;
  let kotobase = null;
  if (result.ok) {
    const database = openDatabase(bucket);
    const tx = kotobaseTransaction(id, scheduledTime, parsed, chunkManifest);
    const head = await kotobaseTransact(database, tx.triples);
    const entity = await kotobasePull(database, tx.entity, [
      "library/source",
      "library/retrieved-at",
      "library/record-count",
      "library/chunk-root",
      "library/total-bytes",
      "library/title"
    ]);
    kotobase = {
      format: "kotobase.engine-receipt/v1",
      head,
      entityId: tx.entity,
      entity
    };
  }
  const summary = {
    format: "toshokan.harvest-receipt/v1",
    id,
    scheduledTime,
    ok: result.ok,
    denied: result.denied ?? null,
    diagnostic: result.diagnostic ?? null,
    title: parsed.title,
    titles: parsed.titles,
    records: parsed.records,
    recordCount: parsed.recordCount,
    parserDiagnostic: parsed.parserDiagnostic,
    chunkManifest,
    kotobase,
    abilityReceipt: result.receipt ?? null
  };
  if (result.ok) {
    // The manifest/chunks above are canonical storage. This convenience object
    // remains for ordinary HTTP/XML tooling and is never the authority root.
    await bucket.put(`${prefix}.xml`, result.value, {
      httpMetadata: { contentType: "application/xml; charset=utf-8" },
      customMetadata: { rootSha256: chunkManifest.rootSha256 }
    });
  }
  await bucket.put(`${prefix}.json`, JSON.stringify(summary), {
    httpMetadata: { contentType: "application/json; charset=utf-8" }
  });
  await bucket.put("ndl/latest.json", JSON.stringify(summary), {
    httpMetadata: { contentType: "application/json; charset=utf-8" }
  });
  return summary;
}

async function harvest(host, bucket, scheduledTime = host.clock.now()) {
  const id = `ndl-${scheduledTime}`;
  const result = await dispatchPortableEffect(harvestEffect(host, id), {
    policy: runtimePolicy(),
    fetchImpl: async (url, options) => {
      const response = await host.http.fetch({
        url,
        method: options.method,
        headers: options.headers,
        body: options.body
      });
      return new Response(response.body, { status: response.status });
    }
  });
  return persistHarvest(bucket, id, result, scheduledTime);
}

function authorized(request, host) {
  const expected = host.secret.get("TOSHOKAN_RUN_TOKEN");
  return typeof expected === "string"
    && expected.length >= 32
    && request.headers.get("authorization") === `Bearer ${expected}`;
}

function closedBucket(host, binding) {
  return Object.freeze({
    async get(key) {
      const object = await host.objectStore.get(binding, key);
      if (!object) return null;
      return Object.freeze({
        etag: object.etag,
        body: object.bytes,
        arrayBuffer: async () => object.bytes.buffer.slice(
          object.bytes.byteOffset,
          object.bytes.byteOffset + object.bytes.byteLength
        ),
        text: async () => new TextDecoder().decode(object.bytes)
      });
    },
    async put(key, value, options = {}) {
      const onlyIf = options.onlyIf;
      if (onlyIf?.etagMatches) {
        const result = await host.objectStore.compareAndSet(
          binding, key, onlyIf.etagMatches, value
        );
        return result.won ? { etag: result.etag } : null;
      }
      if (onlyIf?.etagDoesNotMatch === "*")
        return host.objectStore.putImmutable(binding, key, value);
      return host.objectStore.put(binding, key, value);
    }
  });
}

export function createApplication(host) {
  const lifecycle = workflow();
  const bucket = closedBucket(host, "TOSHOKAN_BUCKET");
  const effectFetch = createWorkerdHandler({
    policy: runtimePolicy(),
    fetchImpl: async (url, options) => {
      const response = await host.http.fetch({
        url,
        method: options.method,
        headers: options.headers,
        body: options.body
      });
      return new Response(response.body, { status: response.status });
    }
  }).fetch;
  return Object.freeze({
  async fetch(request, ctx) {
    const url = new URL(request.url);
    if (lifecycle.fetchAdmitted(request.method, url.pathname) !== 1n)
      return Response.json({ ok: false, error: "not-found" }, { status: 404 });
    if (request.method === "GET" && url.pathname === "/health") {
      return Response.json({
        ok: true,
        service: "murakumo-toshokan",
        policy: "kotoba",
        parser: "kotoba",
        persistence: true,
        host: "kotoba.generated-workerd/v1"
      });
    }
    if (request.method === "GET" && url.pathname === "/latest") {
      const object = await bucket.get("ndl/latest.json");
      if (!object)
        return Response.json({ ok: false, error: "no-harvest-yet" }, { status: 404 });
      return new Response(object.body, {
        headers: { "content-type": "application/json; charset=utf-8" }
      });
    }
    if (request.method === "POST" && url.pathname === "/run") {
      if (!authorized(request, host))
        return Response.json({ ok: false, denied: "unauthorized" }, { status: 401 });
      const summary = await harvest(host, bucket);
      return Response.json(summary, { status: summary.ok ? 200 : 502 });
    }
    if (request.method === "POST" && url.pathname === "/effect") {
      if (!authorized(request, host))
        return Response.json({ ok: false, denied: "unauthorized" }, { status: 401 });
      return effectFetch(request);
    }
    return Response.json({ ok: false, error: "not-found" }, { status: 404 });
  },

  async scheduled(controller, ctx) {
    if (lifecycle.scheduledAdmitted(controller.cron ?? "") !== 1n)
      throw new Error("scheduled-lifecycle-denied");
    ctx.waitUntil(
      harvest(host, bucket, controller.scheduledTime)
        .then(summary => console.log(JSON.stringify(summary)))
    );
  }
  });
}
