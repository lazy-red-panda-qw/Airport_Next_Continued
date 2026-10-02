# Airport Details Pack Continued 玩家指南

**0.7.0.0 - 首个公开 WIP 版本。** 本包提供机场地面标记和铺装，共506项：460 Decal、39 NetLane、7 Surface。适用游戏系列为1.6.*，作者当前环境为1.6.2f。

**[中文版 PDF](../../output/pdf/Airport-Details-Pack-Continued-0.7.0.0-Manual-zh-CN.pdf)** · **[English PDF](../../output/pdf/Airport-Details-Pack-Continued-0.7.0.0-Manual-en-US.pdf)**

两版均含搭建步骤、公开规范图节选、尺寸与适用条件附录，以及全部506项资产的精灵图索引，其中386项为相对原始母版基线新增的资产。

## 开始使用

启用 Extra Assets Importer（80529）、Extra Detailing Tools（80528）及它们所需的 ExtraLib（75724）。在 EAI 设置中启用旧 Decal / NetLane 导入器、Surfaces 与 Localization。游戏中使用四类入口：字符、道路贴花、道路线条、铺装。

1. 用 Surface 铺出混凝土或沥青道面。
2. 用 NetLane 画连续线、周期标线或背景条，先保持默认比例。
3. 用 Decal 放置跑道标记、机坪基础或独立组件。
4. 用透明字符、箭头、背景及描边组合编号和信息标记。
5. 按实际飞机和道具摆放停止点、廊桥活动区、轮位及设备框，校准一组后成组复制。

![基础贴图与玩家组合示意](../apron-layout-example.png)

飞机、编号和灰色底面只是示意；基础资产保留独立组合空间。两侧留白不自动等于车辆道路或获准停车区。所有贴花都是静态组件，摆放由玩家完成。

## 内容与尺寸

- [完整 CSV 清单](../asset-catalog.csv) / [JSON 清单](../asset-catalog.json)：逐项名称、投影、涂漆范围、周期、绘制层及来源。
- [机坪布局尺寸](../stand-presets.md)：10种基础布局、原版飞机实测档位及独立配套。
- PDF附录：本版使用的规范数值、地区图样和包内预设；每项精灵图卡片另列实际投影与涂漆外接尺寸。

可见涂漆范围与含透明留白的投影大小不同。缩放会同时改变线宽、间距和周期。白色为RGB177，黄色为RGB255/239/73。细腻混凝土和沥青为本版正式铺装材质。

## 推荐搭配

[G87](https://mods.paradoxplaza.com/mods/97828/Windows)提供普通道路标线和更多材质选择；[Sully Airport Essentials Pack](https://mods.paradoxplaza.com/mods/117064/Windows)提供机场砖块Surface、跑道边缘及其他机场细节；Airport Pack、LAX Airport Props及Runway Guard Light补充牌体、廊桥、建筑和灯具。

这些是按需搭配的可选包，不是本包强制依赖；尚未全部完成联合适配测试。适量添加，遵循每个包自己的依赖与游戏版本要求。

## 维护说明

主仓库：[Airport_Next_Continued](https://github.com/lazy-red-panda-qw/Airport_Next_Continued)。版本内容以对应Git标签中的清单与PDF为准。后续会继续扩充服务车辆车道和用途明确的机场标记。

PDF由`tools/build_manual.py`读取当前清单、参数、机坪几何与规范图节选生成。规范图的版次、页码、链接和裁切范围见[来源记录](sources.json)。该文档适合将来同步到GitHub Wiki；当前公开文档入口保存在主仓库内。
