"""
Navigation component with sidebar tree structure
"""
import streamlit as st
from typing import Dict, Any, Optional


class NavigationMenu:
    """Navigation menu with hierarchical structure"""
    
    # Navigation structure
    MENU_ITEMS = {
        "dashboard": {
            "label": "📊 Dashboard",
            "icon": "📊",
            "title": "Dashboard Overview",
            "description": "View overall test health and recent activity"
        },
        "provar": {
            "label": "📁 Provar Reports",
            "icon": "📁",
            "title": "Provar Regression Reports",
            "description": "Analyze Provar XML test reports"
        },
        "automation_api": {
            "label": "🔧 AutomationAPI Reports",
            "icon": "🔧",
            "title": "AutomationAPI Reports",
            "description": "Analyze AutomationAPI XML test reports"
        },
        "baselines": {
            "label": "📈 Baselines",
            "icon": "📈",
            "title": "Baseline Management",
            "description": "View and manage test baselines"
        },
        "trends": {
            "label": "📉 Trends",
            "icon": "📉",
            "title": "Trend Analysis",
            "description": "Track test metrics over time"
        },
        "settings": {
            "label": "⚙️ Settings",
            "icon": "⚙️",
            "title": "Application Settings",
            "description": "Configure app preferences and integrations"
        }
    }
    
    @staticmethod
    def render_navigation() -> str:
        """
        Render navigation menu and return selected page
        
        Returns:
            Selected page key (e.g., 'dashboard', 'provar', etc.)
        """
        # Initialize session state for navigation
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 'dashboard'
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🧭 Navigation")
        
        # Render navigation buttons
        for key, item in NavigationMenu.MENU_ITEMS.items():
            # Highlight current page
            is_current = st.session_state.current_page == key
            button_type = "primary" if is_current else "secondary"
            
            if st.sidebar.button(
                item["label"],
                key=f"nav_{key}",
                use_container_width=True,
                type=button_type,
                help=item["description"]
            ):
                st.session_state.current_page = key
                st.rerun()
        
        st.sidebar.markdown("---")
        
        return st.session_state.current_page
    
    @staticmethod
    def get_page_info(page_key: str) -> Dict[str, Any]:
        """
        Get page information
        
        Args:
            page_key: Page identifier
            
        Returns:
            Dictionary with page info
        """
        return NavigationMenu.MENU_ITEMS.get(page_key, {})
    
    @staticmethod
    def render_page_header(page_key: str):
        """
        Render page header with title and description
        
        Args:
            page_key: Page identifier
        """
        info = NavigationMenu.get_page_info(page_key)
        if info:
            st.markdown(f"# {info['title']}")
            st.caption(info['description'])
            st.markdown("---")


class BreadcrumbNavigation:
    """Breadcrumb navigation for hierarchical pages"""
    
    @staticmethod
    def render_breadcrumbs(path: list):
        """
        Render breadcrumb navigation
        
        Args:
            path: List of breadcrumb items [(label, page_key), ...]
        """
        if not path:
            return
        
        breadcrumb_html = '<div style="margin-bottom: 1rem; color: #666;">'
        
        for i, (label, page_key) in enumerate(path):
            if i > 0:
                breadcrumb_html += ' <span style="margin: 0 0.5rem;">›</span> '
            
            if i == len(path) - 1:
                # Current page - not clickable
                breadcrumb_html += f'<span style="color: #1f77b4; font-weight: 600;">{label}</span>'
            else:
                # Clickable breadcrumb
                breadcrumb_html += f'<span style="cursor: pointer;">{label}</span>'
        
        breadcrumb_html += '</div>'
        
        st.markdown(breadcrumb_html, unsafe_allow_html=True)


