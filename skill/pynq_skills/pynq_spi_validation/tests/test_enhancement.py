import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import spi_transactions as mod
class EnhancementTests(unittest.TestCase):

    def test_read_and_config_independent(self):
        from spi_contract import SpiConfig,build_trace
        items=[]
        for name,bits in [('config',32),('read',33)]:
            c=SpiConfig(frame_bits=bits);tx=0xA55A
            items.append(dict(name=name,spi={'frame_bits':bits},tx=tx,rx=7,trace=build_trace(c,tx,7)))
        self.assertTrue(mod.validate_transactions(items)['passed'])
        items[0]['tx']=0
        self.assertFalse(mod.validate_transactions(items)['passed'])
        with self.assertRaises(ValueError):mod.validate_transactions([])

if __name__=='__main__':unittest.main()
