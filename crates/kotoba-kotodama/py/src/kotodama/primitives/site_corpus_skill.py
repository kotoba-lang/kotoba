"""Corpus2Skill distillation tasks for site.etzhayyim.com.

Implements arXiv 2604.14572 "Don't Retrieve, Navigate" offline distillation:
  site.corpus2skill.distillDomain — offline build of level-0..3 skill tree
  site.corpus2skill.navigateDomain — runtime LLM tree navigation (returns cluster_ids)

Weekly batch (R/P7D) rebuilds the full tree per domain. At query time,
navigateDomain is called synchronously from the site.searchSemantic handler.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from kotodama import llm
from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("site_corpus2skill")

_OWNER_DID = "did:web:site.etzhayyim.com"
_DEFAULT_BRANCH_K = 8  # children per non-leaf node
_MAX_HOPS = 3

# ── Offline distillation ───────────────────────────────────────────────────────

def task_site_corpus2skill_distill_domain(
    domain: str = "",
    branch_k: int = _DEFAULT_BRANCH_K,
    sample_limit: int = 50_000,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Build the 4-level skill tree for one domain.

    Level 0: root (1 node, summary of entire domain corpus)
    Level 1: K top-level categories (K-means centroids of all chunk embeddings)
    Level 2: K subcategories per L1 node
    Level 3: K leaf topics per L2 node → each leaf maps to IVF cluster IDs

    LLM (call_tier 'balanced') generates label + summary for each node.
    Nodes are inserted into vertex_corpus_skill_node; leaf-to-chunk edges
    go into edge_skill_doc.
    """
    try:
        import faiss  # type: ignore[import]
        import numpy as np  # type: ignore[import]
    except ImportError:
        return {"ok": False, "error": "faiss-cpu not installed"}

    if not domain:
        return {"ok": False, "error": "domain is required"}

    version_tag = time.strftime("%Y%m%d%H%M", time.gmtime())
    LOG.info("corpus2skill.distillDomain domain=%s version=%s", domain, version_tag)

    # Load embeddings
    kotoba_client = get_kotoba_client()
    # R0: Filtering for 'embedding IS NOT NULL' in Python
    rows = kotoba_client.select_where(
        "vertex_wet_chunk",
        "domain",
        domain,
        columns=["vertex_id", "embedding", "ivf_cluster_id", "markdown", "url"],
        limit=int(sample_limit)
    )
    rows = [row for row in rows if row.get("embedding") is not None]

    if not rows:
        return {"ok": False, "error": "no embedded chunks", "domain": domain}

    vids = [r["vertex_id"] for r in rows]
    embs = np.array([r["embedding"] for r in rows], dtype=np.float32)
    cluster_ids = [r["ivf_cluster_id"] for r in rows]
    markdowns = [r["markdown"] for r in rows]

    def _kmeans_assign(vectors: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        k = min(k, len(vectors))
        km = faiss.Kmeans(d=vectors.shape[1], k=k, niter=15, verbose=False)
        km.train(vectors)
        _, assigns = km.index.search(vectors, 1)
        return km.centroids, assigns.flatten()

    def _llm_label(texts: list[str], level_hint: str) -> tuple[str, str]:
        sample = "\n---\n".join(texts[:8])
        prompt = (
            f"You are labelling a {level_hint} cluster of web documents.\n"
            f"Representative excerpts:\n{sample}\n\n"
            "Reply with JSON: {\"label\": \"<2-5 word label>\", \"summary\": \"<1 sentence>\"}"
        )
        try:
            resp = llm.call_tier("fast", system="You label document clusters concisely.",
                                 user=prompt, max_tokens=120, temperature=0.0)
            parsed = llm.parse_json_content(resp.get("content", ""))
            if parsed and "label" in parsed:
                return str(parsed["label"]), str(parsed.get("summary", ""))
        except Exception:
            pass
        return f"{level_hint} cluster", ""

    def _insert_node(
        node_id: str, parent_id: str | None, level: int,
        centroid: list[float], label: str, summary: str, doc_count: int,
    ) -> None:
        if dry_run:
            return
        kotoba_client = get_kotoba_client()
        row_dict = {
            "node_id": node_id,
            "owner_did": _OWNER_DID,
            "parent_id": parent_id,
            "level": level,
            "domain": domain,
            "summary": summary,
            "doc_count": doc_count,
            "centroid": centroid, # already a list of floats
            "label": label,
            "distill_version": version_tag,
            "status": "active",
        }
        kotoba_client.insert_row("vertex_corpus_skill_node", row_dict)

    def _insert_leaf_edges(node_id: str, chunk_vids: list[str], chunk_cluster_ids: list[int | None]) -> None:
        if dry_run:
            return
        kotoba_client = get_kotoba_client()
        for vid, cid in zip(chunk_vids, chunk_cluster_ids):
            edge_id = hashlib.sha256(f"{node_id}:{vid}:{version_tag}".encode()).hexdigest()[:32]
            row_dict = {
                "edge_id": edge_id,
                "node_id": node_id,
                "chunk_vertex_id": vid,
                "domain": domain,
                "cluster_id": cid,
                "distill_version": version_tag,
                "distance": None,
            }
            kotoba_client.insert_row("edge_skill_doc", row_dict)

    # L0 root
    root_id = f"cs:{domain}:root:{version_tag}"
    root_centroid = embs.mean(axis=0).tolist()
    sample_texts = [m for m in markdowns[:10] if m]
    root_label, root_summary = _llm_label(sample_texts, "domain root")
    _insert_node(root_id, None, 0, root_centroid, root_label, root_summary, len(vids))

    nodes_created = 1
    edges_created = 0

    # L1 categories
    l1_centroids, l1_assigns = _kmeans_assign(embs, branch_k)
    for l1_idx in range(len(l1_centroids)):
        mask1 = l1_assigns == l1_idx
        if not mask1.any():
            continue
        l1_vids_sub = [vids[i] for i in range(len(vids)) if mask1[i]]
        l1_texts = [markdowns[i] for i in range(len(markdowns)) if mask1[i] and markdowns[i]]
        l1_label, l1_summary = _llm_label(l1_texts, "category")
        l1_id = f"cs:{domain}:l1:{version_tag}:{l1_idx}"
        _insert_node(l1_id, root_id, 1, l1_centroids[l1_idx].tolist(), l1_label, l1_summary, int(mask1.sum()))
        nodes_created += 1

        # L2 subcategories
        sub_embs1 = embs[mask1]
        l2_centroids, l2_assigns_local = _kmeans_assign(sub_embs1, branch_k)
        global_l2_assigns = np.zeros(len(vids), dtype=int) - 1
        global_l2_assigns[mask1] = l2_assigns_local

        for l2_idx in range(len(l2_centroids)):
            mask2 = (l1_assigns == l1_idx) & (global_l2_assigns == l2_idx)
            if not mask2.any():
                continue
            l2_vids_sub = [vids[i] for i in range(len(vids)) if mask2[i]]
            l2_texts = [markdowns[i] for i in range(len(markdowns)) if mask2[i] and markdowns[i]]
            l2_label, l2_summary = _llm_label(l2_texts, "topic")
            l2_id = f"cs:{domain}:l2:{version_tag}:{l1_idx}:{l2_idx}"
            _insert_node(l2_id, l1_id, 2, l2_centroids[l2_idx].tolist(), l2_label, l2_summary, int(mask2.sum()))
            nodes_created += 1

            # L3 leaf topics
            sub_embs2 = embs[mask2]
            l3_centroids, l3_assigns_local = _kmeans_assign(sub_embs2, branch_k)
            global_l3_assigns = np.zeros(len(vids), dtype=int) - 1
            global_l3_assigns[mask2] = l3_assigns_local

            for l3_idx in range(len(l3_centroids)):
                mask3 = mask2.copy()
                temp = np.zeros(len(vids), dtype=bool)
                temp[mask2] = l3_assigns_local == l3_idx
                mask3 = temp
                if not mask3.any():
                    continue
                l3_vids_sub = [vids[i] for i in range(len(vids)) if mask3[i]]
                l3_cids_sub = [cluster_ids[i] for i in range(len(vids)) if mask3[i]]
                l3_texts = [markdowns[i] for i in range(len(markdowns)) if mask3[i] and markdowns[i]]
                l3_label, l3_summary = _llm_label(l3_texts, "leaf topic")
                l3_id = f"cs:{domain}:l3:{version_tag}:{l1_idx}:{l2_idx}:{l3_idx}"
                _insert_node(l3_id, l2_id, 3, l3_centroids[l3_idx].tolist(), l3_label, l3_summary, int(mask3.sum()))
                nodes_created += 1
                _insert_leaf_edges(l3_id, l3_vids_sub, l3_cids_sub)
                edges_created += len(l3_vids_sub)

    LOG.info("distillDomain done domain=%s nodes=%d edges=%d", domain, nodes_created, edges_created)
    return {
        "ok": True,
        "domain": domain,
        "version_tag": version_tag,
        "dry_run": dry_run,
        "nodes_created": nodes_created,
        "edges_created": edges_created,
    }


# ── Runtime navigation (synchronous, called from searchSemantic) ───────────────

def corpus_skill_navigate_sync(
    query_text: str,
    domain: str,
    max_hops: int = _MAX_HOPS,
) -> dict[str, Any]:
    """LLM-guided tree navigation for Corpus2Skill.

    At each level: load children of current node, ask LLM to pick the best
    child based on query_text, descend until leaf (level=3) or max_hops.

    Returns: {domain, cluster_ids, node_path, leaf_node_id, hop_count, distill_version}
    """
    # Find latest distill_version for domain
    kotoba_client = get_kotoba_client()
    # R0: Order by and limit 1 to find the latest distill_version.
    query_edn = f"""
    [:find (max ?version) .
     :where
       [?e :vertex_corpus_skill_node/domain "{domain}"]
       [?e :vertex_corpus_skill_node/status "active"]
       [?e :vertex_corpus_skill_node/level 0]
       [?e :vertex_corpus_skill_node/distill_version ?version]]
    """
    distill_version = kotoba_client.q(query_edn)
    if distill_version is not None:
        distill_version = str(distill_version) # Ensure it's a string

    # The original code gets a 'row' then 'row[0]'.
    # If distill_version is None, the original code would have row as None.
    # So we need to handle that.
    row = [distill_version] if distill_version else None
    if not row:
        return {"domain": domain, "cluster_ids": [], "node_path": [], "hop_count": 0}

    distill_version = row[0]

    # Start from root
    kotoba_client = get_kotoba_client()
    # R0: Multiple predicates for selecting the root node.
    query_edn = f"""
    [:find ?node_id ?label ?summary .
     :where
       [?e :vertex_corpus_skill_node/domain "{domain}"]
       [?e :vertex_corpus_skill_node/distill_version "{distill_version}"]
       [?e :vertex_corpus_skill_node/level 0]
       [?e :vertex_corpus_skill_node/status "active"]
       [?e :vertex_corpus_skill_node/node_id ?node_id]
       [?e :vertex_corpus_skill_node/label ?label]
       [?e :vertex_corpus_skill_node/summary ?summary]]
    """
    root = kotoba_client.q(query_edn)

    if not root:
        return {"domain": domain, "cluster_ids": [], "node_path": [], "hop_count": 0}

    current_node_id = root[0]
    node_path: list[str] = [current_node_id]
    hop_count = 0

    for hop in range(max_hops):
        # Load children
        current_level = hop  # root=0, after hop 1 we're at level 1, etc.
        # R0: Multiple predicates for selecting child nodes.
        query_edn = f"""
        [:find ?node_id ?label ?summary
         :where
           [?e :vertex_corpus_skill_node/parent_id "{current_node_id}"]
           [?e :vertex_corpus_skill_node/distill_version "{distill_version}"]
           [?e :vertex_corpus_skill_node/status "active"]
           [?e :vertex_corpus_skill_node/node_id ?node_id]
           [?e :vertex_corpus_skill_node/label ?label]
           [?e :vertex_corpus_skill_node/summary ?summary]
         :limit 32]
        """
        children = kotoba_client.q(query_edn)

        if not children:
            break

        # LLM selects best child
        options_text = "\n".join(
            f"{i+1}. [{c[1]}] {c[2]}" for i, c in enumerate(children)
        )
        prompt = (
            f"Query: {query_text}\n\n"
            f"Choose the most relevant topic node (reply with only the number):\n{options_text}"
        )
        try:
            resp = llm.call_tier(
                "fast",
                system="You are a navigation assistant. Reply with only the option number.",
                user=prompt,
                max_tokens=8,
                temperature=0.0,
            )
            content = (resp.get("content") or "1").strip()
            choice = int("".join(c for c in content if c.isdigit()) or "1") - 1
            choice = max(0, min(choice, len(children) - 1))
        except Exception:
            choice = 0

        current_node_id = children[choice][0]
        node_path.append(current_node_id)
        hop_count += 1

        # Check if we've reached a leaf
        kotoba_client = get_kotoba_client()
        level_row_dict = kotoba_client.select_first_where(
            "vertex_corpus_skill_node",
            "node_id",
            current_node_id,
            columns=["level"]
        )
        level_row = [level_row_dict["level"]] if level_row_dict else None
        if level_row and int(level_row[0]) >= 3:
            break

    # Get cluster_ids from edge_skill_doc for the leaf node
    # R0: Multiple predicates and DISTINCT for selecting cluster_ids.
    query_edn = f"""
    [:find ?cid
     :where
       [?e :edge_skill_doc/node_id "{current_node_id}"]
       [?e :edge_skill_doc/distill_version "{distill_version}"]
       [?e :edge_skill_doc/cluster_id ?cid]
     :limit 64]
    """
    cluster_rows_raw = kotoba_client.q(query_edn)
    # q returns a list of tuples, so we need to flatten and get distinct values
    cluster_rows = list(set([row[0] for row in cluster_rows_raw]))

    cluster_ids = [int(r) for r in cluster_rows]

    return {
        "domain": domain,
        "cluster_ids": cluster_ids,
        "node_path": node_path,
        "leaf_node_id": current_node_id,
        "hop_count": hop_count,
        "distill_version": distill_version,
    }


# ── Zeebe worker registration ──────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="site.corpus2skill.distillDomain",
        single_value=False,
        timeout_ms=max(timeout_ms, 7_200_000),
    )(task_site_corpus2skill_distill_domain)
