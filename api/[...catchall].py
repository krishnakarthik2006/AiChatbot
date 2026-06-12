import sys
import os

# Add the root directory to sys.path so 'backend' module and 'app' can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
