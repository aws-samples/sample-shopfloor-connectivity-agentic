"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

Utility modules for the SFC Wizard Agent UI.
"""

# Import utilities for easier access
from sfc_wizard.ui.utils.formatting import (
    extract_code_blocks,
    format_markdown_text,
    format_code_block,
    format_json,
    format_attachment,
    format_message_content
)

from sfc_wizard.ui.utils.session import (
    conversation_state,
    error_handler
)

# Import new utilities
try:
    from sfc_wizard.ui.utils.caching import (
        cache_data,
        clear_cache,
        get_cache_stats
    )
except ImportError:
    # Fallback if caching module is not available
    def cache_data(ttl_seconds=3600):
        def decorator(func):
            return func
        return decorator
    
    def clear_cache(prefix=None):
        pass
    
    def get_cache_stats():
        return {"cache_entries": 0}

try:
    from sfc_wizard.ui.utils.pagination import (
        Paginator,
        paginate_dataframe
    )
except ImportError:
    # Fallback if pagination module is not available
    class Paginator:
        def __init__(self, items, items_per_page=10, page_key="default"):
            self.items = items
        
        def get_current_page_items(self):
            return self.items
        
        def render_pagination_controls(self, compact=False):
            pass
    
    def paginate_dataframe(df, page_size=10, page_key="default"):
        return df