from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.knowledge_tree import (
    KNOWLEDGE_NODE_TYPE,
    CatalogAsset,
    default_knowledge_nodes,
    ensure_knowledge_tree_seeded,
    fetch_knowledge_tree,
    ingest_custom_knowledge_node,
)


class FakeGraph:
    def __init__(self, node_rows: List[Dict[str, Any]] | None = None) -> None:
        self.node_rows = node_rows or []
        self.ingested: List[Dict[str, str]] = []
        self.queries: List[str] = []

    def query(self, query: str) -> List[Dict[str, Any]]:
        self.queries.append(query)
        if "COUNT(?node)" in query:
            return [{"count": str(len(self.node_rows))}]
        if "swarm:requires" in query:
            return [
                {"node": "http://swarm.os/ontology/knowledge/tdd-level-2", "prereq": "http://swarm.os/ontology/knowledge/tdd-level-1"}
            ]
        if "CommanderProgress" in query:
            return [{"node": "http://swarm.os/ontology/knowledge/tdd-level-1"}]
        if "swarm:KnowledgeNode" in query:
            return self.node_rows
        return []

    def ingest(self, triples: List[Dict[str, str]]) -> None:
        self.ingested.extend(triples)


def test_seed_tree_when_missing() -> None:
    graph = FakeGraph(node_rows=[])

    ensure_knowledge_tree_seeded(graph.query, graph.ingest, catalog_assets=[])

    assert graph.ingested
    assert any(t["object"] == KNOWLEDGE_NODE_TYPE for t in graph.ingested)
    assert any(t["predicate"] == "http://swarm.os/ontology/unlocks" for t in graph.ingested)


def test_fetch_tree_includes_prereqs_and_unlocked_state() -> None:
    graph = FakeGraph(
        node_rows=[
            {
                "node": "http://swarm.os/ontology/knowledge/tdd-level-1",
                "name": "TDD Nivel 1",
                "domain": "Calidad",
                "capability": "Pruebas por feature branch",
                "level": "1",
                "budget": "2.0",
                "hours": "3",
            },
            {
                "node": "http://swarm.os/ontology/knowledge/tdd-level-2",
                "name": "TDD Nivel 2",
                "domain": "Calidad",
                "capability": "Ejecución automática de suites por módulo",
                "level": "2",
                "budget": "3.5",
                "hours": "5",
            },
        ]
    )

    tree = fetch_knowledge_tree(graph.query, graph.ingest, catalog_assets=[])

    assert len(tree) == 2
    tdd_1 = next(node for node in tree if node.id == "tdd-level-1")
    tdd_2 = next(node for node in tree if node.id == "tdd-level-2")

    assert tdd_1.unlocked is True
    assert tdd_2.prerequisites == ["tdd-level-1"]
    assert tdd_2.unlocked is False


def test_default_tree_extends_with_catalog_assets() -> None:
    catalog_assets = [
        CatalogAsset(asset_type="skill", key="skill-creator", label="skill-creator", docs_uri="/opt/codex/skills/.system/skill-creator/SKILL.md"),
        CatalogAsset(asset_type="scenario", key="core", label="core", docs_uri="scenarios/core/docs/readme.md"),
        CatalogAsset(asset_type="namespace", key="default", label="default", docs_uri="namespace://default"),
    ]

    nodes = default_knowledge_nodes(catalog_assets=catalog_assets)
    ids = {node.id for node in nodes}

    assert {"Calidad", "Seguridad", "Performance", "DX", "Orquestación"}.issubset({node.domain for node in nodes})
    assert "skill-skill-creator" in ids
    assert "scenario-core" in ids
    assert "namespace-default" in ids


def test_ingest_custom_knowledge_node_with_docs_and_prerequisites() -> None:
    graph = FakeGraph()

    created = ingest_custom_knowledge_node(
        ingest_triples=graph.ingest,
        node_id="scenario-custom-hardening",
        domain="Seguridad",
        name="Custom Security Scenario",
        capability="Ejecución de escenario de hardening desde juego",
        level=2,
        budget_cost=4.0,
        time_cost_hours=6,
        prerequisites=["threat-modeling"],
        docs_text="# hardening docs",
        source_type="scenario",
        source_ref="scenarios/custom/README.md",
    )

    assert created.id == "scenario-custom-hardening"
    assert any(t["predicate"].endswith("requires") for t in graph.ingested)
    assert any(t["predicate"].endswith("documentation") and "hardening docs" in t["object"] for t in graph.ingested)


def test_discover_catalog_assets_from_repo_layout(tmp_path: Path) -> None:
    (tmp_path / "scenarios" / "core").mkdir(parents=True)
    (tmp_path / "scenarios" / "core" / "manifest.json").write_text('{"name": "core"}', encoding="utf-8")
    (tmp_path / "SKILL.md").write_text("# root skill", encoding="utf-8")

    from lib.knowledge_tree import discover_catalog_assets

    assets = discover_catalog_assets(tmp_path)
    keys = {(asset.asset_type, asset.key) for asset in assets}

    assert ("scenario", "core") in keys
    assert ("skill", "root") in keys
    assert ("namespace", "default") in keys
