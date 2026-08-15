"""Portal adapter interface (Section 9).

Every portal integration implements this. The supervisor and the apply
graph depend only on this interface, never on a concrete adapter — adding
a new portal (Lever, Workday, ...) means adding a new module under
`app/portals/`, not touching orchestration code ("build the architecture
so more adapters are plugins").

Stateful by design, matching the spec's exact method signatures
(``validate_application``/``submit_application``/``verify_submission``
take no arguments): a caller runs the sequence ``authenticate ->
discover_jobs -> get_job_details -> normalize_job -> prepare_application
-> fill_application -> validate_application -> submit_application ->
verify_submission`` against one adapter instance, and the adapter tracks
whatever "current application" state that implies internally.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.jobs.models import NormalizedJob
from app.profile.models import CandidateProfile


class JobPortalAdapter(ABC):
    @abstractmethod
    async def authenticate(self) -> None: ...

    @abstractmethod
    async def discover_jobs(self, search_policy: dict[str, Any]) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_job_details(self, job: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def normalize_job(self, raw_job: dict[str, Any]) -> NormalizedJob: ...

    @abstractmethod
    async def prepare_application(
        self, job: NormalizedJob, candidate: CandidateProfile
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def fill_application(self, application: dict[str, Any]) -> Any: ...

    @abstractmethod
    async def validate_application(self) -> list[str]: ...

    @abstractmethod
    async def submit_application(self) -> dict[str, Any]: ...

    @abstractmethod
    async def verify_submission(self) -> bool: ...
