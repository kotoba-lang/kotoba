// @etzhayyim/pregel — Pregel BSP runtime
// Tranche F Phase 2 scaffolding. Real implementation lands in Phase 3.

export const VERSION = "0.0.0-scaffold";

export type SuperStep = number;

export interface PregelCell<S, M> {
  id: string;
  initialState(): S;
  compute(state: S, incoming: M[], step: SuperStep): { next: S; outgoing: Array<{ to: string; msg: M }> };
  isHalted(state: S): boolean;
}

export interface PregelRunner<S, M> {
  addCell(cell: PregelCell<S, M>): void;
  run(maxSteps: number): Promise<{ step: SuperStep; halted: boolean }>;
}
