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

    // 3. Fetch Tasks/Quests from Trello Ingestion
    let tasks_query = r#"
        PREFIX swarm: <http://swarm.os/ontology/>
        SELECT ?id ?state ?title WHERE {
            ?id a swarm:Task .
            ?id swarm:internalState ?state .
            OPTIONAL { ?id swarm:title ?title }
        }
    "#;
    
    let mut active_quests = serde_json::json!([]);
    if let Ok(res_json) = state.synapse.query(tasks_query).await {
        info!("Task Query Result: {}", res_json);
        if let Ok(parsed) = serde_json::from_str::<Vec<serde_json::Value>>(&res_json) {
            let mut quests = Vec::new();
            for item in parsed {
                let id = item.get("id").or_else(|| item.get("?id"));
                let state = item.get("state").or_else(|| item.get("?state"));
                
                if let (Some(id_val), Some(state_val)) = (id, state) {
                    let id_str = clean_val(id_val);
                    let title_val = item.get("title").or_else(|| item.get("?title"));
                    let title_str = title_val
                        .map(|t| clean_val(t))
                        .unwrap_or_else(|| id_str.split('/').last().unwrap_or("Task").replace('-', " "));

                    quests.push(serde_json::json!({
                        "id": id_str,
                        "status": clean_val(state_val),
                        "title": title_str
                    }));
                }
            }
            active_quests = serde_json::json!(quests);
        }
    }

    // 4. Fetch Repositories and their populations (Geopolitical Swarms)
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

    let mut repositories_out = Vec::new();
    let mut party_out = Vec::new();

    if let Ok(res_json) = state.synapse.query(repo_query).await {
        if let Ok(parsed) = serde_json::from_str::<Vec<serde_json::Value>>(&res_json) {
            use std::collections::HashMap;
            let mut repos: HashMap<String, (String, Vec<String>)> = HashMap::new();
            let mut agents: HashMap<String, serde_json::Value> = HashMap::new();

            for item in parsed {
                let repo_id = clean_val(item.get("repo").or_else(|| item.get("?repo")).unwrap_or(&serde_json::json!("")));
                let repo_name = clean_val(item.get("repoName").or_else(|| item.get("?repoName")).unwrap_or(&serde_json::json!("Unknown")));
                let agent_id_raw = item.get("agent").or_else(|| item.get("?agent"));

                let (_name, agent_ids) = repos.entry(repo_id.clone()).or_insert((repo_name.clone(), Vec::new()));
                
                if let Some(aid_val) = agent_id_raw {
                    let aid = clean_val(aid_val);
                    if !agent_ids.contains(&aid) {
                        agent_ids.push(aid.clone());
                    }

                    if !agents.contains_key(&aid) {
                        let a_name = clean_val(item.get("agentName").or_else(|| item.get("?agentName")).unwrap_or(&serde_json::json!("Agent")));
                        let a_class = clean_val(item.get("agentClass").or_else(|| item.get("?agentClass")).unwrap_or(&serde_json::json!("Commoner")));
                        let a_status = clean_val(item.get("agentStatus").or_else(|| item.get("?agentStatus")).unwrap_or(&serde_json::json!("Standby")));

                        agents.insert(aid.clone(), serde_json::json!({
                            "id": aid.split('/').last().unwrap_or(&aid),
                            "name": a_name,
                            "class": a_class,
                            "level": 5,
                            "stats": { "hp": 100, "mana": 80, "success_rate": "95%" },
                            "current_action": a_status,
                            "location": repo_name
                        }));
                    }
                }
            }

            for (rid, (name, a_ids)) in repos {
                repositories_out.push(serde_json::json!({
                    "id": rid.split('/').last().unwrap_or(&rid),
                    "name": name,
                    "swarm": a_ids.iter().map(|id| id.split('/').last().unwrap_or(id)).collect::<Vec<_>>()
                }));
            }
            for (_aid, val) in agents {
                party_out.push(val);
            }
        }
    }

    let response = serde_json::json!({
        "system_status": current_status,
        "daily_budget": daily_budget,
        "party": party_out,
        "active_quests": active_quests,
        "fog_map": {},
        "repositories": repositories_out
    });

    Json(response)
}

fn clean_val(val: &serde_json::Value) -> String {
    let s = match val {
        serde_json::Value::String(s) => s.as_str(),
        _ => "",
    };
    s.trim_matches(|c| c == '"' || c == '<' || c == '>').to_string()
}
