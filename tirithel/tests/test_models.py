"""Tests for database models."""

import pytest
from sqlalchemy import select

from tirithel.domain.models import (
    NavigationPath,
    SoftwareProfile,
    SupportSession,
)


@pytest.mark.asyncio
async def test_create_software_profile(db_session):
    profile = SoftwareProfile(name="Test Software", description="A test app")
    db_session.add(profile)
    await db_session.flush()

    assert profile.id is not None
    assert profile.name == "Test Software"
    assert profile.is_active is True


@pytest.mark.asyncio
async def test_create_session(db_session):
    session = SupportSession(title="Test Session", status="recording")
    db_session.add(session)
    await db_session.flush()

    assert session.id is not None
    assert session.status == "recording"
    assert session.started_at is not None


@pytest.mark.asyncio
async def test_session_with_profile(db_session):
    profile = SoftwareProfile(name="DocLink")
    db_session.add(profile)
    await db_session.flush()

    session = SupportSession(title="Help session", profile_id=profile.id, status="recording")
    db_session.add(session)
    await db_session.flush()

    result = await db_session.execute(
        select(SupportSession).where(SupportSession.id == session.id)
    )
    loaded = result.scalar_one()
    assert loaded.profile_id == profile.id


@pytest.mark.asyncio
async def test_create_navigation_path(db_session):
    import json

    steps = json.dumps([
        {"step_number": 1, "action": "click", "element_label": "Admin"},
        {"step_number": 2, "action": "click", "element_label": "Fees"},
    ])

    path = NavigationPath(
        issue_summary="Change fee schedule",
        steps_json=steps,
        entry_point="Main Menu",
        destination="Fee Schedules",
        tags_json='["fee", "admin"]',
        confidence_score=0.85,
    )
    db_session.add(path)
    await db_session.flush()

    assert path.id is not None
    assert path.use_count == 0
    assert path.is_verified is False

    loaded_steps = json.loads(path.steps_json)
    assert len(loaded_steps) == 2
    assert loaded_steps[0]["element_label"] == "Admin"
