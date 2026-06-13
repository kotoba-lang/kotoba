;; kotoba-langgraph-echo-clj — the Clojure-WASM port of the componentize-py
;; LangGraph echo agent (../kotoba-langgraph-echo/agent.py), compiled by the
;; in-repo kotoba-clj Clojure→WASM compiler.
;;
;; Graph (identical to agent.py):
;;   START → echo → END        ; echo: {"response": state["prompt"]}
;;
;; Wire format (identical to py/kotoba_langgraph/_entry.py handle_invoke):
;;   in:  CBOR {"graph": str, "session_cid": str,
;;              "args": {"input": {"prompt": str}, "thread_id": str}}
;;   out: CBOR {"ok": "<JSON string of the final state>"}
;;
;; Checkpointer (identical layout to py/kotoba_langgraph/checkpointer.py):
;;   kqe quad — graph "lgraph/ckpt" / subject <thread_id> / predicate "state"
;;   / object CBOR {"Text": <JSON state>}.
;;
;; Compile with the kotoba-clj prelude prepended (containers + CBOR decode/
;; encode + kqe accessors) via `compile_kais_component_str`; the `run` defn
;; satisfies the kotoba-node world's
;; `run: func(ctx-cbor: list<u8>) -> result<list<u8>, string>` export.
;; See crates/kotoba-clj/tests/langgraph_echo.rs for the build + invoke recipe.

;; ---- byte-builder helper -----------------------------------------------------

;; append the raw bytes of string handle s to byte-builder b (returns b)
(defn buf-str! [b s]
  (loop [i 0]
    (if (>= i (str-len s))
      b
      (do (byte-append! b (byte-at s i)) (recur (+ i 1))))))

;; ---- the echo graph (agent.py: StateGraph(EchoState)) -------------------------

;; _echo(state) -> {"response": state.get("prompt", "")} — a *partial update*;
;; the defgraph :state merge applies it with override semantics, exactly like
;; graph.py's _apply_update on a reducer-free EchoState TypedDict.
(defn echo [state]
  (let [u (map-make 2)]
    (map-assoc! u "response" (map-get state "prompt"))))

(defgraph echo-graph
  :state {:prompt :override :response :override}
  :entry :echo
  :nodes {:echo echo}
  :edges {:echo :end})

;; ---- InvokeContext decode (py/kotoba_langgraph/_entry.py) ---------------------
;; cbor-map-seek consumes the map as it scans, so each lookup walks a fresh
;; reader over the same ctx bytes.

;; session_cid = ctx.get("session_cid", "default")
(defn ctx-session-cid [ctx]
  (let [r (cbor-reader ctx)]
    (if (= (cbor-map-seek r "session_cid") 1) (cbor-text r) "default")))

;; thread_id = args.get("thread_id", session_cid)
(defn ctx-thread-id [ctx]
  (let [r (cbor-reader ctx)]
    (if (= (cbor-map-seek r "args") 1)
      (if (= (cbor-map-seek r "thread_id") 1)
        (cbor-text r)
        (ctx-session-cid ctx))
      (ctx-session-cid ctx))))

;; args.input.prompt — or the -1 sentinel when args has no "input" key
(defn ctx-prompt-via-input [ctx]
  (let [r (cbor-reader ctx)]
    (if (= (cbor-map-seek r "args") 1)
      (if (= (cbor-map-seek r "input") 1)
        (if (= (cbor-map-seek r "prompt") 1) (cbor-text r) "")
        -1)
      -1)))

;; input_state = args.get("input", args): no "input" → read prompt off args itself
(defn ctx-prompt-direct [ctx]
  (let [r (cbor-reader ctx)]
    (if (= (cbor-map-seek r "args") 1)
      (if (= (cbor-map-seek r "prompt") 1) (cbor-text r) "")
      "")))

(defn ctx-prompt [ctx]
  (let [p (ctx-prompt-via-input ctx)]
    (if (= p -1) (ctx-prompt-direct ctx) p)))

;; ---- result serialisation (handle_invoke: json.dumps(result)) -----------------

;; {"prompt": "<p>", "response": "<r>"} — json.dumps' default separators.
;; Gap: no JSON string escaping (a prompt containing `"` or `\` differs from py).
(defn state-json [prompt response]
  (let [b (bytes-alloc (+ 48 (+ (str-len prompt) (str-len response))))]
    (buf-str! b "{\"prompt\": \"")
    (buf-str! b prompt)
    (buf-str! b "\", \"response\": \"")
    (buf-str! b response)
    (buf-str! b "\"}")
    (bytes-finish b)))

;; CBOR {"ok": <json>} — handle_invoke's success wire format
(defn ok-result [json]
  (let [out (bytes-alloc (+ 16 (str-len json)))]
    (cbor-enc-map-header! out 1)
    (cbor-enc-text! out "ok")
    (cbor-enc-text! out json)
    (bytes-finish out)))

;; ---- KotobaCheckpointer.save (py/kotoba_langgraph/checkpointer.py) ------------
;; object = CBOR {"Text": <JSON state>} — the ciborium QuadObject::Text encoding
(defn ckpt-save! [thread-id state-json]
  (let [obj (bytes-alloc (+ 16 (str-len state-json)))]
    (cbor-enc-map-header! obj 1)
    (cbor-enc-text! obj "Text")
    (cbor-enc-text! obj state-json)
    (kqe-assert! "lgraph/ckpt" thread-id "state" (bytes-finish obj))))

;; ---- WitWorld.run — the kotoba-node export -------------------------------------
(defn run [ctx]
  (let [s (map-make 8)]
    (map-assoc! s "prompt" (ctx-prompt ctx))
    (let [final (echo-graph s)
          json (state-json (map-get final "prompt") (map-get final "response"))]
      (ckpt-save! (ctx-thread-id ctx) json)
      (ok-result json))))
