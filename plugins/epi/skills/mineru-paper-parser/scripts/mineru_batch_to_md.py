from pathlib import Path
import runpy


runtime_script = (
    Path(__file__).resolve().parents[3]
    / "build"
    / "mineru-paper-parser"
    / "mineru_batch_to_md.py"
)

runpy.run_path(str(runtime_script), run_name="__main__")
