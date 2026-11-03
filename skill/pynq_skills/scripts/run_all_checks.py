"""Run isolated offline tests. Never runs hardware/Notebook motion cells."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    for name in ['pynq_overlay_validation','pynq_spi_validation','pynq_adc_capture','pynq_motion_tuning','pynq_uart_validation','pynq_result_history']:
        print('TEST',name,flush=True)
        result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(ROOT/name/'tests'),'-q'])
        if result.returncode:raise SystemExit(result.returncode)
    print('ALL_OFFLINE_TESTS_PASS; hardware not verified')
