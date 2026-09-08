import os
import sys

# Ensure both the repository root and the parent directory are in sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PRISM_DIR = os.path.dirname(TESTS_DIR)
PARENT_DIR = os.path.dirname(PRISM_DIR)

for p in [PARENT_DIR, PRISM_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)
