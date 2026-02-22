use reqwest::Client;
use serde_json::Value;
use std::time::Duration;
use tracing::{error, info, warn};
use std::collections::HashSet;

use crate::synapse::SynapseClient;

pub async fn poll_trello(api_key: String, token: String, board_id: String, synapse: SynapseClient, client: Client) {
    info!("📋 Trello Poller Started (Board: {})...", board_id);
    let base_url = "https://api.trello.com/1";
    let mut processed_cards = HashSet::new();

    loop {
        // 1. Fetch Lists for the Board
        let lists_url = format!("{}/boards/{}/lists?key={}&token={}", base_url, board_id, api_key, token);
        
        match client.get(&lists_url).send().await {
            Ok(res) => {
                if let Ok(lists) = res.json::<Vec<Value>>().await {
                    for list in lists {
                        let list_id = list.get("id").and_then(|id| id.as_str()).unwrap_or("");
                        let list_name = list.get("name").and_then(|n| n.as_str()).unwrap_or("");

                        // We care about REQUIREMENTS, DESIGN, TODO, IN PROGRESS
                        if ["REQUIREMENTS", "DESIGN", "TODO", "INBOX"].contains(&list_name) {
                            check_list_cards(list_id, list_name, &api_key, &token, &client, &synapse, &mut processed_cards).await;
                        }
                    }
                }
            }
            Err(e) => {
                warn!("⚠️ Trello API error fetching lists: {}", e);
            }
        }

        tokio::time::sleep(Duration::from_secs(10)).await;
    }
}

async fn check_list_cards(
    list_id: &str, 
    list_name: &str, 
    api_key: &str, 
    token: &str, 
    client: &Client, 
    synapse: &SynapseClient,
    processed_cards: &mut HashSet<String>
) {
    let cards_url = format!("https://api.trello.com/1/lists/{}/cards?key={}&token={}", list_id, api_key, token);
    
    if let Ok(res) = client.get(&cards_url).send().await {
        if let Ok(cards) = res.json::<Vec<Value>>().await {
            for card in cards {
                let card_id = card.get("id").and_then(|id| id.as_str()).unwrap_or("");
                let card_name = card.get("name").and_then(|n| n.as_str()).unwrap_or("");
                
                let state_key = format!("{}:{}", card_id, list_name);
                
                if !processed_cards.contains(&state_key) {
                    info!("🔎 Found NEW card '{}' in '{}'", card_name, list_name);
                    
                    // TODO: Actual Agent Logic mapping here. For now, we just ingest a ping to Synapse.
                    let subject = format!("http://swarm.os/trello/card/{}", card_id);
                    let _ = synapse.ingest(vec![
                        (&subject, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "http://swarm.os/ontology/Task"),
                        (&subject, "http://swarm.os/ontology/internalState", &format!("\"{}\"", list_name))
                    ]).await;

                    processed_cards.insert(state_key);
                }
            }
        }
    }
}
