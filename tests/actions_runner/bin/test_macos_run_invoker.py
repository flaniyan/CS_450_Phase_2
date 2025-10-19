#!/usr/bin/env python3
"""
Tests for macOS run invoker macos_run_invoker.py
"""

import unittest
import os
import sys
import subprocess
from unittest.mock import patch, MagicMock
from io import StringIO

# Add the actions-runner directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'actions-runner', 'bin', 'python'))

from macos_run_invoker import main


class TestMacOSRunInvoker(unittest.TestCase):
    """Test macOS run invoker functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.original_argv = sys.argv.copy()
    
    def tearDown(self):
        """Clean up test environment"""
        sys.argv = self.original_argv
    
    def test_main_insufficient_args(self):
        """Test main with insufficient arguments"""
        sys.argv = ['python', 'macos_run_invoker.py']
        
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with self.assertRaises(SystemExit):
                main()
            self.assertIn("Usage:", mock_stderr.getvalue())
    
    def test_main_success(self):
        """Test main with successful command execution"""
        sys.argv = ['python', 'macos_run_invoker.py', 'echo', 'hello', 'world']
        
        with patch('subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                main()
                
                # Check debug output
                output = mock_stdout.getvalue()
                self.assertIn("::debug::macos-run-invoker: echo", output)
                self.assertIn('["hello", "world"]', output)
                
                # Check subprocess call
                mock_popen.assert_called_once_with(
                    ['echo', 'hello', 'world'],
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    stdin=sys.stdin
                )
                mock_process.wait.assert_called_once()
    
    def test_main_command_failure(self):
        """Test main with command failure"""
        sys.argv = ['python', 'macos_run_invoker.py', 'false']
        
        with patch('subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_process.wait.return_value = 1
            mock_popen.return_value = mock_process
            
            with self.assertRaises(SystemExit) as cm:
                main()
            
            self.assertEqual(cm.exception.code, 1)
    
    def test_main_file_not_found(self):
        """Test main with command not found"""
        sys.argv = ['python', 'macos_run_invoker.py', 'nonexistent_command']
        
        with patch('subprocess.Popen', side_effect=FileNotFoundError):
            with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                with self.assertRaises(SystemExit) as cm:
                    main()
                
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("Shell not found", mock_stderr.getvalue())
    
    def test_main_general_exception(self):
        """Test main with general exception"""
        sys.argv = ['python', 'macos_run_invoker.py', 'test_command']
        
        with patch('subprocess.Popen', side_effect=Exception("Test error")):
            with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                with self.assertRaises(SystemExit) as cm:
                    main()
                
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("Failed to run command", mock_stderr.getvalue())
    
    def test_main_with_single_arg(self):
        """Test main with single argument"""
        sys.argv = ['python', 'macos-run-invoker.py', 'ls']
        
        with patch('subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            main()
            
            # Check subprocess call with empty args list
            mock_popen.assert_called_once_with(
                ['ls'],
                stdout=sys.stdout,
                stderr=sys.stderr,
                stdin=sys.stdin
            )
    
    def test_main_with_multiple_args(self):
        """Test main with multiple arguments"""
        sys.argv = ['python', 'macos_run_invoker.py', 'git', 'status', '--porcelain']
        
        with patch('subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process
            
            main()
            
            # Check subprocess call with multiple args
            mock_popen.assert_called_once_with(
                ['git', 'status', '--porcelain'],
                stdout=sys.stdout,
                stderr=sys.stderr,
                stdin=sys.stdin
            )


if __name__ == '__main__':
    unittest.main()
