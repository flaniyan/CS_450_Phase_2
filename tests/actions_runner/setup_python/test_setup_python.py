#!/usr/bin/env python3
"""
Tests for setup-python action setup_python.py
"""

import unittest
import os
import sys
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from io import StringIO

# Add the actions-runner directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'actions-runner', '_work', '_actions', 'actions', 'setup-python', 'v4', 'python'))

from setup_python import (
    CoreActions, is_pypy_version, cache_dependencies, 
    resolve_version_input, resolve_version_input_from_default_file, main
)


class TestCoreActions(unittest.TestCase):
    """Test CoreActions class"""
    
    def test_get_input(self):
        """Test get_input method"""
        with patch.dict(os.environ, {'INPUT_PYTHON_VERSION': '3.9'}):
            result = CoreActions.get_input('python-version')
            self.assertEqual(result, '3.9')
    
    def test_get_input_required(self):
        """Test get_input with required input"""
        with self.assertRaises(ValueError):
            CoreActions.get_input('python-version', required=True)
    
    def test_get_multiline_input(self):
        """Test get_multiline_input method"""
        with patch.dict(os.environ, {'INPUT_PYTHON_VERSION': '3.9\n3.10\n3.11'}):
            result = CoreActions.get_multiline_input('python-version')
            self.assertEqual(result, ['3.9', '3.10', '3.11'])
    
    def test_get_boolean_input_true(self):
        """Test get_boolean_input with true values"""
        true_values = ['true', '1', 'yes', 'on']
        for value in true_values:
            with patch.dict(os.environ, {'INPUT_CHECK_LATEST': value}):
                result = CoreActions.get_boolean_input('check-latest')
                self.assertTrue(result)
    
    def test_get_boolean_input_false(self):
        """Test get_boolean_input with false values"""
        false_values = ['false', '0', 'no', 'off', 'anything_else']
        for value in false_values:
            with patch.dict(os.environ, {'INPUT_CHECK_LATEST': value}):
                result = CoreActions.get_boolean_input('check-latest')
                self.assertFalse(result)
    
    def test_info(self):
        """Test info logging"""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            CoreActions.info("Test message")
            self.assertIn("::info::Test message", mock_stdout.getvalue())
    
    def test_debug(self):
        """Test debug logging"""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            CoreActions.debug("Debug message")
            self.assertIn("::debug::Debug message", mock_stdout.getvalue())
    
    def test_warning(self):
        """Test warning logging"""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            CoreActions.warning("Warning message")
            self.assertIn("::warning::Warning message", mock_stdout.getvalue())
    
    def test_set_failed(self):
        """Test set_failed method"""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            with self.assertRaises(SystemExit):
                CoreActions.set_failed("Failed message")
            self.assertIn("::error::Failed message", mock_stdout.getvalue())


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions"""
    
    def test_is_pypy_version_true(self):
        """Test is_pypy_version with PyPy versions"""
        pypy_versions = ['pypy3.9', 'pypy3.10', 'pypy-3.9']
        for version in pypy_versions:
            self.assertTrue(is_pypy_version(version))
    
    def test_is_pypy_version_false(self):
        """Test is_pypy_version with non-PyPy versions"""
        non_pypy_versions = ['3.9', '3.10', '3.11', 'cpython-3.9']
        for version in non_pypy_versions:
            self.assertFalse(is_pypy_version(version))
    
    @patch('setup_python.get_cache_distributor')
    async def test_cache_dependencies(self, mock_get_distributor):
        """Test cache_dependencies function"""
        mock_distributor = AsyncMock()
        mock_get_distributor.return_value = mock_distributor
        
        await cache_dependencies('pip', '3.9')
        
        mock_get_distributor.assert_called_once_with('pip', '3.9', None)
        mock_distributor.restore_cache.assert_called_once()
    
    @patch('os.path.exists')
    @patch('setup_python.get_version_input_from_plain_file')
    def test_resolve_version_input_from_default_file(self, mock_get_version, mock_exists):
        """Test resolve_version_input_from_default_file"""
        mock_exists.return_value = True
        mock_get_version.return_value = ['3.9']
        
        result = resolve_version_input_from_default_file()
        
        self.assertEqual(result, ['3.9'])
        mock_exists.assert_called_with('.python-version')
        mock_get_version.assert_called_with('.python-version')
    
    @patch('os.path.exists')
    def test_resolve_version_input_from_default_file_not_exists(self, mock_exists):
        """Test resolve_version_input_from_default_file when file doesn't exist"""
        mock_exists.return_value = False
        
        result = resolve_version_input_from_default_file()
        
        self.assertEqual(result, [])
    
    def test_resolve_version_input_from_multiline(self):
        """Test resolve_version_input with multiline input"""
        with patch.dict(os.environ, {'INPUT_PYTHON_VERSION': '3.9\n3.10'}):
            result = resolve_version_input()
            self.assertEqual(result, ['3.9', '3.10'])
    
    def test_resolve_version_input_from_file(self):
        """Test resolve_version_input with file input"""
        with patch.dict(os.environ, {'INPUT_PYTHON_VERSION_FILE': '.python-version'}):
            with patch('os.path.exists', return_value=True):
                with patch('setup_python.get_version_input_from_file', return_value=['3.9']):
                    result = resolve_version_input()
                    self.assertEqual(result, ['3.9'])
    
    def test_resolve_version_input_file_not_exists(self):
        """Test resolve_version_input with non-existent file"""
        with patch.dict(os.environ, {'INPUT_PYTHON_VERSION_FILE': 'nonexistent.txt'}):
            with patch('os.path.exists', return_value=False):
                with self.assertRaises(ValueError):
                    resolve_version_input()
    
    def test_resolve_version_input_priority(self):
        """Test that python-version takes priority over python-version-file"""
        env_vars = {
            'INPUT_PYTHON_VERSION': '3.9',
            'INPUT_PYTHON_VERSION_FILE': '.python-version'
        }
        with patch.dict(os.environ, env_vars):
            with patch('setup_python.CoreActions.warning') as mock_warning:
                result = resolve_version_input()
                self.assertEqual(result, ['3.9'])
                mock_warning.assert_called_once()


