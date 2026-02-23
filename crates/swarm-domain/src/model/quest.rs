use super::QuestTransitionError;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Quest {
    Backlog,
    InProgress,
    Blocked,
    Completed,
    Cancelled,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum QuestCommand {
    Start,
    Block,
    Unblock,
    Complete,
    Cancel,
}

impl Quest {
    pub fn transition(self, command: QuestCommand) -> Result<Self, QuestTransitionError> {
        match (self, command) {
            (Self::Backlog, QuestCommand::Start) => Ok(Self::InProgress),
            (Self::InProgress, QuestCommand::Block) => Ok(Self::Blocked),
            (Self::Blocked, QuestCommand::Unblock) => Ok(Self::InProgress),
            (Self::InProgress | Self::Blocked, QuestCommand::Complete) => Ok(Self::Completed),
            (Self::Backlog | Self::InProgress | Self::Blocked, QuestCommand::Cancel) => {
                Ok(Self::Cancelled)
            }
            _ => Err(QuestTransitionError {
                from: self,
                command,
            }),
        }
    }

    #[must_use]
    pub fn is_terminal(self) -> bool {
        matches!(self, Self::Completed | Self::Cancelled)
    }
}
