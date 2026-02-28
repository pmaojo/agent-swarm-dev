use axum::{
    extract::{ws::{Message, WebSocket, WebSocketUpgrade}, Path, State},
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use chrono::Utc;
use tracing::info;

use crate::server::contracts::{
    AuditRecord, CommandPhase, ControlCommand, ControlCommandAck, CountryState,
    DailyBudget, EventAck, GatewayEvent, GameState, GraphData, GraphEdge, GraphEdgeData,
    GraphElements, GraphNode, GraphNodeData, GraphTriple, IngestKnowledgeNodeResponse,
    KnowledgeNode, KnowledgeNodeCost, KnowledgeNodeDocumentationResponse, KnowledgeNodeIngestRequest,
    MissionAssignment, PartyMember, PartyStats, PolicyApprovalStatus, RepositoryState,
    ServiceHealth, ServiceState, SystemStatus,
};
use crate::server::AppState;

pub async fn get_game_state(State(state): State<AppState>) -> Json<GameState> {
    info!("Fetching Game State from Synapse...");

    let status_query = r#"
        PREFIX nist: <http://nist.gov/caisi/>
        SELECT ?status WHERE { <http://nist.gov/caisi/SystemControl> nist:operationalStatus ?status }
    "#;

    let mut current_status = SystemStatus::Operational;
    if let Ok(res_json) = state.synapse.query(status_query).await {
        if let Ok(parsed) = serde_json::from_str::<Vec<serde_json::Value>>(&res_json) {
            if let Some(last) = parsed.last() {
                if let Some(s) = last.get("status").or_else(|| last.get("?status")) {
                    current_status = parse_system_status(s.as_str().unwrap_or("UNKNOWN"));
                }
            }
        }
    }

    let today = Utc::now().format("%Y-%m-%d").to_string();
    let spend_query = format!(
        r#"
        PREFIX swarm: <http://swarm.os/ontology/>
        SELECT (SUM(?amount) as ?total)
        WHERE {{
            ?event a swarm:SpendEvent .
            ?event swarm:date "{}" .
            ?event swarm:amount ?amount .
        }}
    "#,
        today
    );

    let mut spend = 0.0;
    if let Ok(res_json) = state.synapse.query(&spend_query).await {
        if let Ok(parsed) = serde_json::from_str::<Vec<serde_json::Value>>(&res_json) {
            if let Some(first) = parsed.first() {
                if let Some(t) = first.get("total").or_else(|| first.get("?total")) {
                    let cleaned = _clean_numeric(t.as_str().unwrap_or("0"));
                    spend = cleaned.parse().unwrap_or(0.0);
                }
            }
        }
    }

    // Load Character Profiles
    let char_path = std::path::Path::new("sdk/python/data/character_profiles.json");
    let char_content = std::fs::read_to_string(char_path).unwrap_or_else(|_| "{}".to_string());
    let char_doc: crate::server::contracts::CharacterProfileDocument = serde_json::from_str(&char_content).unwrap_or_else(|_| crate::server::contracts::CharacterProfileDocument {
        selected_character_id: None,
        selected_character_loadout: crate::server::contracts::CharacterLoadoutSelection::default(),
        profiles: vec![],
    });

    let party: Vec<PartyMember> = char_doc.profiles.iter().map(|p| PartyMember {
        id: p.id.clone(),
        name: p.display_name.clone(),
        class_name: p.class_name.clone(),
        level: p.level,
        stats: PartyStats {
            hp: p.loadout.hit_points,
            mana: p.loadout.mana,
            success_rate: format!("{:.0}%", p.base_success_rate * 100.0),
        },
        current_action: p.current_action.clone(),
        location: p.location.clone(),
    }).collect();

    // Load Fog Map
    let fog_path = std::path::Path::new("sdk/python/data/fog_state.json");
    let fog_map = if let Ok(content) = std::fs::read_to_string(fog_path) {
        serde_json::from_str(&content).unwrap_or(serde_json::json!({}))
    } else {
        serde_json::json!({})
    };

    // Load Repositories from JSON file
    let repo_path = std::path::Path::new("sdk/python/data/repositories.json");
    let repositories: Vec<RepositoryState> = if let Ok(content) = std::fs::read_to_string(repo_path) {
        if let Ok(repo_doc) = serde_json::from_str::<serde_json::Value>(&content) {
            repo_doc.get("repositories")
                .and_then(|r| r.as_array())
                .map(|arr| {
                    arr.iter().filter_map(|r| {
                        Some(RepositoryState {
                            id: r.get("id")?.as_str()?.to_string(),
                            name: r.get("name")?.as_str()?.to_string(),
                            swarm: r.get("swarm")
                                .and_then(|s| s.as_array())
                                .map(|a| a.iter().filter_map(|v| v.as_str().map(String::from)).collect())
                                .unwrap_or_default(),
                        })
                    }).collect()
                })
                .unwrap_or_default()
        } else {
            vec![]
        }
    } else {
        vec![]
    };

    Json(GameState {
        system_status: current_status.clone(),
        selected_character_id: char_doc.selected_character_id,
        selected_character_loadout: char_doc.selected_character_loadout,
        daily_budget: DailyBudget {
            max: 10.0,
            spent: spend,
            unit: "USD".to_string(),
        },
        party,
        active_quests: vec![],
        fog_map,
        repositories,
        countries: build_countries(&current_status),
        knowledge_tree: build_knowledge_tree(),
        sovereign_controls: PolicyApprovalStatus {
            approved: true,
            approved_by: Some("security-council".to_string()),
            policy_id: "NIST-800-53-REV5".to_string(),
        },
    })
}

pub async fn get_graph_nodes(State(state): State<AppState>) -> Json<GraphData> {
    // 1. Fetch all triples from Synapse
    let query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 500";
    let mut elements = GraphElements::default();
    
    if let Ok(res_json) = state.synapse.query(query).await {
        if let Ok(parsed) = serde_json::from_str::<Vec<serde_json::Value>>(&res_json) {
            let mut node_map = std::collections::HashMap::new();
            
            for row in parsed {
                let s = _clean_val(row.get("s").or_else(|| row.get("?s")));
                let p = _clean_val(row.get("p").or_else(|| row.get("?p")));
                let o = _clean_val(row.get("o").or_else(|| row.get("?o")));
                
                if s.is_empty() { continue; }

                // Group by subject to form nodes
                let node_data = node_map.entry(s.clone()).or_insert_with(|| GraphNodeData {
                    id: s.clone(),
                    label: s.split('/').last().unwrap_or(&s).to_string(),
                    node_type: "Entity".to_string(),
                    active: false,
                    triples: vec![],
                });
                
                node_data.triples.push(GraphTriple {
                    subject: s.clone(),
                    predicate: p.clone(),
                    object: o.clone(),
                });

                // If object looks like a URI, create an edge
                if o.starts_with("http") {
                    elements.edges.push(GraphEdge {
                        data: GraphEdgeData {
                            id: format!("{}-{}", s, o),
                            source: s.clone(),
                            target: o.clone(),
                            label: p.split('/').last().unwrap_or(&p).to_string(),
                        }
                    });
                }
            }

            for (_, data) in node_map {
                elements.nodes.push(GraphNode { data });
            }
        }
    }

    Json(GraphData { elements })
}

fn _clean_val(val: Option<&serde_json::Value>) -> String {
    match val {
        Some(serde_json::Value::String(s)) => s.trim_matches(|c| c == '"' || c == '<' || c == '>').to_string(),
        _ => String::new(),
    }
}

pub async fn get_audit_log(State(state): State<AppState>) -> Json<Vec<AuditRecord>> {
    let audit = state.audit_log.lock().await;
    Json(audit.clone())
}

pub async fn post_control_command(
    State(state): State<AppState>,
    Json(command): Json<ControlCommand>,
) -> Json<ControlCommandAck> {
    let tracking_id = uuid::Uuid::new_v4().to_string();
    let sent_time = Utc::now().to_rfc3339();
    append_audit(
        &state,
        AuditRecord {
            tracking_id: tracking_id.clone(),
            actor: command.actor.clone(),
            command: command.command.clone(),
            phase: CommandPhase::Sent,
            timestamp: sent_time,
            policy_id: command.nist_policy_id.clone(),
            approved_by: command.approved_by.clone(),
            details: "Action submitted by sovereign panel".to_string(),
        },
    )
    .await;

    if let Some(reason) = evaluate_guardrails(&command) {
        let rejected_time = Utc::now().to_rfc3339();
        append_audit(
            &state,
            AuditRecord {
                tracking_id: tracking_id.clone(),
                actor: command.actor.clone(),
                command: command.command.clone(),
                phase: CommandPhase::Rejected,
                timestamp: rejected_time,
                policy_id: command.nist_policy_id.clone(),
                approved_by: command.approved_by.clone(),
                details: reason.clone(),
            },
        )
        .await;

        return Json(ControlCommandAck {
            tracking_id,
            status: CommandPhase::Rejected,
            reason: Some(reason),
            final_state: Some("REJECTED".to_string()),
            command,
        });
    }

    let accepted_time = Utc::now().to_rfc3339();
    append_audit(
        &state,
        AuditRecord {
            tracking_id: tracking_id.clone(),
            actor: command.actor.clone(),
            command: command.command.clone(),
            phase: CommandPhase::Accepted,
            timestamp: accepted_time,
            policy_id: command.nist_policy_id.clone(),
            approved_by: command.approved_by.clone(),
            details: "NIST guardrails passed and authorization validated".to_string(),
        },
    )
    .await;

    let final_state = execute_command(&command);
    let completed_time = Utc::now().to_rfc3339();
    append_audit(
        &state,
        AuditRecord {
            tracking_id: tracking_id.clone(),
            actor: command.actor.clone(),
            command: command.command.clone(),
            phase: CommandPhase::Completed,
            timestamp: completed_time,
            policy_id: command.nist_policy_id.clone(),
            approved_by: command.approved_by.clone(),
            details: format!("Execution finished with state {final_state}"),
        },
    )
    .await;

    Json(ControlCommandAck {
        tracking_id,
        status: CommandPhase::Completed,
        reason: None,
        final_state: Some(final_state),
        command,
    })
}

pub async fn post_event(
    State(state): State<AppState>,
    Json(event): Json<GatewayEvent>,
) -> Json<EventAck> {
    let _ = state.event_tx.send(event.clone());

    Json(EventAck {
        status: "broadcasted".to_string(),
        event,
    })
}

pub async fn post_mission_assign(
    State(state): State<AppState>,
    Json(mission): Json<MissionAssignment>,
) -> Json<ControlCommandAck> {
    let task_id = uuid::Uuid::new_v4().to_string();
    let task_uri = format!("http://swarm.os/tasks/{}", task_id);
    let agent_uri = if mission.agent_id.is_empty() {
        "http://swarm.os/agents/Coder".to_string()
    } else {
        mission.agent_id.clone()
    };

    let title_lit = format!("\"{}\"", mission.task);
    let agent_ref = format!("<{}>", agent_uri);

    let triples = vec![
        (task_uri.as_str(), "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "http://swarm.os/ontology/Task"),
        (task_uri.as_str(), "http://swarm.os/ontology/title", title_lit.as_str()),
        (task_uri.as_str(), "http://swarm.os/ontology/internalState", "\"REQUIREMENTS\""),
        (task_uri.as_str(), "http://swarm.os/ontology/assignedTo", agent_ref.as_str()),
    ];

    let _ = state.synapse.ingest(triples).await;

    let command = ControlCommand {
        command: crate::server::contracts::ControlCommandType::AssignMission,
        actor: "swarmd".to_string(),
        agent_id: Some(mission.agent_id),
        repo_id: Some(mission.repo_id),
        task: Some(mission.task),
        mission_id: None,
        priority: None,
        deployment_target: None,
        rollback_to: None,
        llm_profile: None,
        nist_policy_id: "NIST-800-53-REV5".to_string(),
        approved_by: Some("swarmd".to_string()),
        metadata: std::collections::HashMap::new(),
    };

    let tracking_id = uuid::Uuid::new_v4().to_string();
    let final_state = execute_command(&command);
    append_audit(
        &state,
        AuditRecord {
            tracking_id: tracking_id.clone(),
            actor: command.actor.clone(),
            command: command.command.clone(),
            phase: CommandPhase::Completed,
            timestamp: Utc::now().to_rfc3339(),
            policy_id: command.nist_policy_id.clone(),
            approved_by: command.approved_by.clone(),
            details: "Mission assigned through sovereign gateway".to_string(),
        },
    )
    .await;

    Json(ControlCommandAck {
        tracking_id,
        status: CommandPhase::Completed,
        reason: None,
        final_state: Some(final_state),
        command,
    })
}

pub async fn post_knowledge_tree_node(
    State(state): State<AppState>,
    Json(payload): Json<KnowledgeNodeIngestRequest>,
) -> Json<IngestKnowledgeNodeResponse> {
    let node = map_ingest_request_to_node(&payload);
    let triples = knowledge_node_to_triples(&node, &payload);
    let triples_refs: Vec<(&str, &str, &str)> = triples.iter().map(|(s, p, o)| (s.as_str(), p.as_str(), o.as_str())).collect();
    let _ = state.synapse.ingest(triples_refs).await;

    Json(IngestKnowledgeNodeResponse {
        status: "ingested".to_string(),
        node,
    })
}

pub async fn get_characters() -> Json<serde_json::Value> {
    let path = std::path::Path::new("sdk/python/data/character_profiles.json");
    let content = std::fs::read_to_string(path).unwrap_or_else(|_| "{}".to_string());
    let val: serde_json::Value = serde_json::from_str(&content).unwrap_or(serde_json::json!({}));
    Json(val)
}

#[derive(Debug, Deserialize)]
pub struct CharacterSelectionRequest {
    pub character_id: String,
}

pub async fn select_character(
    Json(payload): Json<CharacterSelectionRequest>,
) -> impl IntoResponse {
    let path = std::path::Path::new("sdk/python/data/character_profiles.json");
    let content = std::fs::read_to_string(path).unwrap_or_else(|_| "{}".to_string());
    let mut doc: crate::server::contracts::CharacterProfileDocument = 
        serde_json::from_str(&content).unwrap_or_else(|_| crate::server::contracts::CharacterProfileDocument {
            selected_character_id: None,
            selected_character_loadout: crate::server::contracts::CharacterLoadoutSelection::default(),
            profiles: vec![],
        });

    doc.selected_character_id = Some(payload.character_id.clone());
    
    if let Ok(updated) = serde_json::to_string_pretty(&doc) {
        let _ = std::fs::write(path, updated);
    }

    Json(serde_json::json!({ "selected_character_id": payload.character_id }))
}

#[derive(Debug, Deserialize)]
pub struct CharacterLoadoutSaveRequest {
    pub character_id: String,
    pub loadout: crate::server::contracts::CharacterLoadoutSelection,
}

pub async fn save_character_loadout(
    Json(payload): Json<CharacterLoadoutSaveRequest>,
) -> impl IntoResponse {
    let path = std::path::Path::new("sdk/python/data/character_profiles.json");
    let content = std::fs::read_to_string(path).unwrap_or_else(|_| "{}".to_string());
    let mut doc: crate::server::contracts::CharacterProfileDocument = 
        serde_json::from_str(&content).unwrap_or_else(|_| crate::server::contracts::CharacterProfileDocument {
            selected_character_id: None,
            selected_character_loadout: crate::server::contracts::CharacterLoadoutSelection::default(),
            profiles: vec![],
        });

    doc.selected_character_id = Some(payload.character_id.clone());
    doc.selected_character_loadout = payload.loadout.clone();
    
    if let Ok(updated) = serde_json::to_string_pretty(&doc) {
        let _ = std::fs::write(path, updated);
    }

    Json(serde_json::json!({
        "selected_character_id": payload.character_id,
        "selected_character_loadout": payload.loadout
    }))
}

pub async fn get_knowledge_node_documentation(
    State(state): State<AppState>,
    Path(node_id): Path<String>,
) -> Json<KnowledgeNodeDocumentationResponse> {
    let query = format!(
        r#"
        PREFIX swarm: <http://swarm.os/ontology/>
        SELECT ?docs WHERE {{
            <http://swarm.os/ontology/knowledge/{node_id}> swarm:documentation ?docs .
        }} LIMIT 1
        "#
    );

    let mut documentation = state
        .synapse
        .query(&query)
        .await
        .ok()
        .and_then(|json| serde_json::from_str::<Vec<serde_json::Value>>(&json).ok())
        .and_then(|rows| rows.first().cloned())
        .and_then(|row| row.get("docs").or_else(|| row.get("?docs")).cloned())
        .and_then(|value| value.as_str().map(ToString::to_string))
        .unwrap_or_default();

    // Fallback to local build_knowledge_tree if empty
    if documentation.is_empty() {
        if let Some(node) = build_knowledge_tree().into_iter().find(|n| n.id == node_id) {
            documentation = node.documentation;
        }
    }

    Json(KnowledgeNodeDocumentationResponse {
        node_id,
        documentation,
    })
}

pub async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
) -> impl IntoResponse {
    ws.on_upgrade(|socket| handle_socket(socket, state))
}

async fn handle_socket(mut socket: WebSocket, state: AppState) {
    let mut rx = state.event_tx.subscribe();

    while let Ok(event) = rx.recv().await {
        // Wrap in the same envelope format as Python gateway
        let envelope = serde_json::json!({
            "type": event.r#type,
            "payload": event
        });
        
        if let Ok(msg) = serde_json::to_string(&envelope) {
            if socket.send(Message::Text(msg.into())).await.is_err() {
                break;
            }
        }
    }
}

fn _clean_numeric(val: &str) -> String {
    if let Some(pos) = val.find("^^") {
        val[..pos].trim_matches('"').to_string()
    } else {
        val.trim_matches('"').to_string()
    }
}

fn execute_command(command: &ControlCommand) -> String {
    format!("{:?}_EXECUTED", command.command)
}

async fn append_audit(state: &AppState, event: AuditRecord) {
    let mut audit = state.audit_log.lock().await;
    audit.push(event);
}

fn evaluate_guardrails(command: &ControlCommand) -> Option<String> {
    if command.nist_policy_id.trim().is_empty() {
        return Some("NIST policy is required".to_string());
    }

    if command.approved_by.as_ref().map(|s| s.trim().is_empty()).unwrap_or(true) {
        return Some("Authorization approval is required before executing control commands".to_string());
    }

    if matches!(
        command.command,
        crate::server::contracts::ControlCommandType::Deploy
            | crate::server::contracts::ControlCommandType::Rollback
            | crate::server::contracts::ControlCommandType::Halt
            | crate::server::contracts::ControlCommandType::Resume
    ) && command.actor != "sovereign-operator"
    {
        return Some("Actor lacks sovereign permission for critical command".to_string());
    }

    None
}

fn parse_system_status(raw: &str) -> SystemStatus {
    match raw.to_uppercase().as_str() {
        "OPERATIONAL" => SystemStatus::Operational,
        "DEGRADED" => SystemStatus::Degraded,
        "OUTAGE" => SystemStatus::Outage,
        "HALTED" => SystemStatus::Halted,
        _ => SystemStatus::Unknown,
    }
}

fn build_countries(status: &SystemStatus) -> Vec<CountryState> {
    let health = match status {
        SystemStatus::Operational => ServiceHealth::Healthy,
        SystemStatus::Degraded => ServiceHealth::Degraded,
        SystemStatus::Halted => ServiceHealth::Halted,
        _ => ServiceHealth::Healthy,
    };

    vec![
        CountryState {
            id: "country-core".to_string(),
            name: "The Core Empire".to_string(),
            services: vec![
                ServiceState {
                    id: "service-orchestrator".to_string(),
                    name: "orchestrator".to_string(),
                    health: health.clone(),
                    hp: 100,
                    latency_ms: 60.0,
                    error_rate: 0.01,
                },
                ServiceState {
                    id: "service-gateway".to_string(),
                    name: "gateway".to_string(),
                    health: health.clone(),
                    hp: 100,
                    latency_ms: 45.0,
                    error_rate: 0.005,
                },
            ],
        },
        CountryState {
            id: "country-frontend".to_string(),
            name: "The Front-End Republic".to_string(),
            services: vec![
                ServiceState {
                    id: "service-visualizer".to_string(),
                    name: "visualizer".to_string(),
                    health: health.clone(),
                    hp: 100,
                    latency_ms: 30.0,
                    error_rate: 0.001,
                },
                ServiceState {
                    id: "service-web".to_string(),
                    name: "web".to_string(),
                    health: health.clone(),
                    hp: 100,
                    latency_ms: 120.0,
                    error_rate: 0.02,
                },
            ],
        },
        CountryState {
            id: "country-security".to_string(),
            name: "The Security Kingdom".to_string(),
            services: vec![
                ServiceState {
                    id: "service-guardian".to_string(),
                    name: "guardian".to_string(),
                    health: health.clone(),
                    hp: 100,
                    latency_ms: 10.0,
                    error_rate: 0.0,
                },
            ],
        },
        CountryState {
            id: "country-cloud".to_string(),
            name: "The Cloud Kingdom".to_string(),
            services: vec![
                ServiceState {
                    id: "service-jules".to_string(),
                    name: "Jules".to_string(),
                    health: health.clone(),
                    hp: 100,
                    latency_ms: 200.0,
                    error_rate: 0.05,
                },
            ],
        },
    ]
}

fn build_knowledge_tree() -> Vec<KnowledgeNode> {
    vec![
        KnowledgeNode {
            id: "tdd-level-1".to_string(),
            domain: "Quality".to_string(),
            name: "TDD Nivel 1".to_string(),
            capability: "Unit testing for feature branches".to_string(),
            level: 1,
            prerequisites: vec![],
            cost: KnowledgeNodeCost { budget: 2.0, time_hours: 3 },
            unlocked: true,
            source_type: "seed".to_string(),
            source_ref: "seed://default".to_string(),
            documentation: "# TDD Nivel 1: Fundamentals\n\n- Implementation of automated test cycles (Red-Green-Refactor).\n- Mandatory coverage for all core SDK logic.\n- CI/CD integration for pre-merge validation.".to_string(),
        },
        KnowledgeNode {
            id: "neural-swarm-coordination".to_string(),
            domain: "Orchestration".to_string(),
            name: "Neural Swarm Coordination".to_string(),
            capability: "Multi-agent task distribution and conflict resolution".to_string(),
            level: 2,
            prerequisites: vec!["tdd-level-1".to_string()],
            cost: KnowledgeNodeCost { budget: 15.0, time_hours: 12 },
            unlocked: true,
            source_type: "core".to_string(),
            source_ref: "seed://sovereign".to_string(),
            documentation: "# Neural Swarm Coordination\n\nEnables the Sovereign to manage a swarm of specialized agents (Coder, Auditor, Architect) with dynamic role assignment.\n\n### Key Features:\n- **Semantic Routing**: Missions are routed based on agent capability embeddings.\n- **Neural Feedback**: Agents share state via the Neural Stream for collective intelligence.\n- **Conflict Resolution**: Logic-based arbitration for code merge decisions.".to_string(),
        },
        KnowledgeNode {
            id: "autonomous-deployment-v1".to_string(),
            domain: "Operations".to_string(),
            name: "Autonomous Deployment v1".to_string(),
            capability: "Zero-touch deployment to edge sectors".to_string(),
            level: 2,
            prerequisites: vec!["tdd-level-1".to_string()],
            cost: KnowledgeNodeCost { budget: 25.0, time_hours: 8 },
            unlocked: true,
            source_type: "core".to_string(),
            source_ref: "seed://sovereign".to_string(),
            documentation: "# Autonomous Deployment v1\n\nUnlocks the `DEPLOY` mission type for the Coder agent.\n\n- **Sector Scanning**: Automated health checks post-deployment.\n- **Guardrails**: Integration with NIST-800-53 policies for automated rollback on failure.\n- **Ghost Ingress**: Invisible traffic splitting for canary testing.".to_string(),
        },
        KnowledgeNode {
            id: "code-intelligence-semantic".to_string(),
            domain: "Intelligence".to_string(),
            name: "Semantic Code Intelligence".to_string(),
            capability: "Deep graph-based analysis of monorepo structure".to_string(),
            level: 3,
            prerequisites: vec!["neural-swarm-coordination".to_string()],
            cost: KnowledgeNodeCost { budget: 50.0, time_hours: 24 },
            unlocked: true,
            source_type: "core".to_string(),
            source_ref: "seed://sovereign".to_string(),
            documentation: "# Semantic Code Intelligence\n\nIntegrates **GitHub Semantic** into the Synapse Knowledge Graph.\n\n- **Symbol Mapping**: Visualizes classes, methods, and relationships in the TUI.\n- **Call Graph Analysis**: Predicts the blast radius of code changes.\n- **Semantic Search**: Natural language querying of the codebase structure.".to_string(),
        },
        KnowledgeNode {
            id: "global-telemetry-visualizer".to_string(),
            domain: "Intelligence".to_string(),
            name: "Global Sector Telemetry".to_string(),
            capability: "Real-time visualization of all swarm sectors".to_string(),
            level: 3,
            prerequisites: vec!["neural-swarm-coordination".to_string()],
            cost: KnowledgeNodeCost { budget: 30.0, time_hours: 12 },
            unlocked: true,
            source_type: "core".to_string(),
            source_ref: "seed://sovereign".to_string(),
            documentation: "# Global Sector Telemetry\n\nConnects the Godot-based visualizer to the live Synapse event stream.\n\n- **Live Node States**: Watch agents move through the graph in real-time.\n- **Heatmaps**: Identify sectors with high failure rates or resource consumption.\n- **Neural Playback**: Record and re-watch mission executions for post-mortem analysis.".to_string(),
        },
        KnowledgeNode {
            id: "swarm-self-repair-v1".to_string(),
            domain: "Resilience".to_string(),
            name: "Swarm Self-Repair v1".to_string(),
            capability: "Automated healing of severed neural links".to_string(),
            level: 4,
            prerequisites: vec!["autonomous-deployment-v1".to_string()],
            cost: KnowledgeNodeCost { budget: 100.0, time_hours: 48 },
            unlocked: false,
            source_type: "experimental".to_string(),
            source_ref: "seed://sovereign".to_string(),
            documentation: "# Swarm Self-Repair v1 (LOCKED)\n\nA highly advanced protocol that allows the Swarm to redeploy itself when the Sovereign connection is severed.\n\n### Protocols:\n- **Ghost Rebirth**: Autonomous spin-up of backup Gateway instances.\n- **Data Mirroring**: Real-time replication of Synapse triples across edge nodes.\n- **AI Sovereignty**: Agents can continue pre-authorized missions without a live connection.".to_string(),
        },
    ]
}

fn map_ingest_request_to_node(payload: &KnowledgeNodeIngestRequest) -> KnowledgeNode {
    KnowledgeNode {
        id: payload.node_id.clone(),
        domain: payload.domain.clone(),
        name: payload.name.clone(),
        capability: payload.capability.clone(),
        level: payload.level,
        prerequisites: payload.prerequisites.clone(),
        cost: KnowledgeNodeCost {
            budget: payload.budget_cost,
            time_hours: payload.time_cost_hours,
        },
        unlocked: true,
        documentation: payload.docs_text.clone(),
        source_type: payload.source_type.clone(),
        source_ref: payload.source_ref.clone(),
    }
}

fn knowledge_node_to_triples(
    node: &KnowledgeNode,
    payload: &KnowledgeNodeIngestRequest,
) -> Vec<(String, String, String)> {
    let node_uri = format!("http://swarm.os/ontology/knowledge/{}", node.id);
    let mut triples = vec![
        (
            node_uri.clone(),
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#type".to_string(),
            "http://swarm.os/ontology/KnowledgeNode".to_string(),
        ),
        (node_uri.clone(), "http://swarm.os/ontology/domain".to_string(), node.domain.clone()),
        (node_uri.clone(), "http://swarm.os/ontology/name".to_string(), node.name.clone()),
        (
            node_uri.clone(),
            "http://swarm.os/ontology/capability".to_string(),
            node.capability.clone(),
        ),
        (
            node_uri.clone(),
            "http://swarm.os/ontology/documentation".to_string(),
            payload.docs_text.clone(),
        ),
        (
            node_uri.clone(),
            "http://swarm.os/ontology/sourceType".to_string(),
            payload.source_type.clone(),
        ),
        (
            node_uri.clone(),
            "http://swarm.os/ontology/sourceRef".to_string(),
            payload.source_ref.clone(),
        ),
    ];

    for prerequisite in &node.prerequisites {
        triples.push((
            node_uri.clone(),
            "http://swarm.os/ontology/prerequisite".to_string(),
            format!("http://swarm.os/ontology/knowledge/{prerequisite}"),
        ));
    }

    triples
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::server::contracts::{ControlCommandType, LlmProfile};

    fn sample_command(command: ControlCommandType) -> ControlCommand {
        ControlCommand {
            command,
            actor: "sovereign-operator".into(),
            agent_id: Some("agent-1".into()),
            repo_id: Some("repo-core".into()),
            task: Some("Do task".into()),
            mission_id: Some("mission-1".into()),
            priority: Some(1),
            deployment_target: Some("prod".into()),
            rollback_to: Some("release-001".into()),
            llm_profile: Some(LlmProfile {
                provider: "OpenAI".into(),
                model: "gpt-5-mini".into(),
                hierarchy: "minion".into(),
            }),
            nist_policy_id: "NIST-800-53-REV5".into(),
            approved_by: Some("chief-security".into()),
            metadata: std::collections::HashMap::new(),
        }
    }

    #[test]
    fn guardrail_requires_policy() {
        let mut command = sample_command(ControlCommandType::Deploy);
        command.nist_policy_id = " ".into();
        let result = evaluate_guardrails(&command);
        assert_eq!(result, Some("NIST policy is required".into()));
    }

    #[test]
    fn guardrail_requires_sovereign_for_critical() {
        let mut command = sample_command(ControlCommandType::Rollback);
        command.actor = "regular-agent".into();
        let result = evaluate_guardrails(&command);
        assert_eq!(
            result,
            Some("Actor lacks sovereign permission for critical command".into())
        );
    }

    #[test]
    fn guardrail_accepts_valid_command() {
        let command = sample_command(ControlCommandType::AssignMission);
        let result = evaluate_guardrails(&command);
        assert_eq!(result, None);
    }


    #[test]
    fn service_state_defaults_are_applied_when_fields_absent() {
        let parsed: ServiceState = serde_json::from_value(serde_json::json!({
            "id": "svc",
            "name": "gateway",
            "health": "healthy"
        }))
        .expect("service state should deserialize");

        assert_eq!(parsed.hp, 100);
        assert_eq!(parsed.latency_ms, 0.0);
        assert_eq!(parsed.error_rate, 0.0);
    }

    #[test]
    fn knowledge_node_defaults_are_applied_when_fields_absent() {
        let parsed: KnowledgeNode = serde_json::from_value(serde_json::json!({
            "id": "n1",
            "domain": "DX",
            "name": "Node",
            "capability": "Cap",
            "level": 1,
            "prerequisites": [],
            "cost": {"budget": 1.0, "time_hours": 1},
            "unlocked": true
        }))
        .expect("knowledge node should deserialize");

        assert_eq!(parsed.source_type, "seed");
        assert_eq!(parsed.source_ref, "seed://default");
        assert_eq!(parsed.documentation, "");
    }

    #[test]
    fn control_command_aliases_match_python_command_names() {
        let patched: ControlCommand = serde_json::from_value(serde_json::json!({
            "command": "PATCH_SERVICE",
            "actor": "sovereign-operator",
            "nist_policy_id": "NIST-800-53-REV5",
            "approved_by": "chief-security"
        }))
        .expect("alias should deserialize");
        assert!(matches!(patched.command, ControlCommandType::Deploy));

        let rollback: ControlCommand = serde_json::from_value(serde_json::json!({
            "command": "ROLLBACK_SERVICE",
            "actor": "sovereign-operator",
            "nist_policy_id": "NIST-800-53-REV5",
            "approved_by": "chief-security"
        }))
        .expect("alias should deserialize");
        assert!(matches!(rollback.command, ControlCommandType::Rollback));
    }

    #[test]
    fn rust_event_types_cover_python_combat_stream_events() {
        let bug: EventType = serde_json::from_value(serde_json::json!("BUG_SPAWNED"))
            .expect("BUG_SPAWNED should deserialize");
        assert!(matches!(bug, EventType::BugSpawned));

        let damaged: EventType = serde_json::from_value(serde_json::json!("SERVICE_DAMAGED"))
            .expect("SERVICE_DAMAGED should deserialize");
        assert!(matches!(damaged, EventType::ServiceDamaged));

        let recovered: EventType = serde_json::from_value(serde_json::json!("SERVICE_RECOVERED"))
            .expect("SERVICE_RECOVERED should deserialize");
        assert!(matches!(recovered, EventType::ServiceRecovered));
    }

    #[test]
    fn parse_halted_status() {
        assert_eq!(parse_system_status("HALTED"), SystemStatus::Halted);
    }

    #[test]
    fn map_ingest_node_preserves_typed_fields() {
        let payload = KnowledgeNodeIngestRequest {
            node_id: "n1".into(),
            domain: "quality".into(),
            name: "TDD".into(),
            capability: "tests".into(),
            level: 2,
            budget_cost: 3.5,
            time_cost_hours: 4,
            prerequisites: vec!["n0".into()],
            docs_text: "docs".into(),
            source_type: "custom".into(),
            source_ref: "game://manual".into(),
        };
        let node = map_ingest_request_to_node(&payload);
        assert_eq!(node.id, "n1");
        assert_eq!(node.cost.budget, 3.5);
        assert_eq!(node.prerequisites, vec!["n0"]);
    }

    #[test]
    fn knowledge_triples_include_documentation_and_prerequisites() {
        let payload = KnowledgeNodeIngestRequest {
            node_id: "n1".into(),
            domain: "quality".into(),
            name: "TDD".into(),
            capability: "tests".into(),
            level: 2,
            budget_cost: 3.5,
            time_cost_hours: 4,
            prerequisites: vec!["n0".into()],
            docs_text: "docs".into(),
            source_type: "custom".into(),
            source_ref: "game://manual".into(),
        };
        let node = map_ingest_request_to_node(&payload);
        let triples = knowledge_node_to_triples(&node, &payload);
        assert!(triples.iter().any(|(_, p, o)| p.ends_with("documentation") && o == "docs"));
        assert!(triples.iter().any(|(_, p, o)| p.ends_with("prerequisite") && o.ends_with("/n0")));
    }
}
