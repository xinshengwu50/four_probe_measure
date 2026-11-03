"""Generate six offline reports and share existing golden comparison utilities."""
from pathlib import Path
from dataclasses import asdict
import sys,json
ROOT=Path(__file__).resolve().parents[1]
for name in ['pynq_overlay_validation','pynq_spi_validation','pynq_adc_capture','pynq_motion_tuning']:sys.path.insert(0,str(ROOT/name/'scripts'))
from pynq_toolkit import compare,validation_report
from spi_contract import SpiConfig,build_trace,validate_trace,divider
from adc_capture import AdcConfig,analyze_records
from motion_tuning import AxisConfig,preview_move,fingerprint

def save(folder,name,data):
    out=folder/'examples/offline_results';out.mkdir(exist_ok=True)
    (out/(name+'.json')).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')

if __name__=='__main__':
    count=0
    folder=ROOT/'pynq_spi_validation'
    for name in ['mode0_msb_8bit','mode3_lsb_24bit']:
        p=folder/'examples'/(name+'.json')
        data=json.loads(p.read_text());c=SpiConfig(**data['spi']);tx=int(data['tx'],0);rx=int(data['rx'],0)
        check=validate_trace(build_trace(c,tx,rx),c,tx,rx)
        golden=compare([check['transmitted'],check['received']],[tx,rx])
        assert check['passed'] and golden['passed'],check
        report=validation_report('MOCK',{'ip':{'instance':'spi_trace_model'}},golden,divider(c));report.update(trace_check=check,source='SYNTHETIC_TRACE',config=asdict(c));save(folder,p.stem,report);count+=1
    folder=ROOT/'pynq_adc_capture'
    for name in ['single_ended_12bit','bipolar_channel_16bit']:
        data=json.loads((folder/'examples'/(name+'.json')).read_text());records=json.loads((folder/'examples'/(name+'_records.json')).read_text())
        check=analyze_records(records,AdcConfig(**data['adc']),data['discard_first'],data['required_samples'])
        golden=compare([r['signal_v'] for r in check['samples']],[data['golden_signal_v']]*check['valid_count'],atol=1e-12)
        assert check['passed'] and golden['passed'],check
        report=validation_report('MOCK',{'ip':{'instance':'adc_frame_model'}},golden,{});report.update(record_analysis=check,source='SYNTHETIC_RECORDS',config=data);save(folder,name,report);count+=1
    folder=ROOT/'pynq_motion_tuning'
    for name in ['linear_axis','rotary_axis']:
        data=json.loads((folder/'examples'/(name+'.json')).read_text());plan=preview_move(AxisConfig(**data['axis']),**data['move'])
        golden=compare([plan['target_steps']],[data['golden_target_steps']]);assert golden['passed']
        report=validation_report('MOCK',{'ip':{'instance':'motion_parameter_model'}},golden,{});report.update(plan=plan,plan_sha256=fingerprint(plan),source='PREVIEW_NO_MOTOR_COMMAND');save(folder,name,report);count+=1
    print('PASS_MOCK',count,'reports; no board/motion/ADC calls')
