"""Two independent saved MOCK result sets. Never loads FPGA or imports PYNQ."""
import argparse,json,time
from pathlib import Path
from pynq_toolkit import *
ROOT=Path(__file__).resolve().parents[1]
def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);reports=[]
    for name in ('vector_sum','threshold_counter'):
        folder=ROOT/'examples'/name;c=load_contract(folder/'contract.json')
        data=json.loads((folder/'vectors.json').read_text())
        if name=='vector_sum':expected=[sum(v) for v in data['inputs']]
        else:expected=[sum(x>=data['threshold'] for x in v) for v in data['inputs']]
        # Fixture outputs are deliberately stored separately from the golden calculation.
        actual=data['mock_outputs'];started=time.perf_counter_ns()
        result=compare(actual,expected)
        elapsed=time.perf_counter_ns()-started
        report=validation_report('MOCK',c,result,dict(host_compare_ns=elapsed,
            hardware_latency_ns=None,hardware_throughput=None,vivado=parse_vivado('')))
        report['example']=name;report['contract_sha256']=sha256(folder/'contract.json')
        report['fixture_sha256']=sha256(folder/'vectors.json')
        (output/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        reports.append(report)
    lines=['# Offline MOCK comparison report','',
           'No FPGA was loaded. Timing is host comparison only, not FPGA performance.','',
           '| example | passed | vectors | max absolute error |','|---|---|---|---|']
    for r in reports:
        c=r['correctness'];lines.append('| %s | %s | %s | %s |'%(r['example'],c['passed'],c['count'],c['max_abs_error']))
    (output/'comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if not all(r['correctness']['passed'] for r in reports):raise SystemExit(1)
    print('PASS_MOCK:',len(reports),'examples; no hardware operations; reports:',output)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();run(a.output)
