#![forbid(unsafe_code)]
#![deny(clippy::all)]
#![deny(clippy::unwrap_used, clippy::expect_used)]
#![deny(clippy::disallowed_types)]
#![doc = "Domain layer for the swarm engine following hexagonal architecture."]

pub mod model;
pub mod ports;

pub use model::{
    Agent, Budget, BudgetError, GameState, GameStateError, GuardrailEvent, GuardrailEventKind,
    PortError, Quest, QuestCommand, QuestTransitionError, Repository, SystemStatus,
    ValidationError,
};
