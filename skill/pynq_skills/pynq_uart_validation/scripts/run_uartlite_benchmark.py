from uartlite_tx import benchmark
if __name__ == '__main__':
    # 6139 B = one 25-point HMI history restore in the source project; payload content is irrelevant.
    data = (bytes(range(256)) * 24)[:6139]
    print('OFFLINE_MODEL AXI UART Lite 115200 8N1, FIFO16, yield 0.2ms; not hardware evidence')
    for overhead in (0.0, 0.0001, 0.00037):
        rows = {m: benchmark(data, m, sleep_overhead_s=overhead) for m in ('stop_and_wait', 'fill_fifo')}
        for r in rows.values():
            assert r['dropped'] == 0 and r['bytes_match'], r
        print('sleep_overhead=%.2fms  stop_and_wait=%.3fs  fill_fifo=%.3fs  wire=%.3fs  max_accesses_between_yields=%d'
              % (overhead * 1000, rows['stop_and_wait']['seconds'], rows['fill_fifo']['seconds'],
                 rows['fill_fifo']['wire_seconds'], rows['fill_fifo']['max_accesses_between_yields']))
    print('PASS_MOCK UART Lite TX benchmark')
