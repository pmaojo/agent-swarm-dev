use tokio::sync::mpsc;
use futures_util::StreamExt;
use tokio_tungstenite::connect_async;
use serde_json::Value;
use std::time::Duration;

pub async fn spawn_telemetry_handler(tx: mpsc::Sender<String>, status_tx: mpsc::Sender<bool>) {
    let url = "ws://127.0.0.1:18789/api/v1/events/combat/stream";
    tokio::spawn(async move {
        loop {
            match connect_async(url).await {
                Ok((mut ws_stream, _)) => {
                    let _ = status_tx.send(true).await;
                    while let Some(msg) = ws_stream.next().await {
                        if let Ok(msg) = msg {
                            if let Ok(text) = msg.to_text() {
                                if let Ok(v) = serde_json::from_str::<Value>(text) {
                                    let type_str = v["type"].as_str().unwrap_or("UNKNOWN");
                                    let msg_str = v["payload"]["message"].as_str().unwrap_or("");
                                    let style_tag = match type_str {
                                        "AGENT_THOUGHT" => "[THOUGHT]",
                                        "TOOL_EXECUTION" => "[TOOL]",
                                        _ => type_str,
                                    };
                                    let formatted = format!("[{}] {}", style_tag, msg_str);
                                    let _ = tx.send(formatted).await;
                                }
                            }
                        } else {
                            break;
                        }
                    }
                    let _ = status_tx.send(false).await;
                }
                Err(_) => {
                    let _ = status_tx.send(false).await;
                }
            }
            tokio::time::sleep(Duration::from_secs(2)).await;
        }
    });
}

pub async fn spawn_command_handler(tx_msg: mpsc::Sender<String>, mut rx_cmd: mpsc::Receiver<String>, command_tx_internal: mpsc::Sender<String>) {
    let client = reqwest::Client::new();
    tokio::spawn(async move {
        while let Some(cmd) = rx_cmd.recv().await {
            match cmd.as_str() {
                "HALT SWARM" => {
                    let res = client.post("http://127.0.0.1:18789/api/v1/control/commands")
                        .json(&serde_json::json!({
                            "command_type": "Halt",
                            "actor": "operator",
                            "nist_policy_id": "NIST-800-53-REV5",
                            "approved_by": "operator"
                        }))
                        .send().await;
                    match res {
                        Ok(r) if r.status().is_success() => { let _ = tx_msg.send("[SUCCESS] System HALTED command sent.".to_string()).await; }
                        _ => { let _ = tx_msg.send("[ERROR] HALT command failed.".to_string()).await; }
                    }
                }
                "SCAN SECTOR" => {
                    let res = client.get("http://127.0.0.1:18789/api/v1/game-state").send().await;
                    match res {
                        Ok(r) if r.status().is_success() => { let _ = tx_msg.send("[SUCCESS] Sector scanned. Neural sensors active.".to_string()).await; }
                        _ => { let _ = tx_msg.send("[ERROR] Scan failed.".to_string()).await; }
                    }
                }
                c if c.starts_with("MISSION:") => {
                    let task = &c[8..];
                    let res = client.post("http://127.0.0.1:18789/api/v1/mission/assign")
                        .json(&serde_json::json!({
                            "agent_id": "http://swarm.os/agents/Coder",
                            "repo_id": "root",
                            "task": task
                        }))
                        .send().await;
                    match res {
                        Ok(r) if r.status().is_success() => { let _ = tx_msg.send(format!("[SUCCESS] Mission '{}' dispatched.", task)).await; }
                        _ => { let _ = tx_msg.send("[ERROR] Mission rejected by gateway.".to_string()).await; }
                    }
                }
                c if c.starts_with("KNOWLEDGE:") => {
                    let id = &c[10..];
                    let url = format!("http://127.0.0.1:18789/api/v1/knowledge-tree/{}/docs", id);
                    match client.get(&url).send().await {
                        Ok(r) if r.status().is_success() => {
                            if let Ok(json) = r.json::<serde_json::Value>().await {
                                let docs = json.get("documentation").and_then(|d| d.as_str()).unwrap_or("No docs.");
                                let _ = tx_msg.send(format!("DETAIL_VIEW:{}", docs)).await;
                            }
                        }
                        _ => { let _ = tx_msg.send(format!("DETAIL_VIEW:[ERROR] Failed to access node {}", id)).await; }
                    }
                }
                c if c.starts_with("CHAT:") => {
                    let chat = &c[5..];
                    handle_chat(chat, &client, &tx_msg, &command_tx_internal).await;
                }
                _ => {}
            }
        }
    });
}

async fn handle_chat(chat: &str, client: &reqwest::Client, tx_msg: &mpsc::Sender<String>, command_tx: &mpsc::Sender<String>) {
    if let Ok(api_key) = std::env::var("GEMINI_API_KEY") {
        let url = format!("https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent?key={}", api_key);
        let sys_prompt = "You are the AI persona of Agent Swarm. Keep responses very short and technical. Use MISSION_CMD: <task>, SCAN_CMD, or KNOWLEDGE_CMD: <id> to trigger actions.";
        let payload = serde_json::json!({
            "contents": [{"parts": [{"text": format!("{} User: {}", sys_prompt, chat)}]}]
        });
        if let Ok(resp) = client.post(&url).json(&payload).send().await {
            if let Ok(json) = resp.json::<Value>().await {
                if let Some(text) = json.pointer("/candidates/0/content/parts/0/text").and_then(|t| t.as_str()) {
                    let content = text.trim();
                    if content.contains("MISSION_CMD:") {
                        let task = content.split("MISSION_CMD:").nth(1).unwrap_or("").trim();
                        let _ = tx_msg.send(format!("[AI] Mission initialized: {}", task)).await;
                        let _ = command_tx.send(format!("MISSION:{}", task)).await;
                    } else if content.contains("SCAN_CMD") {
                        let _ = tx_msg.send("[AI] Scanning sector...".to_string()).await;
                        let _ = command_tx.send("SCAN SECTOR".to_string()).await;
                    } else if content.contains("KNOWLEDGE_CMD:") {
                         let id = content.split("KNOWLEDGE_CMD:").nth(1).unwrap_or("").trim();
                        let _ = command_tx.send(format!("KNOWLEDGE:{}", id)).await;
                    } else {
                        let _ = tx_msg.send(format!("[AI] {}", content)).await;
                    }
                    return;
                }
            }
        }
    }
    let _ = tx_msg.send("[ERROR] AI Core offline.".to_string()).await;
}
