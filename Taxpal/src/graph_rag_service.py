"""FastAPI query service around a Microsoft GraphRAG index."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


GRAPH_ROOT = Path(os.getenv("GRAPH_RAG_ROOT", "/graph")).resolve()
OUTPUT_DIR = GRAPH_ROOT / "output"
COMMUNITY_LEVEL = int(os.getenv("GRAPH_RAG_COMMUNITY_LEVEL", "2"))
RESPONSE_TYPE = os.getenv("GRAPH_RAG_RESPONSE_TYPE", "Concise answer with supporting facts")

LOCAL_TABLES = ("entities", "communities", "community_reports", "text_units", "relationships")
GLOBAL_TABLES = ("entities", "communities", "community_reports")


class GraphSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    method: Literal["local", "global", "drift"] = "local"
    k: int = Field(default=1, ge=1, le=3)


class GraphIndexUnavailable(RuntimeError):
    """The GraphRAG output has not been built or is incomplete."""


def _required_tables(method: str) -> tuple[str, ...]:
    return GLOBAL_TABLES if method == "global" else LOCAL_TABLES


def _missing_tables(method: str = "local") -> list[str]:
    return [name for name in _required_tables(method) if not (OUTPUT_DIR / f"{name}.parquet").is_file()]


class GraphIndex:
    """Lazily load an immutable GraphRAG index and execute queries against it."""

    def __init__(self, root: Path):
        self.root = root
        self.output = root / "output"
        self._config: Any = None
        self._tables: dict[str, pd.DataFrame | None] = {}
        self._lock = asyncio.Lock()

    async def _load(self, method: str) -> None:
        missing = _missing_tables(method)
        if missing:
            raise GraphIndexUnavailable(
                "GraphRAG index is not ready. Missing: " + ", ".join(missing)
            )

        if self._config is None:
            from graphrag.config.load_config import load_config

            self._config = load_config(self.root)
        for name in _required_tables(method):
            if name not in self._tables:
                self._tables[name] = await asyncio.to_thread(
                    pd.read_parquet, self.output / f"{name}.parquet"
                )
        covariates = self.output / "covariates.parquet"
        if "covariates" not in self._tables:
            self._tables["covariates"] = (
                await asyncio.to_thread(pd.read_parquet, covariates)
                if covariates.is_file()
                else None
            )

    async def search(self, query: str, method: str) -> tuple[str, Any]:
        async with self._lock:
            await self._load(method)
            import graphrag.api as api

            common = {
                "config": self._config,
                "entities": self._tables["entities"],
                "communities": self._tables["communities"],
                "community_reports": self._tables["community_reports"],
                "community_level": COMMUNITY_LEVEL,
                "response_type": RESPONSE_TYPE,
                "query": query,
            }
            if method == "global":
                return await api.global_search(
                    **common,
                    dynamic_community_selection=False,
                )

            local = {
                **common,
                "text_units": self._tables["text_units"],
                "relationships": self._tables["relationships"],
            }
            if method == "drift":
                return await api.drift_search(**local)
            return await api.local_search(
                **local,
                covariates=self._tables["covariates"],
            )


index = GraphIndex(GRAPH_ROOT)
app = FastAPI(title="TaxPal GraphRAG Search API")


@app.get("/health")
def health() -> dict[str, Any]:
    missing = _missing_tables("local")
    return {
        "status": "ok",
        "service": "graph-search",
        "indexed": not missing,
        "root": str(GRAPH_ROOT),
        "missing_tables": missing,
    }


@app.post("/search-graph")
async def search_graph(request: GraphSearchRequest) -> dict[str, Any]:
    try:
        response, context = await index.search(request.query, request.method)
    except GraphIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="GraphRAG query failed.") from exc

    if isinstance(response, str):
        text = response.strip()
    else:
        text = json.dumps(response, ensure_ascii=False)
    if not text:
        return {"query": request.query, "method": request.method, "count": 0, "results": []}

    context_sections = len(context) if isinstance(context, (dict, list)) else 0
    accessed_at = datetime.now(timezone.utc).isoformat()
    result = {
        "text": text,
        "metadata": {
            "title": "TaxPal tax-law knowledge graph",
            "source": "TaxPal GraphRAG index",
            "url": "",
            "section": f"{request.method.title()} graph search",
            "evidence_type": "graph_rag",
            "accessed_at": accessed_at,
            "relevance_score": 0.85,
            "graph_method": request.method,
            "context_sections": context_sections,
        },
    }
    return {"query": request.query, "method": request.method, "count": 1, "results": [result]}
