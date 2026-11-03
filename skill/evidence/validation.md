# 本轮离线验证证据（2026-10-11）

## 实际执行
- 六套独立unittest：Overlay16、SPI10、ADC15、电机16、UART9、历史11，共77项全部OK。
- 包审计反证测试4项OK：正常包、改源码使哈希失败、更新manifest仍能发现断链、更新manifest仍能发现语法错误。总计81项。
- 两个本地Python解释器重复以上测试：D:/softword/python/python.exe、D:/softword/miniconda/conda/python.exe；均以-B运行。
- 五份Notebook共18个代码格在各自notebooks目录、独立Python子进程执行，全部exit0；交付Notebook保留清空outputs/execution_count。默认仅MOCK/PREVIEW，不加载Overlay或触碰GPIO。
- run_three_examples.py输出PASS_MOCK 6 reports。两个新增run_example.py分别输出UART拆粘包通过及CSV25保存/回填50个quantity记录通过；历史示例只写自有临时目录并清理。
- audit_package.py只读检查完整SHA库存、所有Python/Notebook AST、11个SKILL前置字段、Markdown本地链接。精确库存数量见最终命令输出及checksums.sha256。
- 四个原核心模块pynq_toolkit.py、spi_contract.py、adc_capture.py、motion_tuning.py与备份逐字相同；本轮用新增辅助模块增强，未改真实工程。

## 失败与更正（不隐去）
- skill-creator的quick_validate.py尝试运行，但两个解释器均缺PyYAML，ModuleNotFoundError；未联网安装。该官方验证器未成功执行。标准库审计仅校验本包简单前置字段/链接，不能替代完整YAML解析或行为评测。
- 一次维护脚本read_text未指定UTF-8，因默认GBK报UnicodeDecodeError；已显式UTF-8重跑完成，未把该次部分执行标作完成。

## 未执行
未做PYNQ上板、跨板、SPI波形/芯片、ADC、电机、真实UART/HMI历史显示验证。Agent工作流有历史证据与评测卡，但未执行陌生团队/独立Agent前向行为评测；不能宣称自动诊断成功率。

## 复用约束
UART是独立演示协议；CSV是自定义v1格式，不自动导入旧测量CSV。来源MOCK/BOARD显式过滤，BOARD为调用方声明。列表文件名字典序不是历史最新槽。历史完整行数不代表测量有效。硬链接独占发布不承诺目录断电持久性。停止能力及接触高度须实物验证。根目录原有Git状态不作为此Desktop包diff证明。

## 回退
完整修改前技能包在C:/Users/wxs/.codex/tmp/skill_workflows_20261011_172646/skill；恢复前先保留之后用户改动。未安装全局、未发网络请求、未选择发布许可。

## 增补：AXI UART Lite 发送踩坑（2026-10-12）
- 新增 `pynq_uart_validation/scripts/uartlite_tx.py`、`run_uartlite_benchmark.py`、`tests/test_uartlite_tx.py`；原 `uart_protocol.py`、`test_uart.py` 未改。
- `python -B -m unittest discover -s tests -v`（包目录）：Ran 17 tests OK（原9项 + 新8项）。
- 变异检查：分别注入“填满写法退回停等”“去掉TX_FULL检查”“等待改忙等不让出”，三个变异体都被测试抓到（killed=True）。
- `run_uartlite_benchmark.py` 输出 sleep开销 0/0.1/0.37ms 时停等 0.614/0.921/1.749s，填满写法均为 0.533s（线速），并打印 PASS_MOCK。
- 证据级别：OFFLINE_TEST。解释器 C:/Users/wxs/.local/bin/python3.12（Windows CPython 3.12）。未上板，未做跨板验证。
