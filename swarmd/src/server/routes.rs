use axum::{extract::State, Json};
use chrono::Utc;
use tracing::info;

use crate::server::contracts::{
    ActiveQuest, AuditRecord, CommandPhase, ControlCommand, ControlCommandAck, CountryState,
    DailyBudget, EventAck, GameState, GatewayEvent, GraphData, KnowledgeNode, KnowledgeNodeCost,
    PartyMember, PartyStats, PolicyApprovalStatus, QuestStatus, RepositoryState, ServiceHealth,
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

    Json(GameState {
        system_status: current_status,
        daily_budget: DailyBudget {
            max: 10.0,
            spent: spend,
            unit: "USD".to_string(),
        },
        party: vec![],
        active_quests: vec![],
        fog_map: serde_json::json!({}),
        repositories: vec![],
        countries: build_countries(),
        knowledge_tree: build_knowledge_tree(),
        sovereign_controls: PolicyApprovalStatus {
            approved: true,
            approved_by: Some("security-council".to_string()),
            policy_id: "NIST-800-53-REV5".to_string(),
        },
    })
}

pub async fn get_graph_nodes() -> Json<GraphData> {
    Json(GraphData::default())
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

pub async fn post_event(Json(event): Json<GatewayEvent>) -> Json<EventAck> {
    Json(EventAck {
        status: "broadcasted".to_string(),
        event,
    })
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

fn build_countries() -> Vec<CountryState> {
    vec![CountryState {
        id: "country-core".to_string(),
        name: "The Core Empire".to_string(),
        services: vec![ServiceState {
            id: "service-orchestrator".to_string(),
            name: "orchestrator".to_string(),
            health: ServiceHealth::Healthy,
        }],
    }]
}

fn build_knowledge_tree() -> Vec<KnowledgeNode> {
    vec![KnowledgeNode {
        id: "tdd-level-1".to_string(),
        domain: "Calidad".to_string(),
        name: "TDD Nivel 1".to_string(),
        capability: "Pruebas por feature branch".to_string(),
        level: 1,
        prerequisites: vec![],
        cost: KnowledgeNodeCost {
            budget: 2.0,
            time_hours: 3,
        },
        unlocked: true,
    }]
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
    fn parse_halted_status() {
        assert_eq!(parse_system_status("HALTED"), SystemStatus::Halted);
    }
}
