use core::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Budget {
    cap_cents: u64,
    spent_cents: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BudgetError {
    ZeroCap,
    ExceedsCap { attempted_total: u64, cap: u64 },
}

impl fmt::Display for BudgetError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::ZeroCap => write!(f, "budget cap must be greater than zero"),
            Self::ExceedsCap {
                attempted_total,
                cap,
            } => {
                write!(f, "attempted spend {attempted_total} exceeds cap {cap}")
            }
        }
    }
}

impl Budget {
    pub fn new(cap_cents: u64) -> Result<Self, BudgetError> {
        if cap_cents == 0 {
            return Err(BudgetError::ZeroCap);
        }
        Ok(Self {
            cap_cents,
            spent_cents: 0,
        })
    }

    pub fn reserve(&mut self, amount_cents: u64) -> Result<(), BudgetError> {
        let attempted_total = self.spent_cents.saturating_add(amount_cents);
        if attempted_total > self.cap_cents {
            return Err(BudgetError::ExceedsCap {
                attempted_total,
                cap: self.cap_cents,
            });
        }
        self.spent_cents = attempted_total;
        Ok(())
    }

    #[must_use]
    pub fn remaining_cents(self) -> u64 {
        self.cap_cents - self.spent_cents
    }

    #[must_use]
    pub fn cap_cents(self) -> u64 {
        self.cap_cents
    }
}
