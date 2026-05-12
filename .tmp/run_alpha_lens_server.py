import os
import runpy
import sys

os.environ["ALPHA_LENS_SKIP_WORKERS"] = "1"
BACKEND_DIR = r"C:\Project rohan\Alpha_Lens\backend"

os.chdir(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

runpy.run_path(os.path.join(BACKEND_DIR, "app.py"), run_name="__main__")
