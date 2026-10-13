#!/usr/bin/env python3
"""Answer natural-language questions about the job market using the RAG store.

Embeds the question (gemini-embedding-001, 768 dims, RETRIEVAL_QUERY), retrieves
the top-K chunks from rag/.chroma, and asks gemini-3.5-flash to answer from that
context. Exposes answer_question() for the chat API layer.

Usage:
    uv run python rag/query.py "Which companies are hiring for fraud ML?"
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag import _rpm_wait, embed_texts, get_chroma_collection, get_gemini_client

TOP_K = 12

EMPTY_STORE_MESSAGE = "No job data indexed yet. Run the pipeline first."

_PROMPT_TEMPLATE = """You are a job-market analyst for an Israeli tech job-search pipeline. Answer the user's question using ONLY the context documents below - job postings and company records retrieved from the pipeline's datasets.

Rules:
- Ground every claim in the context documents. Do not invent companies, roles, or numbers.
- If the context does not contain enough information to answer, say so plainly.
- Reference companies and job titles by name so the user can trace the answer to its sources.
- Be concise and factual. Use hyphens, not em-dashes.
{history_block}
<context>
{context}
</context>

Question: {question}

Answer:"""


def _format_history(history) -> str:
    """Render prior chat turns (list of {role, content} dicts) into the prompt."""
    if not history:
        return ""
    lines = []
    for turn in history:
        if isinstance(turn, dict):
            role = str(turn.get("role", "user")).strip().lower()
            content = str(turn.get("content", "")).strip()
        else:
            role, content = "user", str(turn).strip()
        if not content:
            continue
        label = "Assistant" if role in ("assistant", "model") else "User"
        lines.append(f"{label}: {content}")
    if not lines:
        return ""
    return "\nPrior conversation (for context only):\n" + "\n".join(lines) + "\n"


def answer_question(question: str, history=None) -> dict:
    """Answer a question against the vector store. Returns {"answer", "sources"}.

    Never raises for an empty/absent store - returns a friendly message instead.
    """
    try:
        collection = get_chroma_collection()
        count = collection.count()
    except Exception:
        count = 0
    if count == 0:
        return {"answer": EMPTY_STORE_MESSAGE, "sources": []}

    client = get_gemini_client()
    query_vec = embed_texts(client, [question], "RETRIEVAL_QUERY")[0]
    result = collection.query(
        query_embeddings=[query_vec],
        n_results=min(TOP_K, count),
        include=["documents", "metadatas"],
    )
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]

    context = "\n\n".join(f"[{i + 1}] {doc}" for i, doc in enumerate(documents))
    prompt = _PROMPT_TEMPLATE.format(
        history_block=_format_history(history),
        context=context,
        question=question,
    )

    _rpm_wait()
    resp = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
    answer = (resp.text or "").strip()

    # Deduped source citations: company + job title (company records cite the profile).
    sources = []
    seen = set()
    for meta in metadatas:
        company = meta.get("company", "")
        if meta.get("type") == "company":
            title = "(company profile)"
        else:
            title = meta.get("title", "")
        key = (company, title)
        if key in seen:
            continue
        seen.add(key)
        sources.append({"company": company, "title": title})

    return {"answer": answer, "sources": sources}


def main():
    if len(sys.argv) < 2:
        print('Usage: uv run python rag/query.py "<question>"', file=sys.stderr)
        sys.exit(1)
    question = " ".join(sys.argv[1:])
    result = answer_question(question)
    print(result["answer"])
    if result["sources"]:
        print("\nSources:")
        for src in result["sources"]:
            title = src["title"] or "(untitled)"
            print(f"  - {src['company']} - {title}")


if __name__ == "__main__":
    main()
