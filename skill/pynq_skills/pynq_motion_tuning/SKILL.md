---
name: pynq-motion-tuning
description: Preview unit-aware linear/rotary motor tuning with quantization and hard-limit checks, then optionally execute through a verified immediate-stop adapter; use for safe notebook parameter debugging, not implicit motion.
---

# 可调电机参数与安全调试

默认PREVIEW_ONLY，不加载Overlay、不直接读写寄存器。Notebook将机械标定、软硬限位、运行速度及减速表分开。

1. 阅读references/adapter.md；先确认真实脉冲周期定义、PL硬限位、回零反馈和STOP能力。所有默认标定是假设例子，绝不能照抄到实际机构。
2. 建立AxisConfig，以mm/deg请求目标与速度，preview_move给出步数量化、周期、脉冲宽度和减速LUT。这里按周期线性插值，不是恒加速度，也不是现有Four_ALL的同义实现。
3. 位置未知/未回零不允许真实plan。离线Notebook用模拟位置仅用于预览，真实执行必须关闭OFFLINE_PREVIEW并读取adapter状态。
4. 参数变更后重新预览并重新授权；单次receipt绑定完整计划指纹并消费一次。授权是软件工作流保护，不是防恶意用户的安全认证。
5. 真实execute_plan默认被禁用；仅允许支持即时STOP和匹配clock/硬限位/profile的已验证adapter。当前工程X轴没有即时软件STOP，不接入、不假装提供急停。
6. 超时、故障、Ctrl-C请求adapter.stop，STOP失败保留stop_error；不能保证Linux故障时物理停止。硬件急停/限位优先级仍须由PL/驱动实现。
7. 默认不自动回零、反向恢复或多轴联动。调试一次小距离，保留独立测量和配置，再决定继续。

## 经验增强入口
motion_safety.py离线预览接触高度/撤回策略；撤回方向必须明确，不能替代硬件互锁和传感器。
历史来源与验证边界见 ../../evidence/cases.md。
