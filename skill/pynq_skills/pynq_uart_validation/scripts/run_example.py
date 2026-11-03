from uart_protocol import FrameParser,encode,timing_budget
if __name__ == '__main__':
    p=FrameParser(); wire=encode(b'START')+encode(b'HISTORY:1')
    frames=[]
    for i in range(0,len(wire),3):
        report=p.feed(wire[i:i+3],i*.001)
        assert not report['errors'],report
        frames.extend(report['frames'])
    assert frames == [b'START',b'HISTORY:1']
    print('PASS_MOCK UART split/merged frames',timing_budget(6811,115200))
