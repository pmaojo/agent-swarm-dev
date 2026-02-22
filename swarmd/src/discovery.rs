use crate::synapse::SynapseClient;
use tracing::{info, error};

pub async fn discover_repositories(synapse: &SynapseClient, _project_root: &str) {
    info!("🌍 Starting Geopolitical Discovery (Repositories as Countries)...");

    // For now, let's manually register the main ones and look for others
    let repositories = vec![
        ("agent-swarm-dev", "The Swarm Motherland"),
        ("synapse-engine", "The Core Empire"),
    ];

    for (id, name) in repositories {
        let subject = format!("http://swarm.os/repository/{}", id);
        let res = synapse.ingest(vec![
            (&subject, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "http://swarm.os/ontology/Repository"),
            (&subject, "http://swarm.os/ontology/shortName", &format!("\"{}\"", name)),
            (&subject, "http://swarm.os/ontology/status", "\"STABLE\""),
        ]).await;

        if let Err(e) = res {
            error!("Failed to register country {}: {}", id, e);
        } else {
            info!("📍 Country registered: {} ({})", name, id);
        }
    }

    // Associate agents with the Motherland by default for now
    let agents = vec![
        ("agent-productmanager", "ProductManager", "Bard"),
        ("agent-coder", "Coder", "Warrior"),
    ];
    for (agent_id, name, class) in agents {
        let agent_subject = format!("http://swarm.os/agent/{}", agent_id);
        let motherland = "http://swarm.os/repository/agent-swarm-dev";
        
        let _ = synapse.ingest(vec![
            (&agent_subject, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "http://swarm.os/ontology/Agent"),
            (&motherland, "http://swarm.os/ontology/hasPopulation", &agent_subject),
            (&agent_subject, "http://swarm.os/ontology/name", &format!("\"{}\"", name)),
            (&agent_subject, "http://swarm.os/ontology/class", &format!("\"{}\"", class)),
            (&agent_subject, "http://swarm.os/ontology/status", "\"Standby\""),
        ]).await;
    }
}
