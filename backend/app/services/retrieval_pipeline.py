"""
Retrieval pipeline — 7-stage legal RAG retrieval.

Stages:
  1. Query Router        — language detection, legal topic matching, metadata filter building
  2. Cross-lingual bal.  — single hybrid search (v1); reranker handles cross-lingual ranking
  3. Hybrid search       — dense + sparse via Milvus (20 candidates)
  4. Knowledge injection — deterministic legal section injection
  5. FlashRank reranker  — pointwise LTR reranking
  6. Score abstention    — reject if top score < 0.4
  7. Citation resolver   — page/section text references with [Source N] tags
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.embedding_service import encode_query
from app.services.vector_store_service import get_search_partitions, hybrid_search

logger = logging.getLogger(__name__)


# ── Data containers ──────────────────────────────────────────────────────────


@dataclass
class Citation:
    """A single cited source reference embedded in the LLM context."""

    source_index: int  # [Source N]
    page: int
    section: str | None
    text: str  # short (≤200 char) snippet


@dataclass
class RetrievalResult:
    """Final output of the full retrieval pipeline."""

    chunks: list[dict]  # ranked context chunks with rerank_score
    citations: list[Citation]
    abstained: bool  # True when top reranker score < 0.4
    coverage_warning: bool  # True when mandatory knowledge-layer sections are missing
    query_plan: dict  # router decision: language, mandatory_sections, metadata_filters, original_query


# ── Stage 1: Query Router ────────────────────────────────────────────────────


# Legal topic keyword maps — English / French / Arabic
_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "penalty_clause": [
        "penalty",
        "liquidated damages",
        "fine",
        "pénalité",
        "dommages",
        "amende",
        "clause pénale",
        "غرامة",
        "عقوبة",
        "تعويض",
    ],
    "termination": [
        "termination",
        "breach",
        "terminate",
        "résiliation",
        "rupture",
        "résilier",
        "إنهاء",
        "فسخ",
        "إخلال",
    ],
    "non_compete": [
        "non-compete",
        "non compete",
        "restrictive covenant",
        "non-concurrence",
        "concurrence",
        "clause restrictive",
        "عدم المنافسة",
        "منافسة",
        "تقييد",
    ],
    "indemnification": [
        "indemnif",
        "indemnity",
        "hold harmless",
        "indemnisation",
        "garantie",
        "dédommagement",
        "تعويض",
        "ضمان",
        "كفالة",
    ],
    "confidentiality": [
        "confidential",
        "nda",
        "non-disclosure",
        "confidentialité",
        "confidentiel",
        "non-divulgation",
        "سرية",
        "معلومات سرية",
        "إفشاء",
    ],
    "governing_law": [
        "governing law",
        "jurisdiction",
        "applicable law",
        "droit applicable",
        "juridiction",
        "loi applicable",
        "قانون واجب التطبيق",
        "اختصاص",
        "قانون",
    ],
    "force_majeure": [
        "force majeure",
        "act of god",
        "cas de force majeure",
        "force majeure",
        "قوة قاهرة",
        "ظرف طارئ",
    ],
    "assignment": [
        "assignment",
        "assign",
        "cession",
        "céder",
        "transfert",
        "تنازل",
        "إحالة",
    ],
    "arbitration": [
        "arbitration",
        "dispute",
        "arbitrage",
        "litige",
        "différend",
        "تحكيم",
        "نزاع",
    ],
    "entire_agreement": [
        "entire agreement",
        "merger clause",
        "integration",
        "intégralité",
        "accord complet",
        "clause de fusion",
        "الاتفاق الكامل",
        "دمج",
        "اتفاق شامل",
    ],
}


def _detect_query_language(text: str) -> str:
    """Detect query language using the same heuristic as pdf_engine.

    Imported at function level to avoid circular imports.
    Returns ``"ar"``, ``"fr"``, or ``"en"``.
    """
    from app.services.pdf_engine import detect_language_from_text

    return detect_language_from_text(text)


def _match_legal_topics(query: str) -> list[str]:
    """Scan the query for legal keywords and return matching topic slugs.

    A topic matches when **any** of its keywords appears as a substring
    (case-insensitive, no word-boundary requirement — legal terms often
    appear in compound forms).
    """
    lower = query.lower()
    matched: list[str] = []
    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(kw.lower() in lower for kw in keywords):
            matched.append(topic)
    return matched


def _route_query(query: str) -> dict:
    """Stage 1 — analyse the user query and build a routing plan.

    Returns a dict with:
      - ``language``         — detected language code
      - ``mandatory_sections`` — legal topics matched via keywords
      - ``metadata_filters``   — Milvus expression fragment (currently empty in v1)
      - ``original_query``     — the raw input
    """
    language = _detect_query_language(query)
    mandatory_sections = _match_legal_topics(query)

    plan = {
        "language": language,
        "mandatory_sections": mandatory_sections,
        "metadata_filters": "",
        "original_query": query,
    }
    logger.debug(
        "Query plan: language=%s mandatory_sections=%s",
        language,
        mandatory_sections,
    )
    return plan


# ── Stage 4: Knowledge-Layer Injection ───────────────────────────────────────


def _inject_knowledge(
    candidates: list[dict],
    query_plan: dict,
) -> list[dict]:
    """Stage 4 — prepend deterministic knowledge-layer chunks for mandatory sections.

    Each synthetic chunk carries ``score=1.0`` so it floats to the top before
    reranking (FlashRank will reassign scores).  The ``metadata`` dict includes
    ``knowledge_layer: True`` so downstream stages can identify it.
    """
    sections: list[str] = query_plan.get("mandatory_sections", [])
    if not sections:
        return candidates

    knowledge_chunks: list[dict] = []
    for section in sections:
        chunk: dict = {
            "id": -1,
            "document_id": -1,
            "chunk_index": -1,
            "text": (
                f"The document addresses {section.replace('_', ' ')} which "
                f"typically involves relevant legal principles and contractual "
                f"obligations. Review related sections for details."
            ),
            "page_number": 1,
            "section_title": f"Knowledge Layer: {section}",
            "score": 1.0,
            "metadata": {
                "knowledge_layer": True,
                "topic": section,
            },
        }
        knowledge_chunks.append(chunk)

    return knowledge_chunks + candidates


# ── Stage 5: FlashRank Reranker ──────────────────────────────────────────────


_reranker: Any = None  # singleton — lazy-loaded (type erased for lazy import)


def _get_reranker():
    """Lazy-load and cache the FlashRank ``Ranker`` singleton."""
    global _reranker
    if _reranker is not None:
        return _reranker
    from flashrank import Ranker

    _reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")
    logger.info("Loaded FlashRank reranker: ms-marco-MiniLM-L-12-v2")
    return _reranker


def _rerank(query: str, candidates: list[dict]) -> list[dict]:
    """Stage 5 — rerank candidates with FlashRank pointwise LTR.

    Operates on the list **in place** by adding ``rerank_score`` to each
    candidate and sorting descending.
    """
    if not candidates:
        return []

    reranker = _get_reranker()

    # Prepare FlashRank input (the library expects these exact keys)
    passages: list[dict] = []
    for i, c in enumerate(candidates):
        passages.append({
            "id": i,
            "text": c.get("text", ""),
        })

    # Rerank returns passages sorted by score descending
    results = reranker.rerank(query, passages)

    # Map scores back to original candidate list
    for r in results:
        idx: int = r["id"]  # type: ignore[assignment]
        if idx < len(candidates):
            candidates[idx]["rerank_score"] = r["score"]

    # Sort by rerank_score descending
    candidates.sort(key=lambda c: c.get("rerank_score", 0) or 0, reverse=True)
    return candidates


# ── Public API ───────────────────────────────────────────────────────────────


async def retrieve(
    query: str,
    user_id_int: int | None = None,
    top_k: int = 5,
) -> RetrievalResult:
    """Full 7-stage retrieval pipeline.

    Args:
        query:       User's natural-language legal question.
        user_id_int: Hashed user id, or ``None`` for an anonymous/system-only
            search. The system corpus (``p_system``) is always searched; when
            ``user_id_int`` is provided the caller's private partition is
            merged in via a single Milvus call.
        top_k:       Number of final context chunks to return (default 5).

    Returns:
        :class:`RetrievalResult` with ranked chunks, citations,
        abstention and coverage flags, and the query plan.
    """
    # ── Stage 1: Route ─────────────────────────────────────────────────
    query_plan = _route_query(query)

    # ── Stages 2 & 3: Embed + Hybrid Search ────────────────────────────
    try:
        dense_vec, sparse_vec = encode_query(query)
    except RuntimeError as e:
        logger.error("Query encoding failed: %s", e)
        return RetrievalResult(
            chunks=[],
            citations=[],
            abstained=True,
            coverage_warning=False,
            query_plan=query_plan,
        )

    try:
        candidates = hybrid_search(
            partition_names=get_search_partitions(user_id_int),
            dense_vec=dense_vec,
            sparse_vec=sparse_vec,
            query_text=query,
            top_k=20,  # retrieve extra candidates for reranking
        )
    except Exception as e:
        logger.error("Hybrid search failed: %s", e)
        return RetrievalResult(
            chunks=[],
            citations=[],
            abstained=True,
            coverage_warning=False,
            query_plan=query_plan,
        )

    if not candidates:
        logger.info("Hybrid search returned zero candidates — abstaining")
        return RetrievalResult(
            chunks=[],
            citations=[],
            abstained=True,
            coverage_warning=False,
            query_plan=query_plan,
        )

    # ── Stage 4: Knowledge-layer injection ─────────────────────────────
    enriched = _inject_knowledge(candidates, query_plan)

    # ── Stage 5: FlashRank reranker ────────────────────────────────────
    reranked = _rerank(query, enriched)

    # ── Stage 6: Score-threshold abstention ────────────────────────────
    if reranked and (reranked[0].get("rerank_score", 0) or 0) < 0.4:
        logger.info(
            "Top reranker score %.4f < 0.4 — abstaining",
            reranked[0].get("rerank_score", 0),
        )
        return RetrievalResult(
            chunks=[],
            citations=[],
            abstained=True,
            coverage_warning=False,
            query_plan=query_plan,
        )

    # Keep only the top_k
    final_chunks = reranked[:top_k]

    # ── Stage 7: Citation resolver ─────────────────────────────────────
    citations: list[Citation] = []
    for i, chunk in enumerate(final_chunks):
        citations.append(
            Citation(
                source_index=i + 1,
                page=chunk.get("page_number", 1),
                section=chunk.get("section_title"),
                text=(chunk.get("text", "") or "")[:200],
            )
        )
        # Embed the [Source N] tag into the chunk for downstream prompt
        # assembly (the generation layer will reference these tags).
        chunk["citation_tag"] = f"[Source {i + 1}]"

    # Coverage warning: True when mandatory sections were requested but
    # *none* of the final chunks come from the knowledge layer.
    coverage_warning = bool(
        query_plan.get("mandatory_sections")
        and not any(
            c.get("metadata", {}).get("knowledge_layer")
            for c in final_chunks
        )
    )

    return RetrievalResult(
        chunks=final_chunks,
        citations=citations,
        abstained=False,
        coverage_warning=coverage_warning,
        query_plan=query_plan,
    )
