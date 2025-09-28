import time


def compute_net_score(results: dict):
    """Compute weighted net score from individual metric results."""
    # Weighted sum (weights should add up to 1.0)
    weights = {
        'license': 0.20,                    # High weight for license compatibility
        'ramp_up_time': 0.15,              # Important for ease of adoption
        'bus_factor': 0.12,                # Risk management
        'performance_claims': 0.12,        # Evidence of quality
        'size_score': 0.10,                # Deployability concerns
        'dataset_and_code_score': 0.10,    # Availability of resources
        'dataset_quality': 0.11,           # Quality of training data
        'code_quality': 0.10,              # Engineering practices
    }
    
    t0 = time.perf_counter()
    net_score = 0.0
    
    for metric_name, weight in weights.items():
        if metric_name in results:
            metric_result = results[metric_name]
            metric_value = metric_result.value
            
            # Handle size_score specially since it's a dict
            if metric_name == 'size_score' and isinstance(metric_value, dict):
                # Average across all platform scores
                platform_scores = list(metric_value.values())
                metric_value = sum(platform_scores) / len(platform_scores) if platform_scores else 0.0
            
            net_score += metric_value * weight
    
    latency_ms = int((time.perf_counter() - t0) * 1000)
    return net_score, latency_ms


def compute_netscore(scores, weights):
    """Simple wrapper function for testing - computes weighted sum of scores."""
    if len(scores) != len(weights):
        return 0.0
    return sum(score * weight for score, weight in zip(scores, weights))