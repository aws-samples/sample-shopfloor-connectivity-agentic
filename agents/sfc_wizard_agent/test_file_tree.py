#!/usr/bin/env python3
"""
Test script for file tree data structure and API logic.
This script tests the FileNode data model and tree generation functionality.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add the sfc_wizard package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sfc_wizard'))

from sfc_wizard.tools.file_explorer import SFCFileExplorer, FileNode


def create_test_structure(base_path: Path):
    """Create a test directory structure for testing."""
    # Create directories
    (base_path / "stored_configs").mkdir(exist_ok=True)
    (base_path / "stored_results").mkdir(exist_ok=True)
    (base_path / "runs" / "test_run_20250131" / "logs").mkdir(parents=True, exist_ok=True)
    (base_path / "runs" / "test_run_20250131" / "data").mkdir(parents=True, exist_ok=True)
    (base_path / "modules" / "sfc-main" / "lib").mkdir(parents=True, exist_ok=True)
    
    # Create test files
    (base_path / "stored_configs" / "test_config.json").write_text('{"test": "config"}')
    (base_path / "stored_results" / "analysis.md").write_text('# Analysis Results\n\nTest results here.')
    (base_path / "runs" / "test_run_20250131" / "logs" / "sfc.log").write_text('INFO: Test log entry\n')
    (base_path / "runs" / "test_run_20250131" / "data" / "sensor_data.csv").write_text('timestamp,value\n2025-01-31,42\n')
    (base_path / "modules" / "sfc-main" / "lib" / "sfc-core.jar").write_text('fake jar content')
    (base_path / "README.md").write_text('# SFC Test Directory\n\nThis is a test.')


def test_file_node_data_model():
    """Test the FileNode data model."""
    print("Testing FileNode data model...")
    
    # Test basic FileNode creation
    node = FileNode(
        name="test.json",
        path="stored_configs/test.json",
        type="file",
        size=1024,
        modified="2025-01-31T12:00:00",
        purpose="config",
        editable=True
    )
    
    # Test to_dict conversion
    node_dict = node.to_dict()
    assert node_dict['name'] == "test.json"
    assert node_dict['type'] == "file"
    assert node_dict['purpose'] == "config"
    assert node_dict['editable'] == True
    
    # Test from_dict conversion
    reconstructed = FileNode.from_dict(node_dict)
    assert reconstructed.name == node.name
    assert reconstructed.type == node.type
    assert reconstructed.purpose == node.purpose
    
    # Test with children
    parent = FileNode(
        name="configs",
        path="configs",
        type="directory",
        children=[node]
    )
    
    parent_dict = parent.to_dict()
    assert len(parent_dict['children']) == 1
    assert parent_dict['children'][0]['name'] == "test.json"
    
    print("✅ FileNode data model tests passed")


def test_file_type_detection():
    """Test file type detection logic."""
    print("Testing file type detection...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        sfc_path = temp_path / ".sfc"
        sfc_path.mkdir()
        
        create_test_structure(sfc_path)
        
        # Initialize file explorer
        explorer = SFCFileExplorer()
        explorer.sfc_root = sfc_path
        
        # Test different file types
        test_cases = [
            ("stored_configs/test_config.json", "config"),
            ("stored_results/analysis.md", "result"),
            ("runs/test_run_20250131/logs/sfc.log", "log"),
            ("runs/test_run_20250131/data/sensor_data.csv", "data"),
            ("modules/sfc-main/lib/sfc-core.jar", "module"),
            ("README.md", "documentation")
        ]
        
        for file_path, expected_purpose in test_cases:
            full_path = sfc_path / file_path
            purpose = explorer._get_file_purpose(full_path)
            print(f"  {file_path} -> {purpose} (expected: {expected_purpose})")
            assert purpose == expected_purpose, f"Expected {expected_purpose}, got {purpose} for {file_path}"
    
    print("✅ File type detection tests passed")


def test_tree_generation():
    """Test tree generation logic."""
    print("Testing tree generation...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        sfc_path = temp_path / ".sfc"
        sfc_path.mkdir()
        
        create_test_structure(sfc_path)
        
        # Initialize file explorer
        explorer = SFCFileExplorer()
        explorer.sfc_root = sfc_path
        
        # Test full tree generation
        tree = explorer.get_file_tree("", depth=3)
        
        assert 'error' not in tree, f"Tree generation failed: {tree.get('error')}"
        assert tree['type'] == 'directory'
        assert tree['name'] == '.sfc'
        assert 'children' in tree
        
        # Check that main directories are present
        child_names = [child['name'] for child in tree['children']]
        expected_dirs = ['modules', 'runs', 'stored_configs', 'stored_results']
        for expected_dir in expected_dirs:
            assert expected_dir in child_names, f"Expected directory {expected_dir} not found"
        
        # Test specific directory
        configs_tree = explorer.get_file_tree("stored_configs", depth=1)
        assert 'error' not in configs_tree, f"Getting configs tree failed: {configs_tree.get('error')}"
        assert configs_tree['name'] == 'stored_configs'
        assert configs_tree['type'] == 'directory'
        
        # Check that config file is present
        config_children = [child['name'] for child in configs_tree['children']]
        assert 'test_config.json' in config_children
        
        # Verify file metadata
        config_file = next(child for child in configs_tree['children'] if child['name'] == 'test_config.json')
        assert config_file['type'] == 'file'
        assert config_file['purpose'] == 'config'
        assert config_file['editable'] == True
        assert config_file['size'] > 0
    
    print("✅ Tree generation tests passed")


def test_lazy_loading():
    """Test lazy loading functionality."""
    print("Testing lazy loading...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        sfc_path = temp_path / ".sfc"
        sfc_path.mkdir()
        
        create_test_structure(sfc_path)
        
        # Initialize file explorer
        explorer = SFCFileExplorer()
        explorer.sfc_root = sfc_path
        
        # Test getting children of a specific directory
        children_result = explorer.get_directory_children("runs")
        
        assert 'error' not in children_result, f"Getting children failed: {children_result.get('error')}"
        assert 'children' in children_result
        
        children = children_result['children']
        child_names = [child['name'] for child in children]
        assert 'test_run_20250131' in child_names
        
        # Test getting children of a deeper directory
        run_children = explorer.get_directory_children("runs/test_run_20250131")
        assert 'children' in run_children
        
        run_child_names = [child['name'] for child in run_children['children']]
        assert 'logs' in run_child_names
        assert 'data' in run_child_names
    
    print("✅ Lazy loading tests passed")


def test_metadata_extraction():
    """Test file metadata extraction."""
    print("Testing metadata extraction...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        sfc_path = temp_path / ".sfc"
        sfc_path.mkdir()
        
        create_test_structure(sfc_path)
        
        # Initialize file explorer
        explorer = SFCFileExplorer()
        explorer.sfc_root = sfc_path
        
        # Test file metadata
        config_path = sfc_path / "stored_configs" / "test_config.json"
        file_node = explorer._get_file_metadata(config_path)
        
        assert file_node.name == "test_config.json"
        assert file_node.type == "file"
        assert file_node.purpose == "config"
        assert file_node.editable == True
        assert file_node.size > 0
        assert file_node.modified is not None
        
        # Test directory metadata
        configs_path = sfc_path / "stored_configs"
        dir_node = explorer._get_file_metadata(configs_path)
        
        assert dir_node.name == "stored_configs"
        assert dir_node.type == "directory"
        assert dir_node.child_count is not None
        assert dir_node.child_count >= 1  # At least the test_config.json file
    
    print("✅ Metadata extraction tests passed")


def main():
    """Run all tests."""
    print("🧪 Running File Tree Implementation Tests")
    print("=" * 50)
    
    try:
        test_file_node_data_model()
        test_file_type_detection()
        test_tree_generation()
        test_lazy_loading()
        test_metadata_extraction()
        
        print("=" * 50)
        print("🎉 All tests passed successfully!")
        print("✅ FileNode data model implemented correctly")
        print("✅ File type detection working properly")
        print("✅ Tree generation logic functional")
        print("✅ Lazy loading implemented")
        print("✅ Metadata extraction working")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()