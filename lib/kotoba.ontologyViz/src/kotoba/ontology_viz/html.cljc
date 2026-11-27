(ns kotoba.ontology-viz.html
  "Self-contained, offline-only interactive HTML5 Viewer generator for
  `ontology.graph/v1` and Yataverse `yataverse.ontology.graph/v1` graphs.

  Security, G2, and G3 invariants:
  - Always validates caller-supplied graphs via `svg/normalize-and-validate-graph` (no unchecked bypass).
  - Strict offline Content-Security-Policy (no external scripts, fonts, styles, or fetches).
  - Self-contained `ov-*` CSS classes only (zero external design-system tokens or dependencies).
  - Strict `#RRGGBB` hex validation for CSS paint values and full HTML escaping for all text & counts.
  - Machine-readable live screen state (`data-screen-state` + `window.__KOTOBA_ONTOLOGY_SCREEN__`)
    synchronized with UI controls, matching agent `filter-graph` and `inspect-node` semantics.
  - WAI-ARIA `tablist`/`tab`/`tabpanel` with `aria-selected`, `aria-controls`, `aria-labelledby`,
    roving `tabindex`, and `ArrowLeft`/`ArrowRight`/`Home`/`End` keyboard navigation.
  - Client-side DOM updates use `textContent` / `createElement` only (never `innerHTML` with graph data)."
  (:require [clojure.string :as str]
            [kotoba.ontology-viz.escape :as esc]
            [kotoba.ontology-viz.graph :as g]
            [kotoba.ontology-viz.semantic :as sem]
            [kotoba.ontology-viz.svg :as svg]
            [kotoba.ontology-viz.validate :as v]))

