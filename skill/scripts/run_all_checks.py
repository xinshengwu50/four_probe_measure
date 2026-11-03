"""Run six isolated offline suites plus package integrity audit."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(ROOT/'tests'),'-q'])
    if result.returncode:raise SystemExit(result.returncode)
    for script in [ROOT/'pynq_skills/scripts/run_all_checks.py',ROOT/'scripts/audit_package.py']:
        result=subprocess.run([sys.executable,'-B',str(script)])
        if result.returncode:raise SystemExit(result.returncode)
