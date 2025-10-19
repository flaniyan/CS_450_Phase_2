#!/usr/bin/env python3
"""
Tests for checkout action main.py
"""

import unittest
import asyncio
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock
from io import StringIO

# Add the actions-runner directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'actions-runner', '_work', '_actions', 'actions', 'checkout', 'v3', 'python'))

from main import run, cleanup_action, CoreActions, CoreCommand


class TestCoreActions(unittest.TestCase):
    """Test CoreActions class"""
    
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
    
    def test_error(self):
        """Test error logging"""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            CoreActions.error("Error message")
            self.assertIn("::error::Error message", mock_stdout.getvalue())
    
    def test_set_failed(self):
        """Test set_failed method"""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            with self.assertRaises(SystemExit):
                CoreActions.set_failed("Failed message")
            self.assertIn("::error::Failed message", mock_stdout.getvalue())
    
    def test_start_group(self):
        """Test start group"""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            CoreActions.start_group("Test Group")
            self.assertIn("::group::Test Group", mock_stdout.getvalue())
    
    def test_end_group(self):
        """Test end group"""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            CoreActions.end_group()
            self.assertIn("::endgroup::", mock_stdout.getvalue())


class TestCoreCommand(unittest.TestCase):
    """Test CoreCommand class"""
    
    def test_issue_command_add_matcher(self):
        """Test add-matcher command"""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            CoreCommand.issue_command('add-matcher', {}, 'test.json')
            self.assertIn("::add-matcher::test.json", mock_stdout.getvalue())
    
    def test_issue_command_remove_matcher(self):
        """Test remove-matcher command"""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            CoreCommand.issue_command('remove-matcher', {'owner': 'test'}, '')
            self.assertIn("::remove-matcher owner=test::", mock_stdout.getvalue())


class TestMainFunctions(unittest.TestCase):
    """Test main functions"""
    
    @patch('main.get_inputs')
    @patch('main.get_source')
    @patch('main.CoreCommand.issue_command')
    @patch('os.path.exists')
    def test_run_success(self, mock_exists, mock_issue_command, mock_get_source, mock_get_inputs):
        """Test successful run"""
        mock_exists.return_value = True
        mock_get_inputs.return_value = {'repository': 'test/repo'}
        mock_get_source.return_value = AsyncMock()
        
        # Run the async function
        asyncio.run(run())
        
        # Verify calls
        mock_get_inputs.assert_called_once()
        mock_issue_command.assert_called()
        mock_get_source.assert_called_once()
    
    @patch('main.get_inputs')
    def test_run_input_error(self, mock_get_inputs):
        """Test run with input error"""
        mock_get_inputs.side_effect = Exception("Input error")
        
        with patch('main.CoreActions.set_failed') as mock_set_failed:
            asyncio.run(run())
            mock_set_failed.assert_called_once()
    
    @patch('main.cleanup')
    def test_cleanup_success(self, mock_cleanup):
        """Test successful cleanup"""
        mock_cleanup.return_value = AsyncMock()
        
        asyncio.run(cleanup_action())
        mock_cleanup.assert_called_once()
    
    @patch('main.cleanup')
    def test_cleanup_error(self, mock_cleanup):
        """Test cleanup with error"""
        mock_cleanup.side_effect = Exception("Cleanup error")
        
        with patch('main.CoreActions.warning') as mock_warning:
            asyncio.run(cleanup_action())
            mock_warning.assert_called_once()


if __name__ == '__main__':
    unittest.main()
