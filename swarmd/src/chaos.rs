use crate::server::contracts::{GatewayEvent, EventType};
use std::time::Duration;
use tokio::sync::broadcast;
use chrono::Utc;
use rand::seq::SliceRandom;
use rand::Rng;
use std::collections::HashMap;

pub struct ChaosEngine {
    tx: broadcast::Sender<GatewayEvent>,
}

impl ChaosEngine {
    pub fn new(tx: broadcast::Sender<GatewayEvent>) -> Self {
        Self { tx }
    }

    pub async fn run(&self) {
        tracing::info!("🌀 Rust Chaos Engine Started");
        let mut interval = tokio::time::interval(Duration::from_secs(10));

        loop {
            interval.tick().await;

            let mut rng = rand::thread_rng();

            // 1. Random anomaly (Bug or Damage)
            if rng.gen_bool(0.3) {
                let services = vec![
                    "service-orchestrator", "service-gateway", 
                    "service-visualizer", "service-web", 
                    "service-guardian", "service-jules"
                ];
                let target = services.choose(&mut rng).unwrap().to_string();
                let event_type = if rng.gen_bool(0.5) {
                    EventType::BugSpawned
                } else {
                    EventType::ServiceDamaged
                };

                let msg = if event_type == EventType::BugSpawned {
                    format!("Chaos anomaly detected affecting {}", target)
                } else {
                    format!("Simulation entropy rising in {}", target)
                };

                let mut details = HashMap::new();
                details.insert("service_id".to_string(), target);
                details.insert("source".to_string(), "rust_chaos_engine".to_string());

                let event = GatewayEvent {
                    r#type: event_type,
                    message: msg,
                    details,
                    severity: "WARNING".to_string(),
                    timestamp: Utc::now().to_rfc3339(),
                };

                let _ = self.tx.send(event);
            }

            // 2. Jules Pulse
            if rng.gen_bool(0.15) {
                let mut details = HashMap::new();
                details.insert("service_id".to_string(), "service-jules".to_string());
                details.insert("pulse_intensity".to_string(), rng.gen::<f32>().to_string());

                let event = GatewayEvent {
                    r#type: EventType::JulesCloudBuilding,
                    message: "Jules Cloud pulsing with data (Rust)".to_string(),
                    details,
                    severity: "INFO".to_string(),
                    timestamp: Utc::now().to_rfc3339(),
                };
                let _ = self.tx.send(event);
            }

            // 3. Recovery
            if rng.gen_bool(0.1) {
                let services = vec!["service-jules", "service-web", "service-orchestrator"];
                let target = services.choose(&mut rng).unwrap().to_string();

                let mut details = HashMap::new();
                details.insert("service_id".to_string(), target.clone());

                let event = GatewayEvent {
                    r#type: EventType::ServiceRecovered,
                    message: format!("{} self-healed by Rust Chaos Engine", target),
                    details,
                    severity: "INFO".to_string(),
                    timestamp: Utc::now().to_rfc3339(),
                };
                let _ = self.tx.send(event);
            }
        }
    }
}
