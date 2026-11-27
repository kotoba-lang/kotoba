(ns kotoba.ontology-viz.html
  "Self-contained, offline-only interactive HTML5 Viewer generator for
  `ontology.graph/v1` graphs.

  Security & policy invariants:
  - Strict offline Content-Security-Policy (no external scripts, fonts, styles, or fetches).
  - Self-contained `ov-*` CSS classes only (zero external design-system tokens or dependencies).
  - All embedded JSON escaped via `json-for-script` (no `</script>` breakout).
  - Client-side DOM updates use `textContent` / `createElement` only (never `innerHTML` with graph data)."
  (:require [clojure.string :as str]
            [kotoba.ontology-viz.escape :as esc]
            [kotoba.ontology-viz.graph :as g]
            [kotoba.ontology-viz.semantic :as sem]
            [kotoba.ontology-viz.svg :as svg]
            [kotoba.ontology-viz.validate :as v]))

(defn- normalize-graph [graph-or-input]
  (if (= g/schema-kind (:schema/kind graph-or-input))
    (if (:layout graph-or-input) graph-or-input (g/layout-graph graph-or-input))
    (g/project-graph graph-or-input)))

(def ^:private viewer-css
  "*,*::before,*::after{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;color:#0f172a;line-height:1.45}
.ov-shell{display:grid;grid-template-rows:auto auto 1fr auto;min-height:100vh}
.ov-header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding:14px 20px;background:#0f172a;color:#f8fafc;border-bottom:1px solid #1e293b}
.ov-header h1{margin:0;font-size:17px;font-weight:700;letter-spacing:-0.01em}
.ov-basis-badges{display:flex;flex-wrap:wrap;gap:8px;font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.ov-pill{display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:999px;background:#1e293b;color:#e2e8f0;border:1px solid #334155}
.ov-toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding:10px 20px;background:#ffffff;border-bottom:1px solid #e2e8f0}
.ov-layers{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.ov-layer-toggle{display:inline-flex;align-items:center;gap:6px;padding:5px 10px;border-radius:6px;border:1px solid #cbd5e1;background:#f8fafc;font-size:12px;font-weight:600;cursor:pointer;user-select:none}
.ov-layer-dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.ov-controls{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.ov-search{padding:6px 10px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;min-width:210px}
.ov-btn{padding:6px 10px;border:1px solid #cbd5e1;border-radius:6px;background:#ffffff;color:#0f172a;font-size:12px;font-weight:600;cursor:pointer}
.ov-btn:hover{background:#f1f5f9}
.ov-main{display:grid;grid-template-columns:minmax(0,1fr) 370px;min-height:0}
@media(max-width:960px){.ov-main{grid-template-columns:1fr}}
.ov-canvas-pane{overflow:auto;padding:16px;background:#f1f5f9;position:relative}
.ov-svg-stage{display:inline-block;transform-origin:0 0;background:#ffffff;border:1px solid #cbd5e1;border-radius:10px;box-shadow:0 1px 3px rgba(15,23,42,0.08)}
.ov-node{cursor:pointer}
.ov-node:hover .ov-node-card,.ov-node.ov-selected .ov-node-card{stroke-width:3;filter:drop-shadow(0 2px 6px rgba(15,23,42,0.18))}
.ov-dimmed{opacity:0.14}
.ov-hidden{display:none}
.ov-sidebar{border-left:1px solid #e2e8f0;background:#ffffff;display:flex;flex-direction:column;min-height:0}
.ov-tabs{display:flex;border-bottom:1px solid #e2e8f0;background:#f8fafc}
.ov-tab{flex:1;padding:10px 8px;border:none;border-bottom:2px solid transparent;background:transparent;font-size:12px;font-weight:700;color:#475569;cursor:pointer}
.ov-tab[aria-selected='true']{color:#1d4ed8;border-bottom-color:#1d4ed8;background:#ffffff}
.ov-panel{padding:14px 16px;overflow:auto;flex:1}
.ov-panel[hidden]{display:none}
.ov-kv{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px}
.ov-kv th,.ov-kv td{text-align:left;padding:6px 8px;border-bottom:1px solid #e2e8f0;vertical-align:top;word-break:break-word}
.ov-kv th{color:#475569;font-weight:600;width:36%}
.ov-code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;background:#f1f5f9;padding:2px 5px;border-radius:4px}
.ov-pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;background:#0f172a;color:#e2e8f0;padding:10px;border-radius:6px;overflow:auto;white-space:pre-wrap;word-break:break-word}
.ov-section-title{margin:14px 0 6px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.04em;color:#475569}
.ov-join-card{border:1px solid #e2e8f0;border-radius:8px;padding:10px;margin-bottom:10px;background:#f8fafc}
.ov-bar-track{height:8px;border-radius:999px;background:#e2e8f0;overflow:hidden;margin:6px 0}
.ov-bar-fill{height:100%;background:#1d4ed8}
.ov-op-card{border:1px solid #e2e8f0;border-radius:8px;padding:10px;margin-bottom:10px}
.ov-op-name{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;font-weight:700;color:#1d4ed8}
.ov-footer{padding:8px 20px;font-size:11.5px;color:#475569;background:#ffffff;border-top:1px solid #e2e8f0;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}")

(def ^:private viewer-js
  "(function(){
  'use strict';
  var graphEl = document.getElementById('kotoba-ontology-graph');
  var schemaEl = document.getElementById('kotoba-semantic-ui-schema');
  if(!graphEl || !schemaEl) return;
  var graph = JSON.parse(graphEl.textContent);
  var semSchema = JSON.parse(schemaEl.textContent);
  var nodesById = Object.create(null);
  (graph.nodes || []).forEach(function(n){ nodesById[n.id] = n; });
  var activeLayers = Object.create(null);
  (graph.layers || []).forEach(function(l){ activeLayers[l.id] = true; });
  var zoom = 1.0;
  var stage = document.getElementById('ov-svg-stage');
  var searchInput = document.getElementById('ov-search');
  var inspectBox = document.getElementById('ov-inspector-body');

  function el(tag, cls, text){
    var node = document.createElement(tag);
    if(cls) node.className = cls;
    if(text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function applyFilters(){
    var q = (searchInput && searchInput.value ? searchInput.value : '').trim().toLowerCase();
    var visible = Object.create(null);
    document.querySelectorAll('.ov-layer-band').forEach(function(b){
      var lid = b.getAttribute('data-layer');
      b.classList.toggle('ov-hidden', !activeLayers[lid]);
    });
    document.querySelectorAll('.ov-node').forEach(function(gEl){
      var id = gEl.getAttribute('data-node-id');
      var lid = gEl.getAttribute('data-layer');
      var n = nodesById[id];
      var inLayer = !!activeLayers[lid];
      var match = !q || (n && (
        String(n.id || '').toLowerCase().indexOf(q) !== -1 ||
        String(n.label || '').toLowerCase().indexOf(q) !== -1 ||
        String(n.cid || '').toLowerCase().indexOf(q) !== -1
      ));
      gEl.classList.toggle('ov-hidden', !inLayer);
      gEl.classList.toggle('ov-dimmed', inLayer && !match);
      if(inLayer && match) visible[id] = true;
    });
    document.querySelectorAll('.ov-edge').forEach(function(eEl){
      var s = eEl.getAttribute('data-source');
      var t = eEl.getAttribute('data-target');
      var sn = nodesById[s];
      var tn = nodesById[t];
      var bothLayer = sn && tn && activeLayers[sn.layer] && activeLayers[tn.layer];
      eEl.classList.toggle('ov-hidden', !bothLayer);
      eEl.classList.toggle('ov-dimmed', bothLayer && !(visible[s] || visible[t]));
    });
  }

  function renderKvTable(rows){
    var tbl = el('table', 'ov-kv');
    var tbody = el('tbody');
    rows.forEach(function(pair){
      var tr = el('tr');
      tr.appendChild(el('th', null, pair[0]));
      var td = el('td');
      td.appendChild(el('span', 'ov-code', pair[1]));
      tr.appendChild(td);
      tbody.appendChild(tr);
    });
    tbl.appendChild(tbody);
    return tbl;
  }

  function selectNode(nodeId){
    document.querySelectorAll('.ov-node.ov-selected').forEach(function(x){ x.classList.remove('ov-selected'); });
    var targetEl = document.querySelector('.ov-node[data-node-id=\"' + CSS.escape(nodeId) + '\"]');
    if(targetEl) targetEl.classList.add('ov-selected');
    var n = nodesById[nodeId];
    if(!inspectBox) return;
    while(inspectBox.firstChild) inspectBox.removeChild(inspectBox.firstChild);
    if(!n){
      inspectBox.appendChild(el('p', null, 'Select a node to inspect its ontology properties, IPLD CID, edges, and joins.'));
      return;
    }
    inspectBox.appendChild(el('h2', null, n.label || n.id));
    var baseRows = [['ID', n.id], ['Kind', n.kind], ['Layer', n.layer]];
    if(n.cid) baseRows.push(['IPLD CID', n.cid]);
    if(n.keys && n.keys.length) baseRows.push(['Keys', n.keys.join(', ')]);
    inspectBox.appendChild(renderKvTable(baseRows));

    if(n.attributes && Object.keys(n.attributes).length){
      inspectBox.appendChild(el('div', 'ov-section-title', 'Attributes'));
      var attrRows = Object.keys(n.attributes).sort().map(function(k){ return [k, n.attributes[k]]; });
      inspectBox.appendChild(renderKvTable(attrRows));
    }
    if(n.provenance && Object.keys(n.provenance).length){
      inspectBox.appendChild(el('div', 'ov-section-title', 'Provenance'));
      var provRows = Object.keys(n.provenance).sort().map(function(k){ return [k, n.provenance[k]]; });
      inspectBox.appendChild(renderKvTable(provRows));
    }
    var relEdges = (graph.edges || []).filter(function(e){ return e.source === nodeId || e.target === nodeId; });
    if(relEdges.length){
      inspectBox.appendChild(el('div', 'ov-section-title', 'Edges (' + relEdges.length + ')'));
      var edgeRows = relEdges.map(function(e){
        var dir = e.source === nodeId ? '-> ' + e.target : '<- ' + e.source;
        return [e.label || e.kind, dir];
      });
      inspectBox.appendChild(renderKvTable(edgeRows));
    }
    inspectBox.appendChild(el('div', 'ov-section-title', 'Semantic UI Request (ontology.inspect)'));
    inspectBox.appendChild(el('pre', 'ov-pre', JSON.stringify({op:'ontology.inspect', params:{'node-id': n.id}}, null, 2)));
  }

  document.querySelectorAll('.ov-layer-checkbox').forEach(function(cb){
    cb.addEventListener('change', function(){
      activeLayers[cb.value] = cb.checked;
      applyFilters();
    });
  });
  if(searchInput) searchInput.addEventListener('input', applyFilters);
  document.querySelectorAll('.ov-node').forEach(function(gEl){
    gEl.addEventListener('click', function(){ selectNode(gEl.getAttribute('data-node-id')); });
    gEl.addEventListener('keydown', function(ev){
      if(ev.key === 'Enter' || ev.key === ' '){
        ev.preventDefault();
        selectNode(gEl.getAttribute('data-node-id'));
      }
    });
  });

  function setZoom(next){
    zoom = Math.max(0.35, Math.min(2.5, next));
    if(stage) stage.style.transform = 'scale(' + zoom.toFixed(2) + ')';
  }
  var zin = document.getElementById('ov-zoom-in');
  var zout = document.getElementById('ov-zoom-out');
  var zrst = document.getElementById('ov-zoom-reset');
  if(zin) zin.addEventListener('click', function(){ setZoom(zoom + 0.15); });
  if(zout) zout.addEventListener('click', function(){ setZoom(zoom - 0.15); });
  if(zrst) zrst.addEventListener('click', function(){ setZoom(1.0); });

  document.querySelectorAll('.ov-tab').forEach(function(tab){
    tab.addEventListener('click', function(){
      var target = tab.getAttribute('data-panel');
      document.querySelectorAll('.ov-tab').forEach(function(t){ t.setAttribute('aria-selected', String(t === tab)); });
      document.querySelectorAll('.ov-panel').forEach(function(p){ p.hidden = (p.id !== target); });
    });
  });

  if(graph.nodes && graph.nodes.length){
    selectNode(graph.nodes[0].id);
  }
})();")

(defn- render-layer-toggles [layers]
  (str/join
   "\n"
   (map
    (fn [l]
      (str "      <label class=\"ov-layer-toggle\">"
           "<input type=\"checkbox\" class=\"ov-layer-checkbox\" value=\"" (esc/escape-attr (:id l)) "\" checked>"
           "<span class=\"ov-layer-dot\" style=\"background:" (esc/escape-attr (or (:color l) "#475569")) "\"></span>"
           "<span>" (esc/escape-html (:label l)) " (" (or (:node-count l) 0) ")</span>"
           "</label>"))
    layers)))

(defn- render-joins-panel [joins]
  (if (empty? joins)
    "<p>No external join coverage rules declared.</p>"
    (str/join
     "\n"
     (map
      (fn [j]
        (let [pct (if (some? (:coverage j))
                    #?(:clj (Math/round (* 100.0 (double (:coverage j))))
                       :cljs (js/Math.round (* 100.0 (double (:coverage j)))))
                    0)
              cov-label (if (some? (:coverage j)) (str pct "%") "schema-only")]
          (str "      <div class=\"ov-join-card\" data-join-id=\"" (esc/escape-attr (:id j)) "\">\n"
               "        <div><strong>" (esc/escape-html (:from-attr j)) "</strong> &harr; <strong>"
               (esc/escape-html (:to-attr j)) "</strong></div>\n"
               (when (:description j)
                 (str "        <div style=\"font-size:12px;color:#475569;margin-top:2px\">"
                      (esc/escape-html (:description j)) "</div>\n"))
               "        <div class=\"ov-bar-track\"><div class=\"ov-bar-fill\" style=\"width:" pct "%\"></div></div>\n"
               "        <table class=\"ov-kv\"><tbody>\n"
               "          <tr><th>Rule</th><td><span class=\"ov-code\">" (esc/escape-html (name (or (:match-rule j) :exact))) "</span> (" (esc/escape-html (name (or (:cardinality j) :many-to-one))) ")</td></tr>\n"
               "          <tr><th>Coverage</th><td><span class=\"ov-code\">" cov-label "</span> [" (esc/escape-html (name (or (:status j) :schema-only))) "]</td></tr>\n"
               "          <tr><th>Counts</th><td>matched=" (:matched-count j) ", unmatched=" (:unmatched-count j) ", excluded=" (:excluded-count j) "</td></tr>\n"
               (when (seq (:exclude j))
                 (str "          <tr><th>Exclude</th><td><span class=\"ov-code\">" (esc/escape-html (str/join ", " (:exclude j))) "</span></td></tr>\n"))
               (when (seq (:unmatched-values j))
                 (str "          <tr><th>Unmatched</th><td><span class=\"ov-code\">" (esc/escape-html (str/join ", " (:unmatched-values j))) "</span></td></tr>\n"))
               "        </tbody></table>\n"
               "      </div>")))
      joins))))

(defn- render-semantic-panel []
  (str/join
   "\n"
   (map
    (fn [op]
      (str "      <div class=\"ov-op-card\" data-op=\"" (esc/escape-attr (:name op)) "\">\n"
           "        <div class=\"ov-op-name\">" (esc/escape-html (:name op)) "</div>\n"
           "        <div style=\"font-size:12px;color:#334155;margin-top:4px\">"
           (esc/escape-html (:summary op)) "</div>\n"
           "      </div>"))
    (:operations sem/schema))))

(defn render-html
  "Render a normalized `ontology.graph/v1` (or raw projection input map) as a
  self-contained, zero-network interactive HTML5 Viewer document."
  ([graph-or-input] (render-html graph-or-input {}))
  ([graph-or-input {:keys [title] :or {title "Kotoba IPLD Ontology Viewer"}}]
   (let [graph (normalize-graph graph-or-input)
         limits (or (get-in graph [:basis :bounds]) v/default-limits)
         _ (v/assert-label-length! limits :html/title title)
         svg-markup (svg/render-svg graph {:title title})
         basis (:basis graph)
         layers (:layers graph)
         joins (:joins graph)
         graph-json (esc/json-for-script graph)
         schema-json (esc/json-for-script sem/schema)]
     (str "<!DOCTYPE html>\n"
          "<html lang=\"en\">\n"
          "<head>\n"
          "  <meta charset=\"utf-8\">\n"
          "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
          "  <meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:;\">\n"
          "  <title>" (esc/escape-html title) "</title>\n"
          "  <style>\n" viewer-css "\n  </style>\n"
          "</head>\n"
          "<body>\n"
          "<div class=\"ov-shell\">\n"
          "  <header class=\"ov-header\">\n"
          "    <h1>" (esc/escape-html title) "</h1>\n"
          "    <div class=\"ov-basis-badges\">\n"
          "      <span class=\"ov-pill\">" (esc/escape-html g/schema-version) "</span>\n"
          "      <span class=\"ov-pill\">codec: " (esc/escape-html (or (:codec basis) "dag-cbor")) "</span>\n"
          (when-let [rc (:root-cid basis)]
            (str "      <span class=\"ov-pill\" title=\"" (esc/escape-attr rc) "\">root: "
                 (esc/escape-html (esc/short-cid rc)) "</span>\n"))
          "      <span class=\"ov-pill\">nodes: " (count (:nodes graph)) "</span>\n"
          "      <span class=\"ov-pill\">edges: " (count (:edges graph)) "</span>\n"
          "      <span class=\"ov-pill\">joins: " (count joins) "</span>\n"
          "    </div>\n"
          "  </header>\n"
          "  <section class=\"ov-toolbar\" aria-label=\"Graph controls\">\n"
          "    <div class=\"ov-layers\">\n"
          (render-layer-toggles layers) "\n"
          "    </div>\n"
          "    <div class=\"ov-controls\">\n"
          "      <input id=\"ov-search\" class=\"ov-search\" type=\"search\" placeholder=\"Filter nodes by ID, label, CID...\" aria-label=\"Filter nodes\">\n"
          "      <button id=\"ov-zoom-out\" class=\"ov-btn\" type=\"button\">-</button>\n"
          "      <button id=\"ov-zoom-reset\" class=\"ov-btn\" type=\"button\">100%</button>\n"
          "      <button id=\"ov-zoom-in\" class=\"ov-btn\" type=\"button\">+</button>\n"
          "    </div>\n"
          "  </section>\n"
          "  <main class=\"ov-main\">\n"
          "    <div class=\"ov-canvas-pane\">\n"
          "      <div id=\"ov-svg-stage\" class=\"ov-svg-stage\">\n"
          svg-markup "\n"
          "      </div>\n"
          "    </div>\n"
          "    <aside class=\"ov-sidebar\" aria-label=\"Ontology inspector\">\n"
          "      <div class=\"ov-tabs\" role=\"tablist\">\n"
          "        <button class=\"ov-tab\" role=\"tab\" aria-selected=\"true\" data-panel=\"ov-panel-inspect\" type=\"button\">Inspect</button>\n"
          "        <button class=\"ov-tab\" role=\"tab\" aria-selected=\"false\" data-panel=\"ov-panel-joins\" type=\"button\">Joins (" (count joins) ")</button>\n"
          "        <button class=\"ov-tab\" role=\"tab\" aria-selected=\"false\" data-panel=\"ov-panel-semantic\" type=\"button\">Semantic UI</button>\n"
          "      </div>\n"
          "      <div id=\"ov-panel-inspect\" class=\"ov-panel\" role=\"tabpanel\">\n"
          "        <div id=\"ov-inspector-body\"><p>Click any node in the graph to inspect details.</p></div>\n"
          "      </div>\n"
          "      <div id=\"ov-panel-joins\" class=\"ov-panel\" role=\"tabpanel\" hidden>\n"
          (render-joins-panel joins) "\n"
          "      </div>\n"
          "      <div id=\"ov-panel-semantic\" class=\"ov-panel\" role=\"tabpanel\" hidden>\n"
          "        <div class=\"ov-section-title\">noun.verb Operations (" (esc/escape-html sem/contract-version) ")</div>\n"
          (render-semantic-panel) "\n"
          "        <div class=\"ov-section-title\">Sample Read-Only Queries</div>\n"
          "        <pre class=\"ov-pre\">SELECT id, label, kind FROM nodes LIMIT 20</pre>\n"
          "        <pre class=\"ov-pre\">SELECT ?s ?p ?o WHERE { ?s ?p ?o }</pre>\n"
          "      </div>\n"
          "    </aside>\n"
          "  </main>\n"
          "  <footer class=\"ov-footer\">\n"
          "    <span>Kotoba Ontology Viz (.cljc, offline fail-closed)</span>\n"
          "    <span>Semantic UI: " (esc/escape-html (str/join ", " sem/operation-names)) "</span>\n"
          "  </footer>\n"
          "</div>\n"
          "<script type=\"application/json\" id=\"kotoba-ontology-graph\">" graph-json "</script>\n"
          "<script type=\"application/json\" id=\"kotoba-semantic-ui-schema\">" schema-json "</script>\n"
          "<script>\n" viewer-js "\n</script>\n"
          "</body>\n"
          "</html>\n"))))
