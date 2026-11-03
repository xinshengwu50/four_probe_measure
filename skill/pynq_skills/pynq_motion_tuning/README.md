# 参数化单轴电机调试Skill

## 目的
Notebook分组配置机械标定、时钟、行程、安全门限、目标位置、运行/末端速度及减速窗口。默认只预览；假设例子不对应当前Four_ALL真实机构。

## 使用（标准库离线）
```bash
python -B -m unittest discover -s tests -q
python -B scripts/motion_tuning.py --config examples/linear_axis.json --output examples/linear_preview.json
python -B scripts/motion_tuning.py --config examples/rotary_axis.json --output examples/rotary_preview.json
```
核心入口notebooks/01_motion_parameter_tuning.ipynb，可直接改参数并预览；默认adapter=None、OFFLINE_PREVIEW=True、ARM_MOTION=False、RUN_MOVE=False。没有PYNQ导入、Overlay下载或隐式MMIO访问。
输出JSON为{plan,plan_sha256}；用于比较配置，不是实际运动/实测位移。

## 参数意义
- steps_per_unit=full_steps_per_rev*microsteps*gear_ratio/units_per_output_rev。
- gear_ratio为电机转数/输出转数；直线单位mm时units_per_output_rev是输出每圈导程；旋转单位deg时通常360。
- 目标取最接近整数步(ties-to-even)，报告量化误差。请求speed换算ceil周期，稳态实现速度不高于请求值；不是实际轴速度实测。
- STEP周期是完整高+低，最小高/低脉宽均检查；真实RTL若参数表示半周期须在adapter转换，不可直接写。
- 减速表是LINEAR_PERIOD_NOT_CONSTANT_ACCEL，按周期线性插值；不是恒加速度/jerk限制/S曲线。小距离有效窗口缩小；分段数不可大于有效窗口，余数分配在decel_segment_steps中明确报告。当前Four_ALL周期表不是同义算法，不能直接移植这个表。
- 硬行程来自实际PL能力，soft limits不得扩大hard；工具也核对adapter能力，不能在Notebook任意放大硬上限。无编码器时位置为STEP_ESTIMATE，不是物理闭环。

## 真实执行条件与限制
执行接口只是可适配模板，无现成板卡驱动。需按references/adapter.md实现已验证adapter，立即STOP、时钟、硬限位和profile必须匹配。当前工程X轴无即时软件STOP，不接入真实入口。本轮不改变原有运动链路/RTL/bit。
先停止其他控制服务，确保机械标定、原点、间隙与急停。关闭OFFLINE_PREVIEW，通过adapter读可信当前状态，重新预览，再人工设置ARM及三个确认标志。每次参数变更撤销旧授权，receipt使用一次。
stop只请求停机；Linux卡死/底层调用阻塞不是Python能处理的，硬件急停/限位必须独立。超时/异常没有自动回零或R/X恢复动作，避免拖动未抬起机构。工具不进行多轴扫描、压力控制、驱动细分配置或自动机械标定。

## 验证与移植
两个例子：丝杆mm与转台deg。测试使用FakeAdapter，涵盖越界、未回零、旧计划授权、STOP缺失、能力不匹配、超时/故障/Ctrl-C请求STOP。默认Notebook已离线执行，不代表上板。换题目/板卡替换配置和经过验证的adapter，不能用同一bit跨板。

## 本轮经验增强
motion_safety.py离线预览接触高度/撤回策略；撤回方向必须明确，不能替代硬件互锁和传感器。
对应tests/test_enhancement.py可离线回归。

新增API review_motion：显式命令LATERAL/DOWN/RETRACT/STOP及状态。fault_latched阻止所有非STOP动作；RETRACT须确认安全方向。复位恢复锁存与硬件故障应由应用区分，本预览不授权解除故障。
