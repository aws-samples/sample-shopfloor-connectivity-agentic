#!/usr/bin/env python3
"""
Integration test for file explorer API endpoints.
Tests the Flask API endpoints that use the file tree functionality.
"""

import os
import sys
import tempfile
import shutil
import json
from pathlib import Path

# Add the sfc_wizard package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sfc_wizard'))

from sfc_wizard.tools.file_explorer import SFCFileExplorer


def create_test_structure(base_path: Path):
    """Create a test directory structure for testing."""
    # Create directories
    (base_path / "stored_configs").mkdir(exist_ok=True)
    (base_path / "stored_results").mkdir(exist_ok=True)
    (base_path / "runs" / "test_run_20250131" / "logs").mkdir(parents=True, exist_ok=True)
    (base_path / "runs" / "test_run_20250131" / "data").mkdir(parents=True, exist_ok=True)
    (base_path / "modules" / "sfc-main" / "lib").mkdir(parents=True, exist_ok=True)
    
    # Create test files
    (base_path / "stored_configs" / "test_config.json").write_text('{"test": "config", "version": "1.0"}')
    (base_path / "stored_results" / "analysis.md").write_text('# Analysis Results\n\nTest results here.')
    (base_path / "runs" / "test_run_20250131" / "logs" / "sfc.log").write_text('INFO: Test log entry\nDEBUG: Another entry\n')
    (base_path / "runs" / "test_run_20250131" / "data" / "sensor_data.csv").write_text('timestamp,value\n2025-01-31,42\n2025-01-31,43\n')
    (base_path / "modules" / "sfc-main" / "lib" / "sfc-core.jar").write_text('fake jar content')
    (base_path / "README.md").write_text('# SFC Test Directory\n\nThis is a test.')


