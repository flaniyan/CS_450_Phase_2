"""
Unit tests for performance statistics calculations.
Tests percentile calculations, throughput calculations, and metric aggregations.
"""
import pytest
import math
from typing import List


def calculate_mean(values: List[float]) -> float:
    """Calculate mean of values"""
    return sum(values) / len(values) if values else 0.0


def calculate_median(values: List[float]) -> float:
    """Calculate median of values"""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    if n % 2 == 0:
        return (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
    else:
        return sorted_values[n // 2]


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculate percentile of values (0-100)"""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    index = int(math.ceil(n * percentile / 100)) - 1
    index = max(0, min(index, n - 1))
    return sorted_values[index]


def calculate_throughput(total_bytes: int, total_time_seconds: float) -> float:
    """Calculate throughput in bytes per second"""
    if total_time_seconds <= 0:
        return 0.0
    return total_bytes / total_time_seconds


def calculate_error_rate(total_requests: int, successful_requests: int) -> float:
    """Calculate error rate as percentage"""
    if total_requests == 0:
        return 0.0
    return (total_requests - successful_requests) / total_requests * 100


class TestMeanCalculation:
    """Test mean calculation"""
    
    def test_mean_simple(self):
        """Test mean with simple values"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        mean = calculate_mean(values)
        assert mean == 3.0
    
    def test_mean_empty(self):
        """Test mean with empty list"""
        values = []
        mean = calculate_mean(values)
        assert mean == 0.0
    
    def test_mean_single_value(self):
        """Test mean with single value"""
        values = [42.0]
        mean = calculate_mean(values)
        assert mean == 42.0
    
    def test_mean_negative_values(self):
        """Test mean with negative values"""
        values = [-1.0, 0.0, 1.0]
        mean = calculate_mean(values)
        assert mean == 0.0
    
    def test_mean_float_precision(self):
        """Test mean maintains float precision"""
        values = [1.5, 2.5, 3.5]
        mean = calculate_mean(values)
        assert mean == 2.5


class TestMedianCalculation:
    """Test median calculation"""
    
    def test_median_odd_count(self):
        """Test median with odd number of values"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        median = calculate_median(values)
        assert median == 3.0
    
    def test_median_even_count(self):
        """Test median with even number of values"""
        values = [1.0, 2.0, 3.0, 4.0]
        median = calculate_median(values)
        assert median == 2.5
    
    def test_median_empty(self):
        """Test median with empty list"""
        values = []
        median = calculate_median(values)
        assert median == 0.0
    
    def test_median_single_value(self):
        """Test median with single value"""
        values = [42.0]
        median = calculate_median(values)
        assert median == 42.0
    
    def test_median_unsorted(self):
        """Test median with unsorted values"""
        values = [5.0, 1.0, 4.0, 2.0, 3.0]
        median = calculate_median(values)
        assert median == 3.0
    
    def test_median_duplicate_values(self):
        """Test median with duplicate values"""
        values = [1.0, 1.0, 2.0, 2.0, 3.0]
        median = calculate_median(values)
        assert median == 2.0


class TestPercentileCalculation:
    """Test percentile calculation"""
    
    def test_percentile_99(self):
        """Test 99th percentile calculation"""
        # 100 values from 1 to 100
        values = list(range(1, 101))
        p99 = calculate_percentile(values, 99)
        assert 95 <= p99 <= 100
    
    def test_percentile_50_equals_median(self):
        """Test that 50th percentile equals median"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        p50 = calculate_percentile(values, 50)
        median = calculate_median(values)
        assert p50 == median
    
    def test_percentile_100(self):
        """Test 100th percentile (maximum)"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        p100 = calculate_percentile(values, 100)
        assert p100 == 5.0
    
    def test_percentile_0(self):
        """Test 0th percentile (minimum)"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        p0 = calculate_percentile(values, 0)
        assert p0 == 1.0
    
    def test_percentile_empty(self):
        """Test percentile with empty list"""
        values = []
        p99 = calculate_percentile(values, 99)
        assert p99 == 0.0
    
    def test_percentile_single_value(self):
        """Test percentile with single value"""
        values = [42.0]
        p99 = calculate_percentile(values, 99)
        assert p99 == 42.0
    
    def test_percentile_latency_values(self):
        """Test percentile with realistic latency values"""
        latencies = [10.5, 15.2, 20.1, 25.8, 30.3, 35.7, 40.2, 45.9, 50.1, 55.6,
                    60.2, 65.8, 70.3, 75.1, 80.7, 85.4, 90.2, 95.8, 100.3, 105.9]
        p99 = calculate_percentile(latencies, 99)
        assert p99 >= max(latencies) * 0.95


class TestThroughputCalculation:
    """Test throughput calculation"""
    
    def test_throughput_simple(self):
        """Test throughput with simple values"""
        total_bytes = 1024
        total_time_seconds = 1.0
        throughput = calculate_throughput(total_bytes, total_time_seconds)
        assert throughput == 1024.0
    
    def test_throughput_kilobytes(self):
        """Test throughput with larger values"""
        total_bytes = 1024 * 100  # 100 KB
        total_time_seconds = 10.0
        throughput = calculate_throughput(total_bytes, total_time_seconds)
        assert throughput == 10240.0
    
    def test_throughput_zero_time(self):
        """Test throughput with zero time"""
        total_bytes = 1024
        total_time_seconds = 0.0
        throughput = calculate_throughput(total_bytes, total_time_seconds)
        assert throughput == 0.0
    
    def test_throughput_zero_bytes(self):
        """Test throughput with zero bytes"""
        total_bytes = 0
        total_time_seconds = 10.0
        throughput = calculate_throughput(total_bytes, total_time_seconds)
        assert throughput == 0.0
    
    def test_throughput_requests_per_second(self):
        """Test converting throughput to requests per second"""
        total_requests = 100
        total_time_seconds = 5.0
        requests_per_second = calculate_throughput(total_requests, total_time_seconds)
        assert requests_per_second == 20.0


class TestErrorRateCalculation:
    """Test error rate calculation"""
    
    def test_error_rate_no_errors(self):
        """Test error rate with no errors"""
        total_requests = 100
        successful_requests = 100
        error_rate = calculate_error_rate(total_requests, successful_requests)
        assert error_rate == 0.0
    
    def test_error_rate_some_errors(self):
        """Test error rate with some errors"""
        total_requests = 100
        successful_requests = 95
        error_rate = calculate_error_rate(total_requests, successful_requests)
        assert error_rate == 5.0
    
    def test_error_rate_all_errors(self):
        """Test error rate with all errors"""
        total_requests = 100
        successful_requests = 0
        error_rate = calculate_error_rate(total_requests, successful_requests)
        assert error_rate == 100.0
    
    def test_error_rate_zero_requests(self):
        """Test error rate with zero requests"""
        total_requests = 0
        successful_requests = 0
        error_rate = calculate_error_rate(total_requests, successful_requests)
        assert error_rate == 0.0
    
    def test_error_rate_half_errors(self):
        """Test error rate with 50% errors"""
        total_requests = 100
        successful_requests = 50
        error_rate = calculate_error_rate(total_requests, successful_requests)
        assert error_rate == 50.0


class TestMetricAggregation:
    """Test metric aggregation functions"""
    
    def test_aggregate_latencies(self):
        """Test aggregating latency metrics"""
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        mean = calculate_mean(latencies)
        median = calculate_median(latencies)
        p99 = calculate_percentile(latencies, 99)
        
        assert mean == 30.0
        assert median == 30.0
        assert p99 >= 45.0
    
    def test_aggregate_with_outliers(self):
        """Test aggregation with outliers"""
        latencies = [10.0, 12.0, 15.0, 18.0, 20.0, 1000.0]  # One outlier
        mean = calculate_mean(latencies)
        median = calculate_median(latencies)
        p99 = calculate_percentile(latencies, 99)
        
        # Mean is affected by outlier
        assert mean > 100.0
        # Median is not affected
        assert median < 20.0
        # P99 should capture the outlier
        assert p99 >= 900.0
    
    def test_realistic_latency_distribution(self):
        """Test with realistic latency distribution (some fast, some slow)"""
        # Simulate realistic latencies: most fast, some slow
        latencies = [10.0] * 80 + [100.0] * 15 + [500.0] * 5
        mean = calculate_mean(latencies)
        median = calculate_median(latencies)
        p99 = calculate_percentile(latencies, 99)
        
        # Mean should be elevated by slow requests
        assert mean > 50.0
        # Median should be fast (10.0)
        assert median == 10.0
        # P99 should capture slow requests
        assert p99 >= 400.0

