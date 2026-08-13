# ORM models are added phase by phase (candidate_profiles, jobs,
# applications, ...) — see Section 27 of the master spec for the full
# planned schema. Each model module must be imported here so its table is
# registered on Base.metadata for Alembic autogenerate and test setup.

from app.database.models.candidate_profile import CandidateProfileRecord  # noqa: F401
