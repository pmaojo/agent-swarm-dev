mod config;
mod server;
mod synapse;
mod workers;
mod notifications;
mod discovery;

use anyhow::Result;
use tracing::{info, error};
use tokio::sync::mpsc;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt::init();
    
    // 1. Load Configuration
    let cfg = config::AppConfig::load()?;
    info!("🚀 Swarm Orchestrator (swarmd) starting up...");

    // 2. Setup Communication Channels
    let (tx, rx) = mpsc::channel(100);

    // 3. Connect to Synapse Core
    let syn_client = synapse::SynapseClient::connect(&cfg.synapse_grpc_host, &cfg.synapse_grpc_port).await?;
    info!("🔗 Connected to Synapse at {}:{}", cfg.synapse_grpc_host, cfg.synapse_grpc_port);

    // Run geopolitical discovery
    discovery::discover_repositories(&syn_client, ".").await;

    // 4. Spawn Background Workers (Telegram, Trello, etc)
    workers::start_background_workers(
        cfg.telegram_bot_token.clone(),
        cfg.telegram_chat_id.clone(),
        cfg.trello_api_key,
        cfg.trello_token,
        cfg.trello_board_id,
        syn_client.clone(),
        tx.clone(),
        rx,
    ).await;

    // 5. Start HTTP Gateway (blocking)
    server::start_server(cfg.gateway_port, syn_client).await?;
    
    Ok(())
}
