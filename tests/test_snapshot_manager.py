"""
Tests for core.snapshot_manager basic scaffold.
"""
import pytest
from core.snapshot_manager import SnapshotManager


def test_snapshot_manager_init():
    sm = SnapshotManager(state_dir="/tmp")
    assert sm.state_dir == "/tmp"


def test_create_snapshot_returns_string():
    sm = SnapshotManager(state_dir="/tmp")
    snap_id = sm.create_snapshot(proposal_id="prop-123", description="test")
    assert isinstance(snap_id, str)
    assert "snap_" in snap_id
    assert "prop-123" in snap_id


def test_rollback_returns_true():
    sm = SnapshotManager(state_dir="/tmp")
    assert sm.rollback(snapshot_id="dummy") is True


def test_list_snapshots_returns_list():
    sm = SnapshotManager(state_dir="/tmp")
    snaps = sm.list_snapshots()
    assert isinstance(snaps, list)
