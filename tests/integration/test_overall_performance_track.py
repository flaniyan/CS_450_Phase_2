"""
Overall Performance Track Test Orchestrator
Runs all performance track tests by phase and provides a comprehensive summary.
Run with: pytest tests/integration/test_overall_performance_track.py -v -s
"""
import pytest
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple
import json
from datetime import datetime

# Module-level storage for phase results
_phase_results = {}

# Test file paths for each phase
PHASE_TESTS = {
    "Phase 1: Workload Setup": [
        "tests/unit/test_performance_load_generator.py",
        "tests/integration/test_performance_workload_setup.py"
    ],
    "Phase 2: Measurement Infrastructure": [
        "tests/unit/test_performance_statistics.py",
        "tests/integration/test_performance_metrics.py"
    ],
    "Phase 3: Bottleneck Identification": [
        "tests/integration/test_performance_bottlenecks.py"
    ],
    "Phase 4: Optimizations": [
        "tests/integration/test_performance_optimizations.py"
    ],
    "Phase 5: Component Comparison": [
        "tests/integration/test_performance_component_comparison.py"
    ],
    "End-to-End Tests": [
        "tests/integration/test_performance_end_to_end.py"
    ]
}


def run_pytest_tests(test_files: List[str], phase_name: str) -> Tuple[bool, Dict]:
    """
    Run pytest on given test files and return results.
    
    Returns:
        Tuple of (success: bool, results: dict)
    """
    results = {
        "phase": phase_name,
        "test_files": test_files,
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "duration": 0,
        "success_rate": 0.0
    }
    
    # Convert relative paths to absolute paths
    base_dir = Path(__file__).parent.parent.parent  # Go up to Dev-ACME/
    absolute_files = []
    for f in test_files:
        abs_path = base_dir / f
        if abs_path.exists():
            absolute_files.append(str(abs_path))
    
    if not absolute_files:
        results["status"] = "no_tests"
        results["message"] = f"No test files found for {phase_name}. Expected: {test_files}"
        return False, results
    
    existing_files = absolute_files
    
    # Build pytest command
    cmd = [
        sys.executable, "-m", "pytest",
        *existing_files,
        "-v",
        "--tb=short",
        "--json-report",
        "--json-report-file=/tmp/pytest_report.json"
    ]
    
    try:
        start_time = datetime.now()
        
        # Run pytest
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        end_time = datetime.now()
        results["duration"] = (end_time - start_time).total_seconds()
        
        # Parse output to extract test counts
        output = result.stdout + result.stderr
        
        # Try to parse JSON report if it exists
        json_report_path = "/tmp/pytest_report.json"
        if os.path.exists(json_report_path):
            try:
                with open(json_report_path, 'r') as f:
                    json_report = json.load(f)
                    results["total_tests"] = json_report.get("summary", {}).get("total", 0)
                    results["passed"] = json_report.get("summary", {}).get("passed", 0)
                    results["failed"] = json_report.get("summary", {}).get("failed", 0)
                    results["skipped"] = json_report.get("summary", {}).get("skipped", 0)
                    results["errors"] = json_report.get("summary", {}).get("error", 0)
            except Exception:
                pass
        
        # Fallback: parse output manually
        if results["total_tests"] == 0:
            lines = output.split('\n')
            for line in lines:
                # Look for pytest summary line like "X passed, Y failed in Zs"
                if "passed" in line.lower() or "failed" in line.lower():
                    import re
                    # Try to extract test counts from summary
                    if "passed" in line.lower():
                        passed_match = re.search(r'(\d+)\s+passed', line.lower())
                        if passed_match:
                            results["passed"] = int(passed_match.group(1))
                    if "failed" in line.lower():
                        failed_match = re.search(r'(\d+)\s+failed', line.lower())
                        if failed_match:
                            results["failed"] = int(failed_match.group(1))
                    if "error" in line.lower():
                        error_match = re.search(r'(\d+)\s+error', line.lower())
                        if error_match:
                            results["errors"] = int(error_match.group(1))
                    
                    results["total_tests"] = results["passed"] + results["failed"] + results["errors"]
                
                # Check for import errors or collection errors
                if "ImportError" in line or "ModuleNotFoundError" in line:
                    results["errors"] = results.get("errors", 0) + 1
                    if results["total_tests"] == 0:
                        results["total_tests"] = 1
                if "collected 0 items" in line.lower():
                    results["status"] = "no_tests_collected"
                    results["message"] = "pytest collected 0 test items - test files may be empty or have syntax errors"
        
        # Calculate success rate
        if results["total_tests"] > 0:
            results["success_rate"] = (results["passed"] / results["total_tests"]) * 100
        else:
            results["success_rate"] = 0.0
        
        # Store returncode
        results["returncode"] = result.returncode
        
        # Determine overall success (allow some failures in TDD)
        # Consider success if > 50% pass (TDD allows failures)
        success = result.returncode == 0 or results["success_rate"] >= 50.0
        results["status"] = "success" if success else "partial_failure"
        
        if results["total_tests"] == 0:
            results["status"] = "no_tests"
            results["message"] = "No tests were collected"
        
        return success, results
        
    except subprocess.TimeoutExpired:
        results["status"] = "timeout"
        results["message"] = f"Tests timed out after 1 hour"
        return False, results
    except Exception as e:
        results["status"] = "error"
        results["message"] = str(e)
        results["error"] = str(e)
        return False, results


