use core::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ValidationError {
    EmptyField(&'static str),
}

impl fmt::Display for ValidationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::EmptyField(field) => write!(f, "{field} must not be empty"),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct QuestTransitionError {
    pub from: crate::model::Quest,
    pub command: crate::model::QuestCommand,
}

impl fmt::Display for QuestTransitionError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "invalid quest transition from {:?} using {:?}",
            self.from, self.command
        )
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GameStateError {
    CommandsNotAccepted(crate::model::SystemStatus),
    Budget(crate::model::BudgetError),
    QuestTransition(QuestTransitionError),
}

impl From<crate::model::BudgetError> for GameStateError {
    fn from(value: crate::model::BudgetError) -> Self {
        Self::Budget(value)
    }
}

impl From<QuestTransitionError> for GameStateError {
    fn from(value: QuestTransitionError) -> Self {
        Self::QuestTransition(value)
    }
}

impl fmt::Display for GameStateError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::CommandsNotAccepted(status) => {
                write!(f, "system cannot accept commands while in {:?}", status)
            }
            Self::Budget(error) => write!(f, "budget error: {error}"),
            Self::QuestTransition(error) => write!(f, "quest transition error: {error}"),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PortError {
    Validation(ValidationError),
    BackendUnavailable,
    Unauthorized,
    Unexpected(String),
}

impl fmt::Display for PortError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Validation(error) => write!(f, "validation error: {error}"),
            Self::BackendUnavailable => write!(f, "backend unavailable"),
            Self::Unauthorized => write!(f, "unauthorized"),
            Self::Unexpected(message) => write!(f, "unexpected error: {message}"),
        }
    }
}
