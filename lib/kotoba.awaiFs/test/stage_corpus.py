"""Materialize frozen corpus literals; no codec, CID or verdict implementation."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HEADER='''(ns awai.fs.corpus (:require [awai.fs.logical-file :as f] [multiformats.cid :as cid])
  (:export [main]))
(defn- nibble [n :i64] :i64 (if (<= n 57) (- n 48) (- n 87)))
(defn- put-hex [b :vector-i64 at :i64 text :string] :vector-i64
  (loop [i 0 out b]
    (if (= i (quot (string-byte-length text) 2)) out
      (recur (+ i 1) (vector-assoc! out (+ at i)
        (+ (* 16 (nibble (string-code-point-at text (* 2 i))))
                  (nibble (string-code-point-at text (+ (* 2 i) 1)))))))))
(defn- put-row [b :vector-i64 at :i64 row :vector-i64] :vector-i64
  (loop [i 0 out b] (if (= i (vector-count row)) out
    (recur (+ i 1) (vector-assoc! out (+ at i) (vector-at row i))))))
(defn- repeated-rows [n :i64 length :i64 link :string] :vector-i64
  (loop [i 0 out (vector-alloc (* n 38))]
    (if (= i n) out (recur (+ i 1) (put-row out (* i 38) (f/chunk-row (* i length) length link))))))
'''
def quote(s):return json.dumps(s,ensure_ascii=True)
def bytes_function(name,h):
    # Chunks avoid the language's individual string bound. Input is literal hex.
    parts=[h[i:i+2048] for i in range(0,len(h),2048)]
    bindings=['b0 (vector-alloc '+str(len(h)//2)+')']
    for i,p in enumerate(parts): bindings.append(f'b{i+1} (put-hex b{i} {i*1024} {quote(p)})')
    return f'(defn- {name} [] :vector-i64 (let ['+'\n'.join(bindings)+f'] b{len(parts)}))\n'
def fixture(case,kind,index):
    name=f'{kind}-{index}';src=HEADER+bytes_function('wire',case['wireHex'])
    if kind=='pack':
        src=src.replace('[multiformats.cid :as cid]', '[multiformats.cid :as cid] [ipld.car.pack :as pack]')
        flat=[]
        for h in case['inputHex']:flat += [len(h)//2]+list(bytes.fromhex(h))
        bindings=[f'b0 (vector-alloc {len(flat)})']
        for i in range(0,len(flat),64):
            k=i//64
            bindings.append(f'b{k+1} (put-row b{k} {i} (vector-i64 {" ".join(map(str,flat[i:i+64]))}))')
        src+='(defn- pack-input [] :vector-i64 (let ['+' '.join(bindings)+f'] b{(len(flat)+63)//64}))\n'
        src+=f"(defn main [] :i64 (let [input (pack-input) e (pack/encode 1 input) c (pack/root-cid 1 input)]\n"
        src+=f"(cond (not (result-ok?-of [:result :vector-i64 :keyword] e)) 1 (not (f/same-bytes? (wire) (result-value-of [:result :vector-i64 :keyword] e (vector-i64)))) 2 (not (string=? (result-value-of [:result :string :keyword] c \"\") {quote(case['rootCid'])})) 3 :else 0)))\n"
    elif kind=='negative':
        src+='''(defn main [] :i64
  (let [b (wire) r (f/decode b) ci (f/bytes-cid b)]
    (if (and (not (result-ok?-of [:result [:ref :awai.fs/file] :keyword] r))
             (not (result-ok?-of [:result :string :keyword] ci))) 0 1)))\n'''
    else:
        v=case['input'];p=v['profile'];cs=v['chunks'];n=len(cs)
        if n>2:
            assert all(c['length']==cs[0]['length'] and c['cid']==cs[0]['cid'] and c['offset']==i*cs[0]['length'] for i,c in enumerate(cs))
            rows=f'(repeated-rows {n} {cs[0]["length"]} {quote(cs[0]["cid"])})'
        else:
            binds=['r0 (vector-alloc '+str(n*38)+')']
            for i,c in enumerate(cs):binds.append(f'r{i+1} (put-row r{i} {38*i} (f/chunk-row {c["offset"]} {c["length"]} {quote(c["cid"])}))')
            rows='(let ['+' '.join(binds)+f'] r{n})'
        src+=bytes_function('profile-wire',case['profileHex'])
        leaf_checks=[];seen=set()
        for body,c in zip(case.get('bodiesHex',[]),cs):
            key=(body,c['cid'])
            if key in seen:continue
            seen.add(key);i=len(leaf_checks);src+=bytes_function(f'body-{i}',body)
            leaf_checks.append(f'(not= (f/verify-leaf (f/chunk-row {c["offset"]} {c["length"]} {quote(c["cid"])}) (body-{i})) :none) {20+i}')
        src+=f'''(defn main [] :i64
  (let [p (f/profile-new {p['version']} {quote(p['kind'])} {p['leafSize']})
        a (f/file-new {v['version']} {v['size']} p {rows})
        expected (wire) encoded (f/encode a) decoded (f/decode expected)
        ci (f/file-cid a) bc (f/bytes-cid expected) pc (f/profile-cid p)
        pe (f/profile-encode p) pd (f/profile-decode (profile-wire))]
    (cond (not= (f/refusal a) :none) 1
          (not (result-ok?-of [:result :vector-i64 :keyword] encoded)) 2
          (not (f/same-bytes? expected (result-value-of [:result :vector-i64 :keyword] encoded (vector-i64)))) 3
          (not (result-ok?-of [:result [:ref :awai.fs/file] :keyword] decoded)) 4
          (not (string=? (result-value-of [:result :string :keyword] ci "") {quote(case['cid'])})) 5
          (not (string=? (result-value-of [:result :string :keyword] bc "") {quote(case['cid'])})) 6
          (not (string=? (result-value-of [:result :string :keyword] pc "") {quote(case['profileCid'])})) 7
          (not (f/same-bytes? (profile-wire) (result-value-of [:result :vector-i64 :keyword] pe (vector-i64)))) 8
          (not (result-ok?-of [:result [:ref :awai.fs/profile] :keyword] pd)) 9
          {chr(10).join(leaf_checks)}
          :else 0)))\n'''
    return src
if __name__=='__main__':
    import sys
    data=json.loads((ROOT/'corpus/v1.json').read_text());out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
    for kind in ('positive','negative'):
        for i,c in enumerate(data[kind]):(out/f'{kind}-{i}.kotoba').write_text(fixture(c,kind,i))
