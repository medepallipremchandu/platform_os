import pytest

from app.core.state_machine import CallStatus, InvalidTransitionError, validate_transition


def test_allowed_transition_passes():
    validate_transition(CallStatus.CREATED, CallStatus.QUEUED)
    validate_transition(CallStatus.CONSENT_PENDING, CallStatus.CONVERSATION)
    validate_transition(CallStatus.SUMMARY, CallStatus.COMPLETED)


def test_illegal_transition_raises():
    with pytest.raises(InvalidTransitionError):
        validate_transition(CallStatus.CREATED, CallStatus.CONVERSATION)


def test_terminal_state_cannot_transition_further():
    with pytest.raises(InvalidTransitionError):
        validate_transition(CallStatus.COMPLETED, CallStatus.QUEUED)
    with pytest.raises(InvalidTransitionError):
        validate_transition(CallStatus.CANCELLED, CallStatus.DIALING)
