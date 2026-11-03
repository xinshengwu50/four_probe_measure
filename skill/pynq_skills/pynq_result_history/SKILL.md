---
name: pynq-result-history
description: 保存自包含CSV、源和参数溯源、缺失质量标志、独占发布、读取校验及先导航后回填；不启动硬件。
---

# CSV 结果与历史管理

读 README.md 决定适配边界；默认只执行 scripts/run_example.py 和 tests，不导入PYNQ、不连接UART、不运动。

save_snapshot(directory,meta,rows)验证后保存；list_history(...,source="MOCK")显式区分合成/真实；restore_snapshot使用begin/write_row/finish回调，全部校验后先begin导航，最后才finish完成。

BOARD是调用方声明不是可信认证；complete表示行集合齐全，不表示所有值有效。列表按文件名字典序不是最新时间；四历史槽排序由应用显式提供。硬链接不支持则失败，不回退到覆盖发布；不承诺断电目录持久性。SHA仅标识当前文件，未与可信manifest比较不能防篡改。

硬件接入需用户提供权威协议/字段/单位和页面映射；示例不授权改屏幕或测量代码。历史失败来源见 ../../evidence/cases.md，当前仅OFFLINE_TEST/MOCK，不声称跨板验证。
