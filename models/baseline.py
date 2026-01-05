"""
Baseline data models
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class Baseline:
    """Model for baseline data"""
    id: str
    project: str
    platform: str  # 'provar' or 'automation_api'
    failures: List[Dict[str, Any]]
    created_at: str
    label: Optional[str] = None
    failure_count: int = 0
    
    def __post_init__(self):
        """Calculate failure count after initialization"""
        if self.failure_count == 0:
            self.failure_count = len(self.failures)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "project": self.project,
            "platform": self.platform,
            "failures": self.failures,
            "created_at": self.created_at,
            "label": self.label,
            "failure_count": self.failure_count
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Baseline':
        """Create from dictionary"""
        return Baseline(
            id=data.get("id", ""),
            project=data.get("project", ""),
            platform=data.get("platform", "provar"),
            failures=data.get("failures", []),
            created_at=data.get("created_at", ""),
            label=data.get("label"),
            failure_count=data.get("failure_count", 0)
        )
    
    def get_signature_set(self) -> set:
        """Get set of failure signatures for comparison"""
        signatures = set()
        
        if self.platform == "provar":
            for failure in self.failures:
                sig = f"{failure.get('testcase')}|{failure.get('error')}"
                signatures.add(sig)
        else:  # automation_api
            for failure in self.failures:
                sig = f"{failure.get('spec_file')}|{failure.get('test_name')}|{failure.get('error_summary', '')}"
                signatures.add(sig)
        
        return signatures


@dataclass
class BaselineComparison:
    """Model for baseline comparison results"""
    new_failures: List[Dict[str, Any]]
    existing_failures: List[Dict[str, Any]]
    baseline_id: Optional[str] = None
    baseline_label: Optional[str] = None
    
    @property
    def new_count(self) -> int:
        """Count of new failures"""
        return len(self.new_failures)
    
    @property
    def existing_count(self) -> int:
        """Count of existing failures"""
        return len(self.existing_failures)
    
    @property
    def total_count(self) -> int:
        """Total count of all failures"""
        return self.new_count + self.existing_count
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "new_failures": self.new_failures,
            "existing_failures": self.existing_failures,
            "new_count": self.new_count,
            "existing_count": self.existing_count,
            "total_count": self.total_count,
            "baseline_id": self.baseline_id,
            "baseline_label": self.baseline_label
        }


@dataclass
class BaselineMetadata:
    """Lightweight baseline metadata (without full failure list)"""
    id: str
    project: str
    platform: str
    created_at: str
    label: Optional[str]
    failure_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "project": self.project,
            "platform": self.platform,
            "created_at": self.created_at,
            "label": self.label,
            "failure_count": self.failure_count
        }
    
    @staticmethod
    def from_baseline(baseline: Baseline) -> 'BaselineMetadata':
        """Create metadata from full baseline"""
        return BaselineMetadata(
            id=baseline.id,
            project=baseline.project,
            platform=baseline.platform,
            created_at=baseline.created_at,
            label=baseline.label,
            failure_count=baseline.failure_count
        )