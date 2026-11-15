# Frozen literals only: no codec, hash or verdict implementation.
def header:
"(ns awai.fs.corpus (:require [awai.fs.logical-file :as f] [multiformats.cid :as cid])\n  (:export [main]))\n(defn- nibble [n :i64] :i64 (if (<= n 57) (- n 48) (- n 87)))\n(defn- put-hex [b :vector-i64 at :i64 text :string] :vector-i64\n  (loop [i 0 out b]\n    (if (= i (quot (string-byte-length text) 2)) out\n      (recur (+ i 1) (vector-assoc! out (+ at i)\n        (+ (* 16 (nibble (string-code-point-at text (* 2 i))))\n                  (nibble (string-code-point-at text (+ (* 2 i) 1)))))))))\n(defn- put-row [b :vector-i64 at :i64 row :vector-i64] :vector-i64\n  (loop [i 0 out b] (if (= i (vector-count row)) out\n    (recur (+ i 1) (vector-assoc! out (+ at i) (vector-at row i))))))\n(defn- repeated-rows [n :i64 length :i64 link :string] :vector-i64\n  (loop [i 0 out (vector-alloc (* n 38))]\n    (if (= i n) out (recur (+ i 1) (put-row out (* i 38) (f/chunk-row (* i length) length link))))))\n";
def require_hex:
  if type == "string" and (length % 2 == 0) and test("^[0-9a-f]*$") and length <= 4194304 then . else error("invalid or oversized hex") end;
def bytes_fn($name; $raw):
  ($raw | require_hex) as $h | ($h|length) as $len |
  [range(0;$len;2048) as $i | "b\(($i/2048|floor)+1) (put-hex b\($i/2048|floor) \(($i/2048|floor)*1024) \($h[$i:($i+2048)]|@json))"] as $bindings |
  "(defn- \($name) [] :vector-i64 (let [b0 (vector-alloc \($len/2))" + (if ($bindings|length)>0 then "\n"+($bindings|join("\n")) else "" end) + "] b\($bindings|length)))\n";
def hexval: . as $c | "0123456789abcdef" | index($c);
def flatten_input:
  [.[] | (require_hex) as $h | ($h|length/2), (range(0;($h|length);2) as $i | (($h[$i:($i+1)] | hexval) * 16 + ($h[($i+1):($i+2)] | hexval)))];
def pack_fn($flat):
  [range(0;($flat|length);64) as $i | "b\(($i/64|floor)+1) (put-row b\($i/64|floor) \($i) (vector-i64 \($flat[$i:($i+64)]|map(tostring)|join(" "))))"] as $parts |
  "(defn- pack-input [] :vector-i64 (let [b0 (vector-alloc \($flat|length))" + (if ($parts|length)>0 then " "+($parts|join(" ")) else "" end) + "] b\($parts|length)))\n";
def rows($cs):
  ($cs|length) as $n |
  if $n > 1024 then error("too many chunks")
  elif $n > 2 then
    $cs[0] as $c |
    if all(range(0;$n); . as $i | $cs[$i] | .length == $c.length and .cid == $c.cid and .offset == ($i*$c.length)) then
      "(repeated-rows \($n) \($c.length) \($c.cid|@json))"
    else error("non-repeated large fixture") end
  else
    [range(0;$n) as $i | $cs[$i] as $c | "r\($i+1) (put-row r\($i) \(38*$i) (f/chunk-row \($c.offset) \($c.length) \($c.cid|@json)))"] as $b |
    "(let [r0 (vector-alloc \($n*38))" + (if $n>0 then " "+($b|join(" ")) else "" end) + "] r\($n))"
  end;
def leafs($case):
  reduce range(0; [($case.bodiesHex|length),($case.input.chunks|length)]|min) as $i ([];
    {body:$case.bodiesHex[$i], c:$case.input.chunks[$i]} as $v |
    if any(.[]; .body == $v.body and .c.cid == $v.c.cid) then . else . + [$v] end);
