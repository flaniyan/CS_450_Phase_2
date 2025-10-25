from decimal import Decimal
from collections.abc import Mapping, Sequence

def to_ddb(o):
    """Convert Python objects to DynamoDB-compatible types"""
    if isinstance(o, float):
        return Decimal(str(o))
    if isinstance(o, Mapping):
        return {k: to_ddb(v) for k, v in o.items()}
    if isinstance(o, Sequence) and not isinstance(o, (str, bytes, bytearray)):
        return [to_ddb(v) for v in o]
    return o
