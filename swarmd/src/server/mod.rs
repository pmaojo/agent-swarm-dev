pub mod routes;

use axum::{routing::get, Router};
use std::net::SocketAddr;
use tracing::info;
use crate::synapse::SynapseClient;

#[derive(Clone)]
pub struct AppState {
    pub synapse: SynapseClient,
}

pub async fn start_server(port: u16, synapse: SynapseClient) -> anyhow::Result<()> {
    let state = AppState { synapse };

    let app = Router::new()
        .route("/api/v1/game-state", get(routes::get_game_state))
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    info!("🌐 Starting Gateway HTTP Server on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
