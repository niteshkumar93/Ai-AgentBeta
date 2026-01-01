"""
Streamlit App with Automatic GitHub Baseline Storage
"""

import streamlit as st
import xml.etree.ElementTree as ET
from datetime import datetime
from github_storage import GitHubStorage
import os

# ============================================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================================

# GitHub Configuration
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")  # Will use Streamlit secrets
GITHUB_OWNER = st.secrets.get("GITHUB_OWNER", "")  # Your GitHub username
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "")    # Your repository name
GITHUB_BRANCH = "main"  # Branch name

# ============================================================
# INITIALIZE GITHUB STORAGE
# ============================================================

@st.cache_resource
def get_github_storage():
    """Initialize GitHub storage (cached to avoid recreating)"""
    if not all([GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO]):
        return None
    return GitHubStorage(GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH)


# ============================================================
# BASELINE FUNCTIONS
# ============================================================

def save_baseline_to_github(xml_content: str, baseline_name: str) -> bool:
    """
    Save baseline to GitHub automatically
    
    Args:
        xml_content: XML content as string
        baseline_name: Name for the baseline
    
    Returns:
        True if successful, False otherwise
    """
    storage = get_github_storage()
    
    if not storage:
        st.error("⚠️ GitHub storage not configured. Please check your secrets.")
        return False
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{baseline_name}_{timestamp}.xml"
    
    # Save to GitHub
    success = storage.save_baseline(xml_content, filename)
    
    return success


def load_baselines_from_github():
    """
    Load all available baselines from GitHub
    
    Returns:
        List of baseline files
    """
    storage = get_github_storage()
    
    if not storage:
        return []
    
    return storage.list_baselines()


def load_specific_baseline(filename: str) -> str:
    """
    Load a specific baseline from GitHub
    
    Args:
        filename: Name of the baseline file
    
    Returns:
        XML content as string
    """
    storage = get_github_storage()
    
    if not storage:
        return None
    
    return storage.load_baseline(filename)


def delete_baseline_from_github(filename: str) -> bool:
    """
    Delete a baseline from GitHub
    
    Args:
        filename: Name of the baseline file
    
    Returns:
        True if successful, False otherwise
    """
    storage = get_github_storage()
    
    if not storage:
        return False
    
    return storage.delete_baseline(filename)


# ============================================================
# STREAMLIT APP
# ============================================================

def main():
    st.set_page_config(
        page_title="Baseline Manager",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Report Analyzer with GitHub Baseline Storage")
    
    # Check if GitHub is configured
    if not get_github_storage():
        st.warning("⚠️ GitHub storage not configured. Please add your credentials to Streamlit secrets.")
        with st.expander("📖 How to configure GitHub"):
            st.markdown("""
            1. Go to your Streamlit app settings
            2. Click on "Secrets"
            3. Add the following:
            ```toml
            GITHUB_TOKEN = "your_github_token"
            GITHUB_OWNER = "your_github_username"
            GITHUB_REPO = "your_repo_name"
            ```
            """)
        return
    
    # Sidebar - Load Existing Baselines
    with st.sidebar:
        st.header("📁 Saved Baselines")
        
        if st.button("🔄 Refresh Baselines"):
            st.cache_resource.clear()
        
        # Load baselines
        baselines = load_baselines_from_github()
        
        if baselines:
            st.success(f"Found {len(baselines)} baseline(s)")
            
            for baseline in baselines:
                with st.expander(f"📄 {baseline['name']}"):
                    st.write(f"**Size:** {baseline['size']} bytes")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("📥 Load", key=f"load_{baseline['name']}"):
                            xml_content = load_specific_baseline(baseline['name'])
                            if xml_content:
                                st.session_state['loaded_baseline'] = xml_content
                                st.session_state['loaded_baseline_name'] = baseline['name']
                                st.success("✅ Loaded!")
                                st.rerun()
                    
                    with col2:
                        if st.button("🗑️ Delete", key=f"delete_{baseline['name']}"):
                            if delete_baseline_from_github(baseline['name']):
                                st.success("✅ Deleted!")
                                st.rerun()
                            else:
                                st.error("❌ Delete failed")
        else:
            st.info("No baselines found. Upload a report and save it as baseline.")
    
    # Main Area
    st.header("1️⃣ Upload Report (XML)")
    
    uploaded_file = st.file_uploader("Choose an XML file", type=['xml'])
    
    if uploaded_file is not None:
        # Read XML content
        xml_content = uploaded_file.read().decode('utf-8')
        
        # Parse XML for display
        try:
            root = ET.fromstring(xml_content)
            
            st.success("✅ XML file loaded successfully!")
            
            # Display some basic info about the XML
            st.subheader("📋 XML Report Summary")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Root Element", root.tag)
            
            with col2:
                st.metric("Child Elements", len(list(root)))
            
            with col3:
                st.metric("Attributes", len(root.attrib))
            
            # Show XML preview
            with st.expander("👁️ View XML Content"):
                st.code(xml_content, language='xml')
            
            # Analyze Report Section
            st.header("2️⃣ Analyze Report")
            
            analysis_placeholder = st.empty()
            
            with analysis_placeholder.container():
                st.info("📊 Analyzing report...")
                
                # Your analysis logic would go here
                # For demo purposes, just showing some dummy analysis
                
                st.write("**Analysis Results:**")
                st.write("- Total elements analyzed: ", len(list(root.iter())))
                st.write("- Report is valid XML ✅")
                st.write("- Ready to save as baseline")
            
            # Save as Baseline Section
            st.header("3️⃣ Save as Baseline")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                baseline_name = st.text_input(
                    "Baseline Name",
                    value=f"baseline_{datetime.now().strftime('%Y%m%d')}",
                    help="Enter a name for this baseline (timestamp will be added automatically)"
                )
            
            with col2:
                st.write("")  # Spacing
                st.write("")  # Spacing
                save_button = st.button("💾 Save as Baseline", type="primary")
            
            if save_button:
                if baseline_name:
                    with st.spinner("Saving to GitHub..."):
                        success = save_baseline_to_github(xml_content, baseline_name)
                    
                    if success:
                        st.success("✅ Baseline saved to GitHub successfully!")
                        st.balloons()
                        # Clear cache to show new baseline in sidebar
                        st.cache_resource.clear()
                    else:
                        st.error("❌ Failed to save baseline. Please check your GitHub configuration.")
                else:
                    st.warning("⚠️ Please enter a baseline name")
            
        except ET.ParseError as e:
            st.error(f"❌ Invalid XML file: {str(e)}")
    
    # Show loaded baseline if exists
    if 'loaded_baseline' in st.session_state:
        st.header("4️⃣ Loaded Baseline")
        
        st.info(f"📄 Currently loaded: **{st.session_state.get('loaded_baseline_name', 'Unknown')}**")
        
        with st.expander("👁️ View Loaded Baseline"):
            st.code(st.session_state['loaded_baseline'], language='xml')
        
        if st.button("🗑️ Clear Loaded Baseline"):
            del st.session_state['loaded_baseline']
            del st.session_state['loaded_baseline_name']
            st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown("💡 **Tip:** Your baselines are automatically saved to GitHub and will persist even when the app goes to sleep!")


if __name__ == "__main__":
    main()