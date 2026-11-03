import tempfile
from result_history import save_snapshot,list_history,restore_snapshot

def mock_snapshot():
    meta=dict(schema_version=1,run_id='mock_scan25',source='MOCK',complete=True,
              expected_points=25,quantities={'voltage':'V','resistance':'ohm'},
              provenance={'generator':'diagnostic_pattern_v1','hardware_verified':False})
    rows=[dict(point=i,quantity=q,value=i/100 if q=='voltage' else 10+i,
               unit=u,quality_flags=['SYNTHETIC'])
          for i in range(1,26) for q,u in meta['quantities'].items()]
    return meta,rows

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as d:
        m,r=mock_snapshot();path=save_snapshot(d,m,r);events=[]
        result=restore_snapshot(path,begin=lambda meta:events.append('PAGE_FIRST'),
                                write_row=lambda row:events.append(row),finish=lambda meta:events.append('FINISH'))
        assert len(list_history(d,source='MOCK')['items'])==1
        assert not list_history(d,source='BOARD')['items']
        assert events[0]=='PAGE_FIRST' and events[-1]=='FINISH' and result['records_written']==50
        print('PASS_MOCK CSV25 save/restore, 50 quantity records; no motor/current/ADC/UART')