def test_api_get_file_tree():
    """Test the get_file_tree API functionality."""
    print("Testing API get_file_tree functionality...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        sfc_path = temp_path / ".sfc"
        sfc_path.mkdir()
        
        create_test_structure(sfc_path)
        
        # Initialize file explorer
        explorer = SFCFileExplorer()
        explorer.sfc_root = sfc_path
        
        # Test root tree
        tree = explorer.get_file_tree("", depth=2)
        assert 'error' not in tree
        assert tree['type'] == 'directory'
        assert 'children' in tree
        
        # Verify main directories are present
        child_names = [child['name'] for child in tree['children']]
        expected_dirs = ['modules', 'runs', 'stored_configs', 'stored_results', 'README.md']
        for expected in expected_dirs:
            assert expected in child_names, f"Expected {expected} not found in {child_names}"
        
        # Test specific directory
        configs_tree = explorer.get_file_tree("stored_configs", depth=1)
        assert 'error' not in configs_tree
        assert configs_tree['name'] == 'stored_configs'
        assert configs_tree['type'] == 'directory'
        assert len(configs_tree['children']) == 1
        assert configs_tree['children'][0]['name'] == 'test_config.json'
        assert configs_tree['children'][0]['purpose'] == 'config'
        assert configs_tree['children'][0]['editable'] == True
    
    print("✅ API get_file_tree tests passed")


def test_api_get_directory_children():
    """Test the get_directory_children API functionality."""
    print("Testing API get_directory_children functionality...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        sfc_path = temp_path / ".sfc"
        sfc_path.mkdir()
        
        create_test_structure(sfc_path)
        
        # Initialize file explorer
        explorer = SFCFileExplorer()
        explorer.sfc_root = sfc_path
        
        # Test getting children of runs directory
        children_result = explorer.get_directory_children("runs")
        assert 'error' not in children_result
        assert 'children' in children_result
        
        children = children_result['children']
        assert len(children) == 1
        assert children[0]['name'] == 'test_run_20250131'
        assert children[0]['type'] == 'directory'
        
        # Test getting children of a deeper directory
        run_children = explorer.get_directory_children("runs/test_run_20250131")
        assert 'error' not in run_children
        assert 'children' in run_children
        
        run_child_names = [child['name'] for child in run_children['children']]
        assert 'logs' in run_child_names
        assert 'data' in run_child_names
    
    print("✅ API get_directory_children tests passed")


def test_api_get_file_content():
    """Test the get_file_content API functionality."""
    print("Testing API get_file_content functionality...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        sfc_path = temp_path / ".sfc"
        sfc_path.mkdir()
        
        create_test_structure(sfc_path)
        
        # Initialize file explorer
        explorer = SFCFileExplorer()
        explorer.sfc_root = sfc_path
        
        # Test reading JSON file
        json_content = explorer.get_file_content("stored_configs/test_config.json")
        assert 'error' not in json_content
        assert json_content['path'] == "stored_configs/test_config.json"
        assert json_content['mime_type'] == 'application/json'
        assert json_content['editable'] == True
        assert json_content['purpose'] == 'config'
        
        # Verify JSON content is valid
        parsed_json = json.loads(json_content['content'])
        assert parsed_json['test'] == 'config'
        assert parsed_json['version'] == '1.0'
        
        # Test reading Markdown file
        md_content = explorer.get_file_content("stored_results/analysis.md")
        assert 'error' not in md_content
        assert md_content['path'] == "stored_results/analysis.md"
        assert md_content['editable'] == True
        assert md_content['purpose'] == 'result'
        assert '# Analysis Results' in md_content['content']
        
        # Test reading log file
        log_content = explorer.get_file_content("runs/test_run_20250131/logs/sfc.log")
        assert 'error' not in log_content
        assert log_content['editable'] == False  # Log files are not editable
        assert log_content['purpose'] == 'log'
        assert 'INFO: Test log entry' in log_content['content']
    
    print("✅ API get_file_content tests passed")


def test_api_create_and_save_file():
    """Test the create_file and save_file API functionality."""
    print("Testing API create_file and save_file functionality...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        sfc_path = temp_path / ".sfc"
        sfc_path.mkdir()
        
        create_test_structure(sfc_path)
        
        # Initialize file explorer
        explorer = SFCFileExplorer()
        explorer.sfc_root = sfc_path
        
        # Test creating a JSON file
        create_result = explorer.create_file("stored_configs/new_config.json", "json")
        assert 'error' not in create_result
        assert create_result['success'] == True
        assert create_result['file']['name'] == 'new_config.json'
        assert create_result['file']['editable'] == True
        
        # Verify file was created
        assert (sfc_path / "stored_configs" / "new_config.json").exists()
        
        # Test saving content to the file
        new_content = '{"name": "new config", "enabled": true}'
        save_result = explorer.save_file("stored_configs/new_config.json", new_content)
        assert 'error' not in save_result
        assert save_result['success'] == True
        
        # Verify content was saved correctly
        saved_content = (sfc_path / "stored_configs" / "new_config.json").read_text()
        parsed_saved = json.loads(saved_content)
        assert parsed_saved['name'] == 'new config'
        assert parsed_saved['enabled'] == True
        
        # Test creating a Markdown file
        md_create_result = explorer.create_file("stored_results/new_doc.md", "markdown")
        assert 'error' not in md_create_result
        assert md_create_result['success'] == True
        
        # Test saving Markdown content
        md_content = "# New Document\n\nThis is a test document.\n\n## Section 1\n\nContent here."
        md_save_result = explorer.save_file("stored_results/new_doc.md", md_content)
        assert 'error' not in md_save_result
        assert md_save_result['success'] == True
        
        # Verify Markdown content
        saved_md = (sfc_path / "stored_results" / "new_doc.md").read_text()
        assert "# New Document" in saved_md
        assert "## Section 1" in saved_md
    
    print("✅ API create_file and save_file tests passed")


def test_api_delete_file():
    """Test the delete_file API functionality."""
    print("Testing API delete_file functionality...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        sfc_path = temp_path / ".sfc"
        sfc_path.mkdir()
        
        create_test_structure(sfc_path)
        
        # Initialize file explorer
        explorer = SFCFileExplorer()
        explorer.sfc_root = sfc_path
        
        # Verify file exists
        test_file = sfc_path / "stored_configs" / "test_config.json"
        assert test_file.exists()
        
        # Test deleting a file
        delete_result = explorer.delete_file("stored_configs/test_config.json")
        assert 'error' not in delete_result
        assert delete_result['success'] == True
        
        # Verify file was deleted
        assert not test_file.exists()
        
        # Test deleting a directory (should require recursive=True)
        delete_dir_result = explorer.delete_file("runs/test_run_20250131", recursive=True)
        assert 'error' not in delete_dir_result
        assert delete_dir_result['success'] == True
        
        # Verify directory was deleted
        assert not (sfc_path / "runs" / "test_run_20250131").exists()
    
    print("✅ API delete_file tests passed")


def main():
    """Run all API integration tests."""
    print("🧪 Running File Explorer API Integration Tests")
    print("=" * 60)
    
    try:
        test_api_get_file_tree()
        test_api_get_directory_children()
        test_api_get_file_content()
        test_api_create_and_save_file()
        test_api_delete_file()
        
        print("=" * 60)
        print("🎉 All API integration tests passed successfully!")
        print("✅ File tree API working correctly")
        print("✅ Directory children API working correctly")
        print("✅ File content API working correctly")
        print("✅ File creation and saving API working correctly")
        print("✅ File deletion API working correctly")
        print()
        print("🚀 The file explorer API is ready for use with the web UI!")
        
    except Exception as e:
        print(f"❌ API integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()