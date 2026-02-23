use swarm_domain::{
    Budget, BudgetError, GameState, GameStateError, GuardrailEvent, GuardrailEventKind, Quest,
    QuestCommand, QuestTransitionError, Repository, SystemStatus, ValidationError,
};

#[test]
fn quest_state_transitions_follow_rules() {
    let q1 = match Quest::Backlog.transition(QuestCommand::Start) {
        Ok(state) => state,
        Err(err) => panic!("unexpected transition error: {err}"),
    };
    assert_eq!(q1, Quest::InProgress);

    let q2 = match q1.transition(QuestCommand::Block) {
        Ok(state) => state,
        Err(err) => panic!("unexpected transition error: {err}"),
    };
    assert_eq!(q2, Quest::Blocked);

    let q3 = match q2.transition(QuestCommand::Complete) {
        Ok(state) => state,
        Err(err) => panic!("unexpected transition error: {err}"),
    };
    assert_eq!(q3, Quest::Completed);
    assert!(q3.is_terminal());
}

#[test]
fn invalid_commands_are_rejected_with_typed_error() {
    let result = Quest::Backlog.transition(QuestCommand::Complete);
    assert_eq!(
        result,
        Err(QuestTransitionError {
            from: Quest::Backlog,
            command: QuestCommand::Complete,
        })
    );
}

#[test]
fn budget_limits_are_enforced() {
    let mut budget = match Budget::new(1_000) {
        Ok(budget) => budget,
        Err(err) => panic!("unexpected budget error: {err:?}"),
    };
    assert!(budget.reserve(700).is_ok());
    assert_eq!(budget.remaining_cents(), 300);

    let err = match budget.reserve(400) {
        Ok(()) => panic!("expected budget overflow"),
        Err(err) => err,
    };
    assert_eq!(
        err,
        BudgetError::ExceedsCap {
            attempted_total: 1_100,
            cap: 1_000,
        }
    );
}

#[test]
fn halting_rules_apply_on_guardrail_events() {
    let repo = match Repository::new("agent-swarm-dev", "main") {
        Ok(repo) => repo,
        Err(err) => panic!("unexpected repository error: {err}"),
    };
    let budget = match Budget::new(5_000) {
        Ok(budget) => budget,
        Err(err) => panic!("unexpected budget error: {err:?}"),
    };
    let mut state = GameState::new(repo, Quest::Backlog, budget);
    state.mark_ready();
    assert_eq!(state.status(), SystemStatus::Ready);

    state.apply_guardrail(GuardrailEvent::new(GuardrailEventKind::SafetyViolation));
    assert!(!state.is_halted());

    state.apply_guardrail(GuardrailEvent::new(GuardrailEventKind::BudgetExceeded));
    assert!(state.is_halted());
    assert_eq!(state.status(), SystemStatus::Halted);
}

#[test]
fn commands_require_ready_state() {
    let repo = match Repository::new("agent-swarm-dev", "main") {
        Ok(repo) => repo,
        Err(err) => panic!("unexpected repository error: {err}"),
    };
    let budget = match Budget::new(5_000) {
        Ok(budget) => budget,
        Err(err) => panic!("unexpected budget error: {err:?}"),
    };
    let mut state = GameState::new(repo, Quest::Backlog, budget);

    assert_eq!(
        state.spend(500),
        Err(GameStateError::CommandsNotAccepted(SystemStatus::Booting))
    );
    assert_eq!(
        state.apply_quest_command(QuestCommand::Start),
        Err(GameStateError::CommandsNotAccepted(SystemStatus::Booting))
    );

    state.mark_ready();
    assert!(state.spend(500).is_ok());
    assert!(state.apply_quest_command(QuestCommand::Start).is_ok());
    assert_eq!(state.quest(), Quest::InProgress);
}

#[test]
fn value_objects_reject_empty_fields() {
    assert_eq!(
        Repository::new("", "main"),
        Err(ValidationError::EmptyField("repository name"))
    );
}
