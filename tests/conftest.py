# conftest.py to ensure project root is on sys.path for imports
import sys
import os

# Insert the workspace root directory to sys.path so tests can import project modules
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, workspace_root)
