use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Notification {
    Trace(String),
    Alert(String),
}
