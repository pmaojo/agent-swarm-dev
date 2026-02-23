use crate::model::{Agent, PortError, Quest, SystemStatus};

pub trait KnowledgeGraphPort {
    fn upsert_fact(&self, subject: &str, predicate: &str, object: &str) -> Result<(), PortError>;
}

pub trait TaskBoardPort {
    fn sync_quest(&self, quest: Quest) -> Result<(), PortError>;
}

pub trait NotificationPort {
    fn notify_agent(&self, agent: &Agent, message: &str) -> Result<(), PortError>;
}

pub trait LLMPort {
    fn complete(&self, prompt: &str) -> Result<String, PortError>;
}

pub trait ExecutionPort {
    fn run_command(&self, command: &str, status: SystemStatus) -> Result<String, PortError>;
}
