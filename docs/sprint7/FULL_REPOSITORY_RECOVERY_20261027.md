# 全仓离线执行恢复 — 2026-10-27

原Guard实测基线：2657 collected/5 errors（Chroma无home、缺evals、organ_eval、stability脚本）。只恢复必要Git原始工具和输入，不编造医学资料；17个唯一文件的18条来源记录见`RESTORED_TEST_TOOLS_20261027.json`、`RESTORED_TEST_INPUTS_20261027.json`。Sprint5 cases采用较晚原始批准版本，初次恢复版本信息亦保留。`.gitattributes`逐路径固定字节，原医学规则、索引启用和迁移checksum未修改。

恢复后真实执行曾为2727p/44f/1error/2skip，失败日志未覆盖。补齐精确输入后2780p/0f/2skip，但Guard仍exit90，不能称通过。调用栈定位到OCR导入Paddle/CUDA发现以及旧CLI嵌套子进程：资料/健康元数据测试显式使用其所断言的引擎不可用条件；真实OCR缺文件/坏PDF先拒绝再初始化，业务降级断言不删；CLI在原Guard里执行真实`__main__`并保留退出码/选项断言，不宣称冷启动子进程验证。

完整通过证据：`overnight-20261027-full-backend-provider-isolated/{result.json,telemetry.json,pytest.log}`，2781p/0f/2skip、exit0、无未知拦截/未批准skip。2skip是既有Windows符号链接权限场景，保留原批准清单。后续账号资源改动需新的完整回归，不把本次结果套用新HEAD。

可信启动器给依赖提供新的空沙箱HOME/缓存及TEMP/TMP，不继承真实用户配置/凭据；不改原Guard权限。新增`run.py --suite full`，只显式加载已安装/声明的pytest-asyncio插件，无自动外部插件。依赖固定为本机验证1.4.0（[官方发布](https://pypi.org/project/pytest-asyncio/1.4.0/)）；没有本地安装/下载。Hosted CI增加全仓后端步骤，Hosted结果仍须以相应SHA实际运行为准。

前端702p/1f/0skip，原素材/源码SHA保护仍保持；自动审查拒绝哈希例外适配，未改断言或制造全绿。H5离线编译及109资源校验通过；这些不等于Android、浏览器安全传输或生产验收。
