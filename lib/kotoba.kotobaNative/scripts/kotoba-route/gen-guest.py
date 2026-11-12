#!/usr/bin/env python3
"""gen-guest.py ROOT FN[:a]...   (ROOT: machine_ir | aarch64; env OVDIR TWDIR GUESTDIR)

Writes the differential guest into GUESTDIR/kotoba/native/: the overlaid ROOT module (Kotoba reading of every
ported definition) with its export list replaced by [main] and a tail that reads `FN [args... expected]` lines
(EDN recorded on the host), converts the args to the twin's parameter types, calls the twin and answers one line
per case: OK (equal; lists and vectors compare alike), DIFF, ERR-OK (both refused), ERR (twin refused), MISS
(host refused). FN:a marks an aborting twin (its call is wrapped in try). A guest requires only what the twins
call; modules not natively linkable yet (functions answering :symbol) become local stubs (see STUB_DEFS)."""
import re, sys, os

TYPES_IN = {'[:ref :form/r]': 'a{i}', ':keyword': '(kw-of a{i})', ':i64': '(form/int-value a{i})',
            ':bool': '(truthy? a{i})', '[:list [:ref :form/r]]': '(form/kids-of a{i})', ':string': '(form/string-value a{i})'}
TYPES_OUT = {'[:ref :form/r]': '{x}', ':keyword': '(form/keyword-form {x})', ':i64': '(form/int-form {x})',
             ':bool': '(form/bool-form {x})', '[:list [:ref :form/r]]': '(form/form-vec {x})', ':string': '(form/string-form {x})'}
ALIASES = {'mir': 'kotoba.mir', 'gmir': 'kotoba.gmir', 'mc': 'kotoba.codegen.mc',
           'aggregate-abi': 'kotoba.native.aggregate-abi', 'image-scratch': 'kotoba.native.image-scratch',
           'document': 'kotoba.native.document', 'string-index': 'kotoba.native.string-index',
           'string-search': 'kotoba.native.string-search', 'interrupt-abi': 'kotoba.native.interrupt-abi',
           'machine-ir': 'kotoba.native.machine-ir', 'keyword-equality': 'kotoba.native.keyword-equality',
           'vector-region': 'kotoba.native.vector-region', 'peephole': 'kotoba.native.peephole'}
STUBBED = ['string-index', 'string-search', 'document', 'interrupt-abi']
DOC_OPS = '"[document-null document-bool document-i64 document-string document-keyword document-symbol document-vector document-list document-set document-map document-count document-kind document-equal? document-set-contains? document-contains document-get document-vector-at document-list-at document-map-entry-at document-vector-assoc document-vector-conj document-vector-drop document-vector-remove document-vector-sort document-assoc document-dissoc document-merge document-string-value document-keyword-value document-symbol-value document-bool-value document-i64-value document-edn-print document-edn-read]"'
R = '[:result [:ref :form/r] :document]'
STUB_DEFS = {
 'string-search/lower-contains': '(defn- guest-stub-string-search-lower-contains [args [:ref :form/r]] [:ref :form/r] (do (vector-at (vector-i64) 0) args))',
 'string-search/lower-replace-all': '(defn- guest-stub-string-search-lower-replace-all [args [:ref :form/r]] [:ref :form/r] (do (vector-at (vector-i64) 0) args))',
 'string-index/lower': f'(defn- guest-stub-string-index-lower [op [:ref :form/r] args [:ref :form/r]] {R} (result-err-of {R} (document-null)))',
 'document/lower': f'(defn- guest-stub-document-lower [op [:ref :form/r] args [:ref :form/r]] {R} (result-err-of {R} (document-null)))',
 'document/operations': '(defn- guest-stub-document-operations [] [:ref :form/r] (form/form-set (form/kids-of (form/edn-form ' + DOC_OPS + '))))',
 # identity: right for a program that uses no string-replace-all / string-index / document (such cases are marked)
 'string-search/augment-functions': f'(defn- guest-stub-string-search-augment-functions [fs [:ref :form/r]] {R} (result-ok-of {R} fs))',
 'string-index/augment-functions': f'(defn- guest-stub-string-index-augment-functions [fs [:ref :form/r]] {R} (result-ok-of {R} fs))',
 'document/augment-functions': f'(defn- guest-stub-document-augment-functions [fs [:ref :form/r]] {R} (result-ok-of {R} fs))',
}