(defn initial-screen-state
  "Build the deterministic, machine-readable initial Semantic UI screen state
  for a validated `ontology.graph/v1` graph."
  [graph]
  (v/validate-graph! graph)
  (let [nodes (:nodes graph)
        edges (:edges graph)
        layers (:layers graph)
        first-id (some-> (first nodes) :id)]
    {:screen/id "kotoba.ontology-viewer"
     :screen/status "ready"
     :schema/version sem/contract-version
     :basis/cid (get-in graph [:basis :root-cid])
     :basis/cid-verification (name (or (get-in graph [:basis :basis-cid-verification])
                                       (get-in graph [:basis :cid-verification])
                                       :syntax-only))
     :basis/basis-cid-verification (name (or (get-in graph [:basis :basis-cid-verification])
                                             (get-in graph [:basis :cid-verification])
                                             :syntax-only))
     :basis/graph-cid-verification (name (or (get-in graph [:basis :graph-cid-verification])
                                             :absent))
     :activeTab "inspect"
     :selectedNodeId first-id
     :activeLayers (mapv :id layers)
     :activeKinds []
     :query ""
     :zoom 1
     :visibleNodeIds (mapv :id nodes)
     :visibleEdgeIds (mapv :id edges)
     :controls {:zoomIn {:enabled true}
                :zoomOut {:enabled true}
                :zoomReset {:enabled false}
                :clearSearch {:enabled false}}
     :opAvailability {"ontology.inspect" {:enabled (boolean first-id)}
                      "ontology.graph" {:enabled true}
                      "ontology.view" {:enabled true}
                      "ontology.query_sql" {:enabled true}
                      "ontology.query_sparql" {:enabled true}}
     :ops sem/operation-names}))

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
.ov-btn:hover:not(:disabled){background:#f1f5f9}
.ov-btn:disabled{opacity:0.45;cursor:not-allowed}
.ov-main{display:grid;grid-template-columns:minmax(0,1fr) 380px;min-height:0}
@media(max-width:960px){.ov-main{grid-template-columns:1fr}}
.ov-canvas-pane{overflow:auto;padding:16px;background:#f1f5f9;position:relative}
.ov-svg-stage{display:inline-block;transform-origin:0 0;background:#ffffff;border:1px solid #cbd5e1;border-radius:10px;box-shadow:0 1px 3px rgba(15,23,42,0.08)}
.ov-node{cursor:pointer}
.ov-node:hover .ov-node-card,.ov-node.ov-selected .ov-node-card{stroke-width:3;filter:drop-shadow(0 2px 6px rgba(15,23,42,0.18))}
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
  var screenEl = document.getElementById('kotoba-ontology-screen');
  if(!graphEl || !schemaEl || !screenEl) return;
  var graph = JSON.parse(graphEl.textContent);
  var semSchema = JSON.parse(schemaEl.textContent);
  var nodesById = Object.create(null);
  (graph.nodes || []).forEach(function(n){ nodesById[n.id] = n; });
  var activeLayers = Object.create(null);
  (graph.layers || []).forEach(function(l){ activeLayers[l.id] = true; });
  var activeTab = 'inspect';
  var selectedNodeId = (graph.nodes && graph.nodes.length) ? graph.nodes[0].id : null;
  var zoom = 1.0;
  var stage = document.getElementById('ov-svg-stage');
  var searchInput = document.getElementById('ov-search');
  var clearBtn = document.getElementById('ov-clear-search');
  var zin = document.getElementById('ov-zoom-in');
  var zout = document.getElementById('ov-zoom-out');
  var zrst = document.getElementById('ov-zoom-reset');
  var inspectBox = document.getElementById('ov-inspector-body');
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.ov-tab'));

  function el(tag, cls, text){
    var node = document.createElement(tag);
    if(cls) node.className = cls;
    if(text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function inspectPayload(nodeId){
    var n = nodeId ? nodesById[nodeId] : null;
    if(!n) return {found:false, node:null, incoming:[], outgoing:[], joins:[]};
    var incoming = (graph.edges || []).filter(function(e){ return e.target === nodeId; });
    var outgoing = (graph.edges || []).filter(function(e){ return e.source === nodeId; });
    var joins = (graph.joins || []).filter(function(j){
      return j['from-node'] === nodeId || j['to-node'] === nodeId;
    });
    return {found:true, node:n, incoming:incoming, outgoing:outgoing, joins:joins};
  }

  function publishScreenState(visibleNodeIds, visibleEdgeIds){
    var q = (searchInput && searchInput.value ? searchInput.value : '').trim();
    var enabledLayers = (graph.layers || []).map(function(l){ return l.id; }).filter(function(id){ return !!activeLayers[id]; });
    var state = {
      'screen/id': 'kotoba.ontology-viewer',
      'screen/status': 'ready',
      'schema/version': semSchema['schema/version'] || 'kotoba.semantic-ui/v1',
      'basis/cid': (graph.basis && graph.basis['root-cid']) || null,
      'basis/cid-verification': (graph.basis && (graph.basis['basis-cid-verification'] || graph.basis['cid-verification'])) || 'syntax-only',
      'basis/basis-cid-verification': (graph.basis && (graph.basis['basis-cid-verification'] || graph.basis['cid-verification'])) || 'syntax-only',
      'basis/graph-cid-verification': (graph.basis && graph.basis['graph-cid-verification']) || 'absent',
      activeTab: activeTab,
      selectedNodeId: selectedNodeId,
      activeLayers: enabledLayers,
      activeKinds: [],
      query: q,
      zoom: Number(zoom.toFixed(2)),
      visibleNodeIds: visibleNodeIds,
      visibleEdgeIds: visibleEdgeIds,
      controls: {
        zoomIn: {enabled: zoom < 2.5},
        zoomOut: {enabled: zoom > 0.35},
        zoomReset: {enabled: Math.abs(zoom - 1.0) > 0.001},
        clearSearch: {enabled: q.length > 0}
      },
      opAvailability: {
        'ontology.inspect': {enabled: !!selectedNodeId},
        'ontology.graph': {enabled: true},
        'ontology.view': {enabled: true},
        'ontology.query_sql': {enabled: true},
        'ontology.query_sparql': {enabled: true}
      },
      ops: (semSchema.operations || []).map(function(o){ return o.name; })
    };
    if(zin) zin.disabled = !state.controls.zoomIn.enabled;
    if(zout) zout.disabled = !state.controls.zoomOut.enabled;
    if(zrst) zrst.disabled = !state.controls.zoomReset.enabled;
    if(clearBtn) clearBtn.disabled = !state.controls.clearSearch.enabled;
    screenEl.setAttribute('data-screen-state', JSON.stringify(state));
    window.__KOTOBA_ONTOLOGY_SCREEN__ = state;
    return state;
  }

  function applyFilters(){
    var q = (searchInput && searchInput.value ? searchInput.value : '').trim().toLowerCase();
    var visible = Object.create(null);
    var visibleNodeIds = [];
    var visibleEdgeIds = [];
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
      var show = inLayer && match;
      gEl.classList.toggle('ov-hidden', !show);
      if(show){
        visible[id] = true;
        visibleNodeIds.push(id);
      }
    });
    document.querySelectorAll('.ov-edge').forEach(function(eEl){
      var eid = eEl.getAttribute('data-edge-id');
      var s = eEl.getAttribute('data-source');
      var t = eEl.getAttribute('data-target');
      var showEdge = !!(visible[s] && visible[t]);
      eEl.classList.toggle('ov-hidden', !showEdge);
      if(showEdge) visibleEdgeIds.push(eid);
    });
    publishScreenState(visibleNodeIds, visibleEdgeIds);
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
    selectedNodeId = nodeId || null;
    document.querySelectorAll('.ov-node.ov-selected').forEach(function(x){ x.classList.remove('ov-selected'); });
    if(nodeId){
      var targetEl = document.querySelector('.ov-node[data-node-id=\"' + CSS.escape(nodeId) + '\"]');
      if(targetEl) targetEl.classList.add('ov-selected');
    }
    var payload = inspectPayload(nodeId);
    if(inspectBox){
      while(inspectBox.firstChild) inspectBox.removeChild(inspectBox.firstChild);
      if(!payload.found){
        inspectBox.appendChild(el('p', null, 'Select a node to inspect its ontology properties, IPLD CID, edges, and joins.'));
      } else {
        var n = payload.node;
        inspectBox.appendChild(el('h2', null, n.label || n.id));
        var baseRows = [['ID', n.id], ['Kind', n.kind], ['Layer', n.layer]];
        if(n.cid) baseRows.push(['IPLD CID', n.cid]);
        if(n.keys && n.keys.length) baseRows.push(['Keys', n.keys.join(', ')]);
        inspectBox.appendChild(renderKvTable(baseRows));

        if(n.attributes && Object.keys(n.attributes).length){
          inspectBox.appendChild(el('div', 'ov-section-title', 'Attributes'));
          var attrRows = Object.keys(n.attributes).sort().map(function(k){
            var v = n.attributes[k];
            return [k, Array.isArray(v) ? v.join(', ') : v];
          });
          inspectBox.appendChild(renderKvTable(attrRows));
        }
        if(n.provenance && Object.keys(n.provenance).length){
          inspectBox.appendChild(el('div', 'ov-section-title', 'Provenance'));
          var provRows = Object.keys(n.provenance).sort().map(function(k){
            var v = n.provenance[k];
            return [k, Array.isArray(v) ? v.join(', ') : v];
          });
          inspectBox.appendChild(renderKvTable(provRows));
        }
        var relEdges = payload.incoming.concat(payload.outgoing);
        if(relEdges.length){
          inspectBox.appendChild(el('div', 'ov-section-title', 'Edges (' + relEdges.length + ')'));
          var edgeRows = relEdges.map(function(e){
            var dir = e.source === nodeId ? '-> ' + e.target : '<- ' + e.source;
            return [e.label || e.kind, dir];
          });
          inspectBox.appendChild(renderKvTable(edgeRows));
        }
        if(payload.joins.length){
          inspectBox.appendChild(el('div', 'ov-section-title', 'Joins (' + payload.joins.length + ')'));
          var joinRows = payload.joins.map(function(j){
            return [j.id, j['from-attr'] + ' <-> ' + j['to-attr'] + ' (' + j.status + ')'];
          });
          inspectBox.appendChild(renderKvTable(joinRows));
        }
        inspectBox.appendChild(el('div', 'ov-section-title', 'ontology.inspect'));
        inspectBox.appendChild(el('pre', 'ov-pre', JSON.stringify(payload, null, 2)));
      }
    }
    applyFilters();
  }

  function activateTab(tab, moveFocus){
    var target = tab.getAttribute('aria-controls');
    activeTab = tab.getAttribute('data-tab-key') || 'inspect';
    tabs.forEach(function(t){
      var sel = (t === tab);
      t.setAttribute('aria-selected', String(sel));
      t.setAttribute('tabindex', sel ? '0' : '-1');
    });
    document.querySelectorAll('.ov-panel').forEach(function(p){ p.hidden = (p.id !== target); });
    if(moveFocus) tab.focus();
    applyFilters();
  }

  tabs.forEach(function(tab, idx){
    tab.addEventListener('click', function(){ activateTab(tab, false); });
    tab.addEventListener('keydown', function(ev){
      var nextIdx = null;
      if(ev.key === 'ArrowRight') nextIdx = (idx + 1) % tabs.length;
      else if(ev.key === 'ArrowLeft') nextIdx = (idx - 1 + tabs.length) % tabs.length;
      else if(ev.key === 'Home') nextIdx = 0;
      else if(ev.key === 'End') nextIdx = tabs.length - 1;
      if(nextIdx !== null){
        ev.preventDefault();
        activateTab(tabs[nextIdx], true);
      }
    });
  });

  document.querySelectorAll('.ov-layer-checkbox').forEach(function(cb){
    cb.addEventListener('change', function(){
      activeLayers[cb.value] = cb.checked;
      applyFilters();
    });
  });
  if(searchInput) searchInput.addEventListener('input', applyFilters);
  if(clearBtn) clearBtn.addEventListener('click', function(){
    if(searchInput) searchInput.value = '';
    applyFilters();
  });
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
    applyFilters();
  }
  if(zin) zin.addEventListener('click', function(){ setZoom(zoom + 0.15); });
  if(zout) zout.addEventListener('click', function(){ setZoom(zoom - 0.15); });
  if(zrst) zrst.addEventListener('click', function(){ setZoom(1.0); });

  function filterGraphLocal(params){
    var p = params || {};
    var rawLayers = (p.activeLayers !== undefined && p.activeLayers !== null) ? p.activeLayers : p.layers;
    var hasLayers = rawLayers !== undefined && rawLayers !== null;
    var layerSet = hasLayers ? Object.create(null) : null;
    if(hasLayers){ rawLayers.forEach(function(l){ layerSet[String(l)] = true; }); }
    var hasKinds = p.kinds !== undefined && p.kinds !== null;
    var kindSet = hasKinds ? Object.create(null) : null;
    if(hasKinds){ p.kinds.forEach(function(k){ kindSet[String(k)] = true; }); }
    var q = (p.query ? String(p.query) : '').trim().toLowerCase();
    var keptNodes = (graph.nodes || []).filter(function(n){
      if(layerSet && !layerSet[n.layer]) return false;
      if(kindSet && !kindSet[n.kind]) return false;
      if(q && String(n.id || '').toLowerCase().indexOf(q) === -1 &&
         String(n.label || '').toLowerCase().indexOf(q) === -1 &&
         String(n.cid || '').toLowerCase().indexOf(q) === -1) return false;
      return true;
    });
    var keptIds = Object.create(null);
    keptNodes.forEach(function(n){ keptIds[n.id] = true; });
    var keptEdges = (graph.edges || []).filter(function(e){
      return !!(keptIds[e.source] && keptIds[e.target]);
    });
    return {nodes: keptNodes, edges: keptEdges};
  }

  var SQL_TABLE_SCHEMAS = {
    nodes: ['cid', 'id', 'kind', 'label', 'layer'],
    edges: ['cid', 'id', 'kind', 'label', 'layer', 'source', 'target'],
    joins: ['cardinality', 'coverage', 'excluded_count', 'from_attr', 'from_node', 'id', 'match_rule', 'matched_count', 'status', 'to_attr', 'to_node', 'unmatched_count'],
    layers: ['id', 'label', 'node_count', 'order']
  };

  function sqlTableRows(tbl){
    if(tbl === 'nodes'){
      return (graph.nodes || []).map(function(n){
        return {id:n.id, label:n.label, kind:String(n.kind || ''), layer:n.layer, cid:n.cid !== undefined ? n.cid : null};
      });
    }
    if(tbl === 'edges'){
      return (graph.edges || []).map(function(e){
        return {id:e.id, source:e.source, target:e.target, label:e.label, kind:String(e.kind || ''), layer:e.layer, cid:e.cid !== undefined ? e.cid : null};
      });
    }
    if(tbl === 'joins'){
      return (graph.joins || []).map(function(j){
        return {
          id:j.id, from_node:j['from-node'], from_attr:j['from-attr'], to_node:j['to-node'], to_attr:j['to-attr'],
          match_rule:String(j['match-rule'] || ''), cardinality:String(j.cardinality || ''),
          matched_count:j['matched-count'], unmatched_count:j['unmatched-count'], excluded_count:j['excluded-count'],
          coverage:j.coverage !== undefined ? j.coverage : null, status:String(j.status || '')
        };
      });
    }
    if(tbl === 'layers'){
      return (graph.layers || []).map(function(l){
        return {id:l.id, label:l.label, order:l.order, node_count:l['node-count']};
      });
    }
    throw new Error('unknown-sql-table');
  }

  function querySqlLocal(sql, opts){
    var s = String(sql || '').trim().replace(/;\\s*$/, '');
    if(!s || s.length > 2048) throw new Error('invalid-sql');
    if(/;|--|\\/\\*/.test(s) || /\\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|PRAGMA|ATTACH|DETACH|REPLACE|MERGE|EXEC|EXECUTE|CALL|GRANT|REVOKE|COPY|VACUUM)\\b/i.test(s)){
      throw new Error('unsafe-sql');
    }
    var m = s.match(/^SELECT\\s+(.+?)\\s+FROM\\s+(nodes|edges|joins|layers)(?:\\s+WHERE\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*=\\s*'([^']*)')?(?:\\s+LIMIT\\s+(\\d+))?$/i);
    if(!m) throw new Error('unsupported-sql-shape');
    var tbl = m[2].toLowerCase();
    var allowed = SQL_TABLE_SCHEMAS[tbl];
    var colsRaw = m[1].trim();
    var cols;
    if(colsRaw === '*'){
      cols = allowed.slice();
    } else {
      cols = colsRaw.split(',').map(function(c){
        var t = c.trim();
        if(!/^[A-Za-z_][A-Za-z0-9_]*$/.test(t)) throw new Error('unsupported-sql-shape');
        var lc = t.toLowerCase();
        if(allowed.indexOf(lc) === -1) throw new Error('unknown-sql-column');
        return lc;
      });
    }
    var rows = sqlTableRows(tbl);
    var scanned = rows.length;
    if(m[3]){
      var wc = m[3].toLowerCase();
      if(allowed.indexOf(wc) === -1) throw new Error('unknown-sql-column');
      rows = rows.filter(function(r){ return String(r[wc] !== undefined && r[wc] !== null ? r[wc] : '') === m[4]; });
    }
    var paramLim = (opts && opts.limit !== undefined) ? parseInt(opts.limit, 10) : 100;
    if(!(paramLim >= 1 && paramLim <= 500)) throw new Error('invalid-sql');
    var lim = paramLim;
    if(m[5]){
      var sqlLim = parseInt(m[5], 10);
      if(!(sqlLim >= 1 && sqlLim <= 500)) throw new Error('invalid-sql');
      lim = Math.min(paramLim, sqlLim);
    }
    var projected = rows.slice(0, lim).map(function(r){
      var obj = {};
      cols.forEach(function(c){ obj[c] = r[c]; });
      return obj;
    });
    return {
      dialect: 'sql-readonly-v1',
      table: tbl,
      columns: cols,
      'row-count': projected.length,
      'scanned-rows': scanned,
      scannedRows: scanned,
      rows: projected
    };
  }

  var DEFAULT_SPARQL_PREFIXES = {
    rdf: 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    rdfs: 'http://www.w3.org/2000/01/rdf-schema#',
    xsd: 'http://www.w3.org/2001/XMLSchema#'
  };

  function canonicalNodeTerm(id){
    var s = String(id || '');
    return s.indexOf('rdf:') === 0 ? s.slice(4) : s;
  }

  function expandSparqlTerm(tok, pmap){
    if(tok.indexOf('?') === 0) return tok;
    if(tok.length >= 2 && tok.charAt(0) === '<' && tok.charAt(tok.length - 1) === '>') return tok.slice(1, -1);
    if(tok.charAt(0) === '\"'){
      var lm = tok.match(/^\"([^\"]*)\"(.*)$/);
      if(lm){
        var lex = lm[1], suf = lm[2];
        if(!suf) return lex;
        if(suf.charAt(0) === '@') return lex + suf;
        if(suf.indexOf('^^') === 0) return lex + '^^<' + expandSparqlTerm(suf.slice(2), pmap) + '>';
      }
      return tok;
    }
    var ci = tok.indexOf(':');
    if(ci !== -1){
      var pfx = tok.slice(0, ci), loc = tok.slice(ci + 1);
      if(Object.prototype.hasOwnProperty.call(pmap, pfx)) return pmap[pfx] + loc;
    }
    return tok;
  }

  function buildLocalTriples(){
    var rdfType = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type';
    var rdfsLabel = 'http://www.w3.org/2000/01/rdf-schema#label';
    var seen = Object.create(null);
    var out = [];
    function pushT(s, p, o){
      var k = s + '\\u0000' + p + '\\u0000' + o;
      if(!seen[k]){ seen[k] = true; out.push([s, p, o]); }
    }
    (graph.nodes || []).forEach(function(n){
      var s = (n.attributes && n.attributes.iri) ? String(n.attributes.iri) : canonicalNodeTerm(n.id);
      pushT(s, rdfType, String(n.kind || 'node'));
      pushT(s, rdfsLabel, String(n.label || ''));
      pushT(s, 'kotoba:layer', String(n.layer || ''));
      if(n.cid) pushT(s, 'ipld:cid', String(n.cid));
      if(n.attributes){
        Object.keys(n.attributes).forEach(function(k){
          if(k === 'iri') return;
          var v = n.attributes[k];
          if(v === null || v === undefined) return;
          var pk = k.replace(/\\s+\\[[^\\]]+\\]$/, '');
          var vals = Array.isArray(v) ? v : [v];
          vals.forEach(function(val){ pushT(s, pk, String(val)); });
        });
      }
    });
    (graph.edges || []).forEach(function(e){
      var s = canonicalNodeTerm(e.source);
      var o = canonicalNodeTerm(e.target);
      var p = (e.metadata && e.metadata['predicate-iri']) ? String(e.metadata['predicate-iri']) : String(e.label || '');
      pushT(s, p, o);
    });
    return out;
  }

  function querySparqlLocal(sparql, opts){
    var s = String(sparql || '').trim();
    if(!s || s.length > 2048) throw new Error('invalid-sparql');
    if(/\\b(SERVICE|LOAD|INSERT|DELETE|DROP|CLEAR|CREATE|ADD|MOVE|COPY|SILENT)\\b|\\bFROM\\s+NAMED\\b|\\bFROM\\s+<https?:/i.test(s)){
      throw new Error('remote-fetch-forbidden');
    }
    var pmap = Object.assign({}, DEFAULT_SPARQL_PREFIXES);
    var rem = s;
    var pm;
    while((pm = rem.match(/^PREFIX\\s+([A-Za-z0-9_-]*):\\s*<([^>]+)>\\s*/i))){
      pmap[pm[1]] = pm[2];
      rem = rem.slice(pm[0].length).trim();
    }
    if(/\\b(OPTIONAL|UNION|FILTER|GRAPH|BIND|VALUES|ORDER\\s+BY|GROUP\\s+BY|HAVING|OFFSET|MINUS|SUBSELECT|CONSTRUCT|DESCRIBE)\\b/i.test(rem)){
      throw new Error('unsupported-sparql-clause');
    }
    var askM = rem.match(/^ASK\\s*(?:WHERE\\s*)?\\{([^{}]*)\\}$/i);
    var selM = askM ? null : rem.match(/^SELECT\\s+(\\*|(?:\\?[A-Za-z0-9_]+(?:\\s+\\?[A-Za-z0-9_]+)*))\\s+(?:WHERE\\s*)?\\{([^{}]*)\\}(?:\\s+LIMIT\\s+([0-9]+))?$/i);
    if(!askM && !selM) throw new Error('unsafe-sparql');
    var whereBody = askM ? askM[1] : selM[2];
    var toks = whereBody.match(/\"[^\"]*\"(?:\\^\\^(?:<[^>]+>|[A-Za-z0-9_-]*:[A-Za-z0-9_.-]+)|@[A-Za-z0-9-]+)?|<[^>]+>|\\?[A-Za-z0-9_]+|[^\\s]+/g) || [];
    var clauses = [], cur = [];
    toks.forEach(function(tok){
      if(tok === '.'){ if(cur.length){ clauses.push(cur); cur = []; } }
      else if(tok.length > 1 && tok.charAt(tok.length - 1) === '.' && tok.charAt(0) !== '\"' && tok.charAt(0) !== '<'){
        cur.push(tok.slice(0, -1)); clauses.push(cur); cur = [];
      } else { cur.push(tok); }
    });
    if(cur.length) clauses.push(cur);
    if(!clauses.length) throw new Error('invalid-sparql');
    var patterns = clauses.map(function(c){
      if(c.length !== 3) throw new Error('invalid-sparql');
      return c.map(function(t){ return expandSparqlTerm(t, pmap); });
    });
    var triples = buildLocalTriples();
    var steps = 0;
    var solutions = [{}];
    patterns.forEach(function(pat){
      var next = [];
      for(var bi = 0; bi < solutions.length; bi++){
        var b = solutions[bi];
        for(var ti = 0; ti < triples.length; ti++){
          steps++;
          if(steps > 100000) throw new Error('sparql-scan-limit-exceeded');
          var t = triples[ti], nb = Object.assign({}, b), ok = true;
          for(var idx = 0; idx < 3; idx++){
            var pt = pat[idx], tv = String(t[idx]);
            if(pt.charAt(0) === '?'){
              if(Object.prototype.hasOwnProperty.call(nb, pt)){ if(nb[pt] !== tv){ ok = false; break; } }
              else { nb[pt] = tv; }
            } else {
              if(pt !== tv && canonicalNodeTerm(pt) !== tv){ ok = false; break; }
            }
          }
          if(ok){
            next.push(nb);
            if(next.length > 10000) throw new Error('sparql-solution-limit-exceeded');
          }
        }
      }
      solutions = next;
    });
    function ednTerm(x){ return x.charAt(0) === '?' ? x : JSON.stringify(x); }
    var bgpEdn = '{:sparql/op :bgp, :patterns [' + patterns.map(function(p){ return '[' + p.map(ednTerm).join(' ') + ']'; }).join(' ') + ']}';
    if(askM){
      var hit = solutions.length > 0;
      return {
        dialect: 'sparql-readonly-v1',
        form: 'ask',
        boolean: hit,
        vars: [],
        'row-count': hit ? 1 : 0,
        'algebra-edn': bgpEdn,
        algebraEdn: bgpEdn,
        bindings: []
      };
    }
    var paramLim = (opts && opts.limit !== undefined) ? parseInt(opts.limit, 10) : 100;
    if(!(paramLim >= 1 && paramLim <= 500)) throw new Error('invalid-sparql');
    var lim = paramLim;
    if(selM[3]){
      var qLim = parseInt(selM[3], 10);
      if(!(qLim >= 1 && qLim <= 500)) throw new Error('invalid-sparql');
      lim = Math.min(paramLim, qLim);
    }
    var head = selM[1].trim();
    var projVars;
    if(head === '*'){
      var vs = Object.create(null);
      solutions.forEach(function(sol){ Object.keys(sol).forEach(function(k){ vs[k] = true; }); });
      projVars = Object.keys(vs).sort();
    } else {
      projVars = head.match(/\\?[A-Za-z0-9_]+/g) || [];
    }
    var limited = solutions.slice(0, lim).map(function(sol){
      var row = {};
      projVars.forEach(function(v){ if(Object.prototype.hasOwnProperty.call(sol, v)) row[v] = sol[v]; });
      return row;
    });
    var projEdn = '{:sparql/op :project, :vars [' + projVars.join(' ') + '], :pattern ' + bgpEdn + '}';
    var sliceEdn = '{:sparql/op :slice, :offset 0, :limit ' + lim + ', :pattern ' + projEdn + '}';
    return {
      dialect: 'sparql-readonly-v1',
      form: 'select',
      vars: projVars,
      'row-count': limited.length,
      'algebra-edn': sliceEdn,
      algebraEdn: sliceEdn,
      bindings: limited
    };
  }

  function invokeLocal(op, params){
    var p = params || {};
    if(op === 'ontology.inspect') return inspectPayload(p['node-id'] || selectedNodeId);
    if(op === 'ontology.graph') return filterGraphLocal(p);
    if(op === 'ontology.view'){
      var fmt = String(p.format || 'svg').toLowerCase();
      if(fmt !== 'svg' && fmt !== 'html') throw new Error('invalid-format');
      var svgEl = stage ? stage.querySelector('svg') : null;
      return {
        format: fmt,
        'content-type': fmt === 'html' ? 'text/html; charset=utf-8' : 'image/svg+xml',
        content: fmt === 'html' ? ('<!DOCTYPE html>' + document.documentElement.outerHTML) : (svgEl ? svgEl.outerHTML : '')
      };
    }
    if(op === 'ontology.query_sql') return querySqlLocal(p.sql || p.query, p);
    if(op === 'ontology.query_sparql') return querySparqlLocal(p.sparql || p.query, p);
    throw new Error('unknown-operation: ' + op);
  }

  window.kotobaOntologyViewer = {
    getState: function(){ return window.__KOTOBA_ONTOLOGY_SCREEN__; },
    selectNode: selectNode,
    inspectNode: inspectPayload,
    filterGraph: filterGraphLocal,
    querySql: querySqlLocal,
    querySparql: querySparqlLocal,
    invoke: invokeLocal
  };

  if(selectedNodeId){
    selectNode(selectedNodeId);
  } else {
    applyFilters();
  }
})();")

