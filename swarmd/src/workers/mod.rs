pub mod telegram;
pub mod trello;

use reqwest::Client;
use std::time::Duration;
use tracing::info;

pub async fn start_background_workers(
    telegram_token: Option<String>,
    trello_api_key: Option<String>,
    trello_token: Option<String>,
    trello_board_id: Option<String>,
    synapse: crate::synapse::SynapseClient,
) {
    let client = Client::builder()
        .timeout(Duration::from_secs(10))
        .build()
        .unwrap();

    if let Some(token) = telegram_token {
        info!("📱 Spawning Telegram Background Poller...");
        tokio::spawn(telegram::poll_telegram(token, synapse.clone(), client.clone()));
    }

    if let (Some(api_key), Some(token), Some(board_id)) = (trello_api_key, trello_token, trello_board_id) {
        info!("📱 Spawning Trello Background Poller...");
        tokio::spawn(trello::poll_trello(api_key, token, board_id, synapse.clone(), client.clone()));
    }
}
