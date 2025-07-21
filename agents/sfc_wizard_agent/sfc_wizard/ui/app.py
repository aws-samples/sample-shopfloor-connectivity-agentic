"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

Main Streamlit application for the SFC Wizard Agent UI.

This module contains the main Streamlit application that provides a web-based
interface for interacting with the SFC Wizard Agent.
"""

import os
import streamlit as st
from pathlib import Path
import threading
import webbrowser
import time

# Import UI components
from sfc_wizard.ui.components.chat import render_chat_interface, render_chat_controls
from sfc_wizard.ui.components.config_viewer import render_config_viewer, extract_configurations_from_messages
from sfc_wizard.ui.components.config_editor import render_config_editor
from sfc_wizard.ui.components.visualization import render_visualization_display, extract_visualizations_from_messages, create_sample_visualizations


# Set page configuration
def configure_page():
    """Configure the Streamlit page settings."""
    st.set_page_config(
        page_title="SFC Wizard Agent",
        page_icon="🏭",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Load custom CSS
    css_path = Path(__file__).parent / "assets" / "css" / "style.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    
    # Add JavaScript for screen size detection
    st.markdown("""
    <script>
        // Function to detect screen size and store in session state
        function detectScreenSize() {
            const width = window.innerWidth;
            
            // Store in sessionStorage for retrieval
            sessionStorage.setItem("screen_width", width);
            
            // Try to communicate with Streamlit
            if (window.parent.streamlit) {
                const data = {
                    width: width,
                    height: window.innerHeight
                };
                window.parent.streamlit.setComponentValue(data);
            }
        }
        
        // Run on load and on resize
        window.addEventListener('load', detectScreenSize);
        window.addEventListener('resize', detectScreenSize);
    </script>
    """, unsafe_allow_html=True)
    
    # Initialize screen width in session state if not already set
    if "screen_width" not in st.session_state:
        st.session_state.screen_width = 1200  # Default to desktop size


def render_header():
    """Render the application header with logo and title."""
    # Detect screen size for responsive layout
    screen_width = st.session_state.get("screen_width", 1200)
    is_mobile = screen_width < 768
    
    # Use different column ratios based on screen size
    if is_mobile:
        col1, col2 = st.columns([1, 2])  # More compact for mobile
    else:
        col1, col2 = st.columns([1, 5])  # Original ratio for desktop

    with col1:
        logo_path = os.path.join(
            os.path.dirname(__file__), "assets", "img", "sfc_logo.png"
        )
        if os.path.exists(logo_path):
            # Adjust logo size based on screen size
            logo_width = 80 if is_mobile else 100
            st.image(logo_path, width=logo_width)
        else:
            # If local logo doesn't exist, use the URL provided
            logo_width = 80 if is_mobile else 100
            st.image(
                "https://yt3.googleusercontent.com/oPLw92IzMo__EbsS38oBdN3b9s_lec0WYMei7tHmQcb2UodbgVLmADG2yaWB1XVxuTWFFhyjjQ=s160-c-k-c0x00ffffff-no-rj",
                width=logo_width,
            )

    with col2:
        # Adjust title size based on screen size
        if is_mobile:
            st.markdown("## AWS Shopfloor Connectivity Wizard")
        else:
            st.title("AWS Shopfloor Connectivity Wizard")
        st.markdown("*Your AI assistant for AWS Shopfloor Connectivity configurations*")


def render_sidebar():
    """Render the sidebar navigation."""
    # Detect screen size for responsive layout
    screen_width = st.session_state.get("screen_width", 1200)
    is_mobile = screen_width < 768
    
    # Adjust title size based on screen size
    if is_mobile:
        st.sidebar.markdown("## Navigation")
    else:
        st.sidebar.title("Navigation")

    # Navigation options
    pages = {
        "Chat": "💬",
        "Configuration": "⚙️",
        "Visualization": "📊",
        "Documentation": "📚",
    }

    # Create navigation with more compact layout for mobile
    if is_mobile:
        # Use horizontal radio buttons for mobile
        selected_page = st.sidebar.radio(
            "Go to", 
            list(pages.keys()), 
            format_func=lambda x: f"{pages[x]} {x}",
            horizontal=True
        )
    else:
        # Use vertical radio buttons for desktop
        selected_page = st.sidebar.radio(
            "Go to", 
            list(pages.keys()), 
            format_func=lambda x: f"{pages[x]} {x}"
        )

    # Additional sidebar content
    st.sidebar.divider()
    
    # More concise info text for mobile
    if is_mobile:
        st.sidebar.info("SFC Wizard Agent UI - Chat or use specific features.")
    else:
        st.sidebar.info(
            "This UI provides a graphical interface to the SFC Wizard Agent. "
            "Use the chat to interact with the agent or navigate to specific features."
        )
    
    # Add debug mode toggle (hidden in an expander)
    with st.sidebar.expander("Advanced", expanded=False):
        # Initialize debug mode in session state if it doesn't exist
        if "debug_mode" not in st.session_state:
            st.session_state.debug_mode = False
        
        # Add debug mode toggle
        st.session_state.debug_mode = st.checkbox(
            "Debug Mode",
            value=st.session_state.debug_mode,
            help="Enable debug information and performance metrics"
        )
        
        # Show performance metrics if debug mode is enabled
        if st.session_state.debug_mode:
            # Get cache statistics
            try:
                from sfc_wizard.ui.utils.caching import get_cache_stats
                cache_stats = get_cache_stats()
                
                st.markdown("### Cache Statistics")
                st.markdown(f"- Entries: {cache_stats['cache_entries']}")
                st.markdown(f"- Oldest: {cache_stats['oldest_entry']}")
                st.markdown(f"- Newest: {cache_stats['newest_entry']}")
            except ImportError:
                st.markdown("Cache statistics not available")
            
            # Show memory usage
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_usage = process.memory_info().rss / 1024 / 1024  # Convert to MB
            
            st.markdown("### Memory Usage")
            st.markdown(f"- Current: {memory_usage:.2f} MB")
            
            # Show session state size
            import sys
            import pickle
            
            try:
                session_state_size = sys.getsizeof(pickle.dumps(st.session_state)) / 1024  # Convert to KB
                st.markdown(f"- Session State: {session_state_size:.2f} KB")
            except:
                st.markdown("- Session State: Unable to calculate size")

    return selected_page


def render_welcome_message():
    """Render the welcome message on the main page."""
    st.markdown(
        """
    ## Welcome to the SFC Wizard Agent UI
    
    This interface allows you to interact with the AWS Shopfloor Connectivity Wizard Agent through a user-friendly web interface.
    
    ### Getting Started
    
    - Use the **Chat** tab to communicate with the agent in a conversational manner
    - View and edit SFC configurations in the **Configuration** tab
    - Explore data visualizations in the **Visualization** tab
    - Access documentation and help in the **Documentation** tab
    
    Select an option from the sidebar to begin.
    """
    )


def render_chat_page():
    """Render the chat interface page."""
    # Detect screen size for responsive layout
    screen_width = st.session_state.get("screen_width", 1200)
    is_mobile = screen_width < 768
    
    # Adjust header size based on screen size
    if is_mobile:
        st.markdown("## 💬 Chat with SFC Wizard")
    else:
        st.header("💬 Chat with SFC Wizard")
    
    # More concise description for mobile
    if is_mobile:
        st.markdown("Chat with the SFC Wizard Agent.")
    else:
        st.markdown("Use this chat interface to communicate with the SFC Wizard Agent.")
    
    # Add chat controls (clear conversation, reinitialize agent)
    render_chat_controls()
    
    # Add a separator
    st.divider()
    
    # Render the main chat interface
    render_chat_interface()


def render_config_page():
    """Render the configuration page."""
    # Detect screen size for responsive layout
    screen_width = st.session_state.get("screen_width", 1200)
    is_mobile = screen_width < 768
    is_tablet = screen_width >= 768 and screen_width < 992
    
    # Adjust header size based on screen size
    if is_mobile:
        st.markdown("## ⚙️ Configuration")
    else:
        st.header("⚙️ Configuration")
    
    # More concise description for mobile
    if is_mobile:
        st.markdown("Manage SFC configurations.")
    else:
        st.markdown("View and edit SFC configurations.")
    
    # Extract configurations from messages if they exist
    extract_configurations_from_messages()
    
    # Set default active tab if not already set
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "View Configurations"
    
    # Create tabs for viewer and editor
    tab_names = ["View Configurations", "Edit Configuration"]
    active_tab_index = tab_names.index(st.session_state.active_tab) if st.session_state.active_tab in tab_names else 0
    tabs = st.tabs(tab_names)
    
    with tabs[0]:
        # Render the configuration viewer
        render_config_viewer()
        
        # Add a button to create a new configuration
        # Use full width button on mobile for better touch targets
        if is_mobile:
            col1, = st.columns(1)
            with col1:
                if st.button("Create New Configuration", use_container_width=True):
                    st.session_state.active_tab = "Edit Configuration"
                    st.session_state.config_to_edit = None
                    st.rerun()
        else:
            if st.button("Create New Configuration"):
                st.session_state.active_tab = "Edit Configuration"
                st.session_state.config_to_edit = None
                st.rerun()
    
    with tabs[1]:
        # Check if there's a configuration to edit
        config_to_edit = st.session_state.get("config_to_edit", None)
        
        if config_to_edit:
            # Render the configuration editor with the selected configuration
            render_config_editor(
                initial_config=config_to_edit.get("config"),
                name=config_to_edit.get("name")
            )
            
            # Add a button to go back to the viewer
            # Use full width button on mobile for better touch targets
            if is_mobile:
                if st.button("Back to Viewer", use_container_width=True):
                    st.session_state.active_tab = "View Configurations"
                    st.session_state.config_to_edit = None
                    st.rerun()
            else:
                if st.button("Back to Viewer"):
                    st.session_state.active_tab = "View Configurations"
                    st.session_state.config_to_edit = None
                    st.rerun()
        else:
            # Render the configuration editor with a new configuration
            render_config_editor()
            
            # Add a button to go back to the viewer
            # Use full width button on mobile for better touch targets
            if is_mobile:
                if st.button("Back to Viewer", use_container_width=True):
                    st.session_state.active_tab = "View Configurations"
                    st.rerun()
            else:
                if st.button("Back to Viewer"):
                    st.session_state.active_tab = "View Configurations"
                    st.rerun()


def render_visualization_page():
    """Render the visualization page."""
    # Detect screen size for responsive layout
    screen_width = st.session_state.get("screen_width", 1200)
    is_mobile = screen_width < 768
    
    # Adjust header size based on screen size
    if is_mobile:
        st.markdown("## 📊 Visualization")
    else:
        st.header("📊 Visualization")
    
    # More concise description for mobile
    if is_mobile:
        st.markdown("View SFC data visualizations.")
    else:
        st.markdown("Explore SFC data visualizations.")
    
    # Extract visualizations from messages if they exist
    extract_visualizations_from_messages()
    
    # Create sample visualizations if none exist (for demonstration)
    create_sample_visualizations()
    
    # Render the visualization display
    render_visualization_display()


def render_documentation_page():
    """Render the documentation page."""
    # Detect screen size for responsive layout
    screen_width = st.session_state.get("screen_width", 1200)
    is_mobile = screen_width < 768
    
    # Adjust header size based on screen size
    if is_mobile:
        st.markdown("## 📚 Documentation")
    else:
        st.header("📚 Documentation")
    
    # More concise description for mobile
    if is_mobile:
        st.markdown("Help resources.")
    else:
        st.markdown("Access documentation and help resources.")

    # Responsive documentation content
    if is_mobile:
        # More compact layout for mobile
        st.markdown(
            """
        ### AWS Shopfloor Connectivity
        
        Framework for industrial data connectivity:
        
        - Connect to industrial equipment
        - Process data
        - Send to AWS services
        
        ### Resources
        
        - [AWS SFC Docs](https://docs.aws.amazon.com/iot-sitewise/latest/userguide/connectivity-sfc.html)
        - [GitHub Repo](https://github.com/aws-samples/shopfloor-connectivity)
        """
        )
    else:
        # Full content for desktop
        st.markdown(
            """
        ### AWS Shopfloor Connectivity (SFC)
        
        AWS Shopfloor Connectivity is a framework for industrial data connectivity that helps you:
        
        - Connect to industrial equipment and systems
        - Process and transform data
        - Send data to AWS services
        
        ### Resources
        
        - [AWS SFC Documentation](https://docs.aws.amazon.com/iot-sitewise/latest/userguide/connectivity-sfc.html)
        - [GitHub Repository](https://github.com/aws-samples/shopfloor-connectivity)
        """
        )


def render_performance_settings():
    """Render performance settings in the sidebar."""
    # Add a section for performance settings
    st.sidebar.divider()
    st.sidebar.markdown("### Performance Settings")
    
    # Initialize performance settings in session state if they don't exist
    if "performance_settings" not in st.session_state:
        st.session_state.performance_settings = {
            "enable_caching": True,
            "cache_ttl": 3600,  # 1 hour in seconds
            "enable_pagination": True,
            "items_per_page": 10,
            "enable_lazy_loading": True,
            "enable_compression": True
        }
    
    # Create a form for the settings
    with st.sidebar.expander("Adjust Performance", expanded=False):
        # Caching settings
        st.session_state.performance_settings["enable_caching"] = st.checkbox(
            "Enable Caching",
            value=st.session_state.performance_settings["enable_caching"],
            help="Cache expensive operations to improve performance"
        )
        
        # Only show cache TTL if caching is enabled
        if st.session_state.performance_settings["enable_caching"]:
            cache_ttl_options = {
                "5 minutes": 300,
                "15 minutes": 900,
                "30 minutes": 1800,
                "1 hour": 3600,
                "2 hours": 7200,
                "4 hours": 14400
            }
            
            selected_ttl = st.selectbox(
                "Cache Duration",
                options=list(cache_ttl_options.keys()),
                index=list(cache_ttl_options.values()).index(st.session_state.performance_settings["cache_ttl"]) if st.session_state.performance_settings["cache_ttl"] in cache_ttl_options.values() else 3,
                help="How long to keep cached data"
            )
            
            st.session_state.performance_settings["cache_ttl"] = cache_ttl_options[selected_ttl]
            
            # Add a button to clear the cache
            if st.button("Clear Cache"):
                try:
                    from sfc_wizard.ui.utils.caching import clear_cache
                    clear_cache()
                    st.success("Cache cleared successfully!")
                except ImportError:
                    st.error("Caching module not available")
        
        # Pagination settings
        st.session_state.performance_settings["enable_pagination"] = st.checkbox(
            "Enable Pagination",
            value=st.session_state.performance_settings["enable_pagination"],
            help="Break large datasets into pages for better performance"
        )
        
        # Only show items per page if pagination is enabled
        if st.session_state.performance_settings["enable_pagination"]:
            st.session_state.performance_settings["items_per_page"] = st.slider(
                "Items Per Page",
                min_value=5,
                max_value=50,
                value=st.session_state.performance_settings["items_per_page"],
                step=5,
                help="Number of items to show per page"
            )
        
        # Lazy loading settings
        st.session_state.performance_settings["enable_lazy_loading"] = st.checkbox(
            "Enable Lazy Loading",
            value=st.session_state.performance_settings["enable_lazy_loading"],
            help="Load content only when needed"
        )
        
        # Compression settings
        st.session_state.performance_settings["enable_compression"] = st.checkbox(
            "Enable Compression",
            value=st.session_state.performance_settings["enable_compression"],
            help="Compress data transfers for better performance"
        )


def main():
    """Main application entry point."""
    # Start timing the page load
    import time
    start_time = time.time()
    
    # Configure the page
    configure_page()
    render_header()

    # Render the sidebar with navigation
    selected_page = render_sidebar()
    
    # Add performance settings to the sidebar
    render_performance_settings()

    # Render the selected page
    if selected_page == "Chat":
        render_chat_page()
    elif selected_page == "Configuration":
        render_config_page()
    elif selected_page == "Visualization":
        render_visualization_page()
    elif selected_page == "Documentation":
        render_documentation_page()
    else:
        render_welcome_message()
    
    # Calculate and display page load time (only in development mode)
    if st.session_state.get("debug_mode", False):
        end_time = time.time()
        load_time = end_time - start_time
        st.sidebar.markdown(f"Page loaded in {load_time:.2f} seconds")


def launch_app(port=8501, open_browser=True, host="localhost", server_headless=True, 
               theme="light", wide_mode=True, allow_remote=False):
    """
    Launch the Streamlit application.

    Args:
        port (int): The port to run the Streamlit app on
        open_browser (bool): Whether to automatically open the browser
        host (str): The host to bind the server to (default: localhost)
        server_headless (bool): Whether to run the server in headless mode
        theme (str): The theme to use (light or dark)
        wide_mode (bool): Whether to use wide mode
        allow_remote (bool): Whether to allow remote connections

    Returns:
        tuple: (str, subprocess.Popen) - The URL where the UI can be accessed and the process object
    """
    import subprocess
    import sys
    import socket

    # Get the path to the current file
    app_path = os.path.abspath(__file__)

    # Construct the command to run Streamlit
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app_path,
        "--server.port",
        str(port),
        "--theme.base",
        theme,
    ]

    # Add server headless mode if specified
    if server_headless:
        cmd.extend(["--server.headless", "true"])

    # Add wide mode if specified
    if wide_mode:
        cmd.extend(["--ui.wideMode", "true"])

    # Configure host for remote access if allowed
    if allow_remote:
        cmd.extend(["--server.address", "0.0.0.0"])
        # Get the machine's IP address for display purposes
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            host = ip_address
        except:
            # Fall back to localhost if we can't determine the IP
            host = "localhost"
    else:
        cmd.extend(["--server.address", host])

    # Start Streamlit in a separate process
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    # URL where the app can be accessed
    url = f"http://{host}:{port}"

    # Open the browser if requested
    if open_browser:
        # Wait a moment for Streamlit to start
        def open_browser_with_delay():
            time.sleep(2)
            webbrowser.open(url)

        threading.Thread(target=open_browser_with_delay).start()

    # Monitor the process output to detect when Streamlit is ready
    def monitor_process_output():
        for line in process.stdout:
            if "You can now view your Streamlit app in your browser" in line:
                print(f"🌐 SFC Wizard UI is running at {url}")
                break

    threading.Thread(target=monitor_process_output, daemon=True).start()

    return url, process


if __name__ == "__main__":
    main()