(defn- render-layer-toggles [layers]
  (str/join
   "\n"
   (map
    (fn [l]
      (let [color (if (v/safe-hex-color? (:color l)) (:color l) "#475569")
            cnt (esc/escape-html (esc/fmt-num (or (:node-count l) 0)))]
        (str "      <label class=\"ov-layer-toggle\">"
             "<input type=\"checkbox\" class=\"ov-layer-checkbox\" value=\"" (esc/escape-attr (:id l)) "\" checked>"
             "<span class=\"ov-layer-dot\" style=\"background:" color "\"></span>"
             "<span>" (esc/escape-html (:label l)) " (" cnt ")</span>"
             "</label>")))
    layers)))

(defn- render-joins-panel [joins]
  (if (empty? joins)
    "<p>No external join coverage rules declared.</p>"
    (str/join
     "\n"
     (map
      (fn [j]
        (let [pct-raw (if (some? (:coverage j))
                        (esc/round-int (* 100.0 (double (:coverage j))))
                        0)
              pct (max 0 (min 100 pct-raw))
              cov-label (if (some? (:coverage j)) (str pct "%") "schema-only")
              matched-s (esc/escape-html (esc/fmt-num (or (:matched-count j) 0)))
              unmatched-s (esc/escape-html (esc/fmt-num (or (:unmatched-count j) 0)))
              excluded-s (esc/escape-html (esc/fmt-num (or (:excluded-count j) 0)))]
          (str "      <div class=\"ov-join-card\" data-join-id=\"" (esc/escape-attr (:id j)) "\">\n"
               "        <div><strong>" (esc/escape-html (:from-attr j)) "</strong> &harr; <strong>"
               (esc/escape-html (:to-attr j)) "</strong></div>\n"
               (when (:description j)
                 (str "        <div style=\"font-size:12px;color:#475569;margin-top:2px\">"
                      (esc/escape-html (:description j)) "</div>\n"))
               "        <div class=\"ov-bar-track\"><div class=\"ov-bar-fill\" style=\"width:" pct "%\"></div></div>\n"
               "        <table class=\"ov-kv\"><tbody>\n"
               "          <tr><th>Rule</th><td><span class=\"ov-code\">"
               (esc/escape-html (name (or (:match-rule j) :exact)))
               "</span> (" (esc/escape-html (name (or (:cardinality j) :many-to-one))) ")</td></tr>\n"
               "          <tr><th>Coverage</th><td><span class=\"ov-code\">"
               (esc/escape-html cov-label) "</span> ["
               (esc/escape-html (name (or (:status j) :schema-only))) "]</td></tr>\n"
               "          <tr><th>Counts</th><td>matched=" matched-s
               ", unmatched=" unmatched-s ", excluded=" excluded-s "</td></tr>\n"
               (when (seq (:exclude j))
                 (str "          <tr><th>Exclude</th><td><span class=\"ov-code\">"
                      (esc/escape-html (str/join ", " (:exclude j))) "</span></td></tr>\n"))
               (when (seq (:unmatched-values j))
                 (str "          <tr><th>Unmatched</th><td><span class=\"ov-code\">"
                      (esc/escape-html (str/join ", " (:unmatched-values j))) "</span></td></tr>\n"))
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
  "Render a validated `ontology.graph/v1`, Yataverse `yataverse.ontology.graph/v1`,
  or raw projection input map as a self-contained, zero-network interactive
  HTML5 Viewer document."
  ([graph-or-input] (render-html graph-or-input {}))
  ([graph-or-input {:keys [title] :or {title "Kotoba IPLD Ontology Viewer"}}]
   (let [graph (svg/normalize-and-validate-graph graph-or-input)
         limits (or (get-in graph [:basis :bounds]) v/default-limits)
         _ (v/assert-label-length! limits :html/title title)
         svg-markup (str/trimr (svg/render-svg graph {:title title :interactive? true}))
         basis (:basis graph)
         layers (:layers graph)
         joins (:joins graph)
         screen-state (initial-screen-state graph)
         graph-json (esc/json-for-script graph)
         schema-json (esc/json-for-script sem/schema)
         screen-state-attr (esc/escape-attr (esc/json-encode screen-state))
         node-cnt-s (esc/escape-html (esc/fmt-num (count (:nodes graph))))
         edge-cnt-s (esc/escape-html (esc/fmt-num (count (:edges graph))))
         join-cnt-s (esc/escape-html (esc/fmt-num (count joins)))
         cid-ver (esc/escape-html (name (or (:basis-cid-verification basis) (:cid-verification basis) :syntax-only)))
         graph-cid-ver (some-> (:graph-cid-verification basis) name)]
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
          "<div id=\"kotoba-ontology-screen\" class=\"ov-shell\" data-screen-id=\"kotoba.ontology-viewer\" data-screen-state=\"" screen-state-attr "\">\n"
          "  <header class=\"ov-header\">\n"
          "    <h1>" (esc/escape-html title) "</h1>\n"
          "    <div class=\"ov-basis-badges\">\n"
          "      <span class=\"ov-pill\">" (esc/escape-html g/schema-version) "</span>\n"
          "      <span class=\"ov-pill\">codec: " (esc/escape-html (or (:codec basis) "dag-cbor")) "</span>\n"
          "      <span class=\"ov-pill\">basis-cid: " cid-ver "</span>\n"
          (when (and graph-cid-ver (not= graph-cid-ver "absent"))
            (str "      <span class=\"ov-pill\">graph-cid: " (esc/escape-html graph-cid-ver) "</span>\n"))
          (when-let [rc (:root-cid basis)]
            (str "      <span class=\"ov-pill\" title=\"" (esc/escape-attr rc) "\">root: "
                 (esc/escape-html (esc/short-cid rc)) "</span>\n"))
          "      <span class=\"ov-pill\">nodes: " node-cnt-s "</span>\n"
          "      <span class=\"ov-pill\">edges: " edge-cnt-s "</span>\n"
          "      <span class=\"ov-pill\">joins: " join-cnt-s "</span>\n"
          "    </div>\n"
          "  </header>\n"
          "  <section class=\"ov-toolbar\" aria-label=\"Graph controls\">\n"
          "    <div class=\"ov-layers\">\n"
          (render-layer-toggles layers) "\n"
          "    </div>\n"
          "    <div class=\"ov-controls\">\n"
          "      <input id=\"ov-search\" class=\"ov-search\" type=\"search\" placeholder=\"Filter nodes by ID, label, CID...\" aria-label=\"Filter nodes\">\n"
          "      <button id=\"ov-clear-search\" class=\"ov-btn\" type=\"button\" disabled>Clear</button>\n"
          "      <button id=\"ov-zoom-out\" class=\"ov-btn\" type=\"button\">-</button>\n"
          "      <button id=\"ov-zoom-reset\" class=\"ov-btn\" type=\"button\" disabled>100%</button>\n"
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
          "      <div class=\"ov-tabs\" role=\"tablist\" aria-label=\"Inspector panels\">\n"
          "        <button id=\"ov-tab-inspect\" class=\"ov-tab\" role=\"tab\" aria-selected=\"true\" aria-controls=\"ov-panel-inspect\" data-tab-key=\"inspect\" tabindex=\"0\" type=\"button\">Inspect</button>\n"
          "        <button id=\"ov-tab-joins\" class=\"ov-tab\" role=\"tab\" aria-selected=\"false\" aria-controls=\"ov-panel-joins\" data-tab-key=\"joins\" tabindex=\"-1\" type=\"button\">Joins (" join-cnt-s ")</button>\n"
          "        <button id=\"ov-tab-semantic\" class=\"ov-tab\" role=\"tab\" aria-selected=\"false\" aria-controls=\"ov-panel-semantic\" data-tab-key=\"semantic\" tabindex=\"-1\" type=\"button\">Semantic UI</button>\n"
          "      </div>\n"
          "      <div id=\"ov-panel-inspect\" class=\"ov-panel\" role=\"tabpanel\" aria-labelledby=\"ov-tab-inspect\" tabindex=\"0\">\n"
          "        <div id=\"ov-inspector-body\"><p>Click any node in the graph to inspect details.</p></div>\n"
          "      </div>\n"
          "      <div id=\"ov-panel-joins\" class=\"ov-panel\" role=\"tabpanel\" aria-labelledby=\"ov-tab-joins\" tabindex=\"0\" hidden>\n"
          (render-joins-panel joins) "\n"
          "      </div>\n"
          "      <div id=\"ov-panel-semantic\" class=\"ov-panel\" role=\"tabpanel\" aria-labelledby=\"ov-tab-semantic\" tabindex=\"0\" hidden>\n"
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
