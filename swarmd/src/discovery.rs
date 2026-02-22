use crate::synapse::SynapseClient;
use tracing::{info, error};

pub async fn discover_repositories(synapse: &SynapseClient, _project_root: &str) {
    info!("🌍 Starting Geopolitical Discovery (Repositories as Countries)...");

    // 1. Motherland (agent-swarm-dev)
    ingest_repo(&synapse, "agent-swarm-dev", "The Swarm Motherland").await;
    
    // 2. Core (synapse-engine)
    ingest_repo(&synapse, "synapse-engine", "The Core Empire").await;

    // 3. Frontend (visualizer)
    ingest_repo(&synapse, "agent-swarm-visualizer", "The Front-End Republic").await;

    // 4. Security (hardening)
    ingest_repo(&synapse, "swarm-security", "The Security Kingdom").await;

    // Associate agents with their respective countries
    let agents = vec![
        // Motherland (Blue)
        ("PM_1", "ProductManager", "ProductManager", "agent-swarm-dev"),
        ("Coder_1", "Coder", "Coder", "agent-swarm-dev"),
        ("Architect_1", "Architect", "Architect", "agent-swarm-dev"),
        
        // Core (Red)
        ("Coder_Core", "Core Dev", "Coder", "synapse-engine"),
        ("Analyst_Core", "Data Seer", "Analyst", "synapse-engine"),
        
        // Frontend (Green)
        ("UI_Master", "UI Master", "Coder", "agent-swarm-visualizer"),
        ("Reviewer_FE", "UX Critic", "Reviewer", "agent-swarm-visualizer"),
        
        // Security (Yellow)
        ("Sentinel", "The Sentinel", "Security", "swarm-security"),
        ("Sec_Analyst", "Warden", "Analyst", "swarm-security"),
    ];

    for (agent_id, name, class, repo_id) in agents {
        let agent_subject = format!("http://swarm.os/agent/{}", agent_id);
        let repo_subject = format!("http://swarm.os/repository/{}", repo_id);

        let _ = synapse.ingest(vec![
            (&agent_subject, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "http://swarm.os/ontology/Agent"),
            (&agent_subject, "http://swarm.os/ontology/name", &format!("\"{}\"", name)),
            (&agent_subject, "http://swarm.os/ontology/shortName", &format!("\"{}\"", name)),
            (&agent_subject, "http://swarm.os/ontology/class", &format!("\"{}\"", class)),
            (&agent_subject, "http://swarm.os/ontology/status", "\"Standby\""),
            (&repo_subject, "http://swarm.os/ontology/hasPopulation", &agent_subject),
        ]).await;
    }
}

async fn ingest_repo(synapse: &SynapseClient, id: &str, name: &str) {
    let repo_subject = format!("http://swarm.os/repository/{}", id);
    let _ = synapse.ingest(vec![
        (&repo_subject, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "http://swarm.os/ontology/Repository"),
        (&repo_subject, "http://swarm.os/ontology/name", &format!("\"{}\"", name)),
        (&repo_subject, "http://swarm.os/ontology/shortName", &format!("\"{}\"", name)),
        (&repo_subject, "http://swarm.os/ontology/status", "\"STABLE\""),
    ]).await;
    info!("📍 Country registered: {} ({})", name, id);
}
