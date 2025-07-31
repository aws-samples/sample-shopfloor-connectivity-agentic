#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

SFC File Explorer module for web UI.
Provides file system access and CRUD operations for the .sfc directory.
"""

import os
import json
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import threading
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class SFCFileSystemHandler(FileSystemEventHandler):
    """File system event handler for monitoring .sfc directory changes."""
    
    def __init__(self, socketio, logger):
        super().__init__()
        self.socketio = socketio
        self.logger = logger
        self.debounce_delay = 0.5  # 500ms debounce
        self.pending_events = {}
        self.timer_lock = threading.Lock()
    
    def _debounced_emit(self, event_type: str, path: str):
        """Emit file system events with debouncing to prevent spam."""
        with self.timer_lock:
            # Cancel existing timer for this path if it exists
            if path in self.pending_events:
                self.pending_events[path].cancel()
            
            # Create new timer
            timer = threading.Timer(
                self.debounce_delay,
                self._emit_file_event,
                args=[event_type, path]
            )
            self.pending_events[path] = timer
            timer.start()
    
    def _emit_file_event(self, event_type: str, path: str):
        """Emit the actual file system event."""
        try:
            # Remove from pending events
            with self.timer_lock:
                if path in self.pending_events:
                    del self.pending_events[path]
            
            # Emit the event
            self.socketio.emit('file_tree_updated', {
                'event_type': event_type,
                'path': path,
                'timestamp': datetime.now().isoformat()
            })
            
            self.logger.info(f"File system event: {event_type} - {path}")
            
        except Exception as e:
            self.logger.error(f"Error emitting file system event: {e}")
    
    def on_created(self, event):
        """Handle file/directory creation."""
        if not event.is_directory:
            self._debounced_emit('created', event.src_path)
    
    def on_deleted(self, event):
        """Handle file/directory deletion."""
        self._debounced_emit('deleted', event.src_path)
    
    def on_modified(self, event):
        """Handle file/directory modification."""
        if not event.is_directory:
            self._debounced_emit('modified', event.src_path)
    
    def on_moved(self, event):
        """Handle file/directory move/rename."""
        self._debounced_emit('moved', event.dest_path)


class SFCFileExplorer:
    """File explorer for SFC directory with security restrictions."""
    
    def __init__(self, socketio=None, logger=None):
        self.socketio = socketio
        self.logger = logger
        self.sfc_root = Path(".sfc").resolve()
        self.observer = None
        self.file_handler = None
        
        # Ensure .sfc directory exists
        self.sfc_root.mkdir(exist_ok=True)
        
        # File type mappings
        self.file_types = {
            '.json': 'config',
            '.log': 'log', 
            '.md': 'documentation',
            '.txt': 'text',
            '.vm': 'template',
            '.jar': 'module',
            '.tar.gz': 'archive'
        }
        
        # Editable file extensions
        self.editable_extensions = {'.json', '.md'}
        
        # Maximum file size for content reading (10MB)
        self.max_file_size = 10 * 1024 * 1024
        
        # Start file system monitoring if socketio is available
        if self.socketio and self.logger:
            self.start_monitoring()
    
    def start_monitoring(self):
        """Start file system monitoring for the .sfc directory."""
        try:
            if self.observer is None:
                self.file_handler = SFCFileSystemHandler(self.socketio, self.logger)
                self.observer = Observer()
                self.observer.schedule(
                    self.file_handler, 
                    str(self.sfc_root), 
                    recursive=True
                )
                self.observer.start()
                self.logger.info(f"Started file system monitoring for {self.sfc_root}")
        except Exception as e:
            self.logger.error(f"Failed to start file system monitoring: {e}")
    
    def stop_monitoring(self):
        """Stop file system monitoring."""
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join()
                self.observer = None
                self.file_handler = None
                self.logger.info("Stopped file system monitoring")
        except Exception as e:
            self.logger.error(f"Error stopping file system monitoring: {e}")
    
    def _validate_path(self, path: str) -> Path:
        """Validate and resolve path to ensure it's within .sfc directory."""
        try:
            # Convert to Path object and resolve
            requested_path = Path(path).resolve()
            
            # Ensure the path is within .sfc directory
            if not str(requested_path).startswith(str(self.sfc_root)):
                # Try relative to .sfc root
                requested_path = (self.sfc_root / path).resolve()
                
                # Double-check it's still within .sfc
                if not str(requested_path).startswith(str(self.sfc_root)):
                    raise ValueError(f"Path outside .sfc directory: {path}")
            
            return requested_path
            
        except Exception as e:
            raise ValueError(f"Invalid path: {path} - {str(e)}")
    
    def _get_file_purpose(self, file_path: Path) -> str:
        """Determine the purpose of a file based on its location and extension."""
        path_str = str(file_path.relative_to(self.sfc_root))
        
        if 'stored_configs' in path_str:
            return 'config'
        elif 'stored_results' in path_str:
            return 'result'
        elif 'runs' in path_str and 'logs' in path_str:
            return 'log'
        elif 'runs' in path_str and 'data' in path_str:
            return 'data'
        elif 'modules' in path_str:
            return 'module'
        else:
            # Fallback to extension-based detection
            return self.file_types.get(file_path.suffix.lower(), 'unknown')
    
    def _get_file_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Get metadata for a file or directory."""
        try:
            stat = file_path.stat()
            relative_path = str(file_path.relative_to(self.sfc_root))
            
            metadata = {
                'name': file_path.name,
                'path': relative_path,
                'type': 'directory' if file_path.is_dir() else 'file',
                'size': stat.st_size if file_path.is_file() else None,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'purpose': self._get_file_purpose(file_path) if file_path.is_file() else None,
                'editable': file_path.suffix.lower() in self.editable_extensions if file_path.is_file() else False
            }
            
            # Add child count for directories
            if file_path.is_dir():
                try:
                    metadata['child_count'] = len(list(file_path.iterdir()))
                except PermissionError:
                    metadata['child_count'] = 0
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error getting metadata for {file_path}: {e}")
            return {
                'name': file_path.name,
                'path': str(file_path.relative_to(self.sfc_root)),
                'type': 'directory' if file_path.is_dir() else 'file',
                'error': str(e)
            }
    
    def get_file_tree(self, path: str = "", depth: int = 2) -> Dict[str, Any]:
        """Get the file tree structure for the specified path."""
        try:
            if not path:
                target_path = self.sfc_root
            else:
                target_path = self._validate_path(path)
            
            if not target_path.exists():
                return {'error': f'Path does not exist: {path}'}
            
            def build_tree(current_path: Path, current_depth: int) -> Dict[str, Any]:
                """Recursively build the file tree."""
                metadata = self._get_file_metadata(current_path)
                
                if current_path.is_dir() and current_depth > 0:
                    children = []
                    try:
                        for child in sorted(current_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
                            child_tree = build_tree(child, current_depth - 1)
                            children.append(child_tree)
                        metadata['children'] = children
                    except PermissionError:
                        metadata['children'] = []
                        metadata['error'] = 'Permission denied'
                
                return metadata
            
            return build_tree(target_path, depth)
            
        except ValueError as e:
            return {'error': str(e)}
        except Exception as e:
            self.logger.error(f"Error building file tree: {e}")
            return {'error': f'Failed to build file tree: {str(e)}'}
    
    def get_file_content(self, path: str, offset: int = 0, limit: int = None) -> Dict[str, Any]:
        """Get the content of a file with optional pagination."""
        try:
            file_path = self._validate_path(path)
            
            if not file_path.exists():
                return {'error': f'File does not exist: {path}'}
            
            if not file_path.is_file():
                return {'error': f'Path is not a file: {path}'}
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                return {'error': f'File too large: {file_size} bytes (max: {self.max_file_size})'}
            
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type is None:
                mime_type = 'text/plain'
            
            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    if offset > 0:
                        f.seek(offset)
                    
                    if limit:
                        content = f.read(limit)
                        truncated = len(content) == limit
                    else:
                        content = f.read()
                        truncated = False
                
                # Get file metadata
                metadata = self._get_file_metadata(file_path)
                
                return {
                    'path': path,
                    'content': content,
                    'size': file_size,
                    'modified': metadata['modified'],
                    'mime_type': mime_type,
                    'encoding': 'utf-8',
                    'truncated': truncated,
                    'editable': file_path.suffix.lower() in self.editable_extensions,
                    'purpose': metadata['purpose']
                }
                
            except UnicodeDecodeError:
                return {'error': f'File is not text-readable: {path}'}
            
        except ValueError as e:
            return {'error': str(e)}
        except Exception as e:
            self.logger.error(f"Error reading file content: {e}")
            return {'error': f'Failed to read file: {str(e)}'}
    
    def create_file(self, path: str, file_type: str, content: str = None) -> Dict[str, Any]:
        """Create a new file with optional initial content."""
        try:
            file_path = self._validate_path(path)
            
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if file_path.exists():
                return {'error': f'File already exists: {path}'}
            
            # Validate file type and extension
            if file_type == 'json':
                if not path.lower().endswith('.json'):
                    file_path = file_path.with_suffix('.json')
                initial_content = content or '{\n  \n}'
            elif file_type == 'markdown':
                if not path.lower().endswith('.md'):
                    file_path = file_path.with_suffix('.md')
                initial_content = content or '# New Document\n\n'
            else:
                return {'error': f'Unsupported file type: {file_type}'}
            
            # Validate JSON content if provided
            if file_type == 'json' and content:
                try:
                    json.loads(content)
                except json.JSONDecodeError as e:
                    return {'error': f'Invalid JSON content: {str(e)}'}
            
            # Create the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(initial_content)
            
            # Return file metadata
            metadata = self._get_file_metadata(file_path)
            return {
                'success': True,
                'message': f'File created successfully: {file_path.relative_to(self.sfc_root)}',
                'file': metadata
            }
            
        except ValueError as e:
            return {'error': str(e)}
        except Exception as e:
            self.logger.error(f"Error creating file: {e}")
            return {'error': f'Failed to create file: {str(e)}'}
    
    def save_file(self, path: str, content: str) -> Dict[str, Any]:
        """Save content to a file with validation."""
        try:
            file_path = self._validate_path(path)
            
            if not file_path.exists():
                return {'error': f'File does not exist: {path}'}
            
            if not file_path.is_file():
                return {'error': f'Path is not a file: {path}'}
            
            # Check if file is editable
            if file_path.suffix.lower() not in self.editable_extensions:
                return {'error': f'File type not editable: {file_path.suffix}'}
            
            # Validate content based on file type
            validation_errors = []
            
            if file_path.suffix.lower() == '.json':
                try:
                    # Validate JSON syntax
                    parsed_json = json.loads(content)
                    # Pretty format the JSON
                    content = json.dumps(parsed_json, indent=2)
                except json.JSONDecodeError as e:
                    validation_errors.append(f'JSON syntax error: {str(e)}')
            
            elif file_path.suffix.lower() == '.md':
                # Basic Markdown validation (check for common issues)
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    # Check for potential issues (this is basic validation)
                    if line.strip().startswith('#') and not line.startswith('# ') and len(line) > 1:
                        validation_errors.append(f'Line {i}: Missing space after # in heading')
            
            if validation_errors:
                return {
                    'error': 'Validation failed',
                    'validation_errors': validation_errors
                }
            
            # Create backup before saving
            backup_path = file_path.with_suffix(file_path.suffix + '.backup')
            try:
                if file_path.exists():
                    import shutil
                    shutil.copy2(file_path, backup_path)
            except Exception as e:
                self.logger.warning(f"Could not create backup: {e}")
            
            # Save the file atomically
            temp_path = file_path.with_suffix(file_path.suffix + '.tmp')
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # Atomic move
                temp_path.replace(file_path)
                
                # Remove backup if save was successful
                if backup_path.exists():
                    backup_path.unlink()
                
            except Exception as e:
                # Restore from backup if save failed
                if backup_path.exists():
                    backup_path.replace(file_path)
                raise e
            finally:
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()
            
            # Return success with file metadata
            metadata = self._get_file_metadata(file_path)
            return {
                'success': True,
                'message': f'File saved successfully: {file_path.relative_to(self.sfc_root)}',
                'file': metadata
            }
            
        except ValueError as e:
            return {'error': str(e)}
        except Exception as e:
            self.logger.error(f"Error saving file: {e}")
            return {'error': f'Failed to save file: {str(e)}'}
    
    def delete_file(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        """Delete a file or directory."""
        try:
            file_path = self._validate_path(path)
            
            if not file_path.exists():
                return {'error': f'Path does not exist: {path}'}
            
            if file_path.is_dir():
                if not recursive:
                    # Check if directory is empty
                    try:
                        if any(file_path.iterdir()):
                            return {'error': f'Directory not empty: {path}. Use recursive=True to delete.'}
                    except PermissionError:
                        return {'error': f'Permission denied accessing directory: {path}'}
                
                # Delete directory
                import shutil
                shutil.rmtree(file_path)
                message = f'Directory deleted successfully: {path}'
            else:
                # Delete file
                file_path.unlink()
                message = f'File deleted successfully: {path}'
            
            return {
                'success': True,
                'message': message
            }
            
        except ValueError as e:
            return {'error': str(e)}
        except Exception as e:
            self.logger.error(f"Error deleting path: {e}")
            return {'error': f'Failed to delete: {str(e)}'}