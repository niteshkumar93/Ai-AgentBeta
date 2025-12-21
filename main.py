# main.py - Main navigation file

import streamlit as st

# Page configuration must be the first Streamlit command
st.set_page_config(
    page_title="Provar AI Test Analyzer",
    layout="wide",
    page_icon="🚀",
    initial_sidebar_state="expanded"
)

# Custom CSS for navigation
st.markdown("""
    <style>
    .nav-header {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
        margin-bottom: 2rem;
    }
    .nav-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        cursor: pointer;
        transition: transform 0.3s;
        margin: 1rem 0;
    }
    .nav-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.2);
    }
    .nav-card h3 {
        color: white;
        margin-bottom: 1rem;
    }
    .nav-card p {
        color: rgba(255,255,255,0.9);
        font-size: 1.1rem;
    }
    .feature-list {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="nav-header">🚀 Provar AI Test Analysis Suite</div>', unsafe_allow_html=True)

st.markdown("---")

# Navigation cards
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 15px; color: white;">
            <h2 style="color: white; text-align: center;">🎯 Provar XML Analysis</h2>
            <p style="color: rgba(255,255,255,0.9); text-align: center; font-size: 1.1rem;">
                Analyze Provar test execution XML reports
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("")
    
    if st.button("📊 Open Provar Analyzer", type="primary", use_container_width=True):
        st.info("ℹ️ To use: Run `streamlit run app.py` in your terminal")
    
    with st.expander("🎯 Provar Features"):
        st.markdown("""
        - **Multi-Browser Testing**: Track failures across Chrome, Firefox, Safari
        - **Project-Based Analysis**: Automatic project detection
        - **Path Tracking**: Full test case path visibility
        - **Baseline Comparison**: Compare against historical results
        - **AI-Powered Analysis**: Get intelligent insights on UI test failures
        - **Batch Processing**: Analyze multiple reports simultaneously
        """)

with col2:
    st.markdown("""
        <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 2rem; border-radius: 15px; color: white;">
            <h2 style="color: white; text-align: center;">🔌 AutomationAPI Analysis</h2>
            <p style="color: rgba(255,255,255,0.9); text-align: center; font-size: 1.1rem;">
                Analyze AutomationAPI test execution XML reports
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("")
    
    if st.button("🔌 Open AutomationAPI Analyzer", type="primary", use_container_width=True):
        st.info("ℹ️ To use: Run `streamlit run pages/1_AutomationAPI.py` in your terminal")
    
    with st.expander("🔌 AutomationAPI Features"):
        st.markdown("""
        - **Endpoint Tracking**: Monitor failures by API endpoint
        - **HTTP Method Analysis**: Analyze GET, POST, PUT, DELETE failures
        - **Status Code Monitoring**: Track HTTP response codes
        - **API Project Detection**: Automatic API project identification
        - **Baseline Comparison**: Compare against API test baselines
        - **AI-Powered Analysis**: Get intelligent insights on API failures
        - **Batch Processing**: Analyze multiple API reports simultaneously
        """)

st.markdown("---")

# Common features section
st.markdown("## 🤖 Common AI-Powered Features")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
        <div class="feature-list">
            <h4>🧠 Intelligent Analysis</h4>
            <ul>
                <li>Root cause identification</li>
                <li>Pattern recognition</li>
                <li>Failure categorization</li>
                <li>Priority recommendations</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
        <div class="feature-list">
            <h4>📝 Auto-Documentation</h4>
            <ul>
                <li>Jira ticket generation</li>
                <li>Detailed error reports</li>
                <li>CSV exports</li>
                <li>Batch analysis reports</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
        <div class="feature-list">
            <h4>💡 Test Improvements</h4>
            <ul>
                <li>Stability suggestions</li>
                <li>Best practice recommendations</li>
                <li>Flakiness detection</li>
                <li>Optimization tips</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Setup instructions
with st.expander("⚙️ Setup Instructions"):
    st.markdown("""
    ### 📁 Project Structure
    
    Create the following structure:
    ```
    your_project/
    ├── main.py                          # This navigation file
    ├── app.py                           # Provar analyzer (your existing file)
    ├── pages/
    │   └── 1_AutomationAPI.py          # AutomationAPI analyzer
    ├── xml_extractor.py                 # Provar XML extractor
    ├── automation_api_extractor.py      # API XML extractor
    ├── baseline_manager.py              # Provar baseline manager
    ├── automation_api_baseline.py       # API baseline manager
    └── ai_reasoner.py                   # AI analysis functions
    ```
    
    ### 🚀 Running the Application
    
    **Option 1: Navigation Page (Recommended)**
    ```bash
    streamlit run main.py
    ```
    
    **Option 2: Direct Access**
    - Provar Analyzer: `streamlit run app.py`
    - AutomationAPI Analyzer: `streamlit run pages/1_AutomationAPI.py`
    
    ### 🔑 Environment Variables
    
    Set up AI credentials (optional):
    ```bash
    export GROQ_API_KEY="your_groq_key"    # Free option
    export OPENAI_API_KEY="your_openai_key" # Paid option
    ```
    
    ### 📦 Dependencies
    
    Install required packages:
    ```bash
    pip install streamlit pandas plotly
    ```
    """)

# Footer
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #666; padding: 2rem;">
        <p>🚀 Provar AI Test Analysis Suite v2.2.0</p>
        <p>Powered by AI • Built with Streamlit</p>
    </div>
""", unsafe_allow_html=True)