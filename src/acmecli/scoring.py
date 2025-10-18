import time


def compute_net_score(results: dict):
    """Compute weighted net score from individual metric results."""
    # Weighted sum
    weights = {
        'license': 0.15,                    # High weight for license compatibility
        'ramp_up_time': 0.12,              # Important for ease of adoption
        'bus_factor': 0.10,                # Risk management
        'performance_claims': 0.10,        # Evidence of quality
        'size_score': 0.08,                # Deployability concerns
        'dataset_and_code_score': 0.08,    # Availability of resources
        'dataset_quality': 0.09,           # Quality of training data
        'code_quality': 0.08,              # Engineering practices
        'reproducibility': 0.10,           # Reproducibility and documentation
        'reviewedness': 0.05,              # Code review quality
        'treescore': 0.05,                 # Code structure and organization
    }

    t0 = time.perf_counter()
    net_score = 0.0

    for metric_name, weight in weights.items():
        # Both lowercase and capitalized versions of metric names
        metric_key = None
        if metric_name in results:
            metric_key = metric_name
        else:
            # Check for capitalized version
            capitalized_key = metric_name.capitalize()
            if capitalized_key in results:
                metric_key = capitalized_key

        if metric_key:
            metric_result = results[metric_key]
            metric_value = metric_result.value

            # Handle size_score specially since it's a dict
            if metric_name == 'size_score' and isinstance(metric_value, dict):
                # Average across all platform scores
                platform_scores = list(metric_value.values())
                if platform_scores:
                    metric_value = sum(platform_scores) / len(platform_scores)
                else:
                    metric_value = 0.0

            net_score += metric_value * weight

    latency_ms = int((time.perf_counter() - t0) * 1000)
    return net_score, latency_ms


def compute_netscore(scores, weights):
    """Simple wrapper function for testing - computes weighted sum of scores."""
    if len(scores) != len(weights):
        return 0.0
    return sum(score * weight for score, weight in zip(scores, weights))
