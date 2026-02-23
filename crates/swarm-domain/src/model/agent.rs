use super::ValidationError;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Agent {
    id: String,
    role: String,
    active: bool,
}

impl Agent {
    pub fn new(id: impl Into<String>, role: impl Into<String>) -> Result<Self, ValidationError> {
        let id = id.into();
        let role = role.into();
        if id.trim().is_empty() {
            return Err(ValidationError::EmptyField("agent id"));
        }
        if role.trim().is_empty() {
            return Err(ValidationError::EmptyField("agent role"));
        }
        Ok(Self {
            id,
            role,
            active: true,
        })
    }

    #[must_use]
    pub fn id(&self) -> &str {
        &self.id
    }

    #[must_use]
    pub fn role(&self) -> &str {
        &self.role
    }

    #[must_use]
    pub fn is_active(&self) -> bool {
        self.active
    }

    pub fn deactivate(&mut self) {
        self.active = false;
    }
}
