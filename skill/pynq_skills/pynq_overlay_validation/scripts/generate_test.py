"""Generate safe offline test skeleton from an explicit interface contract."""
import argparse
from pathlib import Path
from pynq_toolkit import load_contract,generate_driver

def generate(contract):
    code=generate_driver(contract)
    code+='\nimport unittest\nfrom pynq_toolkit import MemoryTransport\nclass GeneratedTests(unittest.TestCase):\n'
    count=0
    for name,r in contract['registers'].items():
        if 'expected' in r:
            from pynq_toolkit import integer
            code+='    def test_'+name+'(self):\n        driver=Driver(MemoryTransport({'+str(integer(r['offset']))+':'+str(integer(r['expected']))+'}))\n        self.assertEqual(driver.read_'+name+'(),'+str(integer(r['expected']))+')\n';count+=1
    if not count:code+='    def test_contract_only(self):\n        self.assertEqual(CONTRACT["schema_version"],1)\n'
    code+='\nif __name__=="__main__":unittest.main()\n';return code
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('contract');p.add_argument('output');a=p.parse_args()
    Path(a.output).write_text(generate(load_contract(a.contract)),encoding='utf-8')
