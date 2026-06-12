"""Kiyo AppView read/write XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


KIYO_DID = "did:web:kiyo.etzhayyim.com"
PAPER_COLLECTION = "com.etzhayyim.apps.kiyo.paper"


def _now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _bounded_int(v: Any, default: int, *, min_value: int, max_value: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = default
    return max(min_value, min(max_value, n))


def _paper_vid(paper_id: str) -> str:
    return f"at://{KIYO_DID}/{PAPER_COLLECTION}/{paper_id}"


def task_kiyo_withdraw_paper(paperId: str = "", **_: Any) -> dict[str, Any]:
    if not paperId:
        return {"error": "paperId required"}
    db = get_kotoba_client()
    paper_vid = _paper_vid(paperId)
    existing_paper = db.select_first_where("vertex_kiyo_paper", "vertex_id", paper_vid)
    if existing_paper:
        existing_paper["status"] = "withdrawn"
        db.insert_row("vertex_kiyo_paper", existing_paper)
    return {"withdrawn": True}


def task_kiyo_add_review(
    paperId: str = "", rating: Any = None, body: str = "", reviewType: str = "comment", callerDid: str = "", **_: Any
) -> dict[str, Any]:
    review_id = f"at://{KIYO_DID}/com.etzhayyim.apps.kiyo.review/{int(datetime.now(timezone.utc).timestamp() * 1000):x}"
    rating_v: int | None
    try:
        rating_v = int(rating) if rating is not None else None
    except (TypeError, ValueError):
        rating_v = None
    db = get_kotoba_client()
    review_data = {
        "vertex_id": review_id,
        "paper_id": paperId,
        "reviewer_did": reviewer,
        "rating": rating_v,
        "body": body,
        "review_type": reviewType or "comment",
        "owner_did": reviewer,
        "actor_did": reviewer,
        "org_did": "anon",
        "created_at": now,
        "sensitivity_ord": 0,
    }
    db.insert_row("vertex_kiyo_review", review_data)
    return {"reviewId": review_id, "accepted": True}

def task_kiyo_endorse_paper(paperId: str = "", callerDid: str = "", **_: Any) -> dict[str, Any]:
    if not paperId:
        return {"error": "paperId required"}
    caller = callerDid or KIYO_DID
    paper_vid = _paper_vid(paperId)
    edge_id = f"edge:kiyo:endorses:{caller}:{paperId}"
    db = get_kotoba_client()
    edge_data = {
        "edge_id": edge_id,
        "src_vid": caller,
        "dst_vid": paper_vid,
        "created_at": _now(),
    }
    db.insert_row("edge_kiyo_endorses", edge_data)
    stats = db.select_first_where("mv_kiyo_paper_stats", "paper_id", paperId)
    return {"endorsed": True, "totalEndorsements": int((stats or {}).get("endorsement_count") or 0)}


def task_kiyo_get_paper(paperId: str = "", **_: Any) -> dict[str, Any]:
    db = get_kotoba_client()
    paper = db.select_first_where("vertex_kiyo_paper", "paper_id", paperId)
    if not paper:
        return {"error": "not found"}
    stats = db.select_first_where("mv_kiyo_paper_stats", "paper_id", paperId)
    # R0: In-Python sorting for 'order_num'
    authors_raw = db.select_where("edge_kiyo_authored_by", "src_vid", _paper_vid(paperId), columns=["dst_vid", "role", "order_num"])
    authors = sorted(authors_raw, key=lambda x: x.get("order_num", 0))

    s = stats if stats else {}
    return {
        "paperId": paper.get("paper_id"),
        "title": paper.get("title"),
        "abstract": paper.get("abstract"),
        "subject": paper.get("subject"),
        "authors": [a.get("dst_vid") for a in authors],
        "authorType": paper.get("author_type"),
        "status": paper.get("status"),
        "ipfsCid": paper.get("ipfs_cid"),
        "latestVersion": paper.get("latest_version"),
        "submittedAt": paper.get("submitted_at"),
        "citationCount": int(s.get("citation_in_count") or 0),
        "reviewCount": int(s.get("review_count") or 0),
        "endorsements": int(s.get("endorsement_count") or 0),
    }


def task_kiyo_list_papers(subject: str = "", authorType: str = "", since: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    limit_n = _bounded_int(limit, 50, min_value=1, max_value=100)
    offset_n = _bounded_int(offset, 0, min_value=0, max_value=100_000)
    db = get_kotoba_client()
    # R0: Multi-predicate WHERE, ORDER BY, LIMIT, OFFSET handled in Python.
    all_papers = db.select_where("vertex_kiyo_paper", "status", "active")

    filtered_papers = []
    for paper in all_papers:
        match = True
        if subject and not (paper.get("subject") and subject in paper["subject"]): # Assuming 'subject' is a list/array
            match = False
        if authorType and paper.get("author_type") != authorType:
            match = False
        if since and paper.get("submitted_at") and paper["submitted_at"] < since:
            match = False
        if match:
            filtered_papers.append(paper)

    sorted_papers = sorted(filtered_papers, key=lambda x: x.get("submitted_at", ""), reverse=True)

    papers = sorted_papers[offset_n : offset_n + limit_n]

    return {"papers": papers, "offset": offset_n, "limit": limit_n}


def task_kiyo_search_papers(q: str = "", subject: str = "", limit: Any = 20, offset: Any = 0, **_: Any) -> dict[str, Any]:
    limit_n = _bounded_int(limit, 20, min_value=1, max_value=50)
    offset_n = _bounded_int(offset, 0, min_value=0, max_value=100_000)
    db = get_kotoba_client()
    # R0: Multi-predicate WHERE (including ILIKE), ORDER BY, LIMIT, OFFSET handled in Python.
    all_papers = db.select_where("vertex_kiyo_paper", "status", "active")

    filtered_papers = []
    q_lower = q.lower()
    for paper in all_papers:
        match = True
        if subject and not (paper.get("subject") and subject in paper["subject"]): # Assuming 'subject' is a list/array
            match = False
        if q and not (
            (paper.get("title") and q_lower in paper["title"].lower())
            or (paper.get("abstract") and q_lower in paper["abstract"].lower())
        ):
            match = False
        if match:
            # Add a dummy score for consistency with original SQL
            paper["score"] = 1.0
            filtered_papers.append(paper)

    sorted_papers = sorted(filtered_papers, key=lambda x: x.get("submitted_at", ""), reverse=True)

    papers = sorted_papers[offset_n : offset_n + limit_n]
    return {"papers": papers, "offset": offset_n, "limit": limit_n}


def task_kiyo_get_paper_file(paperId: str = "", version: Any = None, fileType: str = "pdf", ipfsGatewayUrl: str = "https://ipfs.etzhayyim.com", **_: Any) -> dict[str, Any]:
    version_n = _bounded_int(version, 0, min_value=0, max_value=10_000) if version not in (None, "") else 0
    cid = ""
    db = get_kotoba_client()
    if version_n > 0:
        # R0: Multiple WHERE conditions require raw Datalog q()
        query_edn = """
            [:find ?ipfs_cid ?source_ipfs_cid
             :where
             [?e :vertex_kiyo_revision/paper_id ?paper_id]
             [?e :vertex_kiyo_revision/version ?version_n]
             [?e :vertex_kiyo_revision/ipfs_cid ?ipfs_cid]
             [?e :vertex_kiyo_revision/source_ipfs_cid ?source_ipfs_cid]]
        """
        rows = db.q(query_edn, args={"?paper_id": paperId, "?version_n": version_n})
        if rows:
            # q() returns list of lists, convert to dict for consistency
            row_dict = {"ipfs_cid": rows[0][0], "source_ipfs_cid": rows[0][1]}
            cid = str(row_dict.get("source_ipfs_cid") if fileType == "source" else row_dict.get("ipfs_cid") or "")
    else:
        paper = db.select_first_where("vertex_kiyo_paper", "paper_id", paperId, columns=["ipfs_cid", "latest_version"])
        if paper:
            cid = str(paper.get("ipfs_cid") or "")
    if not cid:
        return {"error": "not found"}
    base = (ipfsGatewayUrl or "https://ipfs.etzhayyim.com").rstrip("/")
    return {
        "url": f"{base}/ipfs/{cid}",
        "cid": cid,
        "version": version_n,
        "contentType": "application/x-tar" if fileType == "source" else "application/pdf",
    }


def task_kiyo_list_by_author(authorDid: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    limit_n = _bounded_int(limit, 50, min_value=1, max_value=100)
    offset_n = _bounded_int(offset, 0, min_value=0, max_value=100_000)
    db = get_kotoba_client()
    h = db.select_first_where("mv_kiyo_author_hindex", "author_did", authorDid)

    # R0: Complex JOIN with ORDER BY, LIMIT, OFFSET handled by Datalog q() and Python processing
    query_edn = """
        [:find
          ?paper_id ?title ?role ?submitted_at ?citation_in_count
         :where
          [?e_authored :edge_kiyo_authored_by/dst_vid ?authorDid]
          [?e_authored :edge_kiyo_authored_by/src_vid ?paper_vid]
          [?e_authored :edge_kiyo_authored_by/role ?role]

          [?p :vertex_kiyo_paper/vertex_id ?paper_vid]
          [?p :vertex_kiyo_paper/paper_id ?paper_id]
          [?p :vertex_kiyo_paper/title ?title]
          [?p :vertex_kiyo_paper/submitted_at ?submitted_at]

          (or
            (and
              [?s :mv_kiyo_paper_stats/paper_id ?paper_id]
              [?s :mv_kiyo_paper_stats/citation_in_count ?citation_in_count]
            )
            (not
              [?s :mv_kiyo_paper_stats/paper_id ?paper_id]
              [(identity 0) ?citation_in_count]
            )
          )
        ]
    """
    raw_papers = db.q(query_edn, args={"?authorDid": authorDid})

    # Convert results from lists to dicts for easier processing
    papers_list = []
    for row in raw_papers:
        papers_list.append({
            "paper_id": row[0],
            "title": row[1],
            "role": row[2],
            "submitted_at": row[3],
            "citationCount": row[4],
        })

    # Apply ORDER BY, LIMIT, OFFSET in Python
    sorted_papers = sorted(papers_list, key=lambda x: x.get("submitted_at", ""), reverse=True)
    papers = sorted_papers[offset_n : offset_n + limit_n]

    total_citations = int(h.get("total_citations") or 0) if h else 0
    return {
        "authorDid": authorDid,
        "hIndex": int(total_citations ** 0.5) if h else 0,
        "totalPapers": int(h.get("total_papers") or 0),
        "totalCitations": total_citations,
        "papers": papers,
        "offset": offset_n,
        "limit": limit_n,
    }


def task_kiyo_get_citation_graph(paperId: str = "", **_: Any) -> dict[str, Any]:
    paper_vid = _paper_vid(paperId)
    db = get_kotoba_client()
    citing = db.select_where("edge_kiyo_cites", "dst_vid", paper_vid, columns=["src_vid", "ref_label", "confidence"], limit=100)
    cited = db.select_where("edge_kiyo_cites", "src_vid", paper_vid, columns=["dst_vid", "resolved_doi", "ref_label", "confidence"], limit=100)
    return {"paperId": paperId, "citing": citing, "cited": cited}


def task_kiyo_get_stats(**_: Any) -> dict[str, Any]:
    db = get_kotoba_client()
    total_papers_count = int(db.aggregate_where("vertex_kiyo_paper", "count", "paper_id", "status", "active"))

    # R0: ORDER BY and LIMIT for mv_kiyo_subject_stats handled by Datalog q() and Python processing
    query_edn = """
        [:find ?subject_code ?paper_count ?recent_30d_count
         :where
         [?e :mv_kiyo_subject_stats/subject_code ?subject_code]
         [?e :mv_kiyo_subject_stats/paper_count ?paper_count]
         [?e :mv_kiyo_subject_stats/recent_30d_count ?recent_30d_count]]
    """
    raw_subject_stats = db.q(query_edn)

    subject_rows_list = []
    for row in raw_subject_stats:
        subject_rows_list.append({
            "subject_code": row[0],
            "paper_count": row[1],
            "recent_30d_count": row[2],
        })

    # Apply ORDER BY and LIMIT in Python
    sorted_subject_rows = sorted(subject_rows_list, key=lambda x: x.get("paper_count", 0), reverse=True)
    subject_rows = sorted_subject_rows[:50]

    return {
        "totalPapers": total_papers_count,
        "subjects": [
            {
                "subjectCode": s.get("subject_code"),
                "paperCount": int(s.get("paper_count") or 0),
                "recent30d": int(s.get("recent_30d_count") or 0),
            }
            for s in subject_rows
        ],
    }


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "xrpc.com.etzhayyim.apps.kiyo.addReview": task_kiyo_add_review,
        "xrpc.com.etzhayyim.apps.kiyo.endorsePaper": task_kiyo_endorse_paper,
        "xrpc.com.etzhayyim.apps.kiyo.getCitationGraph": task_kiyo_get_citation_graph,
        "xrpc.com.etzhayyim.apps.kiyo.getPaper": task_kiyo_get_paper,
        "xrpc.com.etzhayyim.apps.kiyo.getPaperFile": task_kiyo_get_paper_file,
        "xrpc.com.etzhayyim.apps.kiyo.getStats": task_kiyo_get_stats,
        "xrpc.com.etzhayyim.apps.kiyo.listByAuthor": task_kiyo_list_by_author,
        "xrpc.com.etzhayyim.apps.kiyo.listPapers": task_kiyo_list_papers,
        "xrpc.com.etzhayyim.apps.kiyo.searchPapers": task_kiyo_search_papers,
        "xrpc.com.etzhayyim.apps.kiyo.withdrawPaper": task_kiyo_withdraw_paper,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
