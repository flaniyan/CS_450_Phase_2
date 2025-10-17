#!/usr/bin/env python3
"""
Tests for checkout action input_helper.py
"""

import unittest
import os
import sys
from unittest.mock import patch

# Add the actions-runner directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'actions-runner', '_work', '_actions', 'actions', 'checkout', 'v3', 'python'))

from input_helper import get_inputs, get_input, get_boolean_input, get_integer_input


class TestInputHelper(unittest.TestCase):
    """Test input helper functions"""
    
    def setUp(self):
        """Set up test environment"""
        # Clear environment variables
        for key in list(os.environ.keys()):
            if key.startswith('INPUT_'):
                del os.environ[key]
    
    def test_get_input_required(self):
        """Test get_input with required input"""
        with patch.dict(os.environ, {'INPUT_REPOSITORY': 'test/repo'}):
            result = get_input('repository', required=True)
            self.assertEqual(result, 'test/repo')
    
    def test_get_input_required_missing(self):
        """Test get_input with missing required input"""
        with self.assertRaises(ValueError):
            get_input('repository', required=True)
    
    def test_get_input_with_default(self):
        """Test get_input with default value"""
        result = get_input('repository', default='default/repo')
        self.assertEqual(result, 'default/repo')
    
    def test_get_boolean_input_true(self):
        """Test get_boolean_input with true values"""
        true_values = ['true', '1', 'yes', 'on']
        for value in true_values:
            with patch.dict(os.environ, {'INPUT_TEST': value}):
                result = get_boolean_input('test')
                self.assertTrue(result)
    
    def test_get_boolean_input_false(self):
        """Test get_boolean_input with false values"""
        false_values = ['false', '0', 'no', 'off', 'anything_else']
        for value in false_values:
            with patch.dict(os.environ, {'INPUT_TEST': value}):
                result = get_boolean_input('test')
                self.assertFalse(result)
    
    def test_get_boolean_input_default(self):
        """Test get_boolean_input with default value"""
        result = get_boolean_input('test', default=True)
        self.assertTrue(result)
    
    def test_get_integer_input_valid(self):
        """Test get_integer_input with valid integer"""
        with patch.dict(os.environ, {'INPUT_DEPTH': '5'}):
            result = get_integer_input('depth')
            self.assertEqual(result, 5)
    
    def test_get_integer_input_invalid(self):
        """Test get_integer_input with invalid integer"""
        with patch.dict(os.environ, {'INPUT_DEPTH': 'invalid'}):
            result = get_integer_input('depth', default=10)
            self.assertEqual(result, 10)
    
    def test_get_inputs_complete(self):
        """Test get_inputs with complete input set"""
        env_vars = {
            'INPUT_REPOSITORY': 'test/repo',
            'INPUT_REF': 'main',
            'INPUT_TOKEN': 'test_token',
            'INPUT_SSH_KEY': 'test_key',
            'INPUT_SSH_KNOWN_HOSTS': 'test_hosts',
            'INPUT_SSH_STRICT': 'true',
            'INPUT_PERSIST_CREDENTIALS': 'true',
            'INPUT_PATH': './test',
            'INPUT_CLEAN': 'true',
            'INPUT_FETCH_DEPTH': '10',
            'INPUT_LFS': 'false',
            'INPUT_SUBMODULES': 'false',
            'INPUT_SET_SAFE_DIRECTORY': 'true'
        }
        
        with patch.dict(os.environ, env_vars):
            result = get_inputs()
            
            self.assertEqual(result['repository'], 'test/repo')
            self.assertEqual(result['repository_owner'], 'test')
            self.assertEqual(result['repository_name'], 'repo')
            self.assertEqual(result['ref'], 'main')
            self.assertEqual(result['token'], 'test_token')
            self.assertTrue(result['ssh_strict'])
            self.assertTrue(result['persist_credentials'])
            self.assertEqual(result['path'], './test')
            self.assertTrue(result['clean'])
            self.assertEqual(result['fetch_depth'], 10)
            self.assertFalse(result['lfs'])
            self.assertEqual(result['submodules'], 'false')
            self.assertTrue(result['set_safe_directory'])
    
    def test_get_inputs_minimal(self):
        """Test get_inputs with minimal input set"""
        with patch.dict(os.environ, {'INPUT_REPOSITORY': 'test/repo'}):
            result = get_inputs()
            
            self.assertEqual(result['repository'], 'test/repo')
            self.assertEqual(result['repository_owner'], 'test')
            self.assertEqual(result['repository_name'], 'repo')
            self.assertEqual(result['ref'], '')
            self.assertEqual(result['token'], '')
            self.assertTrue(result['ssh_strict'])  # default
            self.assertTrue(result['persist_credentials'])  # default
            self.assertEqual(result['path'], '.')  # default
            self.assertTrue(result['clean'])  # default
            self.assertEqual(result['fetch_depth'], 1)  # default
            self.assertFalse(result['lfs'])  # default
            self.assertEqual(result['submodules'], 'false')  # default
            self.assertTrue(result['set_safe_directory'])  # default


if __name__ == '__main__':
    unittest.main()
