import os 
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

list_of_files = [
    ".github/workflows/ci.yml",
    "config/settings.py",
    "src/__init__.py",
    "src/state.py",
    "src/nodes.py",
    "src/graph.py",
    "tests/__init__.py",
    "tests/test_graph.py",
    ".env",
    "app.py",
    "requirements.txt"
]

for filepath in list_of_files:
    filepath = Path(filepath)
    filedir, filename = os.path.split(filepath)
    
    if filedir != "":
        os.makedirs(filedir, exist_ok=True)
        logging.info(f"Creating directory: {filedir} for file: {filename}")
        
    if (not os.path.exists(filepath)) or (os.path.getsize(filepath)==0):
        with open(filepath, "w") as f:
            pass
        logging.info(f"Creating empty file: {filename}")
        
    else:
        logging.info(f"{filename} already exists and is not empty. Skipping file creation.")