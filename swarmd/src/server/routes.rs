use axum::{extract::State, Json};
use chrono::Utc;
use serde_json::Value;
use tracing::info;

use crate::server::contracts::{
    ActiveQuest, ControlCommand, ControlCommandAck, CountryState, DailyBudget, EventAck, GatewayEvent,
    GameState, GraphData, PartyMember, PartyStats, QuestStatus, RepositoryState, ServiceHealth,
    ServiceState, SystemStatus,
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
                    spend = t.as_str().unwrap_or("0").parse().unwrap_or(0.0);
                }
            }
        }
    }

    let tasks_query = r#"
        PREFIX swarm: <http://swarm.os/ontology/>
        SELECT ?id ?state ?title WHERE {
            ?id a swarm:Task .
            ?id swarm:internalState ?state .
            OPTIONAL { ?id swarm:title ?title }
        }
    "#;

    let mut active_quests: Vec<ActiveQuest> = Vec::new();
    if let Ok(res_json) = state.synapse.query(tasks_query).await {
        if let Ok(parsed) = serde_json::from_str::<Vec<serde_json::Value>>(&res_json) {
            for item in parsed {
                let id = item.get("id").or_else(|| item.get("?id"));
                let state = item.get("state").or_else(|| item.get("?state"));
                if let (Some(id_val), Some(state_val)) = (id, state) {
                    let id_str = clean_val(id_val);
                    let title_str = item
                        .get("title")
                        .or_else(|| item.get("?title"))
                        .map(clean_val)
                        .unwrap_or_else(|| {
                            id_str
                                .split('/')
                                .last()
                                .unwrap_or("Task")
                                .replace('-', " ")
                        });
                    active_quests.push(ActiveQuest {
                        id: id_str,
                        title: title_str,
                        status: parse_quest_status(&clean_val(state_val)),
                    });
                }
            }
        }
    }

    let repo_query = r#"
        PREFIX swarm: <http://swarm.os/ontology/>
        SELECT ?repo ?repoName ?agent ?agentName ?agentClass ?agentStatus WHERE {
            ?repo a swarm:Repository .
            ?repo swarm:shortName ?repoName .
            OPTIONAL {
                ?repo swarm:hasPopulation ?agent .
                ?agent swarm:name ?agentName .
                ?agent swarm:class ?agentClass .
                ?agent swarm:status ?agentStatus .
            }
        }
    "#;

    let mut repositories_out: Vec<RepositoryState> = Vec::new();
    let mut party_out: Vec<PartyMember> = Vec::new();

    if let Ok(res_json) = state.synapse.query(repo_query).await {
        if let Ok(parsed) = serde_json::from_str::<Vec<serde_json::Value>>(&res_json) {
            use std::collections::HashMap;
            let mut repos: HashMap<String, (String, Vec<String>)> = HashMap::new();
            let mut agents: HashMap<String, PartyMember> = HashMap::new();

            for item in parsed {
                let repo_id = clean_val(item.get("repo").or_else(|| item.get("?repo")).unwrap_or(&serde_json::json!("")));
                let repo_name = clean_val(item.get("repoName").or_else(|| item.get("?repoName")).unwrap_or(&serde_json::json!("Unknown")));
                let agent_id_raw = item.get("agent").or_else(|| item.get("?agent"));

                let (_, agent_ids) = repos
                    .entry(repo_id.clone())
                    .or_insert((repo_name.clone(), Vec::new()));

                if let Some(aid_val) = agent_id_raw {
                    let aid = clean_val(aid_val);
                    if !agent_ids.contains(&aid) {
                        agent_ids.push(aid.clone());
                    }

                    agents.entry(aid.clone()).or_insert_with(|| PartyMember {
                        id: aid.split('/').last().unwrap_or(&aid).to_string(),
                        name: clean_val(item.get("agentName").or_else(|| item.get("?agentName")).unwrap_or(&serde_json::json!("Agent"))),
                        class_name: clean_val(item.get("agentClass").or_else(|| item.get("?agentClass")).unwrap_or(&serde_json::json!("Commoner"))),
                        level: 5,
                        stats: PartyStats { hp: 100, mana: 80, success_rate: "95%".to_string() },
                        current_action: clean_val(item.get("agentStatus").or_else(|| item.get("?agentStatus")).unwrap_or(&serde_json::json!("Standby"))),
                        location: repo_name.clone(),
                    });
                }
            }

            for (rid, (name, a_ids)) in repos {
                repositories_out.push(RepositoryState {
                    id: rid.split('/').last().unwrap_or(&rid).to_string(),
                    name,
                    swarm: a_ids
                        .iter()
                        .map(|id| id.split('/').last().unwrap_or(id).to_string())
                        .collect(),
                });
            }

            party_out.extend(agents.into_values());
        }
    }

    Json(GameState {
        system_status: current_status,
        daily_budget: DailyBudget {
            max: 10.0,
            spent: spend,
            unit: "USD".to_string(),
        },
        party: party_out,
        active_quests,
        fog_map: serde_json::json!({}),
        repositories: repositories_out,
        countries: build_countries(),
    })
}

