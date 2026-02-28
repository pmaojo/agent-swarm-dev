use crate::server::contracts::GatewayEvent;
use tokio::sync::broadcast;

pub struct ChaosEngine {
    _tx: broadcast::Sender<GatewayEvent>,
}

impl ChaosEngine {
    pub fn new(tx: broadcast::Sender<GatewayEvent>) -> Self {
        Self { _tx: tx }
    }

    pub async fn run(&self) {
        tracing::info!("🌀 Chaos Engine Standby (Anomalies Disabled)");
        // Anomalies deactivated by user request. 
        // We keep the loop alive but silent, or just return.
        return;
    }
}
