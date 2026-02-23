from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Literal

from lib.contracts import KnowledgeNode, KnowledgeNodeCost

SWARM = "http://swarm.os/ontology/"
KNOWLEDGE_NODE_TYPE = f"{SWARM}KnowledgeNode"
COMMANDER_PROGRESS_URI = f"{SWARM}CommanderProgress"

DOMAIN_BY_ID: Dict[str, str] = {
    "quality": "Calidad",
    "security": "Seguridad",
    "performance": "Performance",
    "dx": "DX",
    "orchestration": "Orquestación",
}

AssetType = Literal["skill", "scenario", "namespace"]


@dataclass(frozen=True)
class CatalogAsset:
    asset_type: AssetType
    key: str
    label: str
    docs_uri: str


@dataclass(frozen=True)
class KnowledgeNodeSeed:
    node_id: str
    domain_id: str
    name: str
    capability: str
    level: int
    budget_cost: float
    time_cost_hours: int
    prerequisites: List[str]
    source_type: str = "seed"
    source_ref: str = "seed://default"
    documentation: str = ""


def discover_catalog_assets(repo_root: Path) -> List[CatalogAsset]:
    assets: List[CatalogAsset] = []

    root_skill = repo_root / "SKILL.md"
    if root_skill.exists():
        assets.append(CatalogAsset(asset_type="skill", key="root", label="root", docs_uri=str(root_skill)))

    system_skills = Path("/opt/codex/skills/.system")
    if system_skills.exists():
        for skill_md in sorted(system_skills.glob("*/SKILL.md")):
            key = skill_md.parent.name
            assets.append(CatalogAsset(asset_type="skill", key=key, label=key, docs_uri=str(skill_md)))

    scenarios_dir = repo_root / "scenarios"
    if scenarios_dir.exists():
        for manifest in sorted(scenarios_dir.glob("*/manifest.json")):
            scenario_id = manifest.parent.name
            docs = manifest.parent / "docs" / "readme.md"
            assets.append(
                CatalogAsset(
                    asset_type="scenario",
                    key=scenario_id,
                    label=scenario_id,
                    docs_uri=str(docs if docs.exists() else manifest),
                )
            )

    namespaces = {"default", *[a.key for a in assets if a.asset_type == "scenario"]}
    for namespace in sorted(namespaces):
        assets.append(
            CatalogAsset(
                asset_type="namespace",
                key=namespace,
                label=namespace,
                docs_uri=f"namespace://{namespace}",
            )
        )

    return assets


def default_knowledge_nodes(catalog_assets: Iterable[CatalogAsset] | None = None) -> List[KnowledgeNode]:
    base_nodes = [
        KnowledgeNodeSeed("tdd-level-1", "quality", "TDD Nivel 1", "Pruebas por feature branch", 1, 2.0, 3, []),
        KnowledgeNodeSeed("tdd-level-2", "quality", "TDD Nivel 2", "Ejecución automática de suites por módulo", 2, 3.5, 5, ["tdd-level-1"]),
        KnowledgeNodeSeed("threat-modeling", "security", "Threat Modeling", "Checklist STRIDE pre-merge", 1, 2.5, 4, []),
        KnowledgeNodeSeed("sast-pipeline", "security", "SAST Pipeline", "Escaneo SAST obligatorio por PR", 2, 4.0, 6, ["threat-modeling"]),
        KnowledgeNodeSeed("profiling-base", "performance", "Profiling Base", "Baseline de latencia por módulo", 1, 2.0, 3, []),
        KnowledgeNodeSeed("performance-gates", "performance", "Performance Gates", "Gates p95/p99 en CI", 2, 4.5, 6, ["profiling-base"]),
        KnowledgeNodeSeed("devx-templates", "dx", "DX Templates", "Plantillas listas para historias y PRs", 1, 1.5, 2, []),
        KnowledgeNodeSeed("context-recipes", "dx", "Context Recipes", "Inyección contextual por tipo de tarea", 2, 3.0, 4, ["devx-templates"]),
        KnowledgeNodeSeed("workflow-mapping", "orchestration", "Workflow Mapping", "Mapa agente->dominio->objetivo", 1, 2.0, 3, []),
        KnowledgeNodeSeed("autonomous-orchestration", "orchestration", "Orquestación Autónoma", "Rebalanceo automático por budget/tiempo", 2, 5.0, 8, ["workflow-mapping"]),
    ]

    asset_nodes: List[KnowledgeNodeSeed] = []
    for asset in catalog_assets or []:
        node_id = f"{asset.asset_type}-{asset.key}"
        domain_id = "dx" if asset.asset_type == "skill" else "orchestration"
        capability = {
            "skill": f"Uso de skill '{asset.label}' en orquestación",
            "scenario": f"Ejecución del scenario '{asset.label}' desde juego",
            "namespace": f"Consultas/ingesta sobre namespace '{asset.label}'",
        }[asset.asset_type]
        asset_nodes.append(
            KnowledgeNodeSeed(
                node_id=node_id,
                domain_id=domain_id,
                name=f"{asset.asset_type.title()}: {asset.label}",
                capability=capability,
                level=1,
                budget_cost=1.0,
                time_cost_hours=1,
                prerequisites=[],
                source_type=asset.asset_type,
                source_ref=asset.docs_uri,
                documentation=asset.docs_uri,
            )
        )

    seeds = [*base_nodes, *asset_nodes]
    return [
        KnowledgeNode(
            id=node.node_id,
            domain=DOMAIN_BY_ID[node.domain_id],
            name=node.name,
            capability=node.capability,
            level=node.level,
            prerequisites=node.prerequisites,
            cost=KnowledgeNodeCost(budget=node.budget_cost, time_hours=node.time_cost_hours),
            unlocked=node.level == 1,
            source_type=node.source_type,
            source_ref=node.source_ref,
            documentation=node.documentation,
        )
        for node in seeds
    ]


