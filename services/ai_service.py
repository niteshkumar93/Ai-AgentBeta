"""
AI service for intelligent failure analysis
"""
from typing import List, Dict, Any, Optional
import streamlit as st
from functools import lru_cache
import hashlib
import json


class AIService:
    """Service for AI-powered analysis operations"""
    
    def __init__(self, ai_reasoner_module):
        """
        Initialize AI service
        
        Args:
            ai_reasoner_module: The ai_reasoner module with AI functions
        """
        self.ai_reasoner = ai_reasoner_module
        self._cache = {}
    
    def generate_summary(
        self, 
        testcase: str, 
        error: str, 
        details: str,
        use_cache: bool = True
    ) -> str:
        """
        Generate AI summary for a single failure
        
        Args:
            testcase: Test case name
            error: Error message
            details: Error details
            use_cache: Whether to use caching (default: True)
            
        Returns:
            AI-generated summary string
        """
        if use_cache:
            cache_key = self._get_cache_key("summary", testcase, error, details)
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        try:
            summary = self.ai_reasoner.generate_ai_summary(testcase, error, details)
            
            if use_cache:
                self._cache[cache_key] = summary
            
            return summary
        
        except Exception as e:
            return f"❌ AI analysis failed: {str(e)}"
    
    def generate_batch_analysis(
        self, 
        failures: List[Dict[str, Any]],
        use_cache: bool = True
    ) -> str:
        """
        Generate batch pattern analysis across multiple failures
        
        Args:
            failures: List of failure dictionaries
            use_cache: Whether to use caching (default: True)
            
        Returns:
            AI-generated batch analysis string
        """
        if not failures:
            return ""
        
        if use_cache:
            # Create cache key from failure signatures
            cache_key = self._get_batch_cache_key(failures)
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        try:
            analysis = self.ai_reasoner.generate_batch_analysis(failures)
            
            if use_cache:
                self._cache[cache_key] = analysis
            
            return analysis
        
        except Exception as e:
            return f"❌ Batch analysis failed: {str(e)}"
    
    def generate_jira_ticket(
        self,
        testcase: str,
        error: str,
        details: str,
        ai_analysis: str = ""
    ) -> str:
        """
        Generate Jira ticket content
        
        Args:
            testcase: Test case name
            error: Error message
            details: Error details
            ai_analysis: Optional AI analysis to include
            
        Returns:
            Jira ticket content as markdown
        """
        try:
            return self.ai_reasoner.generate_jira_ticket(
                testcase, 
                error, 
                details, 
                ai_analysis
            )
        
        except Exception as e:
            return f"❌ Jira generation failed: {str(e)}"
    
    def suggest_improvements(
        self,
        testcase: str,
        error: str,
        details: str
    ) -> str:
        """
        Generate test improvement suggestions
        
        Args:
            testcase: Test case name
            error: Error message
            details: Error details
            
        Returns:
            Improvement suggestions as string
        """
        try:
            return self.ai_reasoner.suggest_test_improvements(
                testcase, 
                error, 
                details
            )
        
        except Exception as e:
            return f"❌ Improvement suggestions failed: {str(e)}"
    
    def _get_cache_key(self, operation: str, *args) -> str:
        """
        Generate cache key for AI operations
        
        Args:
            operation: Type of operation (summary, jira, etc.)
            *args: Arguments to hash
            
        Returns:
            Cache key string
        """
        # Combine all args into a single string
        content = f"{operation}|" + "|".join(str(arg) for arg in args)
        
        # Generate hash
        hash_obj = hashlib.md5(content.encode())
        return f"{operation}_{hash_obj.hexdigest()}"
    
    def _get_batch_cache_key(self, failures: List[Dict[str, Any]]) -> str:
        """
        Generate cache key for batch analysis
        
        Args:
            failures: List of failure dictionaries
            
        Returns:
            Cache key string
        """
        # Create a deterministic representation of failures
        signatures = []
        for f in failures:
            if 'testcase' in f:  # Provar
                sig = f"{f.get('testcase')}|{f.get('error')}"
            else:  # AutomationAPI
                sig = f"{f.get('test_name')}|{f.get('error_summary')}"
            signatures.append(sig)
        
        # Sort to ensure consistent ordering
        signatures.sort()
        content = "batch|" + "|".join(signatures)
        
        hash_obj = hashlib.md5(content.encode())
        return f"batch_{hash_obj.hexdigest()}"
    
    def clear_cache(self):
        """Clear the AI cache"""
        self._cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache stats
        """
        return {
            'total_cached': len(self._cache),
            'summary_cached': len([k for k in self._cache.keys() if k.startswith('summary_')]),
            'batch_cached': len([k for k in self._cache.keys() if k.startswith('batch_')])
        }


class AIServiceWithStreamlit(AIService):
    """AI Service with Streamlit session state caching"""
    
    def __init__(self, ai_reasoner_module):
        """Initialize with Streamlit session state for caching"""
        super().__init__(ai_reasoner_module)
        
        # Use Streamlit session state for persistent cache
        if 'ai_cache' not in st.session_state:
            st.session_state.ai_cache = {}
        
        self._cache = st.session_state.ai_cache
    
    def clear_cache(self):
        """Clear the AI cache from session state"""
        st.session_state.ai_cache.clear()
        self._cache = st.session_state.ai_cache