# Airport Details Pack Continued — 0.6.6 本地测试版

本包依赖 Extra Assets Importer（PDX 80529）、Extra Detailing Tools（80528）及它们所需的 ExtraLib（75724）。0.6.6 共 **500 项：457 Decal、34 NetLane、9 Surface**。玩家可使用机位模板快速铺设，再用透明字符、Surface 底色、细描边线和已有背景条自由组合；继续使用字符、道路贴花、道路线条、铺装四类菜单。

本轮新增 31 张透明贴花：8 档直入机位、3 种独立停止标记、6 种机型的 CAAC／CAAM 停止线旁注、廊桥活动扇区与轮位、带框禁停斜线及设备停放框。三档原版模板参照用户实测飞机尺寸，另覆盖通航、通用窄体与大型宽体；停止线独立定位，一个布局校准后可由玩家成组复制。0.6.5 原 469 项资产全部保留，白色仍为作者实测确定的 RGB 177/177/177。具体尺寸和来源见 [机位制作说明](docs/stand-presets.md)。

游戏端只调用 EAI 的 `LoadCustomAssets`，已移除自定义 Prefab 刷新系统。Decal / NetLane 使用旧导入格式，Surface 使用新版格式。源码中的 `CustomAssets` 在部署时展开到 DLL 同级：运行包直接包含 `CustomDecals`、`CustomNetlanes`、`Surfaces`、`Localization`。机位模板是玩家手动放置的静态贴花；不自动摆放飞机、编号或机位，不修改存档。

当前工作：`codex/icao-standardization`。修改前基线：`baseline/pre-icao-20261001`，提交 `7cf18e1`。基线包含用户后来补齐的贴图。初代 AirportNext 仓库未作修改。

本版验收步骤见 [第七轮测试指南](docs/test-round-7.md)，并保留 [0.6.5 材质待测项](docs/test-round-6.md) 与 [0.6.4 已获反馈](docs/test-round-5.md)。详细尺寸、标准适用条件、字段含义与回退见 [实施说明](docs/ICAO-implementation.md)。每个资产的路径、UiPriority、投影大小、实际涂漆范围、虚线周期和用途见 [完整清单](docs/asset-catalog.csv) 或 [JSON 清单](docs/asset-catalog.json)。[图样预览](docs/asset-preview.png) 中的编号对应 UiPriority。

新模板及部分配套组件可查看[按物理长宽比绘制的预览](docs/stand-preview.png)。预览的灰底只用于看清透明图样，不进入贴图。

后续制作对话可直接阅读 [机场标线扩展与配套资产交接](docs/airport-expansion-handoff.md)，其中包含可选社区资产的版本与反馈核查、服务道路和机坪标线的标准依据、待补核资料、建议制作批次及验收要求。

历史测试见 [第一轮](docs/test-round-1.md)、[第二轮](docs/test-round-2.md)、[第三轮](docs/test-round-3.md)。用户已确认六种 Surface 和 NetLane 铺底可用；0.6.3 保持其纹理和材质参数。带框背景只提供一个可旋转端帽，红底无需端帽；原临时四色粗线、1 m 方块、Surface 诊断项均已退役。第三轮实际地图还暴露了自定义分类缺图标、箭头被背景覆盖和字符系统重复，本版集中处理这些问题。

## 维护资产

`asset-specs.json` 管理尺寸、颜色、绘制层级和优先级分区；`tools/asset_pipeline.py` 是离线制作工具。`SourceAssets/Glyphs` 保存作者的通用字符和箭头原图，`SourceAssets/RunwayGlyphs` 保存作者的跑道字符原图，`SourceAssets/Vectors` 保存米制标线 SVG 母版。它们不进入游戏运行包。编辑规则后运行：

```powershell
python -m pip install -r tools/requirements.txt
python tools/asset_pipeline.py --apply
python tools/asset_pipeline.py --check
python tools/qa_stand_presets.py --baseline artifacts/pre-qa-0.6.6
```

`--apply` 只写入内容有变化的文件，避免无谓改变 EAI 的时间戳哈希。`--check` 不写文件，重新计算全部输出并核对资产集合、原始来源、绘制层级、UiPriority 和涂漆尺寸。不要在修改后的分支重建 `--bootstrap`；原始字形和基线配置已保存。

机位专项检查独立读取实际PNG与配置，量测笔画和斜线净距，并用修改前完整包验证旧资产及翻译保留；需要本机对应备份，不依赖重新生成的基线。报告写入 `artifacts/qa-0.6.6.json`。通航模板2048px，大型模板4096px，以保留0.10m安全线；首次导入耗时和远景压缩细线需游戏复核。

## 构建和测试

本机需已完成官方 C:S II Modding Toolchain 初始化，并安装 EAI。运行 `tools/build-local.ps1` 清理本包暂存目录后在 `artifacts/LocalMod` 中构建测试包；带 `-Deploy` 会安装到游戏用户目录中的本地同名 Mod，已有目录先备份。该脚本只管理本包对应目录。

```powershell
./tools/build-local.ps1 -Deploy
```

尺寸和配置的离线校验不能代替游戏渲染验证。重点测试箭头叠层、四类菜单、Surface 边缘与描边贴合、1 m 字符可读性，以及首次和第二次冷启动的尺寸一致性。分类搬迁改变了部分 Prefab 名称，本版不提供旧测试地图的资产迁移；请用存档副本或重新放置组件测试。
