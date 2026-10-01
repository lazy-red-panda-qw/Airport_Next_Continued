# Airport Details Pack Continued — 0.6.7 本地测试版

本包依赖 Extra Assets Importer（PDX 80529）、Extra Detailing Tools（80528）及它们所需的 ExtraLib（75724）。0.6.7 共 **504 项：461 Decal、34 NetLane、9 Surface**。玩家可使用机位模板快速铺设，再用透明字符、Surface 底色、细描边线和已有背景条自由组合；继续使用字符、道路贴花、道路线条、铺装四类菜单。

本轮将8张模板改成有折角安全边界、角部禁停斜线、引导与服务留白的基础机坪。廊桥活动区、轮位、设备停车框、停止线和编号独立选放，避免模板固定某个机场或道具的布局。另增简洁开放回转、直线开放贯通及两种独立禁停轮廓；现10种基础与25项配套。原500个Prefab身份保留，其余492项资产未改。三档原版飞机尺寸仍用用户实测值，其他档位覆盖更小通航与更大宽体；白色RGB177和作者字形保持原样。尺寸及跨机场对照见[机坪制作说明](docs/stand-presets.md)。

游戏端只调用 EAI 的 `LoadCustomAssets`，已移除自定义 Prefab 刷新系统。Decal / NetLane 使用旧导入格式，Surface 使用新版格式。源码中的 `CustomAssets` 在部署时展开到 DLL 同级：运行包直接包含 `CustomDecals`、`CustomNetlanes`、`Surfaces`、`Localization`。机位模板是玩家手动放置的静态贴花；不自动摆放飞机、编号或机位，不修改存档。

当前工作：`codex/icao-standardization`。修改前基线：`baseline/pre-icao-20261001`，提交 `7cf18e1`。基线包含用户后来补齐的贴图。初代 AirportNext 仓库未作修改。

本版验收步骤见 [第八轮联合测试指南](docs/test-round-8.md)，并保留 [0.6.5 材质待测项](docs/test-round-6.md) 与 [0.6.4 已获反馈](docs/test-round-5.md)。详细尺寸、标准适用条件、字段含义与回退见 [实施说明](docs/ICAO-implementation.md)。每个资产的路径、UiPriority、投影大小、实际涂漆范围、虚线周期和用途见 [完整清单](docs/asset-catalog.csv) 或 [JSON 清单](docs/asset-catalog.json)。[图样预览](docs/asset-preview.png) 中的编号对应 UiPriority。

基础布局与新增可选模块见[物理比例总览](docs/stand-preview.png)，分层搭建见[基础贴图与玩家组合示意](docs/apron-layout-example.png)。飞机、314编号及示意组件的位置不进入基础贴图，玩家可按实际飞机和廊桥重新组合。

后续制作对话可直接阅读 [机场标线扩展与配套资产交接](docs/airport-expansion-handoff.md)，其中包含可选社区资产的版本与反馈核查、服务道路和机坪标线的标准依据、待补核资料、建议制作批次及验收要求。

历史测试见 [第一轮](docs/test-round-1.md)、[第二轮](docs/test-round-2.md)、[第三轮](docs/test-round-3.md)。用户已确认六种 Surface 和 NetLane 铺底可用；0.6.3 保持其纹理和材质参数。带框背景只提供一个可旋转端帽，红底无需端帽；原临时四色粗线、1 m 方块、Surface 诊断项均已退役。第三轮实际地图还暴露了自定义分类缺图标、箭头被背景覆盖和字符系统重复，本版集中处理这些问题。

## 维护资产

`asset-specs.json` 管理尺寸、颜色、绘制层级和优先级分区；`tools/asset_pipeline.py` 是离线制作工具。`tools/apron_layouts.py`管理基础机坪几何，`tools/stand_presets.py`组合模板及独立组件，`tools/apron_preview.py`绘制文档预览。`SourceAssets/Glyphs` 保存作者的通用字符和箭头原图，`SourceAssets/RunwayGlyphs` 保存作者的跑道字符原图，`SourceAssets/Vectors` 保存米制标线 SVG 母版。它们不进入游戏运行包。编辑规则后运行：

```powershell
python -m pip install -r tools/requirements.txt
python tools/asset_pipeline.py --apply
python tools/asset_pipeline.py --check
python tools/qa_apron_layouts.py --baseline artifacts/pre-qa-0.6.7
```

`--apply` 只写入内容有变化的文件，避免无谓改变 EAI 的时间戳哈希。`--check` 不写文件，重新计算全部输出并核对资产集合、原始来源、绘制层级、UiPriority 和涂漆尺寸。不要在修改后的分支重建 `--bootstrap`；原始字形和基线配置已保存。

机位专项检查独立读取实际PNG与配置，量测笔画和斜线净距，并用修改前完整包验证旧资产及翻译保留；需要本机对应备份，不依赖重新生成的基线。报告写入 `artifacts/qa-0.6.7.json`。两款直入通航模板、两种开放机位及新禁停模块2048px，其余六档基础4096px，以保留0.10m安全线；首次导入耗时和远景压缩细线需游戏复核。

## 构建和测试

本机需已完成官方 C:S II Modding Toolchain 初始化，并安装 EAI。运行 `tools/build-local.ps1` 清理本包暂存目录后在 `artifacts/LocalMod` 中构建测试包；带 `-Deploy` 会安装到游戏用户目录中的本地同名 Mod，已有目录先备份。该脚本只管理本包对应目录。

```powershell
./tools/build-local.ps1 -Deploy
```

尺寸和配置的离线校验不能代替游戏渲染验证。重点测试箭头叠层、四类菜单、Surface 边缘与描边贴合、1 m 字符可读性，以及首次和第二次冷启动的尺寸一致性。分类搬迁改变了部分 Prefab 名称，本包不提供早期搬迁资产的存档迁移；0.6.7全部旧身份保持，但8个模板图样与占地更新；请用存档副本或重新放置组件测试。

2026-10-02：0.6.7全量生成与专项检查通过，Release零警告、零错误，已部署本地测试包，暂存与安装共1,566个文件SHA256一致。修改前0.6.6完整备份、测试步骤及旧待测项见[第八轮指南](docs/test-round-8.md)。
