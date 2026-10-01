# Airport Details Pack Continued — 0.6.3 本地测试版

本包依赖 Extra Assets Importer（PDX 80529）、Extra Detailing Tools（80528）及它们所需的 ExtraLib（75724）。0.6.3 共 **462 项：425 Decal、31 NetLane、6 Surface**。玩家用透明字符、Surface 底色、细描边线和已有背景条自行组合标记。菜单收拢到 EAI 的字符、道路贴花、道路线条、铺装四类；移除 148 个带底字符和一个重复瞄准点，加入 1 m 字符、小数点、配套箭头和描边线，恢复作者原始跑道字形。

游戏端只调用 EAI 的 `LoadCustomAssets`，已移除自定义 Prefab 刷新系统。Decal / NetLane 使用旧导入格式，Surface 使用新版格式。源码中的 `CustomAssets` 在部署时展开到 DLL 同级：运行包直接包含 `CustomDecals`、`CustomNetlanes`、`Surfaces`、`Localization`。本版不生成自动文字、预设机位布局或存档转换逻辑。

当前工作：`codex/icao-standardization`。修改前基线：`baseline/pre-icao-20261001`，提交 `7cf18e1`。基线包含用户后来补齐的贴图。初代 AirportNext 仓库未作修改。

本版验收步骤见 [0.6.3 测试指南](docs/test-round-4.md)。详细尺寸、标准适用条件、字段含义与回退见 [实施说明](docs/ICAO-implementation.md)。每个资产的路径、UiPriority、投影大小、实际涂漆范围、虚线周期和用途见 [完整清单](docs/asset-catalog.csv) 或 [JSON 清单](docs/asset-catalog.json)。[图样预览](docs/asset-preview.png) 中的编号对应 UiPriority。

后续制作对话可直接阅读 [机场标线扩展与配套资产交接](docs/airport-expansion-handoff.md)，其中包含可选社区资产的版本与反馈核查、服务道路和机坪标线的标准依据、待补核资料、建议制作批次及验收要求。

历史测试见 [第一轮](docs/test-round-1.md)、[第二轮](docs/test-round-2.md)、[第三轮](docs/test-round-3.md)。用户已确认六种 Surface 和 NetLane 铺底可用；0.6.3 保持其纹理和材质参数。带框背景只提供一个可旋转端帽，红底无需端帽；原临时四色粗线、1 m 方块、Surface 诊断项均已退役。第三轮实际地图还暴露了自定义分类缺图标、箭头被背景覆盖和字符系统重复，本版集中处理这些问题。

## 维护资产

`asset-specs.json` 管理尺寸、颜色、绘制层级和优先级分区；`tools/asset_pipeline.py` 是离线制作工具。`SourceAssets/Glyphs` 保存作者的通用字符和箭头原图，`SourceAssets/RunwayGlyphs` 保存作者的跑道字符原图，`SourceAssets/Vectors` 保存米制标线 SVG 母版。它们不进入游戏运行包。编辑规则后运行：

```powershell
python -m pip install -r tools/requirements.txt
python tools/asset_pipeline.py --apply
python tools/asset_pipeline.py --check
```

`--apply` 只写入内容有变化的文件，避免无谓改变 EAI 的时间戳哈希。`--check` 不写文件，重新计算全部输出并核对资产集合、原始来源、绘制层级、UiPriority 和涂漆尺寸。不要在修改后的分支重建 `--bootstrap`；原始字形和基线配置已保存。

## 构建和测试

本机需已完成官方 C:S II Modding Toolchain 初始化，并安装 EAI。运行 `tools/build-local.ps1` 清理本包暂存目录后在 `artifacts/LocalMod` 中构建测试包；带 `-Deploy` 会安装到游戏用户目录中的本地同名 Mod，已有目录先备份。该脚本只管理本包对应目录。

```powershell
./tools/build-local.ps1 -Deploy
```

尺寸和配置的离线校验不能代替游戏渲染验证。重点测试箭头叠层、四类菜单、Surface 边缘与描边贴合、1 m 字符可读性，以及首次和第二次冷启动的尺寸一致性。分类搬迁改变了部分 Prefab 名称，本版不提供旧测试地图的资产迁移；请用存档副本或重新放置组件测试。
