# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Run Python regressions against both deployment and source mirrors, offline."""
from pathlib import Path
import os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
def main():
    log=ROOT/'sim/results/python_tests.log';log.parent.mkdir(exist_ok=True)
    env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    with log.open('w',encoding='utf-8') as out:
        for folder,modules in [(ROOT/'board/pynq',ROOT/'board/pynq'),(ROOT/'src/project/tests',ROOT/'src/project/sw/pynq')]:
            current=dict(env,PYTHONPATH=str(modules))
            command=[sys.executable,'-B','-m','unittest','discover','-s',str(folder),'-p','test_*.py','-v']
            result=subprocess.run(command,cwd=folder,env=current,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
            out.write('COMMAND '+repr(command)+'\n'+result.stdout+'\n');out.flush()
            print(result.stdout[-500:])
            if result.returncode:return result.returncode
    print('PASS_PYTHON: board/source tests; offline only, no coverage claim')
    return 0
if __name__=='__main__':raise SystemExit(main())
