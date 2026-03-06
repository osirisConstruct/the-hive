"""
Tests for core.receipt_manager basic scaffold.
"""
import pytest
from core.receipt_manager import ReceiptManager


class DummyStorage:
    """Simple in‑memory storage for testing."""
    def __init__(self):
        self.store = {}
    def get(self, key):
        return self.store.get(key)
    def set(self, key, value):
        self.store[key] = value


def test_receipt_manager_init():
    storage = DummyStorage()
    rm = ReceiptManager(storage)
    assert rm.storage is storage


def test_create_receipt_returns_dict():
    storage = DummyStorage()
    rm = ReceiptManager(storage)
    receipt = rm.create_receipt(
        action_id="test-123",
        agent_did="did:test:agent",
        action_type="test",
        payload_hash="abc123"
    )
    assert isinstance(receipt, dict)
    assert receipt["action_id"] == "test-123"
    assert receipt["agent_did"] == "did:test:agent"
    assert receipt["action_type"] == "test"
    assert receipt["payload_hash"] == "abc123"
    assert "timestamp" in receipt
    # At this stage, signature and previous_hash may be None
    assert receipt["signature"] is None
    assert receipt["previous_hash"] is None
