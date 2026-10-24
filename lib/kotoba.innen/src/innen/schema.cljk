(ns innen.schema
  "因縁 (innen) -- the admissibility contract for a dependency record.

   A dependency graph over human history is only worth querying if every edge
   in it can be traced to something a human can check. This namespace defines
   what a node is, what an edge is, and -- the part that actually matters --
   what makes an edge ADMISSIBLE. `problems` is fail-closed: an edge with no
   source, an unknown edge kind, or an interval whose end precedes its start is
   an `:error`, not a warning, and `innen.core/graph` refuses to build a graph
   containing one unless explicitly asked to keep going.

   The reason for the strictness: a dependency claim about history (\"X existed
   because Y funded it\") is exactly the kind of statement a language model
   will happily produce from plausibility alone. The schema makes the
   unsourced version unrepresentable rather than merely discouraged.

   Directionality is fixed and non-negotiable: an edge always reads
   `from` DEPENDS ON `to`. Causation follows the same convention (an event
   `from` depends on its cause `to`), so traversal never has to ask which
   direction a given kind means."
  (:require [kotoba.lang.text :as str]
            [innen.time :as t]))

(def node-kinds
  "What a node can be. Deliberately broad -- per ADR-2607203000 no entity is
   categorically out of scope -- but each kind carries an obligation about what
   sourcing it needs."
  {:organization  {:doc "A firm, company, cooperative, guild, church body, NGO, union, association, or any other non-state organised body."}
   :polity        {:doc "A state, empire, province, municipality, or other governing jurisdiction. Use :innen.node/polity-level for the tier."}
   :person        {:doc "A natural person. Admissible ONLY as a documented historical actor whose role is part of the public record; see person-problems. Never a living private individual, and never a personal name attached to a currently-serving office (that workspace rule predates this repo -- see cloud-itonami municipality organization.edn)."}
   :contract      {:doc "A treaty, charter, concession, licence, lease, loan agreement, franchise, or any other instrument creating obligations."}
   :event         {:doc "A dated occurrence: a founding, a war, an election, a market crash, a launch."}
   :incident      {:doc "A failure or harm event: an outage, a spill, a collapse, a breach, a disaster."}
   :artifact      {:doc "A built thing depended upon: a canal, a cable, a fab, a pipeline, a codebase, a satellite constellation."}
   :standard      {:doc "A specification, protocol, code system, or unit of account others must conform to."}
   :resource      {:doc "A material or natural input: a mineral, a fuel, a watershed, a seed line."}
   :document      {:doc "A record that testifies to other nodes: an archive holding, a filing, a ledger, a chronicle."}})

(def edge-kinds
  "Kinds of dependency. Each entry states what `from depends on to` means for
   that kind, so a reader never has to guess the semantics of an edge."
  {:supply           {:doc "from requires goods/services supplied by to."}
   :ownership        {:doc "from is owned (in whole or part) by to."}
   :control          {:doc "from is directed or governed by to without necessarily being owned by it."}
   :funding          {:doc "from's continuation depends on capital/revenue from to."}
   :legal-authority  {:doc "from's right to act derives from to (a charter, statute, treaty, licence, or grant)."}
   :obligation       {:doc "from owes a performance to to under an instrument."}
   :succession       {:doc "from succeeds, replaces, or inherits the position of to."}
   :causation        {:doc "from occurred because of to. Requires a source that itself asserts the causal link -- see :innen.edge/causal-basis."}
   :participation    {:doc "from (an event/incident) involved to as a party."}
   :infrastructure   {:doc "from depends on physical or digital infrastructure to."}
   :information      {:doc "from depends on data, records, or a standard held/defined by to."}})

(def necessities
  "How load-bearing an edge is. Drives cascade semantics in innen.algo."
  {:required       {:doc "from cannot function without to. A failed to fails from."}
   :substitutable  {:doc "to is one of several sources for the same need. from fails only if ALL substitutable dependencies of that kind fail."}
   :incidental     {:doc "a real relation that does not by itself carry load. Never propagates failure."}})

(def confidences
  "How well-established the claim is. Never inferred -- the ingesting code
   must state it, because 'how sure are we' is a property of the source, not
   something a later reader can reconstruct."
  {:documented {:doc "A primary or authoritative source states the relation directly."}
   :attested   {:doc "A secondary source states it; primary not consulted."}
   :contested  {:doc "Sources disagree. Record it, and record the disagreement in :innen.edge/note."}
   :estimate   {:doc "Derived or inferred rather than stated. Must say by what method in :innen.edge/note."}})

(defn- problem [severity code msg data]
  (merge {:innen/severity severity :innen/code code :innen/message msg} data))

(defn- blank? [s] (or (nil? s) (and (string? s) (str/blank? s))))

(defn node-problems
  "Admissibility problems for one node."
  [{:innen.node/keys [id kind label source existed] :as n}]
  (cond-> []
    (not (keyword? id))
    (conj (problem :error :node/id-not-keyword "node :innen.node/id must be a keyword" {:innen/node n}))

    (not (contains? node-kinds kind))
    (conj (problem :error :node/unknown-kind (str "unknown node kind: " (pr-str kind)) {:innen/node n}))

    (blank? label)
    (conj (problem :error :node/no-label "node needs a human-readable :innen.node/label" {:innen/node n}))

    (blank? source)
    (conj (problem :error :node/no-source
                   "node needs :innen.node/source (citation, with retrieval date for online sources)"
                   {:innen/node n}))

    (and existed (not (t/sane-interval? existed)))
    (conj (problem :error :node/bad-interval
                   (str "node :innen.node/existed is not a sane interval: " (pr-str existed))
                   {:innen/node n}))

    (and (= :person kind) (not (:innen.node/historical? n)))
    (conj (problem :error :node/person-not-marked-historical
                   "a :person node must set :innen.node/historical? true and cite the public record establishing the role; living private individuals are not admissible"
                   {:innen/node n}))))

(defn edge-problems
  "Admissibility problems for one edge. Fail-closed on sourcing."
  [{:innen.edge/keys [from to kind necessity confidence as-of source valid causal-basis] :as e}]
  (cond-> []
    (not (keyword? from))
    (conj (problem :error :edge/from-not-keyword "edge :innen.edge/from must be a node id keyword" {:innen/edge e}))

    (not (keyword? to))
    (conj (problem :error :edge/to-not-keyword "edge :innen.edge/to must be a node id keyword" {:innen/edge e}))

    (= from to)
    (conj (problem :error :edge/self-loop "an entity cannot depend on itself; model the real intermediate node instead" {:innen/edge e}))

    (not (contains? edge-kinds kind))
    (conj (problem :error :edge/unknown-kind (str "unknown edge kind: " (pr-str kind)) {:innen/edge e}))

    (not (contains? necessities necessity))
    (conj (problem :error :edge/unknown-necessity
                   (str "edge must declare :innen.edge/necessity, one of " (pr-str (set (keys necessities))))
                   {:innen/edge e}))

    (not (contains? confidences confidence))
    (conj (problem :error :edge/unknown-confidence
                   (str "edge must declare :innen.edge/confidence, one of " (pr-str (set (keys confidences))))
                   {:innen/edge e}))

    (blank? source)
    (conj (problem :error :edge/no-source
                   "edge needs :innen.edge/source -- a citation a human can check (URL + retrieval date, archive reference, or publication)"
                   {:innen/edge e}))

    (blank? as-of)
    (conj (problem :error :edge/no-as-of
                   "edge needs :innen.edge/as-of -- the date THIS OBSERVATION was made (distinct from :innen.edge/valid, when the relation itself held)"
                   {:innen/edge e}))

    (and as-of (nil? (t/parse as-of)))
    (conj (problem :error :edge/bad-as-of (str "unparseable :innen.edge/as-of: " (pr-str as-of)) {:innen/edge e}))

    (and valid (not (t/sane-interval? valid)))
    (conj (problem :error :edge/bad-valid-interval
                   (str "edge :innen.edge/valid is not a sane interval: " (pr-str valid))
                   {:innen/edge e}))

    (and (= :causation kind) (blank? causal-basis))
    (conj (problem :error :edge/causation-without-basis
                   "a :causation edge needs :innen.edge/causal-basis quoting or naming what in the source asserts causation -- co-occurrence is not causation"
                   {:innen/edge e}))

    (and (= :estimate confidence) (blank? (:innen.edge/note e)))
    (conj (problem :error :edge/estimate-without-method
                   "confidence :estimate needs :innen.edge/note stating the derivation method"
                   {:innen/edge e}))

    (and (= :contested confidence) (blank? (:innen.edge/note e)))
    (conj (problem :warn :edge/contested-without-note
                   "confidence :contested should record the disagreement in :innen.edge/note"
                   {:innen/edge e}))

    (nil? valid)
    (conj (problem :warn :edge/no-valid-interval
                   "edge has no :innen.edge/valid interval -- it will appear in every historical slice, which is rarely what a historical relation means"
                   {:innen/edge e}))))

(defn errors [problems] (filterv #(= :error (:innen/severity %)) problems))
(defn warnings [problems] (filterv #(= :warn (:innen/severity %)) problems))