def bounded_int: type == "number" and floor == . and . >= -9007199254740991 and . <= 9007199254740991;
def check_case($kind):
 if type != "object" then error("case must be an object")
 elif $kind == "positive" then
  if ((.input|type) == "object" and (.input.version|bounded_int) and (.input.size|bounded_int)
      and (.input.profile|type=="object") and (.input.profile.version|bounded_int)
      and (.input.profile.kind|type=="string") and (.input.profile.leafSize|bounded_int)
      and (.input.chunks|type=="array" and length<=1024)
      and (.input.chunks|all(.[]; (.offset|bounded_int) and (.length|bounded_int) and (.cid|type=="string")))
      and (.bodiesHex|type=="array" and length<=1024) and (.cid|type=="string") and (.profileCid|type=="string"))
   then . else error("invalid positive fixture") end
 elif $kind == "pack" then
  if (.inputHex|type=="array" and length<=1024) and (.rootCid|type=="string") then . else error("invalid pack fixture") end
 elif $kind == "negative" then . else error("unknown kind") end;
def fixture($kind):
  check_case($kind) as $case | $case | header as $header | bytes_fn("wire"; (if $kind=="pack" then .carHex else .wireHex end)) as $wire |
  if $kind == "negative" then
    $header+$wire+"(defn main [] :i64\n  (let [b (wire) r (f/decode b) ci (f/bytes-cid b)]\n    (if (and (not (result-ok?-of [:result [:ref :awai.fs/file] :keyword] r))\n             (not (result-ok?-of [:result :string :keyword] ci))) 0 1)))\n"
  elif $kind == "pack" then
    ($case.inputHex | flatten_input) as $flat |
    ($header|sub("\\[multiformats.cid :as cid\\]";"[multiformats.cid :as cid] [ipld.car.pack :as pack]")) + $wire + pack_fn($flat) +
    "(defn main [] :i64 (let [input (pack-input) e (pack/encode 1 input) c (pack/root-cid 1 input)]\n(cond (not (result-ok?-of [:result :vector-i64 :keyword] e)) 1 (not (f/same-bytes? (wire) (result-value-of [:result :vector-i64 :keyword] e (vector-i64)))) 2 (not (string=? (result-value-of [:result :string :keyword] c \"\") \($case.rootCid|@json))) 3 :else 0)))\n"
  elif $kind == "positive" then
    .input as $v | $v.profile as $p | leafs($case) as $l |
    $header + $wire + bytes_fn("profile-wire"; $case.profileHex) +
    ([range(0;($l|length)) as $i | bytes_fn("body-\($i)"; $l[$i].body)]|join("")) +
    "(defn main [] :i64\n  (let [p (f/profile-new \($p.version) \($p.kind|@json) \($p.leafSize))\n        a (f/file-new \($v.version) \($v.size) p \(rows($v.chunks)))\n        expected (wire) encoded (f/encode a) decoded (f/decode expected)\n        ci (f/file-cid a) bc (f/bytes-cid expected) pc (f/profile-cid p)\n        pe (f/profile-encode p) pd (f/profile-decode (profile-wire))]\n    (cond (not= (f/refusal a) :none) 1\n          (not (result-ok?-of [:result :vector-i64 :keyword] encoded)) 2\n          (not (f/same-bytes? expected (result-value-of [:result :vector-i64 :keyword] encoded (vector-i64)))) 3\n          (not (result-ok?-of [:result [:ref :awai.fs/file] :keyword] decoded)) 4\n          (not (string=? (result-value-of [:result :string :keyword] ci \"\") \($case.cid|@json))) 5\n          (not (string=? (result-value-of [:result :string :keyword] bc \"\") \($case.cid|@json))) 6\n          (not (string=? (result-value-of [:result :string :keyword] pc \"\") \($case.profileCid|@json))) 7\n          (not (f/same-bytes? (profile-wire) (result-value-of [:result :vector-i64 :keyword] pe (vector-i64)))) 8\n          (not (result-ok?-of [:result [:ref :awai.fs/profile] :keyword] pd)) 9\n          " +
    ([range(0;($l|length)) as $i | $l[$i].c as $c | "(not= (f/verify-leaf (f/chunk-row \($c.offset) \($c.length) \($c.cid|@json)) (body-\($i))) :none) \(20+$i)"]|join("\n")) + "\n          :else 0)))\n"
  else error("unknown kind") end;
if $kind == "positive" then .positive[$index] | fixture("positive")
elif $kind == "negative" then .negative[$index] | fixture("negative")
elif $kind == "pack" then .legacyPacks.cases[$index] | fixture("pack")
else error("unknown kind") end