pub async fn get_graph_nodes() -> Json<GraphData> {
    Json(GraphData::default())
}

pub async fn post_control_command(Json(command): Json<ControlCommand>) -> Json<ControlCommandAck> {
    Json(ControlCommandAck {
        status: "accepted".to_string(),
        command,
    })
}

pub async fn post_event(Json(event): Json<GatewayEvent>) -> Json<EventAck> {
    Json(EventAck {
        status: "broadcasted".to_string(),
        event,
    })
}

fn clean_val(val: &serde_json::Value) -> String {
    let s = match val {
        serde_json::Value::String(s) => s.as_str(),
        _ => "",
    };
    s.trim_matches(|c| c == '"' || c == '<' || c == '>').to_string()
}

fn parse_system_status(raw: &str) -> SystemStatus {
    match raw.to_uppercase().as_str() {
        "OPERATIONAL" => SystemStatus::Operational,
        "DEGRADED" => SystemStatus::Degraded,
        "OUTAGE" => SystemStatus::Outage,
        _ => SystemStatus::Unknown,
    }
}


fn build_countries() -> Vec<CountryState> {
    vec![
        CountryState {
            id: "country-core".to_string(),
            name: "The Core Empire".to_string(),
            services: vec![
                ServiceState {
                    id: "service-orchestrator".to_string(),
                    name: "orchestrator".to_string(),
                    health: ServiceHealth::Healthy,
                },
                ServiceState {
                    id: "service-gateway".to_string(),
                    name: "gateway".to_string(),
                    health: ServiceHealth::Degraded,
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
                    health: ServiceHealth::Healthy,
                },
                ServiceState {
                    id: "service-web".to_string(),
                    name: "web".to_string(),
                    health: ServiceHealth::UnderAttack,
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
                    health: ServiceHealth::Halted,
                },
            ],
        },
    ]
}

fn parse_quest_status(raw: &str) -> QuestStatus {
    match raw.to_uppercase().replace(' ', "_").as_str() {
        "REQUIREMENTS" => QuestStatus::Requirements,
        "DESIGN" => QuestStatus::Design,
        "READY" | "TODO" => QuestStatus::Ready,
        "IN_PROGRESS" => QuestStatus::InProgress,
        "DONE" => QuestStatus::Done,
        _ => QuestStatus::Blocked,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::server::contracts::{ControlCommandType, EventType};

    #[test]
    fn serializes_game_state_contract_shape() {
        let state = GameState {
            system_status: SystemStatus::Operational,
            daily_budget: DailyBudget { max: 10.0, spent: 3.0, unit: "USD".into() },
            party: vec![PartyMember {
                id: "agent-1".into(),
                name: "Coder".into(),
                class_name: "Warrior".into(),
                level: 5,
                stats: PartyStats { hp: 100, mana: 80, success_rate: "95%".into() },
                current_action: "Idle".into(),
                location: "Main".into(),
            }],
            active_quests: vec![ActiveQuest { id: "q1".into(), title: "Quest".into(), status: QuestStatus::InProgress }],
            fog_map: serde_json::json!({}),
            repositories: vec![RepositoryState { id: "repo".into(), name: "main".into(), swarm: vec!["agent-1".into()] }],
            countries: build_countries(),
        };

        let value = serde_json::to_value(state).expect("state should serialize");
        assert!(value.get("system_status").is_some());
        assert!(value.get("active_quests").is_some());
        assert!(value.get("repositories").is_some());
        assert!(value.get("countries").is_some());
        assert_eq!(value["countries"][0]["services"][0]["health"], "healthy");
    }

    #[tokio::test]
    async fn command_handler_acknowledges_request() {
        let response = post_control_command(Json(ControlCommand {
            command: ControlCommandType::AssignMission,
            agent_id: Some("agent-1".into()),
            repo_id: Some("repo".into()),
            task: Some("Fix".into()),
            metadata: std::collections::HashMap::new(),
        }))
        .await;

        assert_eq!(response.0.status, "accepted");
    }

    #[tokio::test]
    async fn event_handler_acknowledges_request() {
        let response = post_event(Json(GatewayEvent {
            r#type: EventType::HardeningEvent,
            message: "Contract failure".into(),
            details: std::collections::HashMap::new(),
            severity: "WARNING".into(),
            timestamp: "2026-01-01T00:00:00Z".into(),
        }))
        .await;

        assert_eq!(response.0.status, "broadcasted");
    }
}
