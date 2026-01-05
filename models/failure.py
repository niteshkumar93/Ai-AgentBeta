"""
Data models for test failures
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass
class ProvarFailure:
    """Model for Provar test failures"""
    testcase: str
    testcase_path: str
    error: str
    details: str
    source: str
    webBrowserType: str = "Unknown"
    projectCachePath: str = ""
    timestamp: str = "Unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "testcase": self.testcase,
            "testcase_path": self.testcase_path,
            "error": self.error,
            "details": self.details,
            "source": self.source,
            "webBrowserType": self.webBrowserType,
            "projectCachePath": self.projectCachePath,
            "timestamp": self.timestamp
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ProvarFailure':
        """Create from dictionary"""
        return ProvarFailure(
            testcase=data.get("testcase", ""),
            testcase_path=data.get("testcase_path", ""),
            error=data.get("error", ""),
            details=data.get("details", ""),
            source=data.get("source", ""),
            webBrowserType=data.get("webBrowserType", "Unknown"),
            projectCachePath=data.get("projectCachePath", ""),
            timestamp=data.get("timestamp", "Unknown")
        )
    
    def get_signature(self) -> str:
        """Get unique signature for comparison"""
        return f"{self.testcase}|{self.error}"


@dataclass
class AutomationAPIFailure:
    """Model for AutomationAPI test failures"""
    spec_file: str
    test_name: str
    error_summary: str
    error_details: str
    full_stack_trace: str
    execution_time: float
    failure_type: str
    is_skipped: bool
    project: str = "Unknown"
    timestamp: str = "Unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "spec_file": self.spec_file,
            "test_name": self.test_name,
            "error_summary": self.error_summary,
            "error_details": self.error_details,
            "full_stack_trace": self.full_stack_trace,
            "execution_time": self.execution_time,
            "failure_type": self.failure_type,
            "is_skipped": self.is_skipped,
            "project": self.project,
            "timestamp": self.timestamp
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'AutomationAPIFailure':
        """Create from dictionary"""
        return AutomationAPIFailure(
            spec_file=data.get("spec_file", ""),
            test_name=data.get("test_name", ""),
            error_summary=data.get("error_summary", ""),
            error_details=data.get("error_details", ""),
            full_stack_trace=data.get("full_stack_trace", ""),
            execution_time=data.get("execution_time", 0.0),
            failure_type=data.get("failure_type", ""),
            is_skipped=data.get("is_skipped", False),
            project=data.get("project", "Unknown"),
            timestamp=data.get("timestamp", "Unknown")
        )
    
    def get_signature(self) -> str:
        """Get unique signature for comparison"""
        return f"{self.spec_file}|{self.test_name}|{self.error_summary}"


@dataclass
class AnalysisResult:
    """Model for analysis results"""
    filename: str
    project: str
    new_failures: list
    existing_failures: list
    new_count: int
    existing_count: int
    total_count: int
    baseline_exists: bool
    execution_time: str
    stats: Optional[Dict[str, Any]] = None
    grouped_failures: Optional[Dict[str, list]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "filename": self.filename,
            "project": self.project,
            "new_failures": self.new_failures,
            "existing_failures": self.existing_failures,
            "new_count": self.new_count,
            "existing_count": self.existing_count,
            "total_count": self.total_count,
            "baseline_exists": self.baseline_exists,
            "execution_time": self.execution_time,
            "stats": self.stats,
            "grouped_failures": self.grouped_failures
        }