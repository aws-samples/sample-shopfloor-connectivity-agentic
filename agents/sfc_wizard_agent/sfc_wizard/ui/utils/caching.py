"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

Caching utilities for the SFC Wizard Agent UI.

This module provides caching utilities for expensive operations in the UI.
"""

import streamlit as st
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union
import functools
import time
import hashlib
import json

# Type variable for generic function
T = TypeVar('T')

def cache_data(ttl_seconds: int = 3600):
    """
    Cache decorator for expensive data operations with time-to-live.
    
    Args:
        ttl_seconds (int): Time-to-live in seconds for cached data.
        
    Returns:
        Callable: Decorated function with caching.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create a cache key based on function name and arguments
            cache_key = f"cache_{func.__name__}_{_hash_args(*args, **kwargs)}"
            
            # Check if we have a valid cached result
            if cache_key in st.session_state:
                result, timestamp = st.session_state[cache_key]
                # Check if the cache is still valid
                if time.time() - timestamp < ttl_seconds:
                    return result
            
            # If no valid cache, call the function and cache the result
            result = func(*args, **kwargs)
            st.session_state[cache_key] = (result, time.time())
            return result
        
        return wrapper
    
    return decorator


def _hash_args(*args, **kwargs) -> str:
    """
    Create a hash of function arguments for cache keys.
    
    Args:
        *args: Positional arguments.
        **kwargs: Keyword arguments.
        
    Returns:
        str: Hash string of the arguments.
    """
    # Convert args and kwargs to a string representation
    args_str = str(args)
    kwargs_str = str(sorted(kwargs.items()))
    
    # Create a hash of the combined string
    hash_obj = hashlib.md5((args_str + kwargs_str).encode())
    return hash_obj.hexdigest()


def clear_cache(prefix: str = None) -> None:
    """
    Clear cached data from session state.
    
    Args:
        prefix (str, optional): Prefix to filter which cache entries to clear.
    """
    keys_to_clear = []
    
    # Find all cache keys to clear
    for key in st.session_state:
        if key.startswith("cache_"):
            if prefix is None or key.startswith(f"cache_{prefix}"):
                keys_to_clear.append(key)
    
    # Remove the keys
    for key in keys_to_clear:
        del st.session_state[key]


def get_cache_stats() -> Dict[str, Any]:
    """
    Get statistics about the current cache usage.
    
    Returns:
        Dict[str, Any]: Cache statistics.
    """
    cache_keys = [k for k in st.session_state if k.startswith("cache_")]
    cache_size = len(cache_keys)
    
    # Calculate total size of cached data (approximate)
    total_size = 0
    oldest_timestamp = float('inf')
    newest_timestamp = 0
    
    for key in cache_keys:
        if key in st.session_state:
            result, timestamp = st.session_state[key]
            # Update timestamps
            oldest_timestamp = min(oldest_timestamp, timestamp)
            newest_timestamp = max(newest_timestamp, timestamp)
    
    # Format timestamps
    if oldest_timestamp != float('inf'):
        oldest_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(oldest_timestamp))
    else:
        oldest_time = "N/A"
    
    if newest_timestamp > 0:
        newest_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(newest_timestamp))
    else:
        newest_time = "N/A"
    
    return {
        "cache_entries": cache_size,
        "oldest_entry": oldest_time,
        "newest_entry": newest_time
    }