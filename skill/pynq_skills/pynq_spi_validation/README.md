# 通用SPI契约与数字时序验证

## 已实现
scripts/spi_contract.py：可配置MODE0..3、MSB/LSB、1..4096位帧、整数分频、CS建立/保持、数据建立/保持、数字边沿/字数/发送与接收字比对。内部时间单位为PL时钟周期；ceil分频不超过请求SCK。
不包含实际SPI硬件驱动、芯片命令适配、RTL SPI IP或HDL testbench。数字模板/test不是FPGA仿真。幅值、毛刺、振铃、上升时间等模拟信号不在验证范围。

## 使用
在本技能目录运行（Python标准库，无网络依赖）：
```bash
python -B -m unittest discover -s tests -q
python -B scripts/spi_contract.py --config examples/mode0_msb_8bit.json --output examples/mode0_report.json
python -B scripts/spi_contract.py --config examples/mode3_lsb_24bit.json --output examples/mode3_report.json
```
交互调试入口：notebooks/01_spi_contract_debug.ipynb。默认生成波形、不发送信号。可改为自己的数字CSV，列为t_cycles,cs,sck,mosi,miso，t严格递增、电平0/1；同一时刻同时变化用一条记录表示。命令追加--trace-csv trace.csv。

## 通用性
两个例子分别MODE0/MSB/8bit/50MHz和MODE3/LSB/24bit/100MHz；不是任何实际芯片初始化帧。测试另外覆盖所有4种mode及两种位序。换板只更新时钟、位序、时序契约；真实设备IO还需硬件适配。

## 失效边界/来源经验
静态GPIO高低正常不能证明SPI时序/帧格式正常；能测到CS下拉不能证明DIN在指定边沿被芯片接收。采样数据全0时部分模式错误可能无法区分，必须使用非对称诊断字。trace若采样分辨率不足或SCLK漏边沿不能当成正确传输。
工具假设CS低有效、独立连续单事务、没有三态/双线/四线/DDR/3wire半双工；不支持多片选、延迟返回帧或器件特有dummy cycles解释。按手册另写协议适配，不能把通用checker当DAC/ADC完整驱动。
真实硬件、逻辑分析仪及跨板测试未执行，报告hardware_verified=false。

## 本轮经验增强
spi_transactions.py逐事务独立验证配置/读取帧长；不是器件命令生成器，不假设读写同帧长。
对应tests/test_enhancement.py可离线回归。

新增API validate_transactions：列表项含name、spi配置字典、tx/rx整数与trace列表，每项帧长独立。tests/test_enhancement.py含合成32/33拍示例，拍数不是芯片推荐配置。
