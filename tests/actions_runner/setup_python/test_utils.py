#!/usr/bin/env python3
"""
Tests for setup-python action utils.py
"""

import unittest
import os
import sys
import platform
from unittest.mock import patch, MagicMock

# Add the actions-runner directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'actions-runner', '_work', '_actions', 'actions', 'setup-python', 'v4', 'python'))

from utils import (
    IS_WINDOWS, IS_LINUX, IS_MAC, get_os_info, log_warning,
    is_cache_feature_available, get_version_input_from_file,
    get_version_input_from_plain_file, find_python_executable,
    get_python_version
)


class TestPlatformDetection(unittest.TestCase):
    """Test platform detection constants"""
    
    def test_platform_constants(self):
        """Test platform detection constants"""
        current_platform = platform.system()
        
        if current_platform == 'Windows':
            self.assertTrue(IS_WINDOWS)
            self.assertFalse(IS_LINUX)
            self.assertFalse(IS_MAC)
        elif current_platform == 'Linux':
            self.assertFalse(IS_WINDOWS)
            self.assertTrue(IS_LINUX)
            self.assertFalse(IS_MAC)
        elif current_platform == 'Darwin':
            self.assertFalse(IS_WINDOWS)
            self.assertFalse(IS_LINUX)
            self.assertTrue(IS_MAC)
    
    def test_get_os_info(self):
        """Test get_os_info function"""
        os_info = get_os_info()
        
        self.assertIn('platform', os_info)
        self.assertIn('version', os_info)
        self.assertIn('architecture', os_info)
        self.assertIn('processor', os_info)
        
        self.assertEqual(os_info['platform'], platform.system())
        self.assertEqual(os_info['architecture'], platform.machine())


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions"""
    
    def test_log_warning(self):
        """Test log_warning function"""
        with patch('builtins.print') as mock_print:
            log_warning("Test warning")
            mock_print.assert_called_once_with("::warning::Test warning")
    
    def test_is_cache_feature_available(self):
        """Test is_cache_feature_available function"""
        result = is_cache_feature_available()
        self.assertTrue(result)  # Should always return True in our implementation
    
    def test_get_version_input_from_file_exists(self):
        """Test get_version_input_from_file with existing file"""
        test_content = "3.9\n3.10\n3.11\n"
        
        with patch('builtins.open', unittest.mock.mock_open(read_data=test_content)):
            result = get_version_input_from_file('test.txt')
            self.assertEqual(result, ['3.9', '3.10', '3.11'])
    
    def test_get_version_input_from_file_not_exists(self):
        """Test get_version_input_from_file with non-existent file"""
        with patch('builtins.open', side_effect=FileNotFoundError):
            result = get_version_input_from_file('nonexistent.txt')
            self.assertEqual(result, [])
    
    def test_get_version_input_from_plain_file(self):
        """Test get_version_input_from_plain_file function"""
        test_content = "3.9\n3.10\n3.11\n"
        
        with patch('builtins.open', unittest.mock.mock_open(read_data=test_content)):
            result = get_version_input_from_plain_file('test.txt')
            self.assertEqual(result, ['3.9', '3.10', '3.11'])
    
    def test_get_version_input_from_file_empty_lines(self):
        """Test get_version_input_from_file with empty lines"""
        test_content = "3.9\n\n3.10\n\n\n3.11\n"
        
        with patch('builtins.open', unittest.mock.mock_open(read_data=test_content)):
            result = get_version_input_from_file('test.txt')
            self.assertEqual(result, ['3.9', '3.10', '3.11'])
    
    @patch('subprocess.run')
    def test_find_python_executable_python3(self, mock_run):
        """Test find_python_executable finding python3"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '/usr/bin/python3'
        mock_run.return_value = mock_result
        
        result = find_python_executable()
        self.assertEqual(result, '/usr/bin/python3')
        mock_run.assert_called_with(['which', 'python3'], capture_output=True, text=True)
    
    @patch('subprocess.run')
    def test_find_python_executable_python(self, mock_run):
        """Test find_python_executable finding python"""
        # Mock python3 not found
        mock_result_python3 = MagicMock()
        mock_result_python3.returncode = 1
        mock_run.side_effect = [
            mock_result_python3,  # python3 not found
            MagicMock(returncode=0, stdout='/usr/bin/python')  # python found
        ]
        
        result = find_python_executable()
        self.assertEqual(result, '/usr/bin/python')
        self.assertEqual(mock_run.call_count, 2)
    
    @patch('subprocess.run')
    def test_find_python_executable_not_found(self, mock_run):
        """Test find_python_executable when no python found"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        
        result = find_python_executable()
        self.assertIsNone(result)
        self.assertEqual(mock_run.call_count, 2)  # python3 and python
    
    @patch('subprocess.run')
    def test_find_python_executable_file_not_found(self, mock_run):
        """Test find_python_executable when which command not found"""
        mock_run.side_effect = FileNotFoundError()
        
        result = find_python_executable()
        self.assertIsNone(result)
    
    @patch('subprocess.run')
    def test_get_python_version_success(self, mock_run):
        """Test get_python_version with successful command"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'Python 3.9.0'
        mock_run.return_value = mock_result
        
        result = get_python_version('/usr/bin/python3')
        self.assertEqual(result, 'Python 3.9.0')
        mock_run.assert_called_with(['/usr/bin/python3', '--version'], capture_output=True, text=True)
    
    @patch('subprocess.run')
    def test_get_python_version_failure(self, mock_run):
        """Test get_python_version with failed command"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        
        result = get_python_version('/usr/bin/python3')
        self.assertIsNone(result)
    
    @patch('subprocess.run')
    def test_get_python_version_exception(self, mock_run):
        """Test get_python_version with exception"""
        mock_run.side_effect = Exception("Command failed")
        
        result = get_python_version('/usr/bin/python3')
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