def sig(twins, name):
    m = re.search(r'\(defn-?\s+' + re.escape(name) + r'\s*(?:"(?:[^"\\]|\\.)*"\s*)?\[', twins)
    if not m: raise SystemExit(f'no twin {name}')
    i = m.end() - 1; depth, j = 0, i
    while True:
        c = twins[j]
        if c == '[': depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0: break
        j += 1
    params = twins[i+1:j]
    rest = twins[j+1:].lstrip()
    if rest.startswith('['):
        d, k = 0, 0
        while True:
            if rest[k] == '[': d += 1
            elif rest[k] == ']':
                d -= 1
                if d == 0: break
            k += 1
        ret = rest[:k+1]
    else:
        ret = rest.split()[0]
    toks = re.findall(r'\[:list \[:ref :form/r\]\]|\[:ref :form/r\]|:[a-z0-9-]+|[^\s\[\]]+', params)
    return [(toks[k], toks[k+1]) for k in range(0, len(toks), 2)], re.sub(r'\s+', ' ', ret)

def form_end(text, i):
    depth, j = 0, i
    while True:
        c = text[j]
        if c == '(': depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0: return j + 1
        j += 1

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hostview import scan_elems
from ov import scan

def kotoba_only(text):
    """the Kotoba reading of the top-level forms: `#?(:kotoba X :default Y)` -> X, host-only forms dropped"""
    out, pos = [], 0
    for s0, e0 in scan(text):
        b = text[s0:e0]
        out.append(text[pos:s0]); pos = e0
        if b.startswith('(ns '): out.append(b); continue
        if b.startswith('#?(:kotoba'):
            inner = b[3:-1]
            els = [inner[a:z] for a, z in scan_elems(inner)]
            k = els[1] if len(els) > 1 else 'nil'
            out.append('' if k == 'nil' else k)
        # a top-level form with no Kotoba reading is dropped (the overlay already hid it)
    out.append(text[pos:])
    return ''.join(out)

def prune(text, twins):
    text = kotoba_only(text)
    stubs = []
    for a in STUBBED:
        for m in sorted(set(re.findall(r'\(' + re.escape(a) + r'/([a-z\-?!]+)', twins))):
            key = a + '/' + m
            if key not in STUB_DEFS: raise SystemExit('no guest stub for ' + key)
            stubs.append(STUB_DEFS[key])
        text = re.sub(r'\(' + re.escape(a) + r'/([a-z\-?!]+)', lambda m: '(guest-stub-' + a + '-' + m.group(1), text)
    used = [a for a in ALIASES if a not in STUBBED and re.search(r'\(' + re.escape(a) + r'/', twins)]
    req = ' '.join(f'[{ALIASES[a]} :as {a}]' for a in used)
    i = text.index('(:require'); j = form_end(text, i)
    return text[:i] + f'(:require [kotoba.form :as form] {req})' + text[j:] + '\n\n' + '\n'.join(stubs) + '\n'

