# 验证报告与证据边界

compare以 abs(actual-reference)<=atol+rtol*abs(reference) 判定；非有限值和空数据不通过，长度不同明确失败。这里支持一维标量数列；矩阵/复数/位精确流须由调用者转换或扩展。

parse_vivado接收报告文本，识别WNS(ns)/WHS(ns)表和Slice LUTs/Slice Registers/DSPs/Block RAM Tile行。不同器件/语言/版本表名可能不匹配，字段保留null；不要以0代替。工具不会自行宣布DRC通过或依据WNS判断外部无约束IO时序。

```python
from pathlib import Path
from pynq_toolkit import parse_vivado
text=Path('timing_summary.rpt').read_text()+Path('utilization.rpt').read_text()
metrics=parse_vivado(text)
print(metrics)
```

BOARD报告必须提供board_evidence（真实输出路径/哈希、板卡/Overlay/契约身份、参数、软件版本及测试时间）。标签是调用者声明，不是工具自动证明；审查者还需检查原始输出。MOCK与SIMULATION均不等同于物理上板。
当前run_examples仅自动报告Mock正确性、主机比对耗时，不提供真实FPGA延迟/吞吐；真实性能可由应用保存起止计时并明确包括/不包括传输、预热、样本数及重复次数后填入metrics。无需为了加分编造测量。

大模型协作记录应保留实际提示词、回答和失败修正，不伪造历史。本次TDD：新测试最初模块不存在失败；实现后生成Driver缺构造参数测试失败；增加绑定契约的构造函数后通过。此过程可作为本包提炼与自我纠错证据。
