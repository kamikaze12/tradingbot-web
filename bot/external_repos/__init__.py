"""
External repositories as submodules
"""
import os
import sys

# Add all subdirectories to path
current_dir = os.path.dirname(__file__)
for item in os.listdir(current_dir):
    item_path = os.path.join(current_dir, item)
    if os.path.isdir(item_path) and item_path not in sys.path:
        sys.path.insert(0, item_path)

__all__ = [name for name in os.listdir(current_dir) 
           if os.path.isdir(os.path.join(current_dir, name))]
