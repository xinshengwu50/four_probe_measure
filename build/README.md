# 构建与交付

先用英文短路径运行create_project.tcl，然后build_overlay.tcl。工程位于vivado，导出位于rebuilt。脚本拒绝覆盖已有工程；应从干净目录重建。不要手工编辑xpr。

本机中文路径通过Desktop/four_probe_measure_open目录联接解决，外部分发建议直接解压到英文短路径。

交付身份链：构建成功→核对报告→同批bit/hwh复制board/pynq→record_build_provenance.py→refresh_deploy_manifest.py→checksums.sha256→refresh_release_manifest.py→verify_delivery.py。来源摘要不能对没有真实构建的产物伪造；实际板卡验收单独记录。

默认zip排除生成Vivado工程/缓存，只收集源码、脚本、交付和报告。Python测试修改日志后应重新核对发布清单。不要把曾通过但不对应当前输入的旧报告放入本轮交付。