class QuickActions:
    """Quick action buttons for common tasks"""
    
    @staticmethod
    def render_quick_actions():
        """Render quick action section in sidebar"""
        st.sidebar.markdown("---")
        st.sidebar.markdown("### ⚡ Quick Actions")
        
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            if st.button("📤 Upload", key="quick_upload", use_container_width=True):
                # Navigate to appropriate upload page
                if 'current_page' in st.session_state:
                    if st.session_state.current_page not in ['provar', 'automation_api']:
                        st.session_state.current_page = 'provar'
                        st.rerun()
        
        with col2:
            if st.button("💾 Save", key="quick_save", use_container_width=True):
                st.toast("💡 Tip: Use the Actions tab to save baselines")
        
        col3, col4 = st.sidebar.columns(2)
        
        with col3:
            if st.button("🔄 Sync", key="quick_sync", use_container_width=True):
                # Trigger sync operation
                if 'baseline_service' in st.session_state:
                    with st.spinner("Syncing..."):
                        try:
                            synced = st.session_state.baseline_service.sync_from_github()
                            st.toast(f"✅ {synced} baseline(s) synced", icon="✅")
                        except Exception as e:
                            st.toast(f"❌ Sync failed: {str(e)}", icon="❌")
        
        with col4:
            if st.button("🔍 Search", key="quick_search", use_container_width=True):
                st.session_state.show_search = not st.session_state.get('show_search', False)


class NavigationState:
    """Manage navigation state across sessions"""
    
    @staticmethod
    def initialize():
        """Initialize navigation state"""
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 'dashboard'
        
        if 'navigation_history' not in st.session_state:
            st.session_state.navigation_history = ['dashboard']
        
        if 'show_search' not in st.session_state:
            st.session_state.show_search = False
    
    @staticmethod
    def navigate_to(page_key: str):
        """
        Navigate to a specific page
        
        Args:
            page_key: Page identifier
        """
        if page_key in NavigationMenu.MENU_ITEMS:
            # Add to history
            if 'navigation_history' not in st.session_state:
                st.session_state.navigation_history = []
            
            st.session_state.navigation_history.append(page_key)
            st.session_state.current_page = page_key
    
    @staticmethod
    def go_back():
        """Navigate back to previous page"""
        if len(st.session_state.get('navigation_history', [])) > 1:
            st.session_state.navigation_history.pop()
            st.session_state.current_page = st.session_state.navigation_history[-1]
            st.rerun()
    
    @staticmethod
    def get_current_page() -> str:
        """Get current page key"""
        return st.session_state.get('current_page', 'dashboard')


# Custom CSS for navigation
NAVIGATION_CSS = """
<style>
/* Navigation button customization */
.stButton > button[kind="secondary"] {
    background-color: transparent;
    border: 1px solid #e0e0e0;
    color: #333;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
    color: white;
    font-weight: 600;
}

.stButton > button:hover {
    transform: translateX(5px);
    transition: transform 0.2s ease;
}

/* Breadcrumb styling */
.breadcrumb {
    font-size: 0.9rem;
    padding: 0.5rem 0;
    color: #666;
}

.breadcrumb-item {
    display: inline-block;
    margin: 0 0.25rem;
}

.breadcrumb-separator {
    margin: 0 0.5rem;
    color: #999;
}

/* Quick action buttons */
.quick-action-btn {
    padding: 0.5rem;
    text-align: center;
    border-radius: 8px;
    background: #f0f2f6;
    cursor: pointer;
    transition: all 0.2s ease;
}

.quick-action-btn:hover {
    background: #e0e2e6;
    transform: scale(1.05);
}

/* Page header styling */
.page-header {
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 2px solid #e0e0e0;
}

.page-title {
    font-size: 2rem;
    font-weight: bold;
    color: #1f77b4;
    margin-bottom: 0.5rem;
}

.page-description {
    color: #666;
    font-size: 1rem;
}
</style>
"""


def apply_navigation_css():
    """Apply navigation CSS to the app"""
    st.markdown(NAVIGATION_CSS, unsafe_allow_html=True)