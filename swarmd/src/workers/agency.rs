use std::time::Duration;
use tokio::time::sleep;
use tracing::{info, error};
use crate::synapse::SynapseClient;
use serde_json::Value;

pub async fn start_agency(synapse: SynapseClient) {
    info!("🤖 Agent Agency system initialized. Monitoring for new tasks...");

    loop {
        // Simple logic:
        // 1. Fetch active tasks (REQUIREMENTS)
        // 2. Fetch available agents (Standby)
        // 3. Assign task to agent by updating agent's status
        
        let query = r#"
            PREFIX swarm: <http://swarm.os/ontology/>
            SELECT ?task ?title ?agent
            WHERE {
                ?task a swarm:Task ;
                      swarm:internalState "REQUIREMENTS" ;
                      swarm:title ?title .
                ?agent a swarm:Agent ;
                       swarm:status "Standby" .
            }
            LIMIT 1
        "#;

        match synapse.query(query).await {
            Ok(res_json) => {
                if let Ok(parsed) = serde_json::from_str::<Vec<Value>>(&res_json) {
                    if let Some(item) = parsed.first() {
                        let task_id = item.get("?task").or_else(|| item.get("task"));
                        let title = item.get("?title").or_else(|| item.get("title"));
                        let agent_id = item.get("?agent").or_else(|| item.get("agent"));
                        
                        if let (Some(tid), Some(t), Some(aid)) = (task_id, title, agent_id) {
                            let tid_str = clean_val(tid);
                            let title_str = clean_val(t);
                            let aid_str = clean_val(aid);
                            
                            info!("🚀 LAUNCHING REAL AGENT: Orchestrating task '{}' via agent {}", title_str, aid_str);
                            
                            // 1. Transition Task to PROCESSING to avoid race conditions
                            let _ = synapse.ingest(vec![
                                (&tid_str, "http://swarm.os/ontology/internalState", "\"PROCESSING\""),
                                (&aid_str, "http://swarm.os/ontology/status", &format!("\"Working on: {}\"", title_str))
                            ]).await;

                            // 2. Spawn Real Python Orchestrator
                            let title_clone = title_str.clone();
                            tokio::spawn(async move {
                                info!("🐍 [Python] Spawning Orchestrator for: {}", title_clone);
                                let output = tokio::process::Command::new("python3")
                                    .arg("sdk/python/agents/orchestrator.py")
                                    .arg(&title_clone)
                                    .output()
                                    .await;

                                match output {
                                    Ok(out) => {
                                        if out.status.success() {
                                            info!("✅ [Python] Task '{}' completed successfully.", title_clone);
                                        } else {
                                            let err_msg = String::from_utf8_lossy(&out.stderr);
                                            error!("❌ [Python] Task '{}' failed: {}", title_clone, err_msg);
                                        }
                                    }
                                    Err(e) => {
                                        error!("❌ [Python] Failed to spawn process: {}", e);
                                    }
                                }
                            });
                        }
                    }
                }
            }
            Err(e) => {
                error!("Agency query failed: {}", e);
            }
        }

        sleep(Duration::from_secs(15)).await;
    }
}

fn clean_val(val: &Value) -> String {
    let s = match val {
        Value::String(s) => s.as_str(),
        _ => "",
    };
    s.trim_matches(|c| c == '"' || c == '<' || c == '>').to_string()
}
