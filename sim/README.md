# 验证入口

run_tests.py测试board与src生产镜像，完全离线。run_hdl.py使用命令行xvlog/xelab/xsim，必须检查终止PASS与错误日志；GUI会话连接失败不能当成通过。

六个默认HDL套件为fp_dsp、analog、axi、z_safety、stats_bank、reset_watchdog。AXI夹具针对当前ALX5ABI独立测试读写/地址通道；机械前提和复位优先级由独立安全套件检查。

所有实机验证仍需安全夹具和授权；仿真不等于外部引脚波形、实际限位、准确度或复位延迟验收。
