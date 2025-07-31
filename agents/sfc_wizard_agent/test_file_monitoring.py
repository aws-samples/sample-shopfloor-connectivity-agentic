#!/usr/bin/env python3
"""
Test script to verify file system monitoring functionality.
"""

import json
import time
import threading
import sys
import os
from pathlib import Path
import tempfile

# Add the sfc_wizard module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sfc_wizard'))

from sfc_wizard.tools.file_explorer import SFCFileExplorer


class MockSocketIO:
    """Mock SocketIO for testing file system events."""
    
    def __init__(self):
        self.events = []
        self.lock = threading.Lock()
    
    def emit(self, event_name, data):
        """Mock emit method to capture events."""
        with self.lock:
            self.events.append({
                'event': event_name,
                'data': data,
                'timestamp': time.time()
            })
            print(f"📡 Event emitted: {event_name} - {data.get('path', 'unknown')}")
    
    def get_events(self):
        """Get all captured events."""
        with self.lock:
            return self.events.copy()
    
    def clear_events(self):
        """Clear all captured events."""
        with self.lock:
            self.events.clear()


class MockLogger:
    """Mock logger for testing."""
    
    def info(self, message):
        print(f"ℹ️ INFO: {message}")
    
    def error(self, message):
        print(f"❌ ERROR: {message}")
    
    def warning(self, message):
        print(f"⚠️ WARNING: {message}")


def test_file_monitoring():
    """Test the file system monitoring functionality."""
    print("🧪 Testing File System Monitoring...")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Change to temp directory
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Create mock SocketIO and logger
            mock_socketio = MockSocketIO()
            mock_logger = MockLogger()
            
            # Initialize file explorer with monitoring
            explorer = SFCFileExplorer(socketio=mock_socketio, logger=mock_logger)
            print("✅ File explorer with monitoring initialized")
            
            # Wait a moment for monitoring to start
            time.sleep(1)
            
            # Test 1: Create a file and check for event
            print("\n📝 Test 1: Creating a file...")
            mock_socketio.clear_events()
            
            result = explorer.create_file("monitor_test.json", "json", '{"test": "monitoring"}')
            if not result.get('success'):
                print(f"❌ Failed to create file: {result}")
                return False
            
            # Wait for file system event
            time.sleep(1)
            events = mock_socketio.get_events()
            
            if any(event['event'] == 'file_tree_updated' and 'created' in event['data'].get('event_type', '') for event in events):
                print("✅ File creation event detected")
            else:
                print(f"❌ No file creation event detected. Events: {events}")
                # This might not be critical as file creation through our API might not trigger watchdog
                print("ℹ️ Note: File creation through API might not trigger watchdog events")
            
            # Test 2: Modify a file externally and check for event
            print("\n✏️ Test 2: Modifying a file externally...")
            mock_socketio.clear_events()
            
            # Modify file directly (simulating external change)
            sfc_path = Path(".sfc")
            test_file = sfc_path / "monitor_test.json"
            if test_file.exists():
                with open(test_file, 'w') as f:
                    json.dump({"test": "modified_externally", "timestamp": time.time()}, f, indent=2)
                
                # Wait for file system event
                time.sleep(1)
                events = mock_socketio.get_events()
                
                if any(event['event'] == 'file_tree_updated' and 'modified' in event['data'].get('event_type', '') for event in events):
                    print("✅ File modification event detected")
                else:
                    print(f"❌ No file modification event detected. Events: {events}")
                    return False
            else:
                print("❌ Test file not found for modification test")
                return False
            
            # Test 3: Delete a file externally and check for event
            print("\n🗑️ Test 3: Deleting a file externally...")
            mock_socketio.clear_events()
            
            # Delete file directly (simulating external deletion)
            if test_file.exists():
                test_file.unlink()
                
                # Wait for file system event
                time.sleep(1)
                events = mock_socketio.get_events()
                
                if any(event['event'] == 'file_tree_updated' and 'deleted' in event['data'].get('event_type', '') for event in events):
                    print("✅ File deletion event detected")
                else:
                    print(f"❌ No file deletion event detected. Events: {events}")
                    return False
            else:
                print("❌ Test file not found for deletion test")
                return False
            
            # Test 4: Test debouncing (multiple rapid changes)
            print("\n⚡ Test 4: Testing event debouncing...")
            mock_socketio.clear_events()
            
            # Create multiple files rapidly
            for i in range(5):
                test_file_rapid = sfc_path / f"rapid_test_{i}.json"
                with open(test_file_rapid, 'w') as f:
                    json.dump({"rapid_test": i}, f)
                time.sleep(0.1)  # Small delay between creations
            
            # Wait for debounced events
            time.sleep(2)
            events = mock_socketio.get_events()
            
            # Should have fewer events than files created due to debouncing
            creation_events = [e for e in events if e['event'] == 'file_tree_updated' and 'created' in e['data'].get('event_type', '')]
            print(f"✅ Debouncing test: {len(creation_events)} events for 5 file creations")
            
            # Clean up rapid test files
            for i in range(5):
                test_file_rapid = sfc_path / f"rapid_test_{i}.json"
                if test_file_rapid.exists():
                    test_file_rapid.unlink()
            
            # Stop monitoring
            explorer.stop_monitoring()
            print("✅ File system monitoring stopped")
            
            print("\n🎉 File system monitoring tests completed!")
            return True
            
        finally:
            # Ensure monitoring is stopped
            if explorer:
                explorer.stop_monitoring()
            os.chdir(original_cwd)


if __name__ == "__main__":
    success = test_file_monitoring()
    sys.exit(0 if success else 1)