/**
 * @etzhayyim/design-system — motion utility tests (coverage loop iteration 22).
 *
 * The motion module is pure transform/easing math shared by every UIKit
 * component (stagger delays, easing curves, 3D card tilt, parallax). Zero
 * tests. A clamp or sign bug ships visibly-wrong animation across the whole
 * design system. Type-only svelte import → runs standalone (no svelte dep).
 */
import { describe, it, expect } from "vitest";
import {
  staggerFly, staggerFade, staggerScale,
  overshootEase, elasticEase,
  computeTilt, resetTilt, parallaxY,
  slideUp, slideRight, depthEnter, springEnter,
  snapSpring, liquidMorph,
} from "../src/lib/motion/index.ts";

// ── staggered transitions: delay clamping ────────────────────────────────────

describe("stagger delay clamping", () => {
  it("staggerFly delay = index*step clamped to 500ms", () => {
    expect(staggerFly(0).delay).toBe(0);
    expect(staggerFly(3).delay).toBe(150);          // 3 * 50
    expect(staggerFly(100).delay).toBe(500);        // clamped
    // opts.delay is BOTH the per-index step AND a spread override → the spread wins
    expect(staggerFly(2, { delay: 100 }).delay).toBe(100);
    expect(staggerFly(1).y).toBe(20);
  });

  it("staggerFade caps at 400ms, staggerScale caps at 300ms", () => {
    expect(staggerFade(100).delay).toBe(400);
    expect(staggerScale(100).delay).toBe(300);
    expect(staggerScale(0).start).toBe(0.85);
  });

  it("explicit opts override the computed fields (spread wins)", () => {
    // opts spread last → a provided delay overrides the clamped value
    expect(staggerFly(100, { delay: 7 }).delay).toBe(7);
    expect(staggerFly(0, { y: 99 }).y).toBe(99);
  });
});

// ── easing boundary values ───────────────────────────────────────────────────

describe("easing functions", () => {
  it("overshootEase pins 0→0 and 1→1 and overshoots past 1 mid-curve", () => {
    expect(overshootEase(0)).toBeCloseTo(0, 10);
    expect(overshootEase(1)).toBeCloseTo(1, 10);
    // back-ease-out exceeds 1 before settling
    expect(Math.max(...[0.5, 0.6, 0.7, 0.8].map(overshootEase))).toBeGreaterThan(1);
  });

  it("elasticEase pins exactly at 0 and 1", () => {
    expect(elasticEase(0)).toBe(0);
    expect(elasticEase(1)).toBe(1);
    expect(elasticEase(0.5)).toBeGreaterThan(0); // defined mid-curve
  });
});

// ── 3D tilt + parallax ───────────────────────────────────────────────────────

const rect = { left: 0, top: 0, width: 100, height: 100 } as DOMRect;

describe("computeTilt", () => {
  it("center pointer → zero rotation", () => {
    const t = computeTilt(rect, 50, 50);
    // -relY*maxDeg = -0, and `${-0}` stringifies to "0" (not "-0")
    expect(t).toContain("rotateX(0deg)");
    expect(t).toContain("rotateY(0deg)");
    expect(t).toContain("translateZ(12px)");
    expect(t).toContain("perspective(800px)");
  });

  it("corner pointers tilt to ±maxDeg with correct sign", () => {
    // right edge → rotateY +maxDeg; top edge → rotateX +maxDeg (-relY)
    const right = computeTilt(rect, 100, 50, { maxDeg: 10 });
    expect(right).toContain("rotateY(5deg)");      // relX=0.5 → 0.5*10
    const top = computeTilt(rect, 50, 0, { maxDeg: 10 });
    expect(top).toContain("rotateX(5deg)");        // relY=-0.5 → -(-0.5)*10
  });

  it("honors liftPx and perspective options", () => {
    const t = computeTilt(rect, 50, 50, { liftPx: 20, perspective: 1200 });
    expect(t).toContain("translateZ(20px)");
    expect(t).toContain("perspective(1200px)");
  });

  it("resetTilt zeroes rotation + lift", () => {
    expect(resetTilt()).toBe("perspective(800px) rotateX(0deg) rotateY(0deg) translateZ(0px)");
    expect(resetTilt({ perspective: 500 })).toContain("perspective(500px)");
  });
});

describe("parallaxY", () => {
  it("offset = (scrollTop - elementTop) * factor", () => {
    expect(parallaxY(200, 0, 0.1)).toBe("translateY(20px)");
    expect(parallaxY(0, 100, 0.5)).toBe("translateY(-50px)");
    expect(parallaxY(100, 100)).toBe("translateY(0px)"); // default factor, no move
  });
});

// ── param builders: defaults + overrides ─────────────────────────────────────

describe("transition param builders", () => {
  it("slideUp/slideRight set axis + default duration, overridable", () => {
    expect(slideUp()).toMatchObject({ axis: "y", duration: 250 });
    expect(slideRight()).toMatchObject({ axis: "x", duration: 250 });
    expect(slideUp({ duration: 99 }).duration).toBe(99);
  });

  it("depthEnter/springEnter carry an overshoot/elastic easing + scale start", () => {
    const d = depthEnter();
    expect(typeof d.easing).toBe("function");
    expect(d.start).toBeGreaterThan(0);
    const s = springEnter(2);
    expect(typeof s.delay).toBe("number");
  });
});

describe("spring presets", () => {
  it("expose stiffness/damping constants", () => {
    expect(snapSpring).toEqual({ stiffness: 0.2, damping: 0.75 });
    expect(liquidMorph.damping).toBe(0.85);
  });
});
