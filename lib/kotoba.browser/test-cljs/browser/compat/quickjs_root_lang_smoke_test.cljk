(ns browser.compat.quickjs-root-lang-smoke-test
  "Real page-script round-trip proof that :root and :lang() genuinely
  work through the JS-facing selector engine (matches()/querySelector()/
  querySelectorAll()) -- evaluated through the actual webapi shim string
  inside real QuickJS WASM, not a JVM stand-in.

  Before this cycle's fix, both were entirely absent -- any selector
  using either always returned an empty/false/null result, regardless
  of whether the candidate node was actually the document's root or
  carried a matching own/inherited lang.

  Engine quirk documented here (not fixed -- pre-existing, out of scope
  for this cycle): this engine's HTML parser always synthesizes a
  `:document`-tagged wrapper as the real DOM root, one level ABOVE
  whatever the source HTML's own top-level element is (even a literal
  `<html>` tag is parsed as an ordinary child element, never unwrapped
  into the root). So :root -- which real spec defines as always equal
  to document.documentElement -- instead matches ONLY that synthetic
  wrapper here; document.documentElement.matches(':root') is expected
  to be false, not true, in this engine. document.querySelector(':root')
  is used as the robust way to reach the true root regardless of this
  quirk."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- canned-fetch-fn
  [pages]
  (fn [{:keys [url]}]
    (if-let [html (get pages url)]
      {:status 200 :headers {} :body html}
      {:status 404 :headers {} :body (str "<main>not found: " url "</main>")})))

(defn- run-page-and-read-title!
  [html]
  (js/Promise.
   (fn [resolve reject]
     (let [url "https://app.example/root-lang-round-trip"
           fetch-fn (canned-fetch-fn {url html})
           h (host/recording-host)
           base-session (session/new-session
                         (quickjs-runner/quickjs-session-opts {:host h :fetch-fn fetch-fn}))]
       (-> (session/ensure-script-engine! base-session)
           (.then
            (fn [ready-session]
              (try
                (let [after (session/navigate! ready-session url)
                      title (get-in after [:browser.session/page :browser/title])]
                  (dispose-engine! ready-session)
                  (resolve title))
                (catch :default e
                  (dispose-engine! ready-session)
                  (reject e)))))
           (.catch (fn [err]
                     (dispose-engine! base-session)
                     (reject err))))))))

(def ^:private root-script
  "var r = [];
   var root = document.querySelector(':root');

   r.push(root !== null ? 1 : 'root-not-found');
   r.push(root.matches(':root') === true ? 1 : 'root-does-not-match-itself');

   var main = document.getElementById('m');
   r.push(main.matches(':root') === false ? 1 : 'non-root-wrongly-matches-root');

   var allRoots = document.querySelectorAll(':root');
   r.push(allRoots.length === 1 ? 1 : 'query-all-root-count-wrong:' + allRoots.length);

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-root-pseudo-class-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main id=\"m\"><script>" root-script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real :root pseudo-class round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected :root to genuinely match only the document's own root through "
                          "matches()/querySelector()/querySelectorAll() on real QuickJS -- got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs :root smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))

(def ^:private lang-script
  "var r = [];
   var wrap = document.getElementById('wrap');
   var frenchP = document.getElementById('frenchP');
   var plainP = document.getElementById('plainP');
   var blankLangP = document.getElementById('blankLangP');

   // plainP has no own lang -- inherits 'en' from the <div lang=\"en\"> ancestor
   r.push(plainP.matches(':lang(en)') === true ? 1 : 'inherited-lang-not-matched');
   r.push(plainP.matches(':lang(EN)') === true ? 1 : 'lang-match-not-case-insensitive');
   r.push(plainP.matches(':lang(fr)') === false ? 1 : 'inherited-lang-wrongly-matched-other-range');
   // subtag-prefix correctness: 'en' must NOT match a totally different tag
   r.push(plainP.matches(':lang(eng)') === false ? 1 : 'lang-range-wrongly-raw-string-prefix-matched');

   // frenchP's own lang=\"fr-CA\" overrides the inherited 'en'
   r.push(frenchP.matches(':lang(fr)') === true ? 1 : 'own-lang-subtag-not-matched');
   r.push(frenchP.matches(':lang(en)') === false ? 1 : 'own-lang-should-override-inherited');
   r.push(frenchP.matches(':lang(\"fr\")') === true ? 1 : 'quoted-lang-range-not-matched');

   // blank lang=\"\" does NOT count as own -- falls through to inherited 'en'
   r.push(blankLangP.matches(':lang(en)') === true ? 1 : 'blank-lang-attr-should-fall-through-to-inherited');

   // comma-separated ranges match if ANY range matches
   r.push(frenchP.matches(':lang(de, fr)') === true ? 1 : 'comma-separated-ranges-should-match-any');

   // the element carrying the attribute matches its own range
   r.push(wrap.matches(':lang(en)') === true ? 1 : 'own-lang-on-the-carrier-not-matched');

   // :lang() is not descendant-restricted -- every element inheriting or
   // owning 'en' matches: wrap (own), plainP and blankLangP (inherited), and
   // the <script> that is a child of wrap. frenchP is excluded (own fr-CA).
   var englishOnly = document.querySelectorAll(':lang(en)');
   r.push(englishOnly.length === 4 ? 1 : 'query-all-lang-en-count-wrong:' + englishOnly.length);

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

;; The lang carrier is a <div>, not <html>. It used to be <html lang="en">
;; wrapping a <body>, and that made this test RED from 2026-08-05 to
;; 2026-08-29 without anyone seeing it -- htmldom a4f6b94 drops <html>,
;; <head> and <body> outright (correct for the FRAGMENT parsing it does,
;; measured against Brave), so `document.querySelector('html')` was null and
;; the first line of the script threw. Nothing about :lang() was wrong.
;;
;; A <div> carrier tests the same thing -- inheritance down the tree, own
;; attribute overriding an ancestor's, blank attribute falling through,
;; subtag prefix matching, comma-separated ranges -- without depending on a
;; structural tag this engine deliberately does not keep. The :root half of
;; the original moved to its own test above, which does not need <html> to
;; exist.
(deftest quickjs-real-lang-pseudo-class-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<div id=\"wrap\" lang=\"en\">"
              "<p id=\"plainP\">hello</p>"
              "<p id=\"frenchP\" lang=\"fr-CA\">bonjour</p>"
              "<p id=\"blankLangP\" lang=\"\">still english</p>"
              "<script>" lang-script "</script>"
              "</div>"))
        (.then (fn [title]
                 (println "quickjs real :lang() pseudo-class round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected :lang() to genuinely work via real CSS lang inheritance through "
                          "matches()/querySelectorAll() on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs :lang() smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
