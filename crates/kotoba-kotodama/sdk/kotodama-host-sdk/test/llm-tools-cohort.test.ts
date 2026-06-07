import { describe, it, expect } from 'vitest';
import {
  cohortToolSpecs,
  cohortToolDispatch,
  cohortToolNsid,
  createCohortToolHandler,
} from '../src/llm-tools-cohort.js';

describe('cohortToolSpecs', () => {
  it('exports 4 tool specs (seed/emit/fission/list)', () => {
    expect(cohortToolSpecs).toHaveLength(4);
    const names = cohortToolSpecs.map((t) => t.function.name);
    expect(names).toEqual([
      'cohort_seed',
      'cohort_emit_evidence',
      'cohort_fission',
      'cohort_list',
    ]);
  });

  it('cohort_fission gates posterior at 0.95 minimum', () => {
    const spec = cohortToolSpecs.find((t) => t.function.name === 'cohort_fission')!;
    const p = (spec.function.parameters as any).properties.posterior;
    expect(p.minimum).toBe(0.95);
    expect(p.maximum).toBe(1);
  });

  it('cohort_fission gates judgeAgreement to const true', () => {
    const spec = cohortToolSpecs.find((t) => t.function.name === 'cohort_fission')!;
    const j = (spec.function.parameters as any).properties.judgeAgreement;
    expect(j.const).toBe(true);
  });

  it('cohort_seed kAnonymity defaults to 50', () => {
    const spec = cohortToolSpecs.find((t) => t.function.name === 'cohort_seed')!;
    const k = (spec.function.parameters as any).properties.kAnonymity;
    expect(k.default).toBe(50);
    expect(k.minimum).toBe(50);
  });
});

describe('cohortToolDispatch', () => {
  it('maps every tool to an NSID', () => {
    for (const tool of cohortToolSpecs) {
      const entry = cohortToolDispatch[tool.function.name];
      expect(entry).toBeDefined();
      expect(entry.nsid).toMatch(/^com\.etzhayyim\.cohort\./);
    }
  });

  it('cohort_seed builds segmentJsonld from typed fields', () => {
    const body = cohortToolDispatch.cohort_seed.buildBody({
      pcfL1: '3-market-sell',
      role: 'salesRep',
      locale: 'jp',
      kAnonymity: 50,
    }) as any;
    expect(body.kAnonymity).toBe(50);
    const seg = JSON.parse(body.segmentJsonld);
    expect(seg.pcfL1).toBe('3-market-sell');
    expect(seg.role).toBe('salesRep');
    expect(seg.locale).toBe('jp');
  });

  it('cohort_seed includes optional industry / seniority when present', () => {
    const body = cohortToolDispatch.cohort_seed.buildBody({
      pcfL1: '8-info-technology',
      role: 'sreEngineer',
      locale: 'en',
      industry: 'banking',
      seniority: 'senior',
    }) as any;
    const seg = JSON.parse(body.segmentJsonld);
    expect(seg.industry).toBe('banking');
    expect(seg.seniority).toBe('senior');
  });

  it('cohort_seed defaults kAnonymity to 50 when missing', () => {
    const body = cohortToolDispatch.cohort_seed.buildBody({
      pcfL1: 'x',
      role: 'y',
      locale: 'jp',
    }) as any;
    expect(body.kAnonymity).toBe(50);
  });
});

describe('cohortToolNsid', () => {
  it('returns NSID for known tool', () => {
    expect(cohortToolNsid('cohort_fission')).toBe('com.etzhayyim.cohort.fission');
  });
  it('returns null for unknown tool', () => {
    expect(cohortToolNsid('not_a_tool')).toBeNull();
  });
});

describe('createCohortToolHandler', () => {
  it('returns null for unknown tool name', async () => {
    const handler = createCohortToolHandler({
      pdsBaseUrl: 'https://atproto.etzhayyim.com',
      bearerToken: 'tok',
      fetchImpl: (async () => new Response('{}')) as any,
    });
    const r = await handler('not_a_cohort_tool', {});
    expect(r).toBeNull();
  });

  it('routes cohort_seed via POST + Bearer auth + segmentJsonld', async () => {
    let captured: any = null;
    const handler = createCohortToolHandler({
      pdsBaseUrl: 'https://atproto.etzhayyim.com',
      bearerToken: 'tok-abc',
      fetchImpl: (async (url: string, init: any) => {
        captured = { url, init };
        return new Response(JSON.stringify({ did: 'did:plc:pending-x' }), {
          status: 200,
        });
      }) as any,
    });
    const r = await handler('cohort_seed', {
      pcfL1: '3-market-sell',
      role: 'salesRep',
      locale: 'jp',
    }) as any;
    expect(r.did).toBe('did:plc:pending-x');
    expect(captured.url).toBe('https://atproto.etzhayyim.com/xrpc/com.etzhayyim.cohort.seed');
    expect(captured.init.method).toBe('POST');
    expect(captured.init.headers.Authorization).toBe('Bearer tok-abc');
    const body = JSON.parse(captured.init.body);
    expect(body.kAnonymity).toBe(50);
    const seg = JSON.parse(body.segmentJsonld);
    expect(seg.role).toBe('salesRep');
  });

  it('routes cohort_list via GET + query params', async () => {
    let captured: any = null;
    const handler = createCohortToolHandler({
      pdsBaseUrl: 'https://atproto.etzhayyim.com',
      bearerToken: 'tok',
      fetchImpl: (async (url: string, init: any) => {
        captured = { url, init };
        return new Response(JSON.stringify({ cohorts: [] }));
      }) as any,
    });
    await handler('cohort_list', { pcfL1: '8-info-technology', limit: 50 });
    expect(captured.url).toContain('?');
    expect(captured.url).toContain('pcfL1=8-info-technology');
    expect(captured.url).toContain('limit=50');
    expect(captured.init).toBeUndefined(); // no body for GET
  });

  it('returns error object on non-2xx', async () => {
    const handler = createCohortToolHandler({
      pdsBaseUrl: 'https://atproto.etzhayyim.com',
      bearerToken: 'tok',
      fetchImpl: (async () => new Response('oops', { status: 500 })) as any,
    });
    const r = await handler('cohort_seed', {
      pcfL1: 'x',
      role: 'y',
      locale: 'jp',
    }) as any;
    expect(r.error).toContain('500');
  });
});
