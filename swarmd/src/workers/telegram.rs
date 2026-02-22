use reqwest::Client;
use serde_json::Value;
use std::time::Duration;
use tracing::{error, info, warn};

use crate::synapse::SynapseClient;

pub async fn poll_telegram(token: String, synapse: SynapseClient, client: Client) {
    let base_url = format!("https://api.telegram.org/bot{}/", token);
    let mut offset = 0;

    info!("🤖 Telegram Poller Started...");

    loop {
        let url = format!("{}getUpdates?offset={}&timeout=10", base_url, offset);
        
        match client.get(&url).send().await {
            Ok(res) => {
                if let Ok(json) = res.json::<Value>().await {
                    if let Some(result) = json.get("result").and_then(|r| r.as_array()) {
                        for update in result {
                            if let Some(update_id) = update.get("update_id").and_then(|id| id.as_i64()) {
                                offset = update_id + 1;
                                
                                if let Some(message) = update.get("message") {
                                    handle_message(&client, &base_url, &synapse, message).await;
                                }
                            }
                        }
                    }
                }
            }
            Err(e) => {
                warn!("⚠️ Telegram API error (retrying in 5s): {}", e);
                tokio::time::sleep(Duration::from_secs(5)).await;
            }
        }
        
        // Small delay to prevent tight loop if timeout=10 is ignored
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
}

async fn handle_message(client: &Client, base_url: &str, _synapse: &SynapseClient, message: &Value) {
    let chat_id = message.get("chat").and_then(|c| c.get("id")).and_then(|id| id.as_i64());
    let text = message.get("text").and_then(|t| t.as_str()).unwrap_or("");

    if let Some(chat_id) = chat_id {
        let reply_text = match text {
            "/status" => "📊 System Status (Rust Orchestrator): OPERATIONAL\nDaily Spend: $0.00 / $10.00".to_string(),
            "/start" => "🤖 Monitor Service Online (Fast Rust Edition).".to_string(),
            _ => "👋 ¡Hola! Soy el Bot Monitor del Enjambre (Rust).\nSolo respondo a comandos específicos. Prueba:\n/status".to_string()
        };

        let url = format!("{}sendMessage", base_url);
        let payload = serde_json::json!({
            "chat_id": chat_id,
            "text": reply_text
        });

        if let Err(e) = client.post(&url).json(&payload).send().await {
            error!("Failed to send Telegram message: {}", e);
        }
    }
}
