# CSV 结果与历史管理

## 适用与使用
保存自包含CSV、源和参数溯源、缺失质量标志、独占发布、读取校验及先导航后回填；不启动硬件。

包目录运行：
```bash
python -B scripts/run_example.py
python -B -m unittest discover -s tests -v
```
也可打开 notebooks/01_offline_debug.ipynb，默认完全离线。

save_snapshot(directory,meta,rows)验证后保存；list_history(...,source="MOCK")显式区分合成/真实；restore_snapshot使用begin/write_row/finish回调，全部校验后先begin导航，最后才finish完成。

## 验证范围
回归覆盖正常与故障路径，详见tests和根目录验证报告；示例仅MOCK，不代表硬件实测。

## 失败来源与边界
BOARD是调用方声明不是可信认证；complete表示行集合齐全，不表示所有值有效。列表按文件名字典序不是最新时间；四历史槽排序由应用显式提供。硬链接不支持则失败，不回退到覆盖发布；不承诺断电目录持久性。SHA仅标识当前文件，未与可信manifest比较不能防篡改。

UART源于历史FIFO溢出/双服务风险与显示耗时；历史管理源于返回页清空后必须从完整持久化快照恢复，而不是仅保存显示文本。来源见 ../../evidence/cases.md。不提供材料模型、真实HMI控件映射、通用bit或硬件急停。
