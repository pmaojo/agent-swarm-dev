from abc import ABC, abstractmethod
from typing import Dict, Any, List

class CloudProviderInterface(ABC):
    @abstractmethod
    def name(self) -> str:
        """Return the provider name (e.g., 'Claude', 'Jules', 'Codex')."""
        pass

    @abstractmethod
    def delegate_task(self, job_bundle: Dict[str, Any]) -> str:
        """
        Delegate a task to the external provider.
        Returns a PR URI or Task ID.
        """
        pass

    @abstractmethod
    def get_status(self, task_id: str) -> str:
        """Get status of delegated task."""
        pass
