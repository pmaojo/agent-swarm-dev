#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SystemStatus {
    Booting,
    Ready,
    Halted,
    Degraded,
}

impl SystemStatus {
    #[must_use]
    pub fn can_accept_commands(self) -> bool {
        matches!(self, Self::Ready | Self::Degraded)
    }
}
