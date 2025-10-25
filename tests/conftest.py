import sys
import os

# Add the project root to Python path so both 'src' and 'acmecli' modules can be imported
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Also add the src directory to support both import patterns:
# - from src.services.secure_temp import ... (new tests)
# - from acmecli.metrics.bus_factor_metric import ... (existing tests)
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
