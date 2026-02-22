use reqwest::Client;
use serde_json::{json, Value};
use tokio::time::{sleep, Duration};
use tracing::{info, warn, error};
use tokio::sync::mpsc;
use crate::notifications::Notification;

use crate::synapse::SynapseClient;

pub async fn poll_telegram(
    token: String,
    synapse: SynapseClient,
    client: Client,
    auth_chat_id: Option<String>,
    mut rx: mpsc::Receiver<Notification>
) {
    info!("🤖 Telegram Poller & Notifier Started...");
    let mut last_update_id = 0;
    let base_url = format!("https://api.telegram.org/bot{}", token);

    loop {
        tokio::select! {
            // Priority 1: Handle incoming notifications to broadcast
            Some(notification) = rx.recv() => {
                if let Some(target_chat) = &auth_chat_id {
                    let text = match notification {
                        Notification::Trace(msg) => format!("👁️ [TRACE] {}", msg),
                        Notification::Alert(msg) => format!("🚨 [ALERT] {}", msg),
                    };
                    if let Err(e) = send_message(&base_url, target_chat, &text, &client).await {
                        error!("Failed to send Telegram notification: {}", e);
                    }
                } else {
                    warn!("Received notification but no Telegram auth_chat_id configured.");
                }
            }

            // Priority 2: Poll for user commands
            _ = sleep(Duration::from_secs(3)) => {
                let url = format!("{}/getUpdates?offset={}&timeout=10", base_url, last_update_id + 1);
                match client.get(&url).send().await {
                    Ok(res) => {
                        if let Ok(val) = res.json::<Value>().await {
                            if let Some(updates) = val.get("result").and_then(|r| r.as_array()) {
                                for update in updates {
                                    let update_id = update.get("update_id").and_then(|id| id.as_i64()).unwrap_or(0);
                                    if update_id > last_update_id {
                                        last_update_id = update_id;
                                    }

                                    if let Some(message) = update.get("message") {
                                        let msg_chat_id = message.get("chat").and_then(|c| c.get("id")).and_then(|id| id.as_i64()).unwrap_or(0);
                                        let text = message.get("text").and_then(|t| t.as_str()).unwrap_or("");

                                        handle_command(msg_chat_id, text, &base_url, &synapse, &client, &auth_chat_id).await;
                                    }
                                }
                            }
                        }
                    }
                    Err(e) => {
                        warn!("⚠️ Telegram API error during polling: {}", e);
                    }
                }
            }
        }
    }
}

async fn send_message(base_url: &str, chat_id: &str, text: &str, client: &Client) -> Result<(), reqwest::Error> {
    let url = format!("{}/sendMessage", base_url);
    client.post(&url)
        .json(&json!({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }))
        .send()
        .await?;
    Ok(())
}

async fn handle_command(chat_id: i64, text: &str, base_url: &str, synapse: &SynapseClient, client: &Client, authorized_chat_id: &Option<String>) {
    let chat_id_str = chat_id.to_string();
    let is_authorized = authorized_chat_id.as_ref().map(|id| id == &chat_id_str).unwrap_or(true);

    match text {
        "/start" => {
            let _ = send_message(base_url, &chat_id_str, "🤖 *Swarm Orchestrator Online*\nI am monitoring Trello and Synapse.", client).await;
        },
        "/status" => {
            let status = match synapse.query("SELECT ?s WHERE { <http://nist.gov/caisi/SystemControl> <http://nist.gov/caisi/operationalStatus> ?s }").await {
                Ok(res) => res,
                Err(_) => "Error querying Synapse".to_string(),
            };
            let _ = send_message(base_url, &chat_id_str, &format!("📊 *System Status*\n{}", status), client).await;
        },
        "/stop_all" => {
            if !is_authorized {
                let _ = send_message(base_url, &chat_id_str, "⛔ Unauthorized.", client).await;
                return;
            }
            match perform_status_change("HALTED", synapse).await {
                Ok(_) => { let _ = send_message(base_url, &chat_id_str, "🛑 *SYSTEM HALTED* via Emergency Switch.", client).await; },
                Err(e) => { let _ = send_message(base_url, &chat_id_str, &format!("❌ Failed to halt: {}", e), client).await; }
            }
        },
        "/resume" => {
            if !is_authorized {
                let _ = send_message(base_url, &chat_id_str, "⛔ Unauthorized.", client).await;
                return;
            }
            match perform_status_change("OPERATIONAL", synapse).await {
                Ok(_) => { let _ = send_message(base_url, &chat_id_str, "✅ *SYSTEM RESUMED* to Operational status.", client).await; },
                Err(e) => { let _ = send_message(base_url, &chat_id_str, &format!("❌ Failed to resume: {}", e), client).await; }
            }
        },
        _ => {
            if text.to_lowercase().contains("hi") || text.to_lowercase().contains("hola") {
                let _ = send_message(base_url, &chat_id_str, "👋 Hello! I am the Swarm Orchestrator. Use /status to check on things.", client).await;
            }
        }
    }
}

async fn perform_status_change(status: &str, synapse: &SynapseClient) -> anyhow::Result<()> {
    let event_id = format!("http://nist.gov/caisi/event/status/{}", uuid::Uuid::new_v4());
    let timestamp = chrono::Utc::now().to_rfc3339();
    
    synapse.ingest(vec![
        (&event_id, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "http://nist.gov/caisi/StatusChangeEvent"),
        (&event_id, "http://nist.gov/caisi/newStatus", &format!("\"{}\"", status)),
        (&event_id, "http://www.w3.org/ns/prov#generatedAtTime", &format!("\"{}\"", timestamp)),
        ("http://nist.gov/caisi/SystemControl", "http://nist.gov/caisi/hasStatusHistory", &event_id),
        ("http://nist.gov/caisi/SystemControl", "http://nist.gov/caisi/operationalStatus", &format!("\"{}\"", status)),
    ]).await?;
    
    Ok(())
}
