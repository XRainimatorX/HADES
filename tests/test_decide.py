"""Tests for the Stage 2 decision skeleton: it reports SCANNING and never issues a command."""

from __future__ import annotations

from hades.contracts import SystemState, Track, TrackingPacket
from hades.decide import StateMachine


def _packet(frame_id: int, timestamp: int, targets: list[Track]) -> TrackingPacket:
    return TrackingPacket(
        frame_id=frame_id, targets=targets, timestamp=timestamp, t_track=timestamp
    )


def test_first_step_reports_scanning_after_idle() -> None:
    """The first frame moves the machine from IDLE to SCANNING and copies frame_id and timestamp."""
    state, command = StateMachine().step(_packet(7, 1_000, []))
    assert state == SystemState(state="SCANNING", previous="IDLE", frame_id=7, timestamp=1_000)
    assert command is None


def test_later_steps_stay_in_scanning() -> None:
    """After the first frame the previous state is SCANNING too."""
    engine = StateMachine()
    engine.step(_packet(0, 10, []))
    state, command = engine.step(_packet(1, 20, []))
    assert (state.state, state.previous, state.frame_id, state.timestamp) == (
        "SCANNING",
        "SCANNING",
        1,
        20,
    )
    assert command is None


def test_a_confirmed_target_still_issues_no_command() -> None:
    """The skeleton has no decision logic, so even a confirmed target gives no command."""
    track = Track(1, "drone", 0.95, (0.0, 0.0, 10.0, 10.0), True)
    state, command = StateMachine().step(_packet(3, 30, [track]))
    assert state.state == "SCANNING"
    assert command is None


def test_source_lost_returns_no_command() -> None:
    """No alert is ever active in the skeleton, so losing the source has nothing to switch off."""
    assert StateMachine().on_source_lost(123) is None
