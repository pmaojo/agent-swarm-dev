use reqwest::Client;
pub mod telegram;
pub mod trello;
pub mod agency;

use std::time::Duration;
use tracing::info;
use tokio::sync::mpsc;
use crate::notifications::Notification;

pub async fn start_background_workers(
    telegram_token: Option<String>,
    telegram_chat_id: Option<String>,
    trello_api_key: Option<String>,
    trello_token: Option<String>,
    trello_board_id: Option<String>,
    synapse: crate::synapse::SynapseClient,
    tx: mpsc::Sender<Notification>,
    rx: mpsc::Receiver<Notification>,
) {
    let client = Client::builder()
        .timeout(Duration::from_secs(10))
        .build()
        .unwrap();

    if let Some(token) = telegram_token {
        info!("📱 Spawning Telegram Background Poller & Notifier...");
        tokio::spawn(telegram::poll_telegram(token, synapse.clone(), client.clone(), telegram_chat_id, rx));
    }

    if let (Some(api_key), Some(token), Some(board_id)) = (trello_api_key, trello_token, trello_board_id) {
        info!("📱 Spawning Trello Background Poller...");
        tokio::spawn(trello::poll_trello(api_key, token, board_id, synapse.clone(), client.clone(), tx.clone()));
    }

    info!("🤖 Spawning Agent Agency worker...");
    tokio::spawn(agency::start_agency(synapse.clone()));
}
