"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

Visualization Component for the SFC Wizard Agent UI.

This module provides components for displaying and interacting with SFC data visualizations,
including charts, graphs, and module visualizations with interactive features like
zooming, panning, and customization options.

The component is designed to be responsive and work well on different screen sizes,
from desktop to mobile devices.
"""

import streamlit as st
import json
import uuid
import os
import io
import base64
import tempfile
from typing import Any, Dict, List, Optional, Union, Tuple, Callable
import matplotlib.pyplot as plt
import matplotlib
import networkx as nx
from PIL import Image
import pandas as pd
import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

from sfc_wizard.ui.utils.session import conversation_state, error_handler
from sfc_wizard.ui.utils.formatting import format_json


class VisualizationDisplay:
    """Class for displaying and interacting with SFC visualizations."""
    
    def __init__(self):
        """Initialize the visualization display."""
        # Initialize session state for visualizations if it doesn't exist
        if "visualizations" not in st.session_state:
            st.session_state.visualizations = []
        
        # Initialize session state for visualization settings
        if "viz_settings" not in st.session_state:
            st.session_state.viz_settings = {
                "theme": "light",
                "default_height": 500,
                "default_width": 800,
                "show_grid": True,
                "show_legend": True,
                "interactive_mode": True,
                # Responsive design settings
                "responsive_mode": True,
                "mobile_breakpoint": 768,
                "tablet_breakpoint": 992,
                "mobile_height": 300,
                "tablet_height": 400,
                "desktop_height": 500,
                "mobile_font_size": 10,
                "tablet_font_size": 12,
                "desktop_font_size": 14
            }
        
        # Initialize screen size if not already set
        if "screen_width" not in st.session_state:
            st.session_state.screen_width = 1200  # Default to desktop size
        
        # Detect screen size using CSS and JavaScript
        self._detect_screen_size()
    
    def _detect_screen_size(self):
        """
        Detect the screen size using Streamlit components and set appropriate values.
        This method uses a hidden div with custom CSS to detect the viewport width.
        """
        # Inject custom CSS for responsive design
        st.markdown("""
        <style>
        /* Responsive adjustments for visualizations */
        @media (max-width: 768px) {
            /* Mobile view adjustments */
            .stPlotlyChart, .stDataFrame {
                max-width: 100% !important;
                overflow-x: auto !important;
            }
            
            /* Adjust button sizes on mobile */
            .stButton button {
                padding: 0.25rem 0.5rem !important;
                font-size: 0.875rem !important;
            }
            
            /* Make columns stack on mobile */
            .row-widget.stHorizontal {
                flex-direction: column !important;
            }
            
            /* Adjust expander padding */
            .streamlit-expanderHeader {
                padding: 0.5rem !important;
            }
            
            /* Adjust font sizes for better readability on small screens */
            .stMarkdown p, .stMarkdown li {
                font-size: 0.9rem !important;
            }
            
            /* Make tabs more compact */
            .stTabs [data-baseweb="tab-list"] {
                gap: 1px;
            }
            
            .stTabs [data-baseweb="tab"] {
                padding-top: 0.25rem;
                padding-bottom: 0.25rem;
                font-size: 0.8rem;
            }
            
            /* Adjust card padding */
            [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
                padding: 0.5rem !important;
            }
        }
        
        @media (min-width: 769px) and (max-width: 992px) {
            /* Tablet view adjustments */
            .stPlotlyChart, .stDataFrame {
                max-width: 100% !important;
            }
            
            /* Adjust font sizes for better readability on medium screens */
            .stMarkdown p, .stMarkdown li {
                font-size: 0.95rem !important;
            }
        }
        
        /* Improved visualization container */
        .visualization-container {
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            padding: 10px;
            margin-bottom: 15px;
            background-color: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        
        .visualization-container:hover {
            box-shadow: 0 3px 8px rgba(0,0,0,0.15);
        }
        
        /* Responsive visualization title */
        .visualization-title {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 10px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        @media (max-width: 768px) {
            .visualization-title {
                font-size: 1rem;
            }
        }
        
        /* Screen size detection div */
        #screen-size-detector {
            height: 0px;
            width: 0px;
            overflow: hidden;
            position: absolute;
        }
        </style>
        
        <div id="screen-size-detector"></div>
        
        <script>
            // Function to update session state with screen width
            function updateScreenSize() {
                const width = window.innerWidth;
                const key = "screen_width";
                const value = width;
                
                // Use Streamlit's setComponentValue when available
                if (window.parent.streamlit) {
                    window.parent.streamlit.setComponentValue({
                        key: key,
                        value: value
                    });
                }
                
                // Store in sessionStorage as fallback
                sessionStorage.setItem(key, value);
            }
            
            // Update on load and resize
            updateScreenSize();
            window.addEventListener('resize', updateScreenSize);
            
            // Add resize observer to adjust visualization heights
            document.addEventListener('DOMContentLoaded', function() {
                const resizeObserver = new ResizeObserver(entries => {
                    for (let entry of entries) {
                        const width = entry.contentRect.width;
                        const charts = document.querySelectorAll('.stPlotlyChart');
                        
                        charts.forEach(chart => {
                            // Adjust height based on width for better aspect ratio
                            if (width < 500) {
                                chart.style.height = Math.max(250, width * 0.75) + 'px';
                            }
                        });
                    }
                });
                
                // Observe the main content area
                const mainContent = document.querySelector('[data-testid="stAppViewContainer"]');
                if (mainContent) {
                    resizeObserver.observe(mainContent);
                }
            });
        </script>
        """, unsafe_allow_html=True)
        
        # Try to get screen width from session storage (fallback)
        # This is a best effort approach since Streamlit reloads on interactions
        try:
            # Use the stored value or default to desktop size
            screen_width = st.session_state.get("screen_width", 1200)
            
            # Determine device type based on screen width
            if screen_width < st.session_state.viz_settings.get("mobile_breakpoint", 768):
                st.session_state.device_type = "mobile"
            elif screen_width < st.session_state.viz_settings.get("tablet_breakpoint", 992):
                st.session_state.device_type = "tablet"
            else:
                st.session_state.device_type = "desktop"
        except Exception as e:
            # Default to desktop if detection fails
            st.session_state.device_type = "desktop"
    
    def _get_responsive_height(self):
        """
        Get the appropriate height based on detected screen size.
        
        Returns:
            int: The height in pixels for visualizations
        """
        device_type = st.session_state.get("device_type", "desktop")
        
        if device_type == "mobile":
            return st.session_state.viz_settings.get("mobile_height", 300)
        elif device_type == "tablet":
            return st.session_state.viz_settings.get("tablet_height", 400)
        else:
            return st.session_state.viz_settings.get("desktop_height", 500)
    
    def _get_responsive_font_size(self):
        """
        Get the appropriate font size based on detected screen size.
        
        Returns:
            int: The font size in pixels
        """
        device_type = st.session_state.get("device_type", "desktop")
        
        if device_type == "mobile":
            return st.session_state.viz_settings.get("mobile_font_size", 10)
        elif device_type == "tablet":
            return st.session_state.viz_settings.get("tablet_font_size", 12)
        else:
            return st.session_state.viz_settings.get("desktop_font_size", 14)
    
    def add_visualization(self, 
                         viz_data: Any, 
                         viz_type: str, 
                         name: str = None, 
                         metadata: Dict[str, Any] = None) -> str:
        """
        Add a visualization to the session state.
        
        Args:
            viz_data: The visualization data (can be matplotlib figure, networkx graph, etc.)
            viz_type: The type of visualization ("chart", "graph", "module", etc.)
            name: The name of the visualization
            metadata: Additional metadata for the visualization
            
        Returns:
            str: The ID of the added visualization
        """
        # Generate a unique ID for the visualization
        viz_id = str(uuid.uuid4())
        
        # Generate a default name if none is provided
        if not name:
            name = f"Visualization {len(st.session_state.visualizations) + 1}"
        
        # Initialize metadata if not provided
        if metadata is None:
            metadata = {}
        
        # Add timestamp to metadata
        metadata["timestamp"] = datetime.datetime.now().isoformat()
        
        # Add the visualization to the session state
        st.session_state.visualizations.append({
            "id": viz_id,
            "name": name,
            "type": viz_type,
            "data": viz_data,
            "metadata": metadata
        })
        
        return viz_id
    
    def get_visualizations(self) -> List[Dict[str, Any]]:
        """
        Get all visualizations in the session state.
        
        Returns:
            List[Dict[str, Any]]: The list of visualizations.
        """
        return st.session_state.visualizations
    
    def get_visualization(self, viz_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific visualization by ID.
        
        Args:
            viz_id: The ID of the visualization.
            
        Returns:
            Optional[Dict[str, Any]]: The visualization or None if not found.
        """
        for viz in st.session_state.visualizations:
            if viz["id"] == viz_id:
                return viz
        return None
    
    def clear_visualizations(self) -> None:
        """
        Clear all visualizations from the session state.
        """
        st.session_state.visualizations = []
    
    def _render_matplotlib_chart(self, fig, name: str, compact: bool = False) -> None:
        """
        Render a matplotlib figure in the UI.
        
        Args:
            fig: The matplotlib figure to render
            name: The name of the visualization
            compact: Whether to use compact mode for mobile/tablet views
        """
        # Check if interactive mode is enabled
        if st.session_state.viz_settings.get("interactive_mode", True):
            # Convert matplotlib figure to plotly for interactive features
            try:
                # Extract data from matplotlib figure
                ax = fig.axes[0]
                lines = ax.get_lines()
                
                # Create a plotly figure
                plotly_fig = go.Figure()
                
                # Add each line from matplotlib to plotly
                for line in lines:
                    x_data = line.get_xdata()
                    y_data = line.get_ydata()
                    line_name = line.get_label() or "Data"
                    plotly_fig.add_trace(go.Scatter(
                        x=x_data, 
                        y=y_data, 
                        mode='lines+markers',
                        name=line_name
                    ))
                
                # Set layout based on matplotlib figure with responsive settings
                plotly_fig.update_layout(
                    title=ax.get_title(),
                    xaxis_title=ax.get_xlabel(),
                    yaxis_title=ax.get_ylabel(),
                    height=self._get_responsive_height(),
                    template=st.session_state.viz_settings.get("theme", "plotly"),
                    showlegend=st.session_state.viz_settings.get("show_legend", True),
                    font=dict(
                        size=self._get_responsive_font_size()
                    ),
                    margin=dict(l=20, r=20, t=40, b=20),  # Tighter margins for small screens
                    autosize=True  # Allow the chart to resize with container
                )
                
                # Configure grid display
                plotly_fig.update_xaxes(showgrid=st.session_state.viz_settings.get("show_grid", True))
                plotly_fig.update_yaxes(showgrid=st.session_state.viz_settings.get("show_grid", True))
                
                # Add range slider for time series data
                if len(lines) > 0 and len(lines[0].get_xdata()) > 10:
                    plotly_fig.update_layout(
                        xaxis=dict(
                            rangeslider=dict(visible=True),
                            type="linear"
                        )
                    )
                
                # Display the interactive plotly figure
                st.plotly_chart(plotly_fig, use_container_width=True)
                
                # Add download options
                col1, col2 = st.columns(2)
                with col1:
                    # Download as PNG
                    buf = io.BytesIO()
                    fig.savefig(buf, format='png', bbox_inches='tight')
                    buf.seek(0)
                    st.download_button(
                        label="Download as PNG",
                        data=buf,
                        file_name=f"{name.lower().replace(' ', '_')}.png",
                        mime="image/png"
                    )
                
                with col2:
                    # Download as interactive HTML
                    html_buf = io.StringIO()
                    html_content = plotly_fig.to_html(include_plotlyjs="cdn")
                    html_buf.write(html_content)
                    st.download_button(
                        label="Download Interactive HTML",
                        data=html_buf.getvalue(),
                        file_name=f"{name.lower().replace(' ', '_')}.html",
                        mime="text/html"
                    )
                
                # Add filtering options
                with st.expander("Filtering Options"):
                    # Create a form for filtering
                    with st.form(f"filter_form_{name}_{uuid.uuid4()}"):
                        # Get data ranges
                        all_x_data = []
                        all_y_data = []
                        for line in lines:
                            all_x_data.extend(line.get_xdata())
                            all_y_data.extend(line.get_ydata())
                        
                        if len(all_x_data) > 0 and len(all_y_data) > 0:
                            min_x = float(min(all_x_data))
                            max_x = float(max(all_x_data))
                            min_y = float(min(all_y_data))
                            max_y = float(max(all_y_data))
                            
                            # X-axis range filter
                            st.subheader("X-Axis Range")
                            x_min, x_max = st.slider(
                                "X-Axis Range",
                                min_value=min_x,
                                max_value=max_x,
                                value=(min_x, max_x),
                                key=f"x_range_{name}_{uuid.uuid4()}"
                            )
                            
                            # Y-axis range filter
                            st.subheader("Y-Axis Range")
                            y_min, y_max = st.slider(
                                "Y-Axis Range",
                                min_value=min_y,
                                max_value=max_y,
                                value=(min_y, max_y),
                                key=f"y_range_{name}_{uuid.uuid4()}"
                            )
                            
                            # Apply filter button
                            filter_submitted = st.form_submit_button("Apply Filter")
                            
                            if filter_submitted:
                                # Update the plotly figure with the new ranges
                                plotly_fig.update_layout(
                                    xaxis=dict(range=[x_min, x_max]),
                                    yaxis=dict(range=[y_min, y_max])
                                )
                                st.plotly_chart(plotly_fig, use_container_width=True)
            
            except Exception as e:
                # If conversion fails, fall back to matplotlib
                st.warning(f"Interactive mode failed, falling back to static display: {str(e)}")
                st.pyplot(fig)
                
                # Create a BytesIO object to save the figure
                buf = io.BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight')
                buf.seek(0)
                
                # Add download button
                st.download_button(
                    label="Download Chart",
                    data=buf,
                    file_name=f"{name.lower().replace(' ', '_')}.png",
                    mime="image/png"
                )
        else:
            # Display the static matplotlib figure
            st.pyplot(fig)
            
            # Create a BytesIO object to save the figure
            buf = io.BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            
            # Add download button
            st.download_button(
                label="Download Chart",
                data=buf,
                file_name=f"{name.lower().replace(' ', '_')}.png",
                mime="image/png"
            )
    
    def _render_networkx_graph(self, graph, name: str, compact: bool = False) -> None:
        """
        Render a NetworkX graph in the UI.
        
        Args:
            graph: The NetworkX graph to render
            name: The name of the visualization
            compact: Whether to use compact mode for mobile/tablet views
        """
        # Check if interactive mode is enabled
        if st.session_state.viz_settings.get("interactive_mode", True):
            try:
                # Create a Plotly figure for interactive graph visualization
                pos = nx.spring_layout(graph)
                
                # Create edge traces
                edge_x = []
                edge_y = []
                edge_text = []
                
                for edge in graph.edges():
                    x0, y0 = pos[edge[0]]
                    x1, y1 = pos[edge[1]]
                    edge_x.extend([x0, x1, None])
                    edge_y.extend([y0, y1, None])
                    edge_text.append(f"{edge[0]} → {edge[1]}")
                
                edge_trace = go.Scatter(
                    x=edge_x, y=edge_y,
                    line=dict(width=1, color='#888'),
                    hoverinfo='text',
                    mode='lines',
                    text=edge_text,
                    name='Connections'
                )
                
                # Create node traces
                node_x = []
                node_y = []
                node_text = []
                node_colors = []
                
                for node in graph.nodes():
                    x, y = pos[node]
                    node_x.append(x)
                    node_y.append(y)
                    
                    # Get node attributes for hover text
                    attrs = graph.nodes[node]
                    attr_text = "<br>".join([f"{k}: {v}" for k, v in attrs.items()])
                    node_text.append(f"{node}<br>{attr_text}" if attr_text else f"{node}")
                    
                    # Determine node color based on type
                    node_type = attrs.get("type", "unknown")
                    if node_type == "source":
                        node_colors.append("green")
                    elif node_type == "processor":
                        node_colors.append("blue")
                    elif node_type == "target":
                        node_colors.append("red")
                    else:
                        node_colors.append("gray")
                
                node_trace = go.Scatter(
                    x=node_x, y=node_y,
                    mode='markers+text',
                    hoverinfo='text',
                    text=node_text,
                    marker=dict(
                        showscale=False,
                        color=node_colors,
                        size=20,
                        line=dict(width=2, color='white')
                    ),
                    textposition="top center",
                    name='Nodes'
                )
                
                # Create the figure
                plotly_fig = go.Figure(data=[edge_trace, node_trace])
                
                # Update layout with responsive settings
                plotly_fig.update_layout(
                    title=name,
                    showlegend=st.session_state.viz_settings.get("show_legend", True),
                    hovermode='closest',
                    margin=dict(b=20, l=5, r=5, t=40),
                    height=self._get_responsive_height(),
                    template=st.session_state.viz_settings.get("theme", "plotly"),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    font=dict(
                        size=self._get_responsive_font_size()
                    ),
                    autosize=True  # Allow the chart to resize with container
                )
                
                # Add interactive features
                plotly_fig.update_layout(
                    updatemenus=[
                        dict(
                            type="buttons",
                            direction="left",
                            buttons=[
                                dict(
                                    args=[{"visible": [True, True]}],
                                    label="Show All",
                                    method="update"
                                ),
                                dict(
                                    args=[{"visible": [True, False]}],
                                    label="Edges Only",
                                    method="update"
                                ),
                                dict(
                                    args=[{"visible": [False, True]}],
                                    label="Nodes Only",
                                    method="update"
                                )
                            ],
                            pad={"r": 10, "t": 10},
                            showactive=True,
                            x=0.1,
                            xanchor="left",
                            y=1.1,
                            yanchor="top"
                        )
                    ]
                )
                
                # Display the interactive plotly figure
                st.plotly_chart(plotly_fig, use_container_width=True)
                
                # Add download options
                col1, col2 = st.columns(2)
                
                with col1:
                    # Create a static version for PNG download
                    plt.figure(figsize=(10, 6))
                    nx.draw(graph, pos, with_labels=True, node_color=node_colors, 
                            node_size=1500, edge_color='gray', arrows=True)
                    
                    # Create a BytesIO object to save the figure
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png', bbox_inches='tight')
                    buf.seek(0)
                    
                    # Add download button for PNG
                    st.download_button(
                        label="Download as PNG",
                        data=buf,
                        file_name=f"{name.lower().replace(' ', '_')}.png",
                        mime="image/png"
                    )
                    
                    # Close the matplotlib figure to free memory
                    plt.close()
                
                with col2:
                    # Download as interactive HTML
                    html_buf = io.StringIO()
                    html_content = plotly_fig.to_html(include_plotlyjs="cdn")
                    html_buf.write(html_content)
                    st.download_button(
                        label="Download Interactive HTML",
                        data=html_buf.getvalue(),
                        file_name=f"{name.lower().replace(' ', '_')}.html",
                        mime="text/html"
                    )
                
                # Add layout options
                with st.expander("Layout Options"):
                    layout_options = ["spring", "circular", "kamada_kawai", "planar", "random", "shell", "spectral"]
                    selected_layout = st.selectbox(
                        "Graph Layout Algorithm",
                        layout_options,
                        index=0,
                        key=f"layout_{name}_{uuid.uuid4()}"
                    )
                    
                    if st.button("Apply Layout", key=f"apply_layout_{name}_{uuid.uuid4()}"):
                        # Calculate new positions based on selected layout
                        if selected_layout == "spring":
                            new_pos = nx.spring_layout(graph)
                        elif selected_layout == "circular":
                            new_pos = nx.circular_layout(graph)
                        elif selected_layout == "kamada_kawai":
                            new_pos = nx.kamada_kawai_layout(graph)
                        elif selected_layout == "planar":
                            try:
                                new_pos = nx.planar_layout(graph)
                            except:
                                new_pos = nx.spring_layout(graph)
                                st.warning("Planar layout failed, falling back to spring layout.")
                        elif selected_layout == "random":
                            new_pos = nx.random_layout(graph)
                        elif selected_layout == "shell":
                            new_pos = nx.shell_layout(graph)
                        elif selected_layout == "spectral":
                            new_pos = nx.spectral_layout(graph)
                        
                        # Update edge trace
                        new_edge_x = []
                        new_edge_y = []
                        for edge in graph.edges():
                            x0, y0 = new_pos[edge[0]]
                            x1, y1 = new_pos[edge[1]]
                            new_edge_x.extend([x0, x1, None])
                            new_edge_y.extend([y0, y1, None])
                        
                        # Update node trace
                        new_node_x = []
                        new_node_y = []
                        for node in graph.nodes():
                            x, y = new_pos[node]
                            new_node_x.append(x)
                            new_node_y.append(y)
                        
                        # Create updated figure
                        updated_edge_trace = go.Scatter(
                            x=new_edge_x, y=new_edge_y,
                            line=dict(width=1, color='#888'),
                            hoverinfo='text',
                            mode='lines',
                            text=edge_text,
                            name='Connections'
                        )
                        
                        updated_node_trace = go.Scatter(
                            x=new_node_x, y=new_node_y,
                            mode='markers+text',
                            hoverinfo='text',
                            text=node_text,
                            marker=dict(
                                showscale=False,
                                color=node_colors,
                                size=20,
                                line=dict(width=2, color='white')
                            ),
                            textposition="top center",
                            name='Nodes'
                        )
                        
                        updated_fig = go.Figure(data=[updated_edge_trace, updated_node_trace])
                        updated_fig.update_layout(
                            title=f"{name} ({selected_layout} layout)",
                            showlegend=st.session_state.viz_settings.get("show_legend", True),
                            hovermode='closest',
                            margin=dict(b=20, l=5, r=5, t=40),
                            height=self._get_responsive_height(),
                            template=st.session_state.viz_settings.get("theme", "plotly"),
                            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            font=dict(
                                size=self._get_responsive_font_size()
                            ),
                            autosize=True  # Allow the chart to resize with container
                        )
                        
                        st.plotly_chart(updated_fig, use_container_width=True)
                
                # Add node filtering options
                if len(graph.nodes()) > 0:
                    with st.expander("Node Filtering"):
                        # Get unique node types
                        node_types = set()
                        for node in graph.nodes():
                            node_type = graph.nodes[node].get("type", "unknown")
                            node_types.add(node_type)
                        
                        # Create checkboxes for each node type
                        selected_types = {}
                        for node_type in node_types:
                            selected_types[node_type] = st.checkbox(
                                f"Show {node_type.capitalize()} Nodes",
                                value=True,
                                key=f"filter_{node_type}_{name}_{uuid.uuid4()}"
                            )
                        
                        if st.button("Apply Filter", key=f"apply_filter_{name}_{uuid.uuid4()}"):
                            # Filter nodes based on selection
                            filtered_nodes = [
                                node for node in graph.nodes()
                                if selected_types.get(graph.nodes[node].get("type", "unknown"), True)
                            ]
                            
                            # Create subgraph with selected nodes
                            subgraph = graph.subgraph(filtered_nodes)
                            
                            # Recalculate layout for the subgraph
                            sub_pos = nx.spring_layout(subgraph)
                            
                            # Create new traces
                            sub_edge_x = []
                            sub_edge_y = []
                            sub_edge_text = []
                            
                            for edge in subgraph.edges():
                                x0, y0 = sub_pos[edge[0]]
                                x1, y1 = sub_pos[edge[1]]
                                sub_edge_x.extend([x0, x1, None])
                                sub_edge_y.extend([y0, y1, None])
                                sub_edge_text.append(f"{edge[0]} → {edge[1]}")
                            
                            sub_node_x = []
                            sub_node_y = []
                            sub_node_text = []
                            sub_node_colors = []
                            
                            for node in subgraph.nodes():
                                x, y = sub_pos[node]
                                sub_node_x.append(x)
                                sub_node_y.append(y)
                                
                                # Get node attributes for hover text
                                attrs = subgraph.nodes[node]
                                attr_text = "<br>".join([f"{k}: {v}" for k, v in attrs.items()])
                                sub_node_text.append(f"{node}<br>{attr_text}" if attr_text else f"{node}")
                                
                                # Determine node color based on type
                                node_type = attrs.get("type", "unknown")
                                if node_type == "source":
                                    sub_node_colors.append("green")
                                elif node_type == "processor":
                                    sub_node_colors.append("blue")
                                elif node_type == "target":
                                    sub_node_colors.append("red")
                                else:
                                    sub_node_colors.append("gray")
                            
                            # Create filtered figure
                            filtered_edge_trace = go.Scatter(
                                x=sub_edge_x, y=sub_edge_y,
                                line=dict(width=1, color='#888'),
                                hoverinfo='text',
                                mode='lines',
                                text=sub_edge_text,
                                name='Connections'
                            )
                            
                            filtered_node_trace = go.Scatter(
                                x=sub_node_x, y=sub_node_y,
                                mode='markers+text',
                                hoverinfo='text',
                                text=sub_node_text,
                                marker=dict(
                                    showscale=False,
                                    color=sub_node_colors,
                                    size=20,
                                    line=dict(width=2, color='white')
                                ),
                                textposition="top center",
                                name='Nodes'
                            )
                            
                            filtered_fig = go.Figure(data=[filtered_edge_trace, filtered_node_trace])
                            filtered_fig.update_layout(
                                title=f"{name} (Filtered)",
                                showlegend=st.session_state.viz_settings.get("show_legend", True),
                                hovermode='closest',
                                margin=dict(b=20, l=5, r=5, t=40),
                                width=st.session_state.viz_settings.get("default_width", 800),
                                height=st.session_state.viz_settings.get("default_height", 500),
                                template=st.session_state.viz_settings.get("theme", "plotly"),
                                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
                            )
                            
                            st.plotly_chart(filtered_fig, use_container_width=True)
            
            except Exception as e:
                # If interactive visualization fails, fall back to static
                st.warning(f"Interactive graph visualization failed, falling back to static display: {str(e)}")
                
                # Create a matplotlib figure
                plt.figure(figsize=(10, 6))
                
                # Draw the graph
                pos = nx.spring_layout(graph)
                nx.draw(graph, pos, with_labels=True, node_color='skyblue', 
                        node_size=1500, edge_color='gray', arrows=True)
                
                # Display the figure
                st.pyplot(plt.gcf())
                
                # Create a BytesIO object to save the figure
                buf = io.BytesIO()
                plt.savefig(buf, format='png', bbox_inches='tight')
                buf.seek(0)
                
                # Add download button
                st.download_button(
                    label="Download Graph",
                    data=buf,
                    file_name=f"{name.lower().replace(' ', '_')}.png",
                    mime="image/png"
                )
                
                # Close the figure to free memory
                plt.close()
        else:
            # Create a static matplotlib figure
            plt.figure(figsize=(10, 6))
            
            # Draw the graph
            pos = nx.spring_layout(graph)
            nx.draw(graph, pos, with_labels=True, node_color='skyblue', 
                    node_size=1500, edge_color='gray', arrows=True)
            
            # Display the figure
            st.pyplot(plt.gcf())
            
            # Create a BytesIO object to save the figure
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            
            # Add download button
            st.download_button(
                label="Download Graph",
                data=buf,
                file_name=f"{name.lower().replace(' ', '_')}.png",
                mime="image/png"
            )
            
            # Close the figure to free memory
            plt.close()
    
    def _render_image(self, image_data, name: str, compact: bool = False) -> None:
        """
        Render an image in the UI.
        
        Args:
            image_data: The image data to render
            name: The name of the visualization
            compact: Whether to use compact mode for mobile/tablet views
        """
        # Get device type for responsive display
        device_type = st.session_state.get("device_type", "desktop")
        
        # Display the image with responsive width
        if compact or device_type == "mobile":
            # For mobile or compact mode, use full width with reduced quality
            st.image(image_data, use_column_width=True, output_format="JPEG", quality=90)
        else:
            # For desktop, use original image
            st.image(image_data)
        
        # Convert to bytes for download if needed
        if isinstance(image_data, Image.Image):
            buf = io.BytesIO()
            image_data.save(buf, format='PNG')
            buf.seek(0)
            image_bytes = buf.getvalue()
        else:
            # Assume it's already bytes
            image_bytes = image_data
        
        # Add download button - show only if not in compact mode or explicitly on mobile
        if not compact or device_type == "mobile":
            st.download_button(
                label="Download Image",
                data=image_bytes,
                file_name=f"{name.lower().replace(' ', '_')}.png",
                mime="image/png"
            )
    
    def _render_dataframe(self, df, name: str, compact: bool = False) -> None:
        """
        Render a pandas DataFrame in the UI.
        
        Args:
            df: The pandas DataFrame to render
            name: The name of the visualization
            compact: Whether to use compact mode for mobile/tablet views
        """
        # Get device type for responsive display
        device_type = st.session_state.get("device_type", "desktop")
        
        # Adjust dataframe display based on device type and compact mode
        if compact or device_type == "mobile":
            # For mobile or compact mode, limit the number of rows and columns
            max_rows = 5
            max_cols = min(5, len(df.columns))
            
            # Show a preview of the dataframe
            if len(df) > max_rows or len(df.columns) > max_cols:
                preview_df = df.iloc[:max_rows, :max_cols]
                st.dataframe(preview_df, use_container_width=True)
                st.caption(f"Showing preview: {max_rows} of {len(df)} rows, {max_cols} of {len(df.columns)} columns")
                
                # Add a button to show the full dataframe
                if st.button(f"Show Full Data ({len(df)} rows)", key=f"show_full_{name}_{uuid.uuid4()}"):
                    st.dataframe(df, use_container_width=True)
            else:
                # If the dataframe is small enough, show it all
                st.dataframe(df, use_container_width=True)
        else:
            # For desktop, show the full dataframe with pagination
            st.dataframe(df, use_container_width=True)
        
        # Add download options in a more compact layout for mobile
        if compact or device_type == "mobile":
            col1, col2 = st.columns(2)
            with col1:
                # CSV download
                csv = df.to_csv(index=False)
                st.download_button(
                    label="CSV",
                    data=csv,
                    file_name=f"{name.lower().replace(' ', '_')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                # Excel download
                excel_buffer = io.BytesIO()
                df.to_excel(excel_buffer, index=False)
                excel_buffer.seek(0)
                
                st.download_button(
                    label="Excel",
                    data=excel_buffer,
                    file_name=f"{name.lower().replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            # For desktop, show full download options
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"{name.lower().replace(' ', '_')}.csv",
                mime="text/csv"
            )
            
            # Also offer Excel download
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)
            
            st.download_button(
                label="Download Excel",
                data=excel_buffer,
                file_name=f"{name.lower().replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    def _render_sfc_module(self, module_data, name: str, compact: bool = False) -> None:
        """
        Render an SFC module visualization in the UI.
        
        Args:
            module_data: The SFC module data to visualize
            name: The name of the visualization
            compact: Whether to use compact mode for mobile/tablet views
        """
        # Get device type for responsive display
        device_type = st.session_state.get("device_type", "desktop")
        # Create a directed graph from the module data
        G = nx.DiGraph()
        
        # Add nodes for sources, processors, and targets
        if "sources" in module_data:
            for source in module_data["sources"]:
                G.add_node(source["name"], type="source")
        
        if "processors" in module_data:
            for processor in module_data["processors"]:
                G.add_node(processor["name"], type="processor")
        
        if "targets" in module_data:
            for target in module_data["targets"]:
                G.add_node(target["name"], type="target")
        
        # Add edges based on data flow
        # This is a simplified example - actual implementation would depend on the module data structure
        if "connections" in module_data:
            for conn in module_data["connections"]:
                G.add_edge(conn["from"], conn["to"])
        
        # Create a matplotlib figure
        plt.figure(figsize=(12, 8))
        
        # Define node colors based on type
        node_colors = []
        for node in G.nodes():
            node_type = G.nodes[node].get("type", "unknown")
            if node_type == "source":
                node_colors.append("lightgreen")
            elif node_type == "processor":
                node_colors.append("lightblue")
            elif node_type == "target":
                node_colors.append("salmon")
            else:
                node_colors.append("gray")
        
        # Draw the graph
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True, node_color=node_colors, 
                node_size=2000, edge_color='gray', arrows=True, 
                font_size=10, font_weight='bold')
        
        # Display the figure
        st.pyplot(plt.gcf())
        
        # Create a BytesIO object to save the figure
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        
        # Add download button
        st.download_button(
            label="Download Module Visualization",
            data=buf,
            file_name=f"{name.lower().replace(' ', '_')}_module.png",
            mime="image/png"
        )
        
        # Close the figure to free memory
        plt.close()
        
        # Also display the module data as JSON for reference
        with st.expander("Module Data"):
            st.json(module_data)
    
    def render_visualization(self, viz: Dict[str, Any], compact: bool = False) -> None:
        """
        Render a visualization in the UI.
        
        Args:
            viz: The visualization data dictionary
            compact: Whether to use compact mode for mobile/tablet views
        """
        # Extract visualization data
        viz_id = viz["id"]
        name = viz["name"]
        viz_type = viz["type"]
        data = viz["data"]
        metadata = viz.get("metadata", {})
        
        # Determine if we should use an expander based on compact mode
        if compact:
            # In compact mode, render directly without an expander
            # Render based on visualization type
            if viz_type == "chart" and isinstance(data, plt.Figure):
                self._render_matplotlib_chart(data, name, compact=True)
            elif viz_type == "graph" and isinstance(data, nx.Graph):
                self._render_networkx_graph(data, name, compact=True)
            elif viz_type == "image":
                self._render_image(data, name, compact=True)
            elif viz_type == "dataframe" and isinstance(data, pd.DataFrame):
                self._render_dataframe(data, name, compact=True)
            elif viz_type == "module":
                self._render_sfc_module(data, name, compact=True)
            else:
                # If we don't recognize the type, try to display as JSON
                st.warning(f"Unknown visualization type: {viz_type}")
                try:
                    st.json(data)
                except:
                    st.text(str(data))
            
            # Add a button to show metadata in compact mode
            if metadata:
                if st.button(f"Show Details", key=f"metadata_{viz_id}"):
                    st.json(metadata)
        else:
            # In full mode, use an expander
            with st.expander(name, expanded=True):
                # Render based on visualization type
                if viz_type == "chart" and isinstance(data, plt.Figure):
                    self._render_matplotlib_chart(data, name)
                elif viz_type == "graph" and isinstance(data, nx.Graph):
                    self._render_networkx_graph(data, name)
                elif viz_type == "image":
                    self._render_image(data, name)
                elif viz_type == "dataframe" and isinstance(data, pd.DataFrame):
                    self._render_dataframe(data, name)
                elif viz_type == "module":
                    self._render_sfc_module(data, name)
                else:
                    # If we don't recognize the type, try to display as JSON
                    st.warning(f"Unknown visualization type: {viz_type}")
                    try:
                        st.json(data)
                    except:
                        st.text(str(data))
                
                # Display metadata if available
                if metadata:
                with st.expander("Metadata"):
                    st.json(metadata)
    
    def render_visualization_list(self) -> None:
        """
        Render a list of all visualizations in the session state.
        Uses responsive layout based on screen size.
        """
        visualizations = self.get_visualizations()
        
        if not visualizations:
            st.info("No visualizations available. Use the chat to generate visualizations or upload visualization data.")
            return
        
        # Add filter and sort options in an expander
        with st.expander("Visualization Options", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                # Add filter by type
                viz_types = list(set([viz["type"] for viz in visualizations]))
                selected_types = st.multiselect(
                    "Filter by Type",
                    options=viz_types,
                    default=viz_types,
                    key="viz_filter_types"
                )
            
            with col2:
                # Add sort options
                sort_options = ["Newest First", "Oldest First", "Name (A-Z)", "Name (Z-A)", "Type"]
                sort_by = st.selectbox(
                    "Sort By",
                    options=sort_options,
                    index=0,
                    key="viz_sort_by"
                )
            
            # Add a button to clear all visualizations
            if st.button("Clear All Visualizations", key="clear_all_viz"):
                self.clear_visualizations()
                st.rerun()
        
        # Filter visualizations based on selected types
        if selected_types:
            filtered_visualizations = [viz for viz in visualizations if viz["type"] in selected_types]
        else:
            filtered_visualizations = visualizations
        
        # Sort visualizations based on selected option
        if sort_by == "Newest First":
            filtered_visualizations = sorted(
                filtered_visualizations, 
                key=lambda x: x.get("metadata", {}).get("timestamp", ""), 
                reverse=True
            )
        elif sort_by == "Oldest First":
            filtered_visualizations = sorted(
                filtered_visualizations, 
                key=lambda x: x.get("metadata", {}).get("timestamp", "")
            )
        elif sort_by == "Name (A-Z)":
            filtered_visualizations = sorted(
                filtered_visualizations, 
                key=lambda x: x.get("name", "").lower()
            )
        elif sort_by == "Name (Z-A)":
            filtered_visualizations = sorted(
                filtered_visualizations, 
                key=lambda x: x.get("name", "").lower(), 
                reverse=True
            )
        elif sort_by == "Type":
            filtered_visualizations = sorted(
                filtered_visualizations, 
                key=lambda x: x.get("type", "")
            )
        
        # Display count of visualizations
        st.caption(f"Showing {len(filtered_visualizations)} of {len(visualizations)} visualizations")
        
        # Get device type for responsive layout
        device_type = st.session_state.get("device_type", "desktop")
        
        # Display visualizations in a responsive grid layout
        if device_type == "mobile":
            # On mobile, display visualizations in a single column with compact view
            for viz in filtered_visualizations:
                with st.container():
                    st.markdown(f"""
                    <div class="visualization-container">
                        <div class="visualization-title">{viz["name"]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    self.render_visualization(viz, compact=True)
                    st.divider()
        else:
            # On tablet and desktop, use a grid layout
            # Group visualizations in pairs for tablet, triplets for desktop
            viz_per_row = 3 if device_type == "desktop" else 2
            
            # Process visualizations in groups
            for i in range(0, len(filtered_visualizations), viz_per_row):
                # Get the current group of visualizations
                viz_group = filtered_visualizations[i:i+viz_per_row]
                
                # Create columns for this group
                cols = st.columns(len(viz_group))
                
                # Render each visualization in its column
                for j, viz in enumerate(viz_group):
                    with cols[j]:
                        with st.container():
                            st.markdown(f"""
                            <div class="visualization-container">
                                <div class="visualization-title">{viz["name"]}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            compact = device_type == "tablet"  # Use compact view on tablets
                            self.render_visualization(viz, compact=compact)
    
    def render_visualization_upload(self) -> None:
        """
        Render a file uploader for visualization data.
        """
        uploaded_file = st.file_uploader("Upload visualization data", type=["json", "csv", "xlsx", "png", "jpg"])
        
        if uploaded_file is not None:
            try:
                # Process based on file type
                file_type = uploaded_file.name.split('.')[-1].lower()
                
                if file_type in ['json']:
                    # Parse JSON data
                    content = uploaded_file.read()
                    data = json.loads(content)
                    
                    # Try to determine if this is module data
                    if isinstance(data, dict) and any(key in data for key in ["sources", "targets", "processors"]):
                        viz_type = "module"
                    else:
                        viz_type = "json"
                    
                    # Add the visualization
                    self.add_visualization(data, viz_type, name=uploaded_file.name)
                    
                elif file_type in ['csv']:
                    # Parse CSV data
                    df = pd.read_csv(uploaded_file)
                    self.add_visualization(df, "dataframe", name=uploaded_file.name)
                    
                elif file_type in ['xlsx']:
                    # Parse Excel data
                    df = pd.read_excel(uploaded_file)
                    self.add_visualization(df, "dataframe", name=uploaded_file.name)
                    
                elif file_type in ['png', 'jpg', 'jpeg']:
                    # Load image data
                    image = Image.open(uploaded_file)
                    self.add_visualization(image, "image", name=uploaded_file.name)
                
                # Show a success message
                st.success(f"Visualization '{uploaded_file.name}' uploaded successfully!")
                
                # Rerun to update the UI
                st.rerun()
            
            except Exception as e:
                st.error(f"Failed to upload visualization: {str(e)}")


# Create a singleton instance of the visualization display
visualization_display = VisualizationDisplay()


def render_visualization_settings() -> None:
    """
    Render the visualization settings interface.
    """
    st.subheader("Visualization Settings")
    
    # Create tabs for different setting categories
    settings_tabs = st.tabs(["General", "Responsive Design", "Advanced"])
    
    with settings_tabs[0]:
        # Theme selection
        theme = st.selectbox(
            "Theme",
            ["light", "dark", "plotly", "plotly_white", "plotly_dark", "ggplot2"],
            index=["light", "dark", "plotly", "plotly_white", "plotly_dark", "ggplot2"].index(
                st.session_state.viz_settings.get("theme", "light")
            )
        )
        
        # Display options
        col1, col2 = st.columns(2)
        with col1:
            show_grid = st.checkbox(
                "Show Grid",
                value=st.session_state.viz_settings.get("show_grid", True)
            )
        
        with col2:
            show_legend = st.checkbox(
                "Show Legend",
                value=st.session_state.viz_settings.get("show_legend", True)
            )
        
        # Interactive mode
        interactive_mode = st.checkbox(
            "Interactive Mode",
            value=st.session_state.viz_settings.get("interactive_mode", True),
            help="Enable interactive features like zooming, panning, and tooltips"
        )
        
        # Responsive mode
        responsive_mode = st.checkbox(
            "Responsive Mode",
            value=st.session_state.viz_settings.get("responsive_mode", True),
            help="Automatically adjust visualizations based on screen size"
        )
    
    with settings_tabs[1]:
        st.subheader("Screen Size Settings")
        
        # Breakpoints
        col1, col2 = st.columns(2)
        with col1:
            mobile_breakpoint = st.number_input(
                "Mobile Breakpoint (px)",
                min_value=320,
                max_value=1000,
                value=st.session_state.viz_settings.get("mobile_breakpoint", 768),
                step=10,
                help="Maximum width in pixels for mobile view"
            )
        
        with col2:
            tablet_breakpoint = st.number_input(
                "Tablet Breakpoint (px)",
                min_value=mobile_breakpoint + 1,
                max_value=1500,
                value=st.session_state.viz_settings.get("tablet_breakpoint", 992),
                step=10,
                help="Maximum width in pixels for tablet view"
            )
        
        st.subheader("Height Settings")
        
        # Heights for different devices
        col1, col2, col3 = st.columns(3)
        with col1:
            mobile_height = st.number_input(
                "Mobile Height",
                min_value=200,
                max_value=800,
                value=st.session_state.viz_settings.get("mobile_height", 300),
                step=10
            )
        
        with col2:
            tablet_height = st.number_input(
                "Tablet Height",
                min_value=200,
                max_value=1000,
                value=st.session_state.viz_settings.get("tablet_height", 400),
                step=10
            )
        
        with col3:
            desktop_height = st.number_input(
                "Desktop Height",
                min_value=300,
                max_value=1500,
                value=st.session_state.viz_settings.get("desktop_height", 500),
                step=10
            )
        
        st.subheader("Font Size Settings")
        
        # Font sizes for different devices
        col1, col2, col3 = st.columns(3)
        with col1:
            mobile_font_size = st.number_input(
                "Mobile Font Size",
                min_value=8,
                max_value=16,
                value=st.session_state.viz_settings.get("mobile_font_size", 10),
                step=1
            )
        
        with col2:
            tablet_font_size = st.number_input(
                "Tablet Font Size",
                min_value=8,
                max_value=18,
                value=st.session_state.viz_settings.get("tablet_font_size", 12),
                step=1
            )
        
        with col3:
            desktop_font_size = st.number_input(
                "Desktop Font Size",
                min_value=10,
                max_value=20,
                value=st.session_state.viz_settings.get("desktop_font_size", 14),
                step=1
            )
    
    with settings_tabs[2]:
        st.subheader("Advanced Settings")
        
        # Size settings
        col1, col2 = st.columns(2)
        with col1:
            width = st.number_input(
                "Default Width",
                min_value=400,
                max_value=2000,
                value=st.session_state.viz_settings.get("default_width", 800),
                step=50
            )
        
        with col2:
            height = st.number_input(
                "Default Height",
                min_value=300,
                max_value=1500,
                value=st.session_state.viz_settings.get("default_height", 500),
                step=50
            )
        
        # Reset to defaults
        if st.button("Reset to Defaults"):
            st.session_state.viz_settings = {
                "theme": "light",
                "default_width": 800,
                "default_height": 500,
                "show_grid": True,
                "show_legend": True,
                "interactive_mode": True,
                "responsive_mode": True,
                "mobile_breakpoint": 768,
                "tablet_breakpoint": 992,
                "mobile_height": 300,
                "tablet_height": 400,
                "desktop_height": 500,
                "mobile_font_size": 10,
                "tablet_font_size": 12,
                "desktop_font_size": 14
            }
            st.success("Settings reset to defaults!")
            st.rerun()
    
    # Save settings button
    if st.button("Save Settings"):
        st.session_state.viz_settings = {
            "theme": theme,
            "default_width": width,
            "default_height": height,
            "show_grid": show_grid,
            "show_legend": show_legend,
            "interactive_mode": interactive_mode,
            "responsive_mode": responsive_mode,
            "mobile_breakpoint": mobile_breakpoint,
            "tablet_breakpoint": tablet_breakpoint,
            "mobile_height": mobile_height,
            "tablet_height": tablet_height,
            "desktop_height": desktop_height,
            "mobile_font_size": mobile_font_size,
            "tablet_font_size": tablet_font_size,
            "desktop_font_size": desktop_font_size
        }
        st.success("Settings saved!")
        st.rerun()


def render_visualization_display() -> None:
    """
    Render the complete visualization display interface.
    """
    st.header("📊 Visualization Display")
    
    # Add tabs for different sections
    tab1, tab2, tab3 = st.tabs(["View Visualizations", "Upload Visualization", "Settings"])
    
    with tab1:
        # Render the list of visualizations
        visualization_display.render_visualization_list()
    
    with tab2:
        # Render the visualization upload interface
        visualization_display.render_visualization_upload()
    
    with tab3:
        # Render the visualization settings
        render_visualization_settings()


def extract_visualizations_from_messages() -> None:
    """
    Extract visualizations from the conversation history and add them to the visualization display.
    """
    messages = conversation_state.get_messages()
    
    for message in messages:
        # Check if the message has attachments
        attachments = message.get("attachments", [])
        
        for attachment in attachments:
            # Check if the attachment is a visualization
            if attachment.get("type") in ["chart", "graph", "image", "dataframe", "module"]:
                # Add the visualization to the display
                visualization_display.add_visualization(
                    attachment.get("content", {}),
                    attachment.get("type", "unknown"),
                    name=attachment.get("metadata", {}).get("name", "Visualization"),
                    metadata=attachment.get("metadata", {})
                )


def create_sample_visualizations() -> None:
    """
    Create sample visualizations for demonstration purposes.
    """
    # Only create samples if no visualizations exist
    if not st.session_state.visualizations:
        # Sample time series chart
        fig, ax = plt.subplots()
        x = range(10)
        y = [i**2 for i in x]
        ax.plot(x, y)
        ax.set_title("Sample Time Series")
        ax.set_xlabel("Time")
        ax.set_ylabel("Value")
        visualization_display.add_visualization(fig, "chart", name="Sample Time Series")
        
        # Sample SFC module visualization
        module_data = {
            "sources": [
                {"name": "OpcUaSource", "protocol": "OPC-UA"},
                {"name": "ModbusSource", "protocol": "Modbus"}
            ],
            "processors": [
                {"name": "DataTransformer", "type": "transform"}
            ],
            "targets": [
                {"name": "S3Target", "type": "AWS-S3"},
                {"name": "IoTTarget", "type": "AWS-IOT-CORE"}
            ],
            "connections": [
                {"from": "OpcUaSource", "to": "DataTransformer"},
                {"from": "ModbusSource", "to": "DataTransformer"},
                {"from": "DataTransformer", "to": "S3Target"},
                {"from": "DataTransformer", "to": "IoTTarget"}
            ]
        }
        visualization_display.add_visualization(module_data, "module", name="Sample SFC Module")
        
        # Sample data table
        df = pd.DataFrame({
            'Time': pd.date_range(start='2023-01-01', periods=5, freq='H'),
            'Temperature': [22.1, 22.5, 23.0, 22.8, 22.2],
            'Humidity': [45, 47, 48, 46, 44]
        })
        visualization_display.add_visualization(df, "dataframe", name="Sample Sensor Data")
</content>