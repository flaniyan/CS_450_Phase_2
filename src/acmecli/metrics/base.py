from typing import List

REGISTRY = []


def register(metric):
    REGISTRY.append(metric)
