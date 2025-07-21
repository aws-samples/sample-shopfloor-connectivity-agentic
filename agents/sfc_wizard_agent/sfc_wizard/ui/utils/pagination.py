"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

Pagination utilities for the SFC Wizard Agent UI.

This module provides pagination utilities for handling large datasets in the UI.
"""

import streamlit as st
from typing import Any, Dict, List, Optional, Tuple, TypeVar, Union, Generic, Callable
import math

T = TypeVar('T')

class Paginator(Generic[T]):
    """
    Generic paginator for handling large datasets.
    """
    
    def __init__(self, 
                 items: List[T], 
                 items_per_page: int = 10, 
                 page_key: str = "default_paginator"):
        """
        Initialize the paginator.
        
        Args:
            items (List[T]): The list of items to paginate.
            items_per_page (int, optional): Number of items per page. Defaults to 10.
            page_key (str, optional): Key for storing the current page in session state. Defaults to "default_paginator".
        """
        self.items = items
        self.items_per_page = items_per_page
        self.page_key = f"paginator_{page_key}"
        
        # Initialize the current page in session state if it doesn't exist
        if self.page_key not in st.session_state:
            st.session_state[self.page_key] = 1
    
    @property
    def total_pages(self) -> int:
        """
        Get the total number of pages.
        
        Returns:
            int: The total number of pages.
        """
        return math.ceil(len(self.items) / self.items_per_page)
    
    @property
    def current_page(self) -> int:
        """
        Get the current page number.
        
        Returns:
            int: The current page number.
        """
        return st.session_state[self.page_key]
    
    @current_page.setter
    def current_page(self, value: int) -> None:
        """
        Set the current page number.
        
        Args:
            value (int): The page number to set.
        """
        # Ensure the page number is within valid range
        value = max(1, min(value, self.total_pages))
        st.session_state[self.page_key] = value
    
    def get_current_page_items(self) -> List[T]:
        """
        Get the items for the current page.
        
        Returns:
            List[T]: The items for the current page.
        """
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        return self.items[start_idx:end_idx]
    
    def render_pagination_controls(self, compact: bool = False) -> None:
        """
        Render pagination controls in the UI.
        
        Args:
            compact (bool, optional): Whether to use compact mode for mobile. Defaults to False.
        """
        # Don't render controls if there's only one page
        if self.total_pages <= 1:
            return
        
        # Detect screen size for responsive layout
        screen_width = st.session_state.get("screen_width", 1200)
        is_mobile = screen_width < 768
        
        # Use compact mode for mobile or if explicitly requested
        use_compact = compact or is_mobile
        
        st.markdown("---")
        
        if use_compact:
            # Compact controls for mobile
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                if st.button("◀", disabled=self.current_page == 1, key=f"{self.page_key}_prev"):
                    self.current_page -= 1
                    st.rerun()
            
            with col2:
                st.markdown(f"<div style='text-align: center;'>Page {self.current_page} of {self.total_pages}</div>", unsafe_allow_html=True)
            
            with col3:
                if st.button("▶", disabled=self.current_page == self.total_pages, key=f"{self.page_key}_next"):
                    self.current_page += 1
                    st.rerun()
        else:
            # Full controls for desktop
            col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
            
            with col1:
                if st.button("⏮ First", disabled=self.current_page == 1, key=f"{self.page_key}_first"):
                    self.current_page = 1
                    st.rerun()
            
            with col2:
                if st.button("◀ Previous", disabled=self.current_page == 1, key=f"{self.page_key}_prev"):
                    self.current_page -= 1
                    st.rerun()
            
            with col3:
                # Page selector
                page_options = list(range(1, self.total_pages + 1))
                new_page = st.selectbox(
                    "Page",
                    page_options,
                    index=self.current_page - 1,
                    key=f"{self.page_key}_select"
                )
                
                if new_page != self.current_page:
                    self.current_page = new_page
                    st.rerun()
            
            with col4:
                if st.button("Next ▶", disabled=self.current_page == self.total_pages, key=f"{self.page_key}_next"):
                    self.current_page += 1
                    st.rerun()
            
            with col5:
                if st.button("Last ⏭", disabled=self.current_page == self.total_pages, key=f"{self.page_key}_last"):
                    self.current_page = self.total_pages
                    st.rerun()


def paginate_dataframe(df, page_size=10, page_key="default_df_paginator"):
    """
    Paginate a pandas DataFrame.
    
    Args:
        df: The pandas DataFrame to paginate.
        page_size (int, optional): Number of rows per page. Defaults to 10.
        page_key (str, optional): Key for storing the current page in session state. Defaults to "default_df_paginator".
        
    Returns:
        DataFrame: The paginated DataFrame for the current page.
    """
    # Convert DataFrame to list of rows
    rows = df.values.tolist()
    
    # Create a paginator
    paginator = Paginator(rows, items_per_page=page_size, page_key=page_key)
    
    # Get the current page rows
    current_page_rows = paginator.get_current_page_items()
    
    # Create a new DataFrame with the current page rows
    import pandas as pd
    paginated_df = pd.DataFrame(current_page_rows, columns=df.columns)
    
    # Render pagination controls
    paginator.render_pagination_controls()
    
    return paginated_df