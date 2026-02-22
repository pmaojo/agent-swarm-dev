use axum::{extract::State, Json};
use serde_json::Value;
use tracing::{error, info};
use chrono::Utc;

use crate::server::AppState;

pub async fn get_game_state(State(state): State<AppState>) -> Json<Value> {
    info!("Fetching Game State from Synapse...");
    
    // 1. Fetch System Status
    let status_query = r#"
        PREFIX nist: <http://nist.gov/caisi/>
        SELECT ?status WHERE { <http://nist.gov/caisi/SystemControl> nist:operationalStatus ?status }
    "#;
    
    let mut current_status = "OPERATIONAL".to_string();
    if let Ok(res_json) = state.synapse.query(status_query).await {
        if let Ok(parsed) = serde_json::from_str::<Vec<serde_json::Value>>(&res_json) {
            if let Some(last) = parsed.last() {
                if let Some(s) = last.get("status").or_else(|| last.get("?status")) {
                    current_status = s.as_str().unwrap_or("UNKNOWN").to_string();
                }
            }
        }
    }

    // 2. Daily Spend
    let today = Utc::now().format("%Y-%m-%d").to_string();
    let spend_query = format!(r#"
        PREFIX swarm: <http://swarm.os/ontology/>
        SELECT (SUM(?amount) as ?total)
        WHERE {{
            ?event a swarm:SpendEvent .
            ?event swarm:date "{}" .
            ?event swarm:amount ?amount .
        }}
    "#, today);

    let mut spend = 0.0;
    if let Ok(res_json) = state.synapse.query(&spend_query).await {
        if let Ok(parsed) = serde_json::from_str::<Vec<serde_json::Value>>(&res_json) {
            if let Some(first) = parsed.first() {
                if let Some(t) = first.get("total").or_else(|| first.get("?total")) {
                    // Try parsing string or f64
                    spend = t.as_str().unwrap_or("0").parse().unwrap_or(0.0);
                }
            }
        }
    }

    let daily_budget = serde_json::json!({
        "max": 10.0,
        "spent": spend,
        "unit": "USD"
    });

    // 3. Mock Party / Pending structure (for now, equivalent to python basic response)
    let party = serde_json::json!([
        {
            "id": "agent-productmanager",
            "name": "ProductManager",
            "class": "Bard",
            "level": 5,
            "stats": { "hp": 100, "mana": 80, "success_rate": "95%" },
            "current_action": "Idle",
            "location": "The Requirements Hall"
        },
        {
            "id": "agent-coder",
            "name": "Coder",
            "class": "Warrior",
            "level": 5,
            "stats": { "hp": 100, "mana": 80, "success_rate": "95%" },
            "current_action": "Idle",
            "location": "The Shell Dungeon"
        }
    ]);

    let response = serde_json::json!({
        "system_status": current_status,
        "daily_budget": daily_budget,
        "party": party,
        "active_quests": [],
        "fog_map": {},
        "repositories": []
    });

    Json(response)
}
