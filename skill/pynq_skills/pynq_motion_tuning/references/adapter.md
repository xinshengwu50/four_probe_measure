# 真实运动adapter契约

必须提供capabilities字典：immediate_stop=True、axis、clock_hz、hard_min_steps、hard_max_steps、profile='LINEAR_PERIOD_NOT_CONSTANT_ACCEL'。这些来自已核验硬件设计/接口契约，不应仅复制Notebook配置冒充能力。

- status(): 有界/非阻塞返回busy/done/fault布尔、position_steps整数、homed/trusted布尔。适配器负责明确状态语义、脉冲累计方向、位置有效性和完成标志生命周期。
- start(plan): 显式接受命令后返回True；必须正确设置周期/目标/段表及每段decel_segment_steps(含余数分配)并保证命令原子性与PL互锁。不能忽略参数、无返回就当成功。
- stop(): 有界请求即时停止，不自动回零；实际STOP响应/最坏停止距离需硬件验证。execute_plan对所有BaseException请求stop，stop失败在原异常stop_error中保留。

所有方法必须有界；Python轮询不是实时控制器。执行前状态busy=False/fault=False/homed=True/trusted=True且位置与plan起点一致；完成必须busy=False/done=True/目标计数正确/trusted=True。
每次授权绑定参数与机械配置，执行一次即消费，参数/状态/能力变化拒绝。不支持并发控制同一轴，需要应用确保唯一控制者；软件检查不是硬件互锁，单靠busy检查不能防并发竞态。
位置脉冲累计不证明机构没有丢步。独立实际标定、行程和编码器测量必须保存；不得把假adapter标为上板实测。

当前本队现有PL X不能立即软件stop，而Z/R及减速表也必须逐项核验，不能将本模板直接作为现有工程驱动。首先仅使用preview做参数换算与审查；真实接入另定接口并测试。
