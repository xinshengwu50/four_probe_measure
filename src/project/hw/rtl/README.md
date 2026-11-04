# RTL Source

当前可综合顶层为 `all/all_final.v`，由 `all_design` Block Design 通过 AXI-Lite、50 MHz PS FCLK 和同步复位驱动。不要将新源码只保存在 Vivado 自动生成目录中。

- `all/`：当前集成的 ALL_Final ADC、测量、UART 和 X/Z 运动控制器。
- `filter/`：后续滤波和质量统计模块。
- `motion/`：后续参数化 N 轴控制器。
- `common/`：跨模块复用逻辑。
