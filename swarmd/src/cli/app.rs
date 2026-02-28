use ratatui::widgets::ListState;
use std::time::Duration;
use tokio::sync::mpsc;
use serde::Deserialize;

#[derive(PartialEq, Eq, Clone, Copy, Debug)]
pub enum ActivePanel {
    Input,
    Knowledge,
    KnowledgeDetail,
    Actions,
    Stream,
}

#[derive(Clone, Deserialize, Debug)]
pub struct KnowledgeNode {
    pub id: String,
    pub name: String,
    pub domain: String,
    pub level: u32,
}

pub struct App {
    pub frame_count: u64,
    pub messages: Vec<String>,
    pub input: String,
    pub connected: bool,
    pub list_state: ListState,
    pub active_panel: ActivePanel,
    pub knowledge_nodes: Vec<KnowledgeNode>,
    pub knowledge_state: ListState,
    pub active_node_detail: String,
    pub actions: Vec<String>,
    pub action_index: usize,
}

impl App {
    pub async fn new() -> App {
        let mut list_state = ListState::default();
        list_state.select(Some(0));
        let mut knowledge_state = ListState::default();
        knowledge_state.select(Some(0));
        
        let knowledge_nodes = Self::fetch_knowledge_nodes().await;
        let status = Self::fetch_system_status().await;
        let mut messages = vec!["Initializing neural links...".to_string()];
        if let Some(s) = status {
            messages.push(s);
        }
        
        App { 
            frame_count: 0,
            messages,
            input: String::new(),
            connected: false,
            list_state,
            active_panel: ActivePanel::Input,
            knowledge_nodes,
            knowledge_state,
            active_node_detail: String::new(),
            actions: vec![
                "SCAN SECTOR".to_string(),
                "LAUNCH MISSION".to_string(),
                "CANARY DEPLOY".to_string(),
                "NEURAL RESET".to_string(),
                "HALT SWARM".to_string(),
                "PURGE RECENT BRAIN".to_string(),
            ],
            action_index: 0,
        }
    }
    
    pub async fn fetch_knowledge_nodes() -> Vec<KnowledgeNode> {
        let client = reqwest::Client::new();
        match client.get("http://127.0.0.1:18789/api/v1/game-state")
            .timeout(Duration::from_secs(3))
            .send()
            .await
        {
            Ok(resp) => {
                match resp.json::<serde_json::Value>().await {
                    Ok(json) => {
                        let nodes = json.get("knowledge_tree")
                            .and_then(|n| n.as_array())
                            .map(|arr| arr.iter()
                                .filter_map(|n| {
                                    let id = n.get("id")?.as_str()?.to_string();
                                    let name = n.get("name")?.as_str()?.to_string();
                                    let domain = n.get("domain").and_then(|d| d.as_str()).unwrap_or("General").to_string();
                                    let level = n.get("level").and_then(|l| l.as_u64()).unwrap_or(1) as u32;
                                    Some(KnowledgeNode { id, name, domain, level })
                                })
                                .collect::<Vec<KnowledgeNode>>()
                            );
                        
                        let resolved = nodes.unwrap_or_default();
                        if resolved.is_empty() {
                            vec![KnowledgeNode { id: "none".to_string(), name: "No knowledge nodes found".to_string(), domain: "SYSTEM".to_string(), level: 0 }]
                        } else {
                            resolved
                        }
                    }
                    Err(_) => vec![KnowledgeNode { id: "error".to_string(), name: "Failed to parse knowledge".to_string(), domain: "ERROR".to_string(), level: 0 }]
                }
            }
            Err(_) => vec![KnowledgeNode { id: "error".to_string(), name: "Connect to gateway for knowledge".to_string(), domain: "NETWORK".to_string(), level: 0 }]
        }
    }
    
    pub async fn fetch_system_status() -> Option<String> {
        let client = reqwest::Client::new();
        match client.get("http://127.0.0.1:18789/api/v1/game-state")
            .timeout(Duration::from_secs(3))
            .send()
            .await
        {
            Ok(resp) => {
                match resp.json::<serde_json::Value>().await {
                    Ok(json) => {
                        let status = json.get("system_status")
                            .and_then(|s| s.as_str())
                            .unwrap_or("UNKNOWN");
                        let budget = json.get("daily_budget").and_then(|b| {
                            let max = b.get("max").and_then(|m| m.as_f64()).unwrap_or(0.0);
                            let spent = b.get("spent").and_then(|s| s.as_f64()).unwrap_or(0.0);
                            Some(format!("${spent:.2}/${max:.2}"))
                        });
                        Some(format!("System: {} | Budget: {}", status, budget.unwrap_or_default()))
                    }
                    Err(_) => None
                }
            }
            Err(_) => None
        }
    }

    pub fn on_tick(&mut self) {
        self.frame_count += 1;
    }

    pub fn add_message(&mut self, msg: String) {
        self.messages.push(msg);
        if self.messages.len() > 500 {
            self.messages.remove(0);
        }
        self.list_state.select(Some(self.messages.len().saturating_sub(1)));
    }

    pub fn clear_messages(&mut self) {
        self.messages.clear();
        self.messages.push("[SYSTEM] Neural stream purged.".to_string());
        self.list_state.select(Some(0));
    }

    pub fn next_panel(&mut self) {
        self.active_panel = match self.active_panel {
            ActivePanel::Input => ActivePanel::Knowledge,
            ActivePanel::Knowledge => ActivePanel::Stream,
            ActivePanel::Stream => ActivePanel::Actions,
            ActivePanel::Actions => ActivePanel::Input,
            ActivePanel::KnowledgeDetail => ActivePanel::KnowledgeDetail,
        };
    }

    pub fn handle_input(&mut self, input: String, command_tx: &mpsc::Sender<String>) {
        let normalized = input.trim().to_lowercase();
        if normalized == "status" {
            let status = if self.connected { "SECURE" } else { "SEVERED" };
            self.add_message(format!("[SYSTEM] Core telemetry: {}", status));
        } else if normalized == "help" {
            self.add_message("[SYSTEM] Available: status, help, /run <task>. Standard input talks to AI.".to_string());
        } else if input.starts_with("/run ") || input.starts_with("/mission ") {
            let task = input.replacen("/run ", "", 1).replacen("/mission ", "", 1);
            self.add_message(format!("[SYSTEM] Assigning mission: {}", task));
            let _ = command_tx.try_send(format!("MISSION:{}", task));
        } else {
            let _ = command_tx.try_send(format!("CHAT:{}", input));
        }
    }
}
