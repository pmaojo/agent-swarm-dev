use std::time::Duration;
use tokio::time::sleep;
use tracing::{info, error};
use crate::synapse::SynapseClient;

pub async fn start_agency(synapse: SynapseClient) {
    info!("🤖 Agent Agency system initialized. Monitoring for new tasks...");

    loop {
        // Simple logic:
        // 1. Fetch active tasks (REQUIREMENTS)
        // 2. Fetch available agents (Standby)
        // 3. Assign task to agent by updating agent's status
        
        let query = r#"
            PREFIX swarm: <http://swarm.os/>
            SELECT ?task ?title ?agent
            WHERE {
                ?task a swarm:Task ;
                      swarm:status "REQUIREMENTS" ;
                      swarm:title ?title .
                ?agent a swarm:Agent ;
                       swarm:status "Standby" .
            }
            LIMIT 1
        "#;

        match synapse.query(query).await {
            Ok(results) => {
                if !results.is_empty() {
                    let task_id = &results[0]["?task"];
                    let title = &results[0]["?title"];
                    let agent_id = &results[0]["?agent"];
                    
                    info!("Assigning task {} to agent {}", title, agent_id);
                    
                    // Update agent status to working on the task
                    let working_status = format!("\"Working on: {}\"", title.trim_matches('"'));
                    let ingest_res = synapse.ingest(vec![
                        (agent_id, "http://swarm.os/status", &working_status)
                    ]).await;

                    if let Err(e) = ingest_res {
                        error!("Failed to update agent status: {}", e);
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
