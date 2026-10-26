(ns kotoba.kir-cljs-i64-ashr-test
  "`kotoba.kir.cljs-i64/ashr` at shifts of 32 and more.

  `.cljs`, not `.cljc`: the namespace under test is `.cljs`, because it exists
  precisely to say what ClojureScript needs and the JVM does not.

  Until 2026-08-25 `ashr` built its divisor with
  `(js/BigInt (bit-shift-left 1 shift))`. cljs `bit-shift-left` coerces to
  int32, so that expression is 2^24 for a shift of 56 and 1 for a shift of 32 --
  the hazard `cljs-i64`'s own docstring is about, inside `cljs-i64`. It
  returned a plausible bigint rather than failing, which is the kind that
  survives.

  Nothing had asked: the only caller was `sleb128` in `kotoba.wasm.core`, which
  shifts by 7. The second caller, `kotoba.compiler.backend.evm`'s PUSH8
  operand, needs shifts 56 down to 0 and got the low four bytes twice."
  (:require [cljs.test :refer [deftest is testing]]
            [kotoba.kir.cljs-i64 :as i64]))

(defn- bytes-of [x]
  (mapv (fn [shift] (js/Number (js/BigInt.asUintN 8 (i64/ashr x shift))))
        [56 48 40 32 24 16 8 0]))

(deftest ashr-is-correct-at-every-shift-a-64-bit-value-needs
  (testing "a value whose eight bytes are all distinct -- the shape that makes
            a wrapped shift visible instead of coincidentally right"
    (is (= [0x11 0x22 0x33 0x44 0x55 0x66 0x77 0x88]
           (bytes-of (js/BigInt "1234605616436508552")))))
  (testing "the shifts that used to wrap, one at a time"
    ;; 2^32 shifted right by 32 is 1. With the int32 divisor this was
    ;; (/ 2^32 1) = 2^32, and by 56 it was (/ 2^32 2^24) = 256.
    (is (= (js/BigInt 1) (i64/ashr (js/BigInt "4294967296") 32)))
    (is (= (js/BigInt 0) (i64/ashr (js/BigInt "4294967296") 33)))
    (is (= (js/BigInt 127) (i64/ashr (js/BigInt "9223372036854775807") 56)))))

(deftest ashr-still-floors-toward-negative-infinity
  (testing "arithmetic shift, not truncating division -- the property the
            original implementation's remainder adjustment exists for"
    (is (= (js/BigInt -3) (i64/ashr (js/BigInt -300) 7)))
    (is (= (js/BigInt -1) (i64/ashr (js/BigInt -1) 63)))
    (is (= (js/BigInt -1) (i64/ashr (js/BigInt -1) 32)))
    (is (= [0xff 0xff 0xff 0xff 0xff 0xff 0xff 0xff] (bytes-of (js/BigInt -1)))))
  (testing "the most negative i64 shifts down to -1, never to 0"
    (is (= (js/BigInt -1) (i64/ashr i64/min-i64 63)))))

(deftest ashr-by-zero-is-identity
  (is (= (js/BigInt 42) (i64/ashr (js/BigInt 42) 0)))
  (is (= (js/BigInt -42) (i64/ashr (js/BigInt -42) 0))))
