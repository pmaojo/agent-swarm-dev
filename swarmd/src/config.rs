use anyhow::Result;
use dotenvy::dotenv;
use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct AppConfig {
    pub synapse_grpc_host: String,
    pub synapse_grpc_port: String,
    pub gateway_port: u16,

    // Telegram
    pub telegram_bot_token: Option<String>,
    pub telegram_chat_id: Option<String>,

    // Trello
    pub trello_api_key: Option<String>,
    pub trello_token: Option<String>,
    pub trello_board_id: Option<String>,
    pub trello_mock_mode: bool,
}

impl AppConfig {
    pub fn load() -> Result<Self> {
        // Load variables from .env if present. Ignore errors to allow overriding from environment
        let _ = dotenv();

        Ok(Self {
            synapse_grpc_host: std::env::var("SYNAPSE_GRPC_HOST").unwrap_or_else(|_| "127.0.0.1".into()),
            synapse_grpc_port: std::env::var("SYNAPSE_GRPC_PORT").unwrap_or_else(|_| "50051".into()),
            gateway_port: std::env::var("GATEWAY_PORT")
                .unwrap_or_else(|_| "18789".into())
                .parse()
                .unwrap_or(18789),

            telegram_bot_token: std::env::var("TELEGRAM_BOT_TOKEN").ok(),
            telegram_chat_id: std::env::var("TELEGRAM_CHAT_ID").ok(),

            trello_api_key: std::env::var("TRELLO_API_KEY").ok(),
            trello_token: std::env::var("TRELLO_TOKEN").ok(),
            trello_board_id: std::env::var("TRELLO_BOARD_ID").ok(),
            trello_mock_mode: std::env::var("TRELLO_MOCK_MODE")
                .map(|v| v.to_lowercase() == "true" || v == "1")
                .unwrap_or(false),
        })
    }
}
