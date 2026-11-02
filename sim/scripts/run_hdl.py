# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""Reproducible command-line XSim tests; check terminal PASS, not just process exit."""
from pathlib import Path
from datetime import datetime
import argparse,os,shutil,subprocess,json
ROOT=Path(__file__).absolute().parents[2]
PROJECT=ROOT/'src/project'
SUITES={'fp_dsp':'tb_fp_dsp','analog':'tb_all_final_analog','axi':'tb_all_final_axi',
        'z_safety':'tb_all_final_z_safety','stats_bank':'tb_all_final_stats_bank',
        'reset_watchdog':'tb_all_final_reset_watchdog'}
def sources():
    out=[]
    for name in ['hw/rtl/rtl_sources.f','hw/rtl/fp_dsp/fp_dsp_sources.f']:
        for line in (PROJECT/name).read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if line and not line.startswith('#'):out.append(PROJECT/line)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--vivado-bin',default=os.environ.get('VIVADO_BIN'))
    ap.add_argument('--suite',choices=['all',*SUITES],default='all');a=ap.parse_args()
    def tool(name):
        path=Path(a.vivado_bin)/(name+'.bat' if os.name=='nt' else name) if a.vivado_bin else shutil.which(name)
        if not path or not Path(path).is_file():raise SystemExit('Provide --vivado-bin or VIVADO_BIN/PATH: '+name)
        return str(path)
    tools={n:tool(n) for n in ('xvlog','xelab','xsim')}
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S');resultlog=ROOT/'sim/results/hdl_tests.log'
    results={}
    with resultlog.open('w',encoding='utf-8') as log:
        for name,top in SUITES.items():
            if a.suite!='all' and a.suite!=name:continue
            out=ROOT/'build/sim_cli'/stamp/name;out.mkdir(parents=True,exist_ok=False)
            cmds=[[tools['xvlog'],'--sv',*[str(p) for p in sources()],str(PROJECT/'hw/tb'/((('tb_all_final_modular_'+name) if name in ('stats_bank','reset_watchdog') else top)+'.sv'))],
                  [tools['xelab'],top,'-s',top+'_snapshot','--debug','typical'],
                  [tools['xsim'],top+'_snapshot','-runall','-onfinish','quit','-log','simulation.log']]
            try:
                for cmd in cmds:
                    p=subprocess.run(cmd,cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',timeout=300)
                    log.write('COMMAND '+repr(cmd)+'\n'+p.stdout+'\n');log.flush()
                    if p.returncode:raise RuntimeError(name+' tool failed: '+str(p.returncode))
                text=(out/'simulation.log').read_text(encoding='utf-8',errors='replace')
                if 'PASS' not in text or 'Fatal:' in text or 'ERROR:' in text:raise RuntimeError('no terminal PASS or simulator error')
                results[name]={'passed':True,'artifact':str(out.relative_to(ROOT))}
                print('PASS_HDL',name,flush=True)
            except Exception as exc:
                results[name]={'passed':False,'error':str(exc),'artifact':str(out.relative_to(ROOT))}
                print('FAIL_HDL',name,str(exc),flush=True)
    (ROOT/'sim/results/hdl_summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    if not all(r['passed'] for r in results.values()):raise SystemExit(1)
    print('PASS_HDL; board measurements archived under data/measured')
if __name__=='__main__':main()
