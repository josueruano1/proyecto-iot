import sys
import os

# Add the api/ directory to the path so imports work without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
