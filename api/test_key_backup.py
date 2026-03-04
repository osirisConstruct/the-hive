"""
The Hive - Key Backup Tests
Test suite for Phase 5.1: Automated Key Backup
"""

import pytest
import tempfile
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.identity_manager import IdentityManager
from core.key_backup import KeyBackup, create_backup, restore_backup


class TestKeyBackup:
    
    @pytest.fixture
    def identity(self):
        return IdentityManager.create_identity("test_agent")
    
    @pytest.fixture
    def password(self):
        return "secure_password_123"
    
    def test_export_identity(self, identity, password):
        backup = KeyBackup.export_identity(
            identity["did"],
            identity["private_key"],
            identity["public_key"],
            identity["did_document"],
            password,
            metadata={"agent_id": "test"}
        )
        
        assert isinstance(backup, str)
        assert len(backup) > 100
    
    def test_import_identity(self, identity, password):
        backup = KeyBackup.export_identity(
            identity["did"],
            identity["private_key"],
            identity["public_key"],
            identity["did_document"],
            password
        )
        
        restored = KeyBackup.import_identity(backup, password)
        
        assert restored["did"] == identity["did"]
        assert restored["private_key"] == identity["private_key"]
        assert restored["public_key"] == identity["public_key"]
        assert restored["did_document"]["id"] == identity["did"]
    
    def test_wrong_password_fails(self, identity):
        backup = KeyBackup.export_identity(
            identity["did"],
            identity["private_key"],
            identity["public_key"],
            identity["did_document"],
            "correct_password"
        )
        
        with pytest.raises(ValueError, match="Failed to decrypt"):
            KeyBackup.import_identity(backup, "wrong_password")
    
    def test_verify_backup(self, identity, password):
        backup = KeyBackup.export_identity(
            identity["did"],
            identity["private_key"],
            identity["public_key"],
            identity["did_document"],
            password
        )
        
        assert KeyBackup.verify_backup(backup, password) is True
        assert KeyBackup.verify_backup(backup, "wrong") is False
    
    def test_export_to_file(self, identity, password):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".hive") as f:
            filepath = f.name
        
        try:
            KeyBackup.export_to_file(
                identity["did"],
                identity["private_key"],
                identity["public_key"],
                identity["did_document"],
                password,
                filepath,
                metadata={"test": True}
            )
            
            assert Path(filepath).exists()
            
            restored = KeyBackup.import_from_file(filepath, password)
            assert restored["did"] == identity["did"]
            assert restored["metadata"]["test"] is True
        finally:
            os.unlink(filepath)
    
    def test_convenience_functions(self, identity, password):
        backup = create_backup(
            identity["did"],
            identity["private_key"],
            identity["public_key"],
            identity["did_document"],
            password,
            metadata={"convenience": True}
        )
        
        restored = restore_backup(backup_string=backup, password=password)
        
        assert restored["did"] == identity["did"]
        assert restored["metadata"]["convenience"] is True
    
    def test_get_fingerprint(self, identity):
        fp = KeyBackup.get_fingerprint(identity["public_key"])
        
        assert isinstance(fp, str)
        assert len(fp) > 0
    
    def test_metadata_preserved(self, identity, password):
        metadata = {
            "agent_id": "my_agent",
            "origin": "production",
            "tags": ["security", "production"]
        }
        
        backup = KeyBackup.export_identity(
            identity["did"],
            identity["private_key"],
            identity["public_key"],
            identity["did_document"],
            password,
            metadata=metadata
        )
        
        restored = KeyBackup.import_identity(backup, password)
        
        assert restored["metadata"]["agent_id"] == "my_agent"
        assert restored["metadata"]["origin"] == "production"
        assert restored["metadata"]["tags"] == ["security", "production"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
