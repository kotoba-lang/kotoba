(ns buildbench.workload
  "One workload, four source languages, N sizes.

  The programs are generated rather than hand-written for a single reason:
  a build-time comparison is only meaningful if every toolchain is handed the
  same amount of the same work. Hand-written 'equivalent' programs drift, and
  the drift lands in the timing as if it were a compiler property.

  Shape at size K:

    K independent leaf functions, each four operations and one branch, and
    one `main` that accumulates all K of them through a flat sequence of
    bindings. Flat, so no toolchain is measured against its parser's
    recursion limit; all K live, so no toolchain gets to skip codegen for
    dead code.

  Every leaf is `f_i(x) = |(x + i) - i + 1|`, which is `x + 1` — chosen
  because it stays inside a small integer range at every size, so no
  language needs overflow semantics that another language does not have.
  `main` returns `K`, which is the value each lane is checked against."
  (:require [clojure.string :as str]))

(defn expected-answer
  "What `main` returns at size K. Each of the K leaves contributes 1."
  [k]
  k)

;; ── Kotoba ───────────────────────────────────────────────────────────────

(defn- kotoba-leaf [i]
  (str "(defn f" i " [x :i64] :i64\n"
       "  (let [a (+ x " i ")\n"
       "        b (- a " i ")\n"
       "        c (+ b 1)]\n"
       "    (if (< c 0) (- 0 c) c)))"))

(defn kotoba-source [k]
  (str (str/join "\n\n" (map kotoba-leaf (range k)))
       "\n\n(defn main [] :i64\n  (let ["
       (str/join "\n        "
                 (for [i (range k)]
                   (if (zero? i)
                     (str "a0 (f0 0)")
                     (str "a" i " (+ a" (dec i) " (f" i " 0))"))))
       "]\n    a" (dec k) "))\n"))

;; ── Rust ─────────────────────────────────────────────────────────────────

(defn- rust-leaf [i]
  (str "#[unsafe(no_mangle)]\npub extern \"C\" fn f" i "(x: i64) -> i64 {\n"
       "    let a = x + " i ";\n"
       "    let b = a - " i ";\n"
       "    let c = b + 1;\n"
       "    if c < 0 { -c } else { c }\n}"))

(defn rust-source [k]
  (str "#![allow(dead_code)]\n\n"
       (str/join "\n\n" (map rust-leaf (range k)))
       "\n\n#[unsafe(no_mangle)]\npub extern \"C\" fn main() -> i64 {\n"
       "    let a0 = f0(0);\n"
       (str/join "" (for [i (range 1 k)]
                      (str "    let a" i " = a" (dec i) " + f" i "(0);\n")))
       "    a" (dec k) "\n}\n"))

;; ── C ────────────────────────────────────────────────────────────────────

(defn- c-leaf [i]
  (str "long long f" i "(long long x) {\n"
       "    long long a = x + " i ";\n"
       "    long long b = a - " i ";\n"
       "    long long c = b + 1;\n"
       "    return c < 0 ? -c : c;\n}"))

(defn c-source [k]
  (str (str/join "\n\n" (map c-leaf (range k)))
       "\n\nlong long main(void) {\n"
       "    long long a0 = f0(0);\n"
       (str/join "" (for [i (range 1 k)]
                      (str "    long long a" i " = a" (dec i) " + f" i "(0);\n")))
       "    return a" (dec k) ";\n}\n"))

;; ── Java ─────────────────────────────────────────────────────────────────

(defn- java-leaf [i]
  (str "    static long f" i "(long x) {\n"
       "        long a = x + " i ";\n"
       "        long b = a - " i ";\n"
       "        long c = b + 1;\n"
       "        return c < 0 ? -c : c;\n    }"))

(defn java-source [k]
  (str "public final class Main {\n"
       (str/join "\n\n" (map java-leaf (range k)))
       "\n\n    static long answer() {\n"
       "        long a0 = f0(0);\n"
       (str/join "" (for [i (range 1 k)]
                      (str "        long a" i " = a" (dec i) " + f" i "(0);\n")))
       "        return a" (dec k) ";\n    }\n\n"
       "    public static void main(String[] args) {\n"
       "        if (answer() != " (dec k) "L + 1L) { System.exit(1); }\n"
       "    }\n}\n"))

(def emitters
  {:kotoba {:filename "main.kotoba" :source kotoba-source}
   :rust   {:filename "main.rs"     :source rust-source}
   :c      {:filename "main.c"      :source c-source}
   :java   {:filename "Main.java"   :source java-source}})
