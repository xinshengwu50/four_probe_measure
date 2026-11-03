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
完整修改前技能包在 C:/Users/wxs/.codex/tmp/skill_workflows_20261011_172646/skill；恢复前先保留之后用户改动。未安装全局、未发网络请求、未选择发布许可。

---

# 第二轮（2026-10-31）：补齐构建报告工具 + 修正重复描述

## 为什么改

对照《选题指南》§3.3.5.2 逐条查，发现四类缺口：

1. 指南点名"性能与资源数据自动采集并生成报告的工具"，包里没有。`pynq_toolkit.parse_vivado` 只能抠出几个数，没有对比、没有溯源、没有护栏。
2. 5 个 Agent 技能的结尾段（`## 使用与输出` 到文件末尾）**逐字节相同**（`md5sum` 同为 `71cfe87092a533f8f4e69e11fefafda5`），连"用户请求示例"都是同一句与本技能无关的话。新用户无法从描述判断该用哪个。
3. `skill/README.md` 写着"唯一任务账本为 `C:/Users/wxs/Desktop/AMD/WORKLOG.md`"——指向外部绝对路径，复用者无法访问，且与"证据文件不是第二本进度日志"自相矛盾。
4. 每个 Agent 技能都声称"来自历史失败"，但历史只以 `log/1/WORKLOG.md:6500` 这种形式存在，**原始日志不在包内**。别人无法核实。

## 实际执行

- 新增 `pynq_skills/pynq_build_report/`：`scripts/build_report.py`（采集/对比/Markdown）、28 项测试、真实报告样例、SKILL.md、README.md。
- **真实报告解析**：拿本项目基线与 V4 的 `utilization/timing_summary/drc.rpt` 原文跑通，输出 BRAM 104→55（−47.1%）、WNS +1.337→+2.767（+107.0%）、DRC Error 0→0。这些数字来自 Vivado 导出文件，不是夹具。
- 新增 `evidence/worked-examples.md`：三个真实失败的完整复盘（错误删除 `meas_chain` 被综合拒绝、时序瓶颈定位、解析器被真实报告打脸两次），含编译器原文与消费者链行号。
- 5 个 Agent 技能各补"何时用 / 何时不用"与本技能专属的启动示例，删掉重复段。
- 修正 README 的外部绝对路径；补"已知缺口"一节。

## 验证命令与实际输出

```bash
python -B -m unittest discover -s tests -q        # pynq_build_report，Ran 28 tests，OK
python -B scripts/run_all_checks.py               # ALL_OFFLINE_TESTS_PASS; hardware not verified
python -B scripts/refresh_manifest.py             # MANIFEST_REFRESHED 115 files
python -B scripts/audit_package.py                # PASS_PACKAGE: 115 hashes, 12 skills,
                                                  #   18 code cells, 41 local links; no hardware
```

各包测试数：Overlay 16、SPI 10、ADC 15、电机 16、UART 17、历史 11、构建报告 28、包审计 4，合计 **117 项全 OK**。

## 本轮被测试抓到的两个真 bug（不隐去）

- `RAMB36/FIFO*` 的脚注星号：正则字符类 `[A-Za-z0-9 ./]` 不含 `*`，整行未匹配，该指标在两轮里都读成 `None`。真实报告才暴露，合成夹具覆盖不到。
- Clock Summary 段头：代码用 `startswith('Clock Summary')`，但 Vivado 实际写 `| Clock Summary`，导致时钟表解析出 0 条。

两处都已修，并各补一条针对性测试（`test_starred_label_is_matched`、`test_clock_summary_read`）。

## 仍未执行

- **Agent 技能前向行为评测**：5 个技能各带评测卡，一张都没跑。不能宣称"用了它就能定位问题"。
- **上板与跨板**：全部验证止于 OFFLINE_TEST。`pynq_build_report` 只解析文本报告，不接触 Vivado 进程或硬件。
- **DMA 封装**：指南 §3.3.2 举例提到，本包没有——本工程用 AXI-Lite + MMIO，没有 DMA 通道，写一个没用过的封装只会是纸面代码。这是明确的空白，不是已完成项。
- **PyYAML 仍缺**：官方 `quick_validate.py` 仍未跑成。

## 复用约束（本轮补充）

`pynq_build_report` 只认 Vivado ASCII 报告，只测过 2026.1；层级模式（`-hierarchical`）的按模块表不解析；时序只读 Design Timing Summary。跨器件对比会被硬性拒绝，综合 vs 布线混合会警告——这两条是设计意图，不是缺陷。

## 增补：AXI UART Lite 发送踩坑（2026-10-12）
- 新增 `pynq_uart_validation/scripts/uartlite_tx.py`、`run_uartlite_benchmark.py`、`tests/test_uartlite_tx.py`；原 `uart_protocol.py`、`test_uart.py` 未改。
- `python -B -m unittest discover -s tests -v`（包目录）：Ran 17 tests OK（原9项 + 新8项）。
- 变异检查：分别注入“填满写法退回停等”“去掉TX_FULL检查”“等待改忙等不让出”，三个变异体都被测试抓到（killed=True）。
- `run_uartlite_benchmark.py` 输出 sleep开销 0/0.1/0.37ms 时停等 0.614/0.921/1.749s，填满写法均为 0.533s（线速），并打印 PASS_MOCK。
- 证据级别：OFFLINE_TEST。解释器 C:/Users/wxs/.local/bin/python3.12（Windows CPython 3.12）。未上板，未做跨板验证。
