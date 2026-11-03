# 基于接口契约的通用PYNQ校验工具

## 目的与边界
适用于支持PYNQ的板卡及32位AXI-Lite IP。更换题目/板卡仅修改Overlay、契约和参考数据，不修改核心工具。案例为整数求和与阈值计数，不依赖四探针。
跨板通用的是工作流和Python封装，不是bit文件；每块板卡必须有对应器件、引脚、时钟和镜像支持的Overlay。

当前完成：文件对/HASH、HWH与加载后IP身份检查、安全寄存器访问、代码/测试骨架生成、数值黄金比对、Vivado报告提取、MOCK报告生成。
未完成/未验证：DMA与缓存一致性封装、HLS专用ap_ctrl接口、FPGA功能仿真、自动识别全部板卡型号、板上运行、跨板实测。不要将本工具表述为已实现这些内容。

## 环境
离线：Python3.9+标准库，无pip安装、不需要PYNQ。已测试Python3.14.0a5及Python3.14.6/Windows；其他版本尚未逐个验证。
上板：板卡自身可用的PYNQ环境；PYNQ版本兼容性待上板确认。load_board通过Overlay/IP标准接口访问；不改系统文件、不配置SD卡。

## 从零开始：离线可运行
在本目录打开终端（命令中的python替换为自己的Python路径）。

```bash
python -B -m unittest discover -s tests -q
python -B scripts/run_examples.py --output examples/offline_results
python -B scripts/pynq_toolkit.py generate examples/vector_sum/contract.json examples/vector_sum/generated_driver.py
python -B scripts/generate_test.py examples/vector_sum/contract.json examples/vector_sum/generated_test.py
```

生成文件导入pynq_toolkit，因此需将scripts加入PYTHONPATH，或复制pynq_toolkit.py到生成文件同目录。例如在Jupyter：

```python
from pathlib import Path
import sys
root = Path.cwd()  # 指向技能目录，不是Windows固定路径
sys.path.insert(0, str(root / 'scripts'))
from generate_test import generate
from pynq_toolkit import load_contract
ns = {'__name__': 'generated_test'}
exec(generate(load_contract(root/'examples/vector_sum/contract.json')), ns)
import unittest
result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(ns['GeneratedTests']))
assert result.wasSuccessful()
```

结果位于examples/offline_results：两个JSON报告和comparison.md。每项标记MOCK；host_compare_ns只是主机比对耗时，不是FPGA延迟。资源/硬件性能未测字段为null。
两个examples包含独立保存的mock_outputs；黄金函数由输入另行计算，仍只是Mock测试，不是硬件输出。

## 自己的Overlay：发布与只读审查
examples没有附bit，不要将占位契约写到实际硬件上。

构建完成后由构建者生成发布清单，可信地与bit/hwh一同交付：

```bash
python -B scripts/pynq_toolkit.py manifest my_design.bit release.json --board my_actual_board
python -B scripts/pynq_toolkit.py audit my_design.bit release.json my_contract.json
```

manifest创建仅记录当前文件，不能证明两者确实同一构建；应在完成构建后由可信构建脚本执行。接收者不得对不明文件重建manifest然后声称已验证配套。
audit只验证文件与HWH信息，不加载Overlay。特定板卡、电气兼容性、时钟和IO安全仍由设计者确认。

## 上板操作模板（尚未实测）
停止其他硬件控制服务，按自己的应用关闭电流/电机/功率输出，人工确认安全；不能用通用工具假定这些已关闭。

```python
from pynq_toolkit import load_contract, load_board
contract = load_contract('my_contract.json')
overlay, client, checks = load_board(
    'my_design.bit', 'release.json', contract,
    actual_board='my_actual_board', download=True,
    safety_confirmed=True,  # 人工确认后才设置，不要机械复制
)
print(overlay.ip_dict)
print('checked identity registers:', checks)
print(client.read('status'))  # status必须在契约中标为安全无副作用读取
```

load_board默认拒绝下载；显式确认后才导入PYNQ并加载，检查ip_dict后读取expected定义的安全寄存器。不提供no-download附着模式，避免误认旧PL状态。
actual_board是用户提供的板卡标识而非自动硬件检测。若元数据地址无法解析或不匹配则停止，不能访问猜测地址。

## register_map使用范式
如果IP通过HWH正确描述寄存器/字段，可直接使用PYNQ驱动的register_map：

```python
ip = overlay.processor_0  # 名称由自己的契约决定
print(ip.register_map)    # 先看元数据描述，不猜字段名
# 仅在确认字段定义及安全性后访问，例如：ip.register_map.STATUS
```

不要用读取全部寄存器的方式审查包含read-to-clear/FIFO pop的设备；打印register_map也可能读取寄存器，必须先核对IP行为。缺少完整寄存器元数据的IP使用RegisterClient适配其read/write，不自动猜测register_map字段。

## 验证与故障案例
当前单元测试覆盖契约校验、地址/版本不匹配、只读写保护、危险命令授权、破坏性读保护、int32、超时、hash不符、缺hwh、XML安全、黄金非有限/长度不匹配、缺失指标、生成代码。
详见tests/test_toolkit.py和references。真实工程HWH审查证明解析器能读取该格式，不证明这个技能已在该板运行。

## 来自开发过程的经验
- 文件路径显示自己的bit但ip_dict显示基础Overlay：不能只认路径；核对实际IP和身份寄存器。
- 波特率是UART Lite硬件配置：Python参数不等于PL已经改变；发布清单用于避免旧位流误用。
- 数据与单位/极性/固定点缩放需要契约，不混入通用封装的业务公式。
- 无效值不当成0；测试通过与上板验证分开，资源性能必须带来源。
以上是观察沉淀，不宣称新增Skill已经解决全部来源工程问题。

## 提交与许可
SKILL.md支持智能体加载；竞赛主入口为skill/README.md。报告中描述用途、失败来源、测试证据、失效边界和复现步骤；通用性需展示不同契约用同一工具。
本次不替用户确定开源许可证，也未Git提交/发布。对外发布前队伍应选择许可并审查第三方来源；当前代码为本次新增标准库实现。

## 本轮经验增强
source_identity.py比较显式指定源码哈希；必须另从Tcl/日志确认实际综合源。
对应tests/test_enhancement.py可离线回归。

新增CLI（只读）：python -B scripts/source_identity.py project.v packaged.v generated.v；一致返回0、不一致返回1。先从Tcl/日志确认实际综合源，脚本不能自动发现它。
