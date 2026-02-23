use super::{
    Budget, GameStateError, GuardrailEvent, Quest, QuestCommand, Repository, SystemStatus,
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GameState {
    repository: Repository,
    quest: Quest,
    budget: Budget,
    status: SystemStatus,
}

impl GameState {
    #[must_use]
    pub fn new(repository: Repository, quest: Quest, budget: Budget) -> Self {
        Self {
            repository,
            quest,
            budget,
            status: SystemStatus::Booting,
        }
    }

    pub fn mark_ready(&mut self) {
        if matches!(self.status, SystemStatus::Booting) {
            self.status = SystemStatus::Ready;
        }
    }

    pub fn apply_quest_command(&mut self, command: QuestCommand) -> Result<(), GameStateError> {
        if !self.status.can_accept_commands() {
            return Err(GameStateError::CommandsNotAccepted(self.status));
        }
        self.quest = self.quest.transition(command)?;
        Ok(())
    }

    pub fn spend(&mut self, amount_cents: u64) -> Result<(), GameStateError> {
        if !self.status.can_accept_commands() {
            return Err(GameStateError::CommandsNotAccepted(self.status));
        }
        self.budget.reserve(amount_cents)?;
        Ok(())
    }

    pub fn apply_guardrail(&mut self, event: GuardrailEvent) {
        if event.should_halt() {
            self.status = SystemStatus::Halted;
        }
    }

    #[must_use]
    pub fn is_halted(&self) -> bool {
        matches!(self.status, SystemStatus::Halted)
    }

    #[must_use]
    pub fn status(&self) -> SystemStatus {
        self.status
    }

    #[must_use]
    pub fn quest(&self) -> Quest {
        self.quest
    }

    #[must_use]
    pub fn budget(&self) -> Budget {
        self.budget
    }

    #[must_use]
    pub fn repository(&self) -> &Repository {
        &self.repository
    }
}
