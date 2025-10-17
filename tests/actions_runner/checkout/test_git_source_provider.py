#!/usr/bin/env python3
"""
Tests for checkout action git_source_provider.py
"""

import unittest
import os
import sys
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import subprocess

# Add the actions-runner directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'actions-runner', '_work', '_actions', 'actions', 'checkout', 'v3', 'python'))

from git_source_provider import GitCommandManager, get_source, cleanup


class TestGitCommandManager(unittest.TestCase):
    """Test GitCommandManager class"""
    
    def setUp(self):
        """Set up test environment"""
        self.git_manager = GitCommandManager()
    
    @patch('subprocess.run')
    def test_exec_success(self, mock_run):
        """Test successful git command execution"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = asyncio.run(self.git_manager.exec(['status']))
        
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "success")
        mock_run.assert_called_once_with(['git', 'status'], cwd=None, capture_output=True, text=True)
    
    @patch('subprocess.run')
    def test_exec_failure(self, mock_run):
        """Test failed git command execution"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error"
        mock_run.return_value = mock_result
        
        result = asyncio.run(self.git_manager.exec(['invalid']))
        
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "error")
    
    @patch('subprocess.run')
    def test_exec_stdout_success(self, mock_run):
        """Test exec_stdout with successful command"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = asyncio.run(self.git_manager.exec_stdout(['status']))
        
        self.assertEqual(result, "output")
    
    @patch('subprocess.run')
    def test_exec_stdout_failure(self, mock_run):
        """Test exec_stdout with failed command"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error"
        mock_run.return_value = mock_result
        
        with self.assertRaises(RuntimeError):
            asyncio.run(self.git_manager.exec_stdout(['invalid']))


class TestGitSourceProvider(unittest.TestCase):
    """Test git source provider functions"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_settings = {
            'repository_owner': 'test',
            'repository_name': 'repo',
            'path': './test_repo',
            'ref': 'main',
            'token': 'test_token',
            'set_safe_directory': True
        }
    
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('git_source_provider.GitCommandManager')
    @patch('shutil.rmtree')
    def test_get_source_success(self, mock_rmtree, mock_git_class, mock_makedirs, mock_exists):
        """Test successful get_source"""
        # Setup mocks
        mock_exists.return_value = False  # Repository doesn't exist
        mock_git = AsyncMock()
        mock_git_class.return_value = mock_git
        
        # Mock successful git commands
        mock_clone_result = MagicMock()
        mock_clone_result.returncode = 0
        mock_checkout_result = MagicMock()
        mock_checkout_result.returncode = 0
        mock_safe_dir_result = MagicMock()
        mock_safe_dir_result.returncode = 0
        
        mock_git.exec.side_effect = [mock_clone_result, mock_checkout_result, mock_safe_dir_result]
        
        # Run the function
        asyncio.run(get_source(self.test_settings))
        
        # Verify calls
        mock_rmtree.assert_not_called()  # Path doesn't exist
        mock_makedirs.assert_called_once_with('./test_repo', exist_ok=True)
        self.assertEqual(mock_git.exec.call_count, 3)  # clone, checkout, safe directory
    
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('git_source_provider.GitCommandManager')
    @patch('shutil.rmtree')
    def test_get_source_existing_path(self, mock_rmtree, mock_git_class, mock_makedirs, mock_exists):
        """Test get_source with existing path"""
        # Setup mocks
        mock_exists.return_value = True  # Repository exists
        mock_git = AsyncMock()
        mock_git_class.return_value = mock_git
        
        # Mock successful git commands
        mock_clone_result = MagicMock()
        mock_clone_result.returncode = 0
        mock_checkout_result = MagicMock()
        mock_checkout_result.returncode = 0
        mock_safe_dir_result = MagicMock()
        mock_safe_dir_result.returncode = 0
        
        mock_git.exec.side_effect = [mock_clone_result, mock_checkout_result, mock_safe_dir_result]
        
        # Run the function
        asyncio.run(get_source(self.test_settings))
        
        # Verify calls
        mock_rmtree.assert_called_once_with('./test_repo')
        mock_makedirs.assert_called_once_with('./test_repo', exist_ok=True)
    
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('git_source_provider.GitCommandManager')
    def test_get_source_clone_failure(self, mock_git_class, mock_makedirs, mock_exists):
        """Test get_source with clone failure"""
        # Setup mocks
        mock_exists.return_value = False
        mock_git = AsyncMock()
        mock_git_class.return_value = mock_git
        
        # Mock failed clone
        mock_clone_result = MagicMock()
        mock_clone_result.returncode = 1
        mock_clone_result.stderr = "Clone failed"
        mock_git.exec.return_value = mock_clone_result
        
        # Run the function and expect exception
        with self.assertRaises(RuntimeError):
            asyncio.run(get_source(self.test_settings))
    
    @patch('os.path.exists')
    @patch('shutil.rmtree')
    def test_cleanup_success(self, mock_rmtree, mock_exists):
        """Test successful cleanup"""
        mock_exists.return_value = True
        
        asyncio.run(cleanup('./test_repo'))
        
        mock_rmtree.assert_called_once_with('./test_repo')
    
    @patch('os.path.exists')
    @patch('shutil.rmtree')
    def test_cleanup_path_not_exists(self, mock_rmtree, mock_exists):
        """Test cleanup when path doesn't exist"""
        mock_exists.return_value = False
        
        asyncio.run(cleanup('./test_repo'))
        
        mock_rmtree.assert_not_called()
    
    @patch('os.path.exists')
    @patch('shutil.rmtree')
    def test_cleanup_error(self, mock_rmtree, mock_exists):
        """Test cleanup with error"""
        mock_exists.return_value = True
        mock_rmtree.side_effect = Exception("Cleanup error")
        
        # Should not raise exception, just log warning
        asyncio.run(cleanup('./test_repo'))
        
        mock_rmtree.assert_called_once_with('./test_repo')


if __name__ == '__main__':
    unittest.main()
