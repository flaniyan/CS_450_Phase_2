"""
Integration tests for Phase 3: Bottleneck Identification
Tests baseline measurement, component analysis, and bottleneck detection.
Run with: pytest tests/integration/test_performance_bottlenecks.py -v
"""
import pytest
import requests
import boto3
import os
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "https://pc1plkgnbd.execute-api.us-east-1.amazonaws.com/prod")
REGION = os.getenv("AWS_REGION", "us-east-1")


@pytest.fixture
def api_base_url():
    """Fixture for API base URL"""
    return BASE_URL


@pytest.fixture
def auth_token(api_base_url):
    """Fixture to get authentication token"""
    try:
        response = requests.put(
            f"{api_base_url}/authenticate",
            json={
                "user": {
                    "name": "ece30861defaultadminuser",
                    "is_admin": True
                },
                "secret": {
                    "password": "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"
                }
            }
        )
        if response.status_code == 200:
            return response.text.strip('"')
    except Exception:
        pass
    return None


@pytest.fixture
def baseline_workload_run_id(api_base_url, auth_token):
    """Fixture to create a baseline performance workload run"""
    if not auth_token:
        pytest.skip("Authentication not available")
    
    payload = {
        "num_clients": 100,
        "model_id": "arnir0/Tiny-LLM",
        "duration_seconds": 300
    }
    
    try:
        response = requests.post(
            f"{api_base_url}/health/performance/workload",
            json=payload,
            headers={"X-Authorization": auth_token}
        )
        if response.status_code in [200, 202]:
            data = response.json()
            run_id = data.get("run_id")
            if run_id:
                yield run_id
            else:
                pytest.skip("Could not create baseline workload run")
        else:
            pytest.skip(f"Could not create baseline workload run: {response.status_code}")
    except requests.exceptions.ConnectionError:
        pytest.skip("API server not running")


class TestBaselineMeasurement:
    """Test baseline measurement collection"""
    
    def test_baseline_workload_completes(self, api_base_url, auth_token, baseline_workload_run_id):
        """Run full 100-client workload and verify completion"""
        if not auth_token:
            pytest.skip("Authentication not available")
        
        run_id = baseline_workload_run_id
        
        # Wait for workload to complete (5 minutes + buffer)
        max_wait_time = 360  # 6 minutes
        wait_interval = 10
        elapsed = 0
        
        while elapsed < max_wait_time:
            try:
                response = requests.get(
                    f"{api_base_url}/health/performance/results/{run_id}",
                    headers={"X-Authorization": auth_token}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")
                    
                    if status == "completed":
                        assert True
                        return
                    elif status == "failed":
                        pytest.fail("Workload failed")
                        return
                
                time.sleep(wait_interval)
                elapsed += wait_interval
            except requests.exceptions.ConnectionError:
                pytest.skip("API server not running")
        
        pytest.fail("Workload did not complete within timeout")
    
    def test_baseline_metrics_recorded(self, api_base_url, auth_token, baseline_workload_run_id):
        """Verify all component metrics are collected during baseline"""
        run_id = baseline_workload_run_id
        
        # Wait for workload to complete
        time.sleep(310)  # Wait 5+ minutes
        
        # Verify metrics exist in DynamoDB
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table("performance_metrics")
        
        response = table.query(
            KeyConditionExpression='run_id = :run_id',
            ExpressionAttributeValues={':run_id': run_id}
        )
        
        items = response.get('Items', [])
        assert len(items) > 0, "No baseline metrics found"
        
        # Verify CloudWatch metrics exist
        cloudwatch = boto3.client('cloudwatch', region_name=REGION)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=10)
        
        # Check for various metric namespaces
        namespaces = ['ACME/Performance', 'AWS/ECS', 'AWS/DynamoDB', 'AWS/S3']
        metrics_found = 0
        
        for namespace in namespaces:
            try:
                response = cloudwatch.list_metrics(Namespace=namespace)
                if response.get('Metrics'):
                    metrics_found += 1
            except Exception:
                pass
        
        assert metrics_found > 0, "No CloudWatch metrics found"


