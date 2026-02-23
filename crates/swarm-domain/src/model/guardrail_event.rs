#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GuardrailEventKind {
    BudgetExceeded,
    KillSwitch,
    SafetyViolation,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct GuardrailEvent {
    kind: GuardrailEventKind,
    should_halt: bool,
}

impl GuardrailEvent {
    #[must_use]
    pub fn new(kind: GuardrailEventKind) -> Self {
        let should_halt = matches!(
            kind,
            GuardrailEventKind::BudgetExceeded | GuardrailEventKind::KillSwitch
        );
        Self { kind, should_halt }
    }

    #[must_use]
    pub fn should_halt(self) -> bool {
        self.should_halt
    }

    #[must_use]
    pub fn kind(self) -> GuardrailEventKind {
        self.kind
    }
}
