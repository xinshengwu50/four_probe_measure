# 时序契约
CPOL=mode>>1；CPHA=mode&1。leading是从idle翻转的边沿；MODE0/2在leading采样，MODE1/3在trailing采样，launch在相反边沿。MODE0需CS拉低后首位预置；MODE1首leading发送首位。

half_cycles=ceil(clock_hz/(2*requested_sck_hz))；actual_sck=clock_hz/(2*half_cycles)。分频上限、CS和数据周期限制都由配置说明，不暗含某芯片参数。
validate_trace检查逻辑记录的采样位、CS窗口和最小时间；允许SCK放慢/暂停，不会替你确认器件最大暂停时间或最高合法片选间隔。数据建立/保持只对观察到的变化判定，未捕获变化不能被检测。

实际调试：先查电平/供电/共地、确认CPOL/CPHA/CS极性、用非对称测试字、对照采样边沿/帧长，再查命令地址/更新/复位/参考电压。没有逻辑分析仪时慢速GPIO只能辅助接线，不能给出纳秒时序验证证据。
