# 接口契约

schema_version固定1；ip.instance为HWH/overlay.ip_dict实例路径，支持层级a/b。
ip.addr_range指定需要的最小映射范围（4字节整数对齐）；phys_addr可省略以允许板间地址不同，提供时严格匹配；vlnv可省略，提供时严格匹配type。
registers各项必须有offset/access；32bit对齐、不可重叠，offset在IP范围内。
access: ro/rw/wo；read_effect: none/clear/pop；write_effect: none/pulse/w1c/command。
signed默认False；scale是raw到物理值的正比例因子，read_scaled=raw*scale；不自动支持offset校准。unit仅说明字段，可由应用记录。
dangerous标记可能启动外设的寄存器。expected用于只读安全身份检查：禁止wo/有读取副作用。没有版本寄存器的IP不用expected；没有身份检查只能验证元数据，报告必须说明。

RegisterClient默认所有写禁止。allow_writes=True是会话授权；allow_side_effect=True是每次危险操作授权。它不会替调用者关电机、停止DMA或决定量程。
不能随意读改写包含W1C或脉冲寄存器；字段访问需要设计者定义具体组合。当前不支持64bit原子寄存器、跨寄存器快照或自动生成RTL。JSON由validate_contract验证，不依赖jsonschema包。
生成代码必须让工具契约先通过验证；无任意用户代码注入/eval。生成测试只Mock，不是testbench。