def ensure_knowledge_tree_seeded(
    query_graph: Callable[[str], List[Dict[str, str]]],
    ingest_triples: Callable[[List[Dict[str, str]]], None],
    catalog_assets: Iterable[CatalogAsset] | None = None,
) -> None:
    count_query = f"""
    PREFIX swarm: <{SWARM}>
    SELECT (COUNT(?node) AS ?count)
    WHERE {{
        ?node a swarm:KnowledgeNode .
    }}
    """
    count_rows = query_graph(count_query)
    raw_count = (count_rows[0].get("count") if count_rows else "0") or "0"
    if int(float(str(raw_count))) > 0:
        return

    triples: List[Dict[str, str]] = []
    for node in default_knowledge_nodes(catalog_assets=catalog_assets):
        triples.extend(_node_to_triples(node))

    ingest_triples(triples)


def fetch_knowledge_tree(
    query_graph: Callable[[str], List[Dict[str, str]]],
    ingest_triples: Callable[[List[Dict[str, str]]], None],
    catalog_assets: Iterable[CatalogAsset] | None = None,
) -> List[KnowledgeNode]:
    ensure_knowledge_tree_seeded(query_graph, ingest_triples, catalog_assets=catalog_assets)

    nodes_query = f"""
    PREFIX swarm: <{SWARM}>
    SELECT ?node ?name ?domain ?capability ?level ?budget ?hours ?sourceType ?sourceRef ?documentation
    WHERE {{
      ?node a swarm:KnowledgeNode ;
            swarm:name ?name ;
            swarm:domain ?domain ;
            swarm:capabilityUnlock ?capability ;
            swarm:level ?level ;
            swarm:budgetCost ?budget ;
            swarm:timeCostHours ?hours .
      OPTIONAL {{ ?node swarm:sourceType ?sourceType . }}
      OPTIONAL {{ ?node swarm:sourceRef ?sourceRef . }}
      OPTIONAL {{ ?node swarm:documentation ?documentation . }}
    }}
    """
    prerequisite_query = f"""
    PREFIX swarm: <{SWARM}>
    SELECT ?node ?prereq
    WHERE {{
      ?node a swarm:KnowledgeNode ;
            swarm:requires ?prereq .
    }}
    """
    unlocked_query = f"""
    PREFIX swarm: <{SWARM}>
    SELECT ?node
    WHERE {{
      <{COMMANDER_PROGRESS_URI}> swarm:unlocks ?node .
    }}
    """

    node_rows = query_graph(nodes_query)
    prerequisite_rows = query_graph(prerequisite_query)
    unlocked_rows = query_graph(unlocked_query)

    prereq_by_node: Dict[str, List[str]] = {}
    for row in prerequisite_rows:
        node_key = _compact_node_id(row.get("node", ""))
        prereq_key = _compact_node_id(row.get("prereq", ""))
        if not node_key or not prereq_key:
            continue
        prereq_by_node.setdefault(node_key, []).append(prereq_key)

    unlocked_node_ids = {
        _compact_node_id(row.get("node", "")) for row in unlocked_rows if _compact_node_id(row.get("node", ""))
    }

    knowledge_nodes: List[KnowledgeNode] = []
    for row in node_rows:
        node_id = _compact_node_id(row.get("node", ""))
        if not node_id:
            continue
        knowledge_nodes.append(
            KnowledgeNode(
                id=node_id,
                domain=str(row.get("domain", "")),
                name=str(row.get("name", node_id)),
                capability=str(row.get("capability", "")),
                level=int(float(str(row.get("level", "0")))),
                prerequisites=sorted(prereq_by_node.get(node_id, [])),
                cost=KnowledgeNodeCost(
                    budget=float(str(row.get("budget", "0"))),
                    time_hours=int(float(str(row.get("hours", "0")))),
                ),
                unlocked=node_id in unlocked_node_ids,
                source_type=str(row.get("sourceType", "") or "seed"),
                source_ref=str(row.get("sourceRef", "") or "seed://default"),
                documentation=str(row.get("documentation", "") or ""),
            )
        )

    return sorted(knowledge_nodes, key=lambda item: (item.domain, item.level, item.name))


