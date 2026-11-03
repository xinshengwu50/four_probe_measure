# 通用ADC帧解析与采集质量

## 已实现
scripts/adc_capture.py：有效位域与通道提取，straight/twos/offset编码、2^N分母映射、前端bias/gain换算、序号去重/回卷/缺失/乱序检查、启动弃样、超时、有界provider接口、统计和饱和/噪声/有效比例标志。
不含实际ADC SPI配置序列、MMIO驱动、校准表、材料模型或电流控制。

## 使用
```bash
python -B -m unittest discover -s tests -q
python -B scripts/adc_capture.py --config examples/single_ended_12bit.json --records examples/single_ended_12bit_records.json --output examples/single_ended_report.json
python -B scripts/adc_capture.py --config examples/bipolar_channel_16bit.json --records examples/bipolar_channel_16bit_records.json --output examples/bipolar_report.json
```
notebooks/01_adc_frame_debug.ipynb中可调整位数、编码、范围、增益、偏置、样本数和噪声门限，默认只读合成records。

## 记录与新帧
record={sequence:int,frame:int,status_ok:bool可选}。sequence必须来自硬件帧计数或等价可信事件；禁止Python读循环累加。sequence与frame须原子关联。重复数值不是重复帧；重复序号不计入样本。模计数器差值>=半范围判乱序，无法区分硬件复位/长间隔/过半回卷，需要新会话；SEQ_GAP默认使质量失败。
provider每次返回record/None，可用StopIteration表示结束；capture要求provider有界、非阻塞，Python不能中断一个卡死的底层read。采集超时/数据耗尽/质量失败均抛CaptureError并携带partial，不能当成功。

## 单位与有效性
adc=input_min+(normalized_code/2^N)*(input_max-input_min)；signal=(adc-bias)/gain。最高码为上限减一LSB，真实芯片可能有不同端点定义，需查手册后扩展。straight支持所配置单极/双极映射；twos和offset将符号码映射到所配置范围，零码电压是否0取决于范围是否对称。
饱和端点指ADC码边界，不证明模拟前端实际没有提前饱和。状态异常/通道错误不进入统计；valid_ratio分母含拒绝记录但去掉有效启动弃样。无样本mean/std/min/max为null。
ADC软件质量通过不证明恒流、接触、压力或物理单位校准正确。质量门限不能照搬四探针实验参数。

## 验证范围
两个合成例子：12bit单端带前端增益偏置、16bit有符号双极带通道头。无实际ADC/Overlay调用，无跨芯片/跨板实测。完整硬件样本新鲜度需PL序号/握手/FIFO支持，不能仅靠软件保证。

## 本轮经验增强
adc_window.py从相同偏置/增益逆算窗口，二补码跨零可能拆为两个原码区间；不会写PL，浮点边界按计算结果向内取整。
对应tests/test_enhancement.py可离线回归。

新增API signal_window_codes(config,low_v,high_v)：返回normalized_bounds、raw_intervals、signal_zero_raw_code。二补码跨零可能需要两个原码区间，适配PL时不可无符号拼成一个大范围。
