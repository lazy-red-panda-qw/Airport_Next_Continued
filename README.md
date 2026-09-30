# Airport Details Pack Continued — 0.6.1 本地测试版

本包依赖 Extra Assets Importer（PDX 80529）、Extra Detailing Tools（80528）及它们所需的 ExtraLib（75724）。当前分支在原有 187 项资产身份上整理 ICAO 尺寸和菜单排序，加入机场标线模块、组合背景与 Surface；共 508 项资产。运行时仍使用 EAI 的 `LoadCustomAssets` 挂载入口，原有 Decal / NetLane 保持旧格式，Surface 使用新版格式。源码中的 `CustomAssets` 在部署时展开到 DLL 同级：运行包直接包含 `CustomDecals`、`CustomNetlanes`、`Surfaces`、`Localization`。

当前工作：`codex/icao-standardization`。修改前基线：`baseline/pre-icao-20261001`，提交 `7cf18e1`。基线包含用户后来补齐的贴图。初代 AirportNext 仓库未作修改。

详细尺寸、标准适用条件、字段含义、测试与回退见 [实施与测试说明](docs/ICAO-implementation.md)。每个资产的路径、UiPriority、投影大小、实际透明区域测量结果、虚线周期和用途见 [完整清单](docs/asset-catalog.csv) 或 [JSON 清单](docs/asset-catalog.json)。[图样预览](docs/asset-preview.png) 中的编号对应 UiPriority。

0.6.0 的截图审查及实际加载失败记录见 [第一轮测试记录](docs/test-round-1.md)。0.6.1 修正连字符比例、十个旧导入器名称与整体刷新阻塞，新增固定宽度/自由长度背景和透明底黑黄字符。Surface 不可见的原因尚未通过游戏对照确认；此版恢复默认边缘参数，并提供 A/B/C/D 对照资产。第二轮放置方式和测试项目见 [0.6.1 测试指南](docs/test-round-2.md)。

## 维护资产

`asset-specs.json` 管理通用尺寸、颜色和优先级分区；`tools/asset_pipeline.py` 管理标准标线几何。`SourceAssets/Glyphs` 是作者的通用字符原始贴图，`SourceAssets/Vectors` 是程序生成的米制 SVG 母版。编辑规则后运行：

```powershell
python -m pip install -r tools/requirements.txt
python tools/asset_pipeline.py --apply
python tools/asset_pipeline.py --check
```

`--apply` 只写入内容有变化的文件，避免无谓改变 EAI 的时间戳哈希。`--check` 不写文件，重新计算全部输出并核对尺寸、身份、绘制层级和 UiPriority。不要在修改后的分支重建 `--bootstrap`；原始字形和基线配置已保存。

## 构建和测试

本机需已完成官方 C:S II Modding Toolchain 初始化，并安装 EAI。运行 `tools/build-local.ps1` 在 `artifacts/LocalMod` 中构建测试包；带 `-Deploy` 会安装到游戏用户目录中的本地同名 Mod，已有目录先备份。该脚本只管理本包对应目录。

```powershell
./tools/build-local.ps1 -Deploy
```

此版已按标准图样与米制目标生成，但需要实际游戏验证投影比例、NetLane 周期、Surface 遮盖关系和冷启动刷新。通用字符仍保留作者字体；部分箭头与 V 形资产明确标注为标准约束下的模块预设。其用途是游戏造景。

刷新调度回归检查（直接执行生产源码；不模拟 Unity 渲染）：

```powershell
dotnet run --project tools/tests/RefreshHarness.csproj -c Release
```