def ingest_custom_knowledge_node(
    ingest_triples: Callable[[List[Dict[str, str]]], None],
    node_id: str,
    domain: str,
    name: str,
    capability: str,
    level: int,
    budget_cost: float,
    time_cost_hours: int,
    prerequisites: List[str],
    docs_text: str,
    source_type: str,
    source_ref: str,
) -> KnowledgeNode:
    node = KnowledgeNode(
        id=node_id,
        domain=domain,
        name=name,
        capability=capability,
        level=level,
        prerequisites=prerequisites,
        cost=KnowledgeNodeCost(budget=budget_cost, time_hours=time_cost_hours),
        unlocked=level == 1,
        source_type=source_type,
        source_ref=source_ref,
        documentation=docs_text,
    )
    ingest_triples(_node_to_triples(node))
    return node


def _node_to_triples(node: KnowledgeNode) -> List[Dict[str, str]]:
    node_uri = f"{SWARM}knowledge/{node.id}"
    triples: List[Dict[str, str]] = [
        {"subject": node_uri, "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "object": KNOWLEDGE_NODE_TYPE},
        {"subject": node_uri, "predicate": f"{SWARM}name", "object": f'"{node.name}"'},
        {"subject": node_uri, "predicate": f"{SWARM}domain", "object": f'"{node.domain}"'},
        {"subject": node_uri, "predicate": f"{SWARM}capabilityUnlock", "object": f'"{node.capability}"'},
        {"subject": node_uri, "predicate": f"{SWARM}level", "object": f'"{node.level}"'},
        {"subject": node_uri, "predicate": f"{SWARM}budgetCost", "object": f'"{node.cost.budget}"'},
        {"subject": node_uri, "predicate": f"{SWARM}timeCostHours", "object": f'"{node.cost.time_hours}"'},
        {"subject": node_uri, "predicate": f"{SWARM}sourceType", "object": f'"{node.source_type}"'},
        {"subject": node_uri, "predicate": f"{SWARM}sourceRef", "object": f'"{node.source_ref}"'},
    ]
    if node.documentation:
        triples.append(
            {"subject": node_uri, "predicate": f"{SWARM}documentation", "object": f'"{node.documentation}"'}
        )
    for prereq_id in node.prerequisites:
        triples.append(
            {
                "subject": node_uri,
                "predicate": f"{SWARM}requires",
                "object": f"{SWARM}knowledge/{prereq_id}",
            }
        )
    if node.unlocked:
        triples.append(
            {
                "subject": COMMANDER_PROGRESS_URI,
                "predicate": f"{SWARM}unlocks",
                "object": node_uri,
            }
        )
    return triples


def _compact_node_id(uri_or_id: str) -> str:
    raw = str(uri_or_id).strip('<>"')
    if "/knowledge/" in raw:
        return raw.split("/knowledge/")[-1]
    if raw.startswith(SWARM):
        return raw.replace(SWARM, "")
    return raw