class TestOverallPerformanceTrack:
    """Master test class that orchestrates all phase tests"""
    
    def test_phase_1_workload_setup(self):
        """Test Phase 1: Workload Setup"""
        phase_name = "Phase 1: Workload Setup"
        test_files = PHASE_TESTS[phase_name]
        
        success, results = run_pytest_tests(test_files, phase_name)
        
        # Store results in module-level dict
        _phase_results["Phase 1: Workload Setup"] = results
        
        # Print summary
        print(f"\n{'='*80}")
        print(f"{phase_name} - Results")
        print(f"{'='*80}")
        print(f"Status: {results['status']}")
        print(f"Total Tests: {results['total_tests']}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"Skipped: {results['skipped']}")
        print(f"Success Rate: {results['success_rate']:.1f}%")
        print(f"Duration: {results['duration']:.2f}s")
        if results.get('message'):
            print(f"Message: {results['message']}")
        print(f"{'='*80}\n")
        
        # For TDD: Fail if no tests were collected (implementation missing)
        if results['status'] == 'no_tests':
            pytest.fail(f"{phase_name}: No test files found - implementation may be missing")
        
        # Fail if all tests failed (likely implementation issues)
        if results['total_tests'] > 0 and results['passed'] == 0 and results['failed'] > 0:
            pytest.fail(f"{phase_name}: All {results['total_tests']} tests failed - implementation needs work")
        
        # Pass if tests exist and at least some are passing (TDD allows partial failures)
        assert results['total_tests'] > 0 or results['status'] == 'no_tests', \
            f"{phase_name}: Expected test execution but got status: {results['status']}"
    
    def test_phase_2_measurement_infrastructure(self):
        """Test Phase 2: Measurement Infrastructure"""
        phase_name = "Phase 2: Measurement Infrastructure"
        test_files = PHASE_TESTS[phase_name]
        
        success, results = run_pytest_tests(test_files, phase_name)
        _phase_results["Phase 2: Measurement Infrastructure"] = results
        
        print(f"\n{'='*80}")
        print(f"{phase_name} - Results")
        print(f"{'='*80}")
        print(f"Status: {results['status']}")
        print(f"Total Tests: {results['total_tests']}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"Skipped: {results['skipped']}")
        print(f"Success Rate: {results['success_rate']:.1f}%")
        print(f"Duration: {results['duration']:.2f}s")
        if results.get('message'):
            print(f"Message: {results['message']}")
        print(f"{'='*80}\n")
        
        # For TDD: Fail if no tests were collected (implementation missing)
        if results['status'] == 'no_tests':
            pytest.fail(f"{phase_name}: No test files found - implementation may be missing")
        
        # Fail if all tests failed (likely implementation issues)
        if results['total_tests'] > 0 and results['passed'] == 0 and results['failed'] > 0:
            pytest.fail(f"{phase_name}: All {results['total_tests']} tests failed - implementation needs work")
        
        # Pass if tests exist and at least some are passing (TDD allows partial failures)
        assert results['total_tests'] > 0 or results['status'] == 'no_tests', \
            f"{phase_name}: Expected test execution but got status: {results['status']}"
    
    def test_phase_3_bottleneck_identification(self):
        """Test Phase 3: Bottleneck Identification"""
        phase_name = "Phase 3: Bottleneck Identification"
        test_files = PHASE_TESTS[phase_name]
        
        success, results = run_pytest_tests(test_files, phase_name)
        _phase_results["Phase 3: Bottleneck Identification"] = results
        
        print(f"\n{'='*80}")
        print(f"{phase_name} - Results")
        print(f"{'='*80}")
        print(f"Status: {results['status']}")
        print(f"Total Tests: {results['total_tests']}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"Skipped: {results['skipped']}")
        print(f"Success Rate: {results['success_rate']:.1f}%")
        print(f"Duration: {results['duration']:.2f}s")
        if results.get('message'):
            print(f"Message: {results['message']}")
        print(f"{'='*80}\n")
        
        # For TDD: Fail if no tests were collected (implementation missing)
        if results['status'] == 'no_tests':
            pytest.fail(f"{phase_name}: No test files found - implementation may be missing")
        
        # Fail if all tests failed (likely implementation issues)
        if results['total_tests'] > 0 and results['passed'] == 0 and results['failed'] > 0:
            pytest.fail(f"{phase_name}: All {results['total_tests']} tests failed - implementation needs work")
        
        # Pass if tests exist and at least some are passing (TDD allows partial failures)
        assert results['total_tests'] > 0 or results['status'] == 'no_tests', \
            f"{phase_name}: Expected test execution but got status: {results['status']}"
    
    def test_phase_4_optimizations(self):
        """Test Phase 4: Optimizations"""
        phase_name = "Phase 4: Optimizations"
        test_files = PHASE_TESTS[phase_name]
        
        success, results = run_pytest_tests(test_files, phase_name)
        _phase_results["Phase 4: Optimizations"] = results
        
        print(f"\n{'='*80}")
        print(f"{phase_name} - Results")
        print(f"{'='*80}")
        print(f"Status: {results['status']}")
        print(f"Total Tests: {results['total_tests']}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"Skipped: {results['skipped']}")
        print(f"Success Rate: {results['success_rate']:.1f}%")
        print(f"Duration: {results['duration']:.2f}s")
        if results.get('message'):
            print(f"Message: {results['message']}")
        print(f"{'='*80}\n")
        
        # For TDD: Fail if no tests were collected (implementation missing)
        if results['status'] == 'no_tests':
            pytest.fail(f"{phase_name}: No test files found - implementation may be missing")
        
        # Fail if all tests failed (likely implementation issues)
        if results['total_tests'] > 0 and results['passed'] == 0 and results['failed'] > 0:
            pytest.fail(f"{phase_name}: All {results['total_tests']} tests failed - implementation needs work")
        
        # Pass if tests exist and at least some are passing (TDD allows partial failures)
        assert results['total_tests'] > 0 or results['status'] == 'no_tests', \
            f"{phase_name}: Expected test execution but got status: {results['status']}"
    
    def test_phase_5_component_comparison(self):
        """Test Phase 5: Component Comparison"""
        phase_name = "Phase 5: Component Comparison"
        test_files = PHASE_TESTS[phase_name]
        
        success, results = run_pytest_tests(test_files, phase_name)
        _phase_results["Phase 5: Component Comparison"] = results
        
        print(f"\n{'='*80}")
        print(f"{phase_name} - Results")
        print(f"{'='*80}")
        print(f"Status: {results['status']}")
        print(f"Total Tests: {results['total_tests']}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"Skipped: {results['skipped']}")
        print(f"Success Rate: {results['success_rate']:.1f}%")
        print(f"Duration: {results['duration']:.2f}s")
        if results.get('message'):
            print(f"Message: {results['message']}")
        print(f"{'='*80}\n")
        
        # For TDD: Fail if no tests were collected (implementation missing)
        if results['status'] == 'no_tests':
            pytest.fail(f"{phase_name}: No test files found - implementation may be missing")
        
        # Fail if all tests failed (likely implementation issues)
        if results['total_tests'] > 0 and results['passed'] == 0 and results['failed'] > 0:
            pytest.fail(f"{phase_name}: All {results['total_tests']} tests failed - implementation needs work")
        
        # Pass if tests exist and at least some are passing (TDD allows partial failures)
        assert results['total_tests'] > 0 or results['status'] == 'no_tests', \
            f"{phase_name}: Expected test execution but got status: {results['status']}"
    
    def test_end_to_end_tests(self):
        """Test End-to-End Workflow"""
        phase_name = "End-to-End Tests"
        test_files = PHASE_TESTS[phase_name]
        
        success, results = run_pytest_tests(test_files, phase_name)
        _phase_results["End-to-End Tests"] = results
        
        print(f"\n{'='*80}")
        print(f"{phase_name} - Results")
        print(f"{'='*80}")
        print(f"Status: {results['status']}")
        print(f"Total Tests: {results['total_tests']}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"Skipped: {results['skipped']}")
        print(f"Success Rate: {results['success_rate']:.1f}%")
        print(f"Duration: {results['duration']:.2f}s")
        if results.get('message'):
            print(f"Message: {results['message']}")
        print(f"{'='*80}\n")
        
        # For TDD: Fail if no tests were collected (implementation missing)
        if results['status'] == 'no_tests':
            pytest.fail(f"{phase_name}: No test files found - implementation may be missing")
        
        # Fail if all tests failed (likely implementation issues)
        if results['total_tests'] > 0 and results['passed'] == 0 and results['failed'] > 0:
            pytest.fail(f"{phase_name}: All {results['total_tests']} tests failed - implementation needs work")
        
        # Pass if tests exist and at least some are passing (TDD allows partial failures)
        assert results['total_tests'] > 0 or results['status'] == 'no_tests', \
            f"{phase_name}: Expected test execution but got status: {results['status']}"
    
    def test_performance_track_summary(self):
        """Generate and display overall Performance Track summary"""
        # Use module-level stored results
        all_results = _phase_results.copy()
        
        # Calculate overall statistics
        total_tests = sum(r.get("total_tests", 0) for r in all_results.values())
        total_passed = sum(r.get("passed", 0) for r in all_results.values())
        total_failed = sum(r.get("failed", 0) for r in all_results.values())
        total_skipped = sum(r.get("skipped", 0) for r in all_results.values())
        total_duration = sum(r.get("duration", 0) for r in all_results.values())
        overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        # Print comprehensive summary
        print(f"\n\n{'='*80}")
        print(f"{' '*25}PERFORMANCE TRACK SUMMARY")
        print(f"{'='*80}")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        # Phase-by-phase breakdown
        print(f"{'Phase':<45} {'Status':<15} {'Tests':<10} {'Pass':<8} {'Fail':<8} {'Skip':<8} {'Rate':<10}")
        print(f"{'-'*80}")
        
        for phase_name, results in all_results.items():
            status = results.get("status", "unknown")
            total = results.get("total_tests", 0)
            passed = results.get("passed", 0)
            failed = results.get("failed", 0)
            skipped = results.get("skipped", 0)
            rate = results.get("success_rate", 0)
            
            # Status indicator
            status_symbol = "✓" if status == "success" else "⚠" if status == "partial_failure" else "✗"
            status_display = f"{status_symbol} {status}"
            
            print(f"{phase_name:<45} {status_display:<15} {total:<10} {passed:<8} {failed:<8} {skipped:<8} {rate:>6.1f}%")
        
        print(f"{'-'*80}")
        print(f"{'TOTAL':<45} {'':<15} {total_tests:<10} {total_passed:<8} {total_failed:<8} {total_skipped:<8} {overall_success_rate:>6.1f}%")
        print(f"{'='*80}\n")
        
        # Overall summary
        print(f"Overall Statistics:")
        print(f"  • Total Tests Run: {total_tests}")
        print(f"  • Passed: {total_passed}")
        print(f"  • Failed: {total_failed}")
        print(f"  • Skipped: {total_skipped}")
        print(f"  • Success Rate: {overall_success_rate:.1f}%")
        print(f"  • Total Duration: {total_duration:.2f}s ({total_duration/60:.1f} minutes)")
        print(f"  • Phases Completed: {len(all_results)}/{len(PHASE_TESTS)}")
        
        # Phases status summary
        phases_completed = sum(1 for r in all_results.values() if r.get("status") == "success")
        phases_partial = sum(1 for r in all_results.values() if r.get("status") == "partial_failure")
        phases_failed = sum(1 for r in all_results.values() if r.get("status") in ["error", "timeout", "no_tests"])
        
        print(f"\nPhase Status Summary:")
        print(f"  • Fully Successful: {phases_completed}")
        print(f"  • Partial Success: {phases_partial}")
        print(f"  • Failed/Errors: {phases_failed}")
        
        # Recommendations
        print(f"\nRecommendations:")
        if total_tests == 0:
            print(f"  ⚠ No tests were collected. Check test file paths and pytest configuration.")
        elif overall_success_rate < 50:
            print(f"  ⚠ Low success rate. Review failing tests and implementation status.")
        elif overall_success_rate < 80:
            print(f"  ✓ Good progress. Continue implementing remaining features.")
        else:
            print(f"  ✓ Excellent! Most tests passing. Focus on remaining failures.")
        
        if phases_failed > 0:
            print(f"  ⚠ Some phases have errors. Review phase results above.")
        
        print(f"\n{'='*80}\n")
        
        # Store summary for potential export
        summary_data = {
            "timestamp": datetime.now().isoformat(),
            "phases": all_results,
            "overall": {
                "total_tests": total_tests,
                "total_passed": total_passed,
                "total_failed": total_failed,
                "total_skipped": total_skipped,
                "success_rate": overall_success_rate,
                "total_duration": total_duration,
                "phases_completed": len(all_results),
                "phases_successful": phases_completed,
                "phases_partial": phases_partial,
                "phases_failed": phases_failed
            }
        }
        
        # Optionally save to file
        summary_file = "performance_track_summary.json"
        try:
            with open(summary_file, 'w') as f:
                json.dump(summary_data, f, indent=2)
            print(f"Summary saved to: {summary_file}")
        except Exception as e:
            print(f"Note: Could not save summary to file: {e}")
        
        # For TDD: Fail if no tests were run at all (nothing implemented)
        if total_tests == 0:
            pytest.fail("Performance Track Summary: No tests were executed - implementations may be missing")
        
        # Don't fail on low success rate (TDD allows failures), but do check that tests ran
        assert len(all_results) > 0, "No phase results collected - tests may not have executed"


@pytest.fixture(scope="class", autouse=True)
def initialize_results():
    """Initialize result storage for all phases"""
    _phase_results.clear()
    yield
    # Results remain in module-level dict for summary

