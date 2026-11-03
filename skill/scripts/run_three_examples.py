"""Compatibility entry for six original MOCK reports."""
from pathlib import Path
import runpy
if __name__=='__main__':
    runpy.run_path(str(Path(__file__).resolve().parents[1]/'pynq_skills/scripts/run_three_examples.py'),run_name='__main__')
