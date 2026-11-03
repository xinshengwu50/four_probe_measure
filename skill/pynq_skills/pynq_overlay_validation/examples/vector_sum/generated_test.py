from pynq_toolkit import RegisterClient
CONTRACT = {'schema_version': 1, 'ip': {'instance': 'processor_0', 'phys_addr': '0x40000000', 'addr_range': 4096, 'vlnv': 'vendor:ip:vector_sum:1.0'}, 'registers': {'control': {'offset': 0, 'access': 'wo', 'write_effect': 'pulse', 'dangerous': True}, 'status': {'offset': 4, 'access': 'ro', 'read_effect': 'none'}, 'result': {'offset': 8, 'access': 'ro', 'signed': True, 'scale': 1}, 'version': {'offset': 16, 'access': 'ro', 'expected': 65537}}}
class Driver(RegisterClient):
    def __init__(self,transport,allow_writes=False):
        super().__init__(CONTRACT,transport,allow_writes=allow_writes)
    def write_control(self,value,allow_side_effect=False):
        return self.write('control',value,allow_side_effect=allow_side_effect)
    def read_status(self):
        return self.read('status')
    def read_result(self):
        return self.read('result')
    def read_version(self):
        return self.read('version')

import unittest
from pynq_toolkit import MemoryTransport
class GeneratedTests(unittest.TestCase):
    def test_version(self):
        driver=Driver(MemoryTransport({16:65537}))
        self.assertEqual(driver.read_version(),65537)

if __name__=="__main__":unittest.main()