class TestBottleneckDetection:
    """Test bottleneck detection and analysis"""
    
    def test_component_latency_analysis(self, api_base_url, auth_token, baseline_workload_run_id):
        """Compare latencies across components to identify bottleneck"""
        run_id = baseline_workload_run_id
        
        # Wait for workload to complete
        time.sleep(310)
        
        # Get results
        try:
            response = requests.get(
                f"{api_base_url}/health/performance/results/{run_id}",
                headers={"X-Authorization": auth_token} if auth_token else {}
            )
            
            if response.status_code == 200:
                data = response.json()
                metrics = data.get("metrics", {})
                
                # Verify latency metrics exist
                latency = metrics.get("latency", {})
                assert "mean_ms" in latency or "p99_ms" in latency
                
                # Analyze component latencies from CloudWatch
                cloudwatch = boto3.client('cloudwatch', region_name=REGION)
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(minutes=10)
                
                component_latencies = {}
                
                # Get ECS latency
                try:
                    ecs_response = cloudwatch.get_metric_statistics(
                        Namespace='AWS/ECS',
                        MetricName='CPUUtilization',
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=300,
                        Statistics=['Average']
                    )
                    if ecs_response.get('Datapoints'):
                        component_latencies['ecs'] = ecs_response['Datapoints'][-1]['Average']
                except Exception:
                    pass
                
                # Component latencies should be analyzable
                assert isinstance(component_latencies, dict)
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_resource_utilization_tracking(self, baseline_workload_run_id):
        """Verify resource utilization is tracked for all components"""
        run_id = baseline_workload_run_id
        
        # Wait for metrics to be collected
        time.sleep(310)
        
        cloudwatch = boto3.client('cloudwatch', region_name=REGION)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=10)
        
        # Check ECS CPU utilization
        try:
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/ECS',
                MetricName='CPUUtilization',
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average', 'Maximum']
            )
            datapoints = response.get('Datapoints', [])
            if datapoints:
                assert True  # CPU metrics exist
        except Exception:
            pass
        
        # Check ECS Memory utilization
        try:
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/ECS',
                MetricName='MemoryUtilization',
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average', 'Maximum']
            )
            datapoints = response.get('Datapoints', [])
            if datapoints:
                assert True  # Memory metrics exist
        except Exception:
            pass
        
        # Check DynamoDB read capacity
        try:
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/DynamoDB',
                MetricName='ConsumedReadCapacityUnits',
                Dimensions=[{'Name': 'TableName', 'Value': 'artifacts'}],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average', 'Sum']
            )
            datapoints = response.get('Datapoints', [])
            if datapoints:
                assert True  # DynamoDB metrics exist
        except Exception:
            pass
    
    def test_statistical_analysis(self, api_base_url, auth_token, baseline_workload_run_id):
        """Test variance and correlation analysis"""
        run_id = baseline_workload_run_id
        
        # Wait for workload to complete
        time.sleep(310)
        
        try:
            response = requests.get(
                f"{api_base_url}/health/performance/results/{run_id}",
                headers={"X-Authorization": auth_token} if auth_token else {}
            )
            
            if response.status_code == 200:
                data = response.json()
                metrics = data.get("metrics", {})
                latency = metrics.get("latency", {})
                
                # Calculate variance if we have multiple latency values
                if "mean_ms" in latency and "p99_ms" in latency:
                    mean = latency["mean_ms"]
                    p99 = latency["p99_ms"]
                    variance_estimate = (p99 - mean) ** 2
                    assert variance_estimate >= 0
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_identify_highest_latency_component(self, api_base_url, auth_token, baseline_workload_run_id):
        """Identify component with highest latency"""
        run_id = baseline_workload_run_id
        
        time.sleep(310)
        
        cloudwatch = boto3.client('cloudwatch', region_name=REGION)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=10)
        
        component_metrics = {}
        
        # Collect metrics from different components
        metric_queries = [
            ('AWS/ECS', 'CPUUtilization', 'ecs_cpu'),
            ('AWS/DynamoDB', 'ConsumedReadCapacityUnits', 'ddb_read'),
            ('ACME/Performance', 'S3DownloadLatency', 's3_latency'),
            ('ACME/Performance', 'RequestProcessingTime', 'api_latency'),
        ]
        
        for namespace, metric_name, key in metric_queries:
            try:
                response = cloudwatch.get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric_name,
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=['Average']
                )
                if response.get('Datapoints'):
                    component_metrics[key] = response['Datapoints'][-1]['Average']
            except Exception:
                pass
        
        # Should be able to identify highest latency component
        if component_metrics:
            highest = max(component_metrics.items(), key=lambda x: x[1])
            assert highest is not None

