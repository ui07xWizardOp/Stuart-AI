import sys
import os

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

for entry in os.listdir(root_dir):
    full_path = os.path.join(root_dir, entry)
    if os.path.isdir(full_path) and not entry.startswith('.') and entry not in ('tests', 'venv'):
        sys.path.insert(0, full_path)
