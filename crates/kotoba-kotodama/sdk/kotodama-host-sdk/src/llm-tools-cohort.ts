/**
 * Cohort LLM tool registration (ADR-0026).
 *
 * Exposes com.etzhayyim.cohort.* procedures as OpenAI-compatible tool schemas
 * so Murakumo / Ameno LLM agents can drive the cohort lifecycle by name.
 *
 * Spec: `90-docs/260415-cohort-llm-tool-registration-spec.md`
 *
 * Safety:
 *   - cohort_fission posterior min 0.95 + judgeAgreement const true
 *     (LLM cannot accidentally trigger fission without the gate met)
 *   - cohort_seed kAnonymity defaults to 50 (ADR-0026 R2 floor)
 */

export interface OpenAIToolSpec {
  type: 'function';
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
}

export const cohortToolSpecs: ReadonlyArray<OpenAIToolSpec> = [
  {
    type: 'function',
    function: {
      name: 'cohort_seed',
      description:
        'Create a new cohort generative actor (ADR-0026 Phase A genesis). Idempotent by segment_hash.',
      parameters: {
        type: 'object',
        properties: {
          pcfL1: {
            type: 'string',
            description: 'APQC L1 slug (1-vision-strategy ... 13-business-capability)',
          },
          role: {
            type: 'string',
            description: 'Role persona (e.g. salesRep, sreEngineer)',
          },
          locale: { type: 'string', enum: ['jp', 'en', 'zh', 'ko'] },
          industry: { type: 'string' },
          seniority: { type: 'string', enum: ['junior', 'mid', 'senior'] },
          kAnonymity: { type: 'integer', minimum: 50, default: 50 },
        },
        required: ['pcfL1', 'role', 'locale'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'cohort_emit_evidence',
      description:
        'Append behavioral evidence to a cohort (Phase B). Triggers MV update for fission readiness.',
      parameters: {
        type: 'object',
        properties: {
          cohortDid: { type: 'string' },
          signalKind: {
            type: 'string',
            description: 'e.g. behavior.observation, identity.confirm',
          },
          evidencePayload: { type: 'string' },
          posterior: { type: 'number', minimum: 0, maximum: 1 },
          judgeAgreement: { type: 'boolean' },
        },
        required: ['cohortDid', 'signalKind', 'evidencePayload'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'cohort_fission',
      description:
        'Mint a fissioned individual actor from a cohort (Phase C). REQUIRES posterior>=0.95 + judgeAgreement=true + evidence>=1.',
      parameters: {
        type: 'object',
        properties: {
          cohortDid: { type: 'string' },
          posterior: { type: 'number', minimum: 0.95, maximum: 1 },
          judgeAgreement: { type: 'boolean', const: true },
          evidenceUris: {
            type: 'array',
            items: { type: 'string' },
            minItems: 1,
          },
        },
        required: ['cohortDid', 'posterior', 'judgeAgreement', 'evidenceUris'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'cohort_list',
      description: 'Enumerate cohorts with optional filters.',
      parameters: {
        type: 'object',
        properties: {
          pcfL1: { type: 'string' },
          locale: { type: 'string' },
          kind: { type: 'string', enum: ['cohort', 'fissioned'] },
          fissionEnabled: { type: 'boolean' },
          limit: { type: 'integer', default: 100 },
        },
      },
    },
  },
];

/**
 * Tool dispatcher: maps tool name → XRPC NSID + HTTP method.
 * Caller (e.g. llm.ts agentReact loop) uses this to bridge LLM tool call
 * to PDS XRPC fetch.
 */
export interface CohortToolDispatchEntry {
  nsid: string;
  method: 'GET' | 'POST';
  /**
   * For POST: rebuild input body from typed args.
   * For cohort_seed in particular, the wire format expects
   * `segmentJsonld` (string) but the tool surface accepts typed fields
   * for LLM convenience.
   */
  buildBody: (args: Record<string, unknown>) => unknown;
}

export const cohortToolDispatch: Record<string, CohortToolDispatchEntry> = {
  cohort_seed: {
    nsid: 'com.etzhayyim.cohort.seed',
    method: 'POST',
    buildBody: (args) => {
      const segment: Record<string, unknown> = {
        pcfL1: args.pcfL1,
        role: args.role,
        locale: args.locale,
      };
      if (args.industry) segment.industry = args.industry;
      if (args.seniority) segment.seniority = args.seniority;
      return {
        segmentJsonld: JSON.stringify(segment),
        kAnonymity: typeof args.kAnonymity === 'number' ? args.kAnonymity : 50,
      };
    },
  },
  cohort_emit_evidence: {
    nsid: 'com.etzhayyim.cohort.emitEvidence',
    method: 'POST',
    buildBody: (args) => args,
  },
  cohort_fission: {
    nsid: 'com.etzhayyim.cohort.fission',
    method: 'POST',
    buildBody: (args) => args,
  },
  cohort_list: {
    nsid: 'com.etzhayyim.cohort.listCohorts',
    method: 'GET',
    buildBody: (args) => args,
  },
};

/**
 * Helper: name → nsid (for OCEL audit emission).
 */
export function cohortToolNsid(toolName: string): string | null {
  return cohortToolDispatch[toolName]?.nsid ?? null;
}

/**
 * Build a tool handler closure for use with `llm.agentReact({ toolHandler })`.
 * Wraps cohortToolDispatch in the (name, args) → result signature that
 * react.ts and similar agent loops expect.
 *
 * Caller supplies pdsBaseUrl + Bearer token; this helper handles GET vs POST
 * and JSON ser/de. Returns null for unknown tool names so the outer handler
 * can fall through to standard tools.
 */
export function createCohortToolHandler(opts: {
  pdsBaseUrl: string;
  bearerToken: string;
  fetchImpl?: typeof fetch;
}): (name: string, args: Record<string, unknown>) => Promise<unknown | null> {
  const f = opts.fetchImpl ?? fetch;
  return async (name, args) => {
    const entry = cohortToolDispatch[name];
    if (!entry) return null;
    const url = `${opts.pdsBaseUrl.replace(/\/$/, '')}/xrpc/${entry.nsid}`;
    const body = entry.buildBody(args);
    if (entry.method === 'GET') {
      const params = new URLSearchParams();
      for (const [k, v] of Object.entries(body as Record<string, unknown>)) {
        if (v != null) params.set(k, String(v));
      }
      const resp = await f(`${url}?${params.toString()}`, {
        headers: { Authorization: `Bearer ${opts.bearerToken}` },
      });
      if (!resp.ok) {
        return { error: `XRPC ${entry.nsid} failed: ${resp.status}` };
      }
      return resp.json();
    }
    const resp = await f(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${opts.bearerToken}`,
      },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      return { error: `XRPC ${entry.nsid} failed: ${resp.status}` };
    }
    return resp.json();
  };
}
