/**
 * Cohort segment hash parser + evidence helpers (ADR-0026).
 *
 * segment_hash format:
 *   "sha256:pcfL1=<slug>;role=<role>[;industry=<industry>];locale=<locale>"
 *
 * Example:
 *   "sha256:pcfL1=3-market-sell;role=salesRep;industry=retail;locale=jp"
 *
 * Parses into structured fields used by:
 *   - OCEL apqcEvent emission (pcfL1 → APQC L1 DID)
 *   - Fission decision logging
 *   - k-anonymity drift dashboards
 */
export interface CohortSegment {
  pcfL1: string;
  role: string;
  industry: string | null;
  seniority: string | null;
  locale: string;
}

export function parseSegmentHash(segmentHash: string): CohortSegment | null {
  const prefix = "sha256:";
  if (!segmentHash.startsWith(prefix)) return null;
  const body = segmentHash.slice(prefix.length);
  const parts = body.split(";");
  const kv: Record<string, string> = {};
  for (const p of parts) {
    const eq = p.indexOf("=");
    if (eq === -1) continue;
    kv[p.slice(0, eq)] = p.slice(eq + 1);
  }
  const pcfL1 = kv.pcfL1;
  const role = kv.role;
  const locale = kv.locale;
  if (!pcfL1 || !role || !locale) return null;
  return {
    pcfL1,
    role,
    industry: kv.industry ?? null,
    seniority: kv.seniority ?? null,
    locale,
  };
}

export function apqcL1DidFromSegment(
  segment: CohortSegment,
  projectorHost = "kyber-projector.etzhayyim.com"
): string {
  return `did:web:${projectorHost}:apqc:${segment.pcfL1}`;
}

/**
 * OCEL eventType derivation rule (ADR-0026 + ADR-0025).
 */
export type CohortOcelEventType =
  | "cohort.genesis"
  | "cohort.evidence.accrued"
  | "cohort.evidence.fissionReady"
  | "cohort.kReevaluated"
  | "cohort.fission"
  | "cohort.purge";

export function deriveCohortEventType(input: {
  evidenceCountBefore: number;
  posterior: number | null;
  judgeAgreement: boolean | null;
  kProxy: number | null;
  fissionEnabled: boolean;
  didFission: boolean;
}): CohortOcelEventType {
  if (input.didFission) return "cohort.fission";
  if (input.kProxy !== null && input.kProxy < 50) return "cohort.kReevaluated";
  if (
    input.posterior !== null &&
    input.posterior > 0.95 &&
    input.judgeAgreement === true &&
    input.fissionEnabled
  ) {
    return "cohort.evidence.fissionReady";
  }
  if (input.evidenceCountBefore === 0) return "cohort.genesis";
  return "cohort.evidence.accrued";
}
