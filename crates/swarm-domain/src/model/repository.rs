use super::ValidationError;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Repository {
    name: String,
    default_branch: String,
}

impl Repository {
    pub fn new(
        name: impl Into<String>,
        default_branch: impl Into<String>,
    ) -> Result<Self, ValidationError> {
        let name = name.into();
        let default_branch = default_branch.into();
        if name.trim().is_empty() {
            return Err(ValidationError::EmptyField("repository name"));
        }
        if default_branch.trim().is_empty() {
            return Err(ValidationError::EmptyField("default branch"));
        }
        Ok(Self {
            name,
            default_branch,
        })
    }

    #[must_use]
    pub fn name(&self) -> &str {
        &self.name
    }

    #[must_use]
    pub fn default_branch(&self) -> &str {
        &self.default_branch
    }
}