TAIL = '''
;; -- differential tail (generated by gen-guest.py) --
(defn- dx-kw? [f [:ref :form/r] k :keyword] :bool (and (form/is-keyword? f) (= (form/keyword-value f) k)))
(defn- dx-kw-of [f [:ref :form/r]] :keyword (if (form/is-keyword? f) (form/keyword-value f) :none))
(defn- dx-truthy? [f [:ref :form/r]] :bool (not (or (form/is-nil? f) (and (form/is-bool? f) (not (form/bool-value f))))))
(defn- loose-list? [t :i64] :bool (or (= t 6) (= t 7)))
(defn- loose-seq-eq [a [:ref :form/r] b [:ref :form/r]] :bool
  (let [xs (form/kids-of a) ys (form/kids-of b) n (vector-count xs)]
    (and (= n (vector-count ys))
         (loop [i 0]
           (if (>= i n) true
             (if (loose-eq (typed-list-nth [:list [:ref :form/r]] xs i) (typed-list-nth [:list [:ref :form/r]] ys i))
               (recur (inc i)) false))))))
(defn- loose-map-eq [a [:ref :form/r] b [:ref :form/r]] :bool
  (let [xs (form/kids-of a) n (vector-count xs)]
    (and (= n (vector-count (form/kids-of b)))
         (loop [j 0]
           (if (>= (+ j 1) n) true
             (let [k (typed-list-nth [:list [:ref :form/r]] xs j)]
               (if (and (form/form-has? b k)
                        (loose-eq (typed-list-nth [:list [:ref :form/r]] xs (+ j 1)) (form/form-get b k)))
                 (recur (+ j 2)) false)))))))
(defn- loose-eq [a [:ref :form/r] b [:ref :form/r]] :bool
  (let [ta (form/tag-of a) tb (form/tag-of b)]
    (cond
      (and (loose-list? ta) (loose-list? tb)) (loose-seq-eq a b)
      (and (= ta 9) (= tb 9)) (loose-map-eq a b)
      :else (form/eq a b))))

(defn- dx-case [name :string c [:ref :form/r]] :string
  (cond
CLAUSES
    :else "UNKNOWN"))

(defn- dx-lines [text :string i :i64 n :i64 out :string] :string
  (if (>= i n)
    out
    (let [j (string-find-byte text 10 i)
          end (if (< j 0) n j)
          sp (string-find-byte text 32 i)
          name (string-substring text i sp)
          c (form/edn-form (string-substring text (+ sp 1) end))]
      (dx-lines text (+ end 1) n (string-concat out (string-concat (dx-case name c) "\\n"))))))

(defn main [] :i64
  (let [text (typed-cap-call :io/read :string :string "")
        out (dx-lines text 0 (string-byte-length text) "")
        n (typed-cap-call :io/write :string :string out)]
    0))
'''

def main(root, fns):
    ov = os.environ['OVDIR'] + '/kotoba/native/'
    tw = os.environ['TWDIR'] + '/'
    out = os.environ['GUESTDIR'] + '/kotoba/native/'
    mi = prune(open(ov + 'machine_ir.cljk').read(), open(tw + 'machine_ir.cljk').read())
    if root == 'aarch64':
        open(out + 'machine_ir.cljk', 'w').write(mi)
        twins = open(tw + 'aarch64.cljk').read()
        text = prune(open(ov + 'aarch64.cljk').read(), twins)
        out_path = out + 'aarch64.cljk'
    else:
        twins = open(tw + 'machine_ir.cljk').read()
        text = mi
        out_path = out + 'machine_ir.cljk'
    m = re.search(r':kotoba/export\s*', text)
    k = m.end()
    if text[k:].startswith('#?('): e = form_end(text, k + 2)
    else: e = text.index(']', k) + 1
    text = text[:m.start()] + ':kotoba/export [main]' + text[e:]
    clauses = []
    for spec in fns:
        fn, aborts = (spec[:-2], True) if spec.endswith(':a') else (spec, False)
        ps, ret = sig(twins, fn)
        args = ' '.join(TYPES_IN[t].format(i=k).replace('(kw-of', '(dx-kw-of').replace('(truthy?', '(dx-truthy?') for k, (_, t) in enumerate(ps))
        binds = ' '.join(f'a{k} (form/nth-of c {k})' for k in range(len(ps)))
        call = TYPES_OUT[ret].format(x=f'({fn} {args})')
        inner = f'(let [got {call}] (if host-err? "MISS" (if (loose-eq got expected) "OK" "DIFF")))'
        body = f'(try {inner} (catch e (if host-err? "ERR-OK" "ERR")))' if aborts else inner
        clauses.append(f'''    (string=? name "{fn}")
    (let [{binds}
          expected (form/nth-of c {len(ps)})
          host-err? (and (form/is-vec? expected) (> (form/count-of expected) 0)
                         (dx-kw? (form/nth-of expected 0) :kotoba/error))]
      {body})''')
    open(out_path, 'w').write(text + TAIL.replace('CLAUSES', '\n'.join(clauses)))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
