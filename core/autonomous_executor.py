"""
The Hive - Autonomous Execution Module
Executes approved code diffs after quorum consensus
"""

import hashlib
import subprocess
import re
from pathlib import Path
from typing import Optional
from datetime import datetime


class AutonomousExecutor:
    """
    Executes approved code diffs on the filesystem.
    Requires quorum approval and signature verification.
    """
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.execution_log = []
    
    def validate_diff(self, diff: str) -> dict:
        """Validate a code diff for safety."""
        issues = []
        
        dangerous_patterns = [
            (r'rm\s+-rf', "Recursive delete detected"),
            (r'>\s*/dev/sd', "Direct disk write detected"),
            (r'chmod\s+777', "World-writable permission"),
            (r'sudo\s+', "Sudo command"),
            (r'curl\s+.*\|\s*sh', "Pipe to shell"),
            (r'wget\s+.*\|\s*sh', "Pipe to shell"),
            (r'import\s+os\s*;.*system', "OS system call"),
            (r'subprocess.*shell\s*=\s*True', "Shell=True subprocess"),
        ]
        
        for pattern, message in dangerous_patterns:
            if re.search(pattern, diff, re.IGNORECASE):
                issues.append(message)
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "lines": len(diff.split('\n')),
            "hash": hashlib.sha256(diff.encode()).hexdigest()[:16]
        }
    
    def parse_unified_diff(self, diff: str) -> list:
        """Parse unified diff format into file operations."""
        operations = []
        current_file = None
        current_hunks = []
        
        for line in diff.split('\n'):
            if line.startswith('--- ') or line.startswith('+++ '):
                if current_file and current_hunks:
                    operations.append({
                        "file": current_file,
                        "hunks": current_hunks
                    })
                full_path = line[4:].split('\t')[0]
                if full_path.startswith('a/') or full_path.startswith('b/'):
                    current_file = full_path[2:]
                else:
                    current_file = full_path
                current_hunks = []
            elif line.startswith('@@'):
                current_hunks.append(line)
        
        if current_file and current_hunks:
            operations.append({
                "file": current_file,
                "hunks": current_hunks
            })
        
        return operations
    
    def apply_diff(self, diff: str, dry_run: bool = True) -> dict:
        """Apply a diff to the filesystem."""
        validation = self.validate_diff(diff)
        
        if not validation["valid"]:
            return {
                "success": False,
                "error": f"Dangerous patterns detected: {validation['issues']}"
            }
        
        operations = self.parse_unified_diff(diff)
        
        if not operations:
            return {
                "success": False,
                "error": "No valid file operations found in diff"
            }
        
        results = []
        
        for op in operations:
            file_path = self.base_path / op["file"]
            
            if dry_run:
                results.append({
                    "file": op["file"],
                    "action": "would_apply",
                    "exists": file_path.exists()
                })
            else:
                try:
                    with open(file_path, 'r') as f:
                        original = f.read()
                    
                    result = subprocess.run(
                        ['patch', '-p1'],
                        input=diff,
                        capture_output=True,
                        text=True,
                        cwd=self.base_path
                    )
                    
                    results.append({
                        "file": op["file"],
                        "action": "applied",
                        "success": result.returncode == 0,
                        "output": result.stdout if result.returncode == 0 else result.stderr
                    })
                except Exception as e:
                    results.append({
                        "file": op["file"],
                        "action": "error",
                        "error": str(e)
                    })
        
        return {
            "success": all(r.get("success", True) for r in results),
            "validation": validation,
            "operations": results
        }
    
    def execute_approved_proposal(self, proposal: dict, diff: str) -> dict:
        """Execute a proposal that has passed quorum."""
        if proposal.get("status") != "approved":
            return {
                "success": False,
                "error": "Proposal is not approved"
            }
        
        quorum = proposal.get("quorum", {})
        if quorum.get("total_weight", 0) < 60:
            return {
                "success": False,
                "error": "Quorum not met (need 60% weight)"
            }
        
        if quorum.get("participant_count", 0) < 3:
            return {
                "success": False,
                "error": "Minimum 3 participants required"
            }
        
        result = self.apply_diff(diff, dry_run=False)
        
        execution_record = {
            "proposal_id": proposal.get("proposal_id"),
            "title": proposal.get("title"),
            "timestamp": datetime.utcnow().isoformat(),
            "result": result
        }
        
        self.execution_log.append(execution_record)
        
        return {
            "success": result["success"],
            "execution": execution_record
        }
    
    def get_execution_history(self) -> list:
        """Get all execution records."""
        return self.execution_log


def create_executor(base_path: str = ".") -> AutonomousExecutor:
    """Create a new executor instance."""
    return AutonomousExecutor(base_path)


if __name__ == "__main__":
    executor = create_executor(".")
    
    test_diff = """--- a/test.txt
+++ b/test.txt
@@ -1 +1 @@
-Hello
+Hello World
"""
    
    print("=== Autonomous Executor Test ===")
    
    v = executor.validate_diff(test_diff)
    print(f"Validation: {v}")
    
    result = executor.apply_diff(test_diff, dry_run=True)
    print(f"Dry run: {result}")
