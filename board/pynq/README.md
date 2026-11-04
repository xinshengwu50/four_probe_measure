# 上板运行包

唯一入口pynq/01_four_all_system.ipynb。完整上传pynq到同一Jupyter目录；测试文件可不上传，但four_probe_sw目录不可自行删减，其deploy_manifest.json会核对每个核心文件和bit/hwh。

版本：PS24、ADC19、HMI11、FP_DSP5；ALL_Final ABI0x414C5835；UART115200/8N1。
无网页、自动图片上传、高级频谱/拟合/波形；电压不乘4，显示无独立倍率。

默认安全门全部关闭。先停止其他UART/运动服务，确认电流OFF和探针不依赖Z保持力，才能重配PL。不能用重载Overlay清除复位/看门狗。Ctrl-C/RST停止并保持，人工恢复才移动Z/R，X方位人工确认。

01按导入、参数、Overlay、状态、服务顺序执行。正式开始由串口屏发帧；历史不触发测量。完整成功后正常退出，后台RX继续识别RST；再次运行服务前按原初始化管理唯一所有者。

实机加载、机械标定、已知负载精度及新版屏幕显示仍需逐级验收。详见根README与report/verification.md，不能将离线测试当成板测。
