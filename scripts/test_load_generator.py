#!/usr/bin/env python3
"""
Simple script to test the load generator directly
Useful for quick testing without running the full API server
"""
import asyncio
import sys
import uuid
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.services.performance.load_generator import LoadGenerator


async def test_load_generator():
    """Test the load generator with a small number of clients"""
    print("=" * 80)
    print("Testing Load Generator")
    print("=" * 80)
    
    # Configuration
    base_url = "http://localhost:8000"  # Change if your server is on different port
    num_clients = 10  # Start small for testing
    model_id = "arnir0/Tiny-LLM"  # Make sure this model is ingested first
    run_id = str(uuid.uuid4())
    
    print(f"Configuration:")
    print(f"  Base URL: {base_url}")
    print(f"  Number of clients: {num_clients}")
    print(f"  Model ID: {model_id}")
    print(f"  Run ID: {run_id}")
    print()
    
    # Create load generator
    generator = LoadGenerator(
        run_id=run_id,
        base_url=base_url,
        num_clients=num_clients,
        model_id=model_id,
        version="main",
        duration_seconds=None,  # Single request per client
    )
    
    print("Starting load generation...")
    print(f"URL: {generator._get_download_url()}")
    print()
    
    # Run the load generator
    try:
        await generator.run()
        
        # Get results
        metrics = generator.get_metrics()
        summary = generator.get_summary()
        
        print()
        print("=" * 80)
        print("Test Results")
        print("=" * 80)
        print(f"Total requests: {summary['total_requests']}")
        print(f"Successful: {summary['successful_requests']}")
        print(f"Failed: {summary['failed_requests']}")
        print(f"Total duration: {summary['total_duration_seconds']:.2f}s")
        print()
        print("Latency Statistics:")
        print(f"  Mean: {summary['mean_latency_ms']:.2f} ms")
        print(f"  Median: {summary['median_latency_ms']:.2f} ms")
        print(f"  P99: {summary['p99_latency_ms']:.2f} ms")
        print(f"  Min: {summary['min_latency_ms']:.2f} ms")
        print(f"  Max: {summary['max_latency_ms']:.2f} ms")
        print()
        print(f"Throughput: {summary['throughput_bps']:.2f} bytes/sec")
        print(f"Total bytes transferred: {summary['total_bytes_transferred']}")
        print()
        
        # Show sample metrics
        if metrics:
            print("Sample metrics (first 3):")
            for i, metric in enumerate(metrics[:3], 1):
                print(f"  {i}. Client {metric['client_id']}: "
                      f"{metric['status_code']} status, "
                      f"{metric['request_latency_ms']:.2f}ms, "
                      f"{metric['bytes_transferred']} bytes")
        
        print()
        print("✓ Load generator test completed successfully!")
        return 0
        
    except Exception as e:
        print(f"\n✗ Error running load generator: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    # Run the async test
    exit_code = asyncio.run(test_load_generator())
    sys.exit(exit_code)

