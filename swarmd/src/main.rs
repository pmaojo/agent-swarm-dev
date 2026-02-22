mod config;
mod server;
mod synapse;
mod workers;

use anyhow::Result;
use tracing::info;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt::init();
    
    // 1. Load Configuration
    let cfg = config::AppConfig::load()?;
    info!("🚀 Swarm Orchestrator (swarmd) starting up...");

    // 2. Connect to Synapse Core
    let syn_client = synapse::SynapseClient::connect(&cfg.synapse_grpc_host, &cfg.synapse_grpc_port).await?;
    info!("🔗 Connected to Synapse at {}:{}", cfg.synapse_grpc_host, cfg.synapse_grpc_port);

    // 3. Spawn Background Workers (Telegram, Trello, etc)
    workers::start_background_workers(
        cfg.telegram_bot_token,
        cfg.trello_api_key,
        cfg.trello_token,
        cfg.trello_board_id,
        syn_client.clone(),
    ).await;

    // 4. Start HTTP Gateway (blocking)
    server::start_server(cfg.gateway_port, syn_client).await?;
    
    Ok(())
}