class TestMainFunction(unittest.TestCase):
    """Test main function"""
    
    def setUp(self):
        """Set up test environment"""
        # Clear environment variables
        for key in list(os.environ.keys()):
            if key.startswith('INPUT_'):
                del os.environ[key]
    
    @patch('setup_python.resolve_version_input')
    @patch('setup_python.use_cpython_version')
    @patch('setup_python.find_pypy_version')
    @patch('setup_python.is_cache_feature_available')
    @patch('setup_python.cache_dependencies')
    @patch('setup_python.os.environ')
    async def test_main_with_versions(self, mock_environ, mock_cache_deps, mock_cache_available, 
                                    mock_find_pypy, mock_use_cpython, mock_resolve_versions):
        """Test main function with Python versions"""
        # Setup mocks
        mock_resolve_versions.return_value = ['3.9', 'pypy3.9']
        mock_cache_available.return_value = True
        
        # Mock CPython installation
        mock_cpython_result = MagicMock()
        mock_cpython_result.version = '3.9.0'
        mock_cpython_result.impl = 'CPython'
        mock_use_cpython.return_value = AsyncMock(return_value=mock_cpython_result)
        
        # Mock PyPy installation
        mock_pypy_result = MagicMock()
        mock_pypy_result.resolvedPyPyVersion = '7.3.9'
        mock_pypy_result.resolvedPythonVersion = '3.9.12'
        mock_find_pypy.return_value = AsyncMock(return_value=mock_pypy_result)
        
        # Mock environment
        mock_environ.get.return_value = '/usr/local/bin'
        
        # Mock CoreActions methods
        with patch('setup_python.CoreActions') as mock_core:
            mock_core.get_input.side_effect = lambda x, default='': {
                'architecture': 'x64',
                'update-environment': 'true',
                'cache': 'pip'
            }.get(x, default)
            mock_core.get_boolean_input.side_effect = lambda x, default=False: {
                'check-latest': False,
                'allow-prereleases': False,
                'update-environment': True
            }.get(x, default)
            mock_core.debug = MagicMock()
            mock_core.start_group = MagicMock()
            mock_core.end_group = MagicMock()
            mock_core.info = MagicMock()
            
            await main()
            
            # Verify calls
            mock_resolve_versions.assert_called_once()
            mock_use_cpython.assert_called_once()
            mock_find_pypy.assert_called_once()
            mock_cache_deps.assert_called_once()
    
    @patch('setup_python.resolve_version_input')
    @patch('setup_python.CoreActions')
    async def test_main_no_versions(self, mock_core, mock_resolve_versions):
        """Test main function with no versions specified"""
        mock_resolve_versions.return_value = []
        mock_core.warning = MagicMock()
        
        await main()
        
        mock_core.warning.assert_called_once()


if __name__ == '__main__':
    unittest.main()
