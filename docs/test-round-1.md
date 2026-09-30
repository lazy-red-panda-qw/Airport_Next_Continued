# 0.6.0 第一轮游戏测试记录 — 2026-10-01

版本：提交 `8c62975`，标签 `test/icao-0.6.0-20261001`。截图由作者在游戏编辑器提供，包含五张近俯视图与两张原版飞机相对比例图。本记录不宣称正式游玩、所有资产或绝对米制尺寸已经通过验证。

## 已观察

- 作者确认 UI 显示顺序正确。
- 跑道字符、条纹组、瞄准点、关闭 X、箭头与滑行线的相对尺度没有明显整体错位；第三张黑色中/粗线宽度比约 1.7，接近目标 3/1.8。
- 10 m 网格和 20 m 标尺由同一生成器创建，只能独立于图样检查包内比例。绝对米制尺寸仍需游戏的独立距离参照。
- 作者报告三个带 Surface 名称的区域绘制后不可见，未记录具体资产名。

## 发现的问题

### 连字符被错误放大

生成器以每个字符自身 alpha 外接高度作为 2/4 m 基准，横杠因此变成 2/4 m 厚的大色块。第二张的黑心黄边、黄心黑边、白心红边来自 `Outbound Dash`、`Taxiway Dash`、`Mandatory Dash 2m/4m`，不是预先设计的空白背景。4 m 档带背景外接尺寸约 14.8×5 m，2 m 红底档约 7.9×3 m。

作者提出把宽框形式改为可绘制长度的 NetLane 背景，置于字符 Decal 下方、Surface 上方。0.6.1 为此加入独立主体、端帽、宽幅 Decal 和透明底字符，原连字符项目仍修正其字形。

### 十项资产导入失败

两次启动日志均出现 `SurfaceAsset doesn't have a matching extension and can't be added`。旧 EAI 创建缓存文件名时没有明确扩展名；下面的新项目名称含小数点，导致资产数据库误判扩展名：

- Apron Safety Red 0.1m
- Stand Lead In 0.15m
- Runway Centerline 0.3m / 0.45m / 0.9m
- Runway Edge 0.45m / 0.9m
- Displaced Threshold Bar 1.8m Module
- Threshold Stripe 1.8x30m
- Touchdown Zone Basic 3x22.5m

这里日志中的 SurfaceAsset 是 Decal/NetLane 的材质缓存，不能据此把这十项故障当成 SurfacePrefab 的不可见原因。

### 整批刷新超时

第一次日志在 01:47:26 显示 `Airport prefab refresh timed out`。代码要求所有 318 项旧格式父 Prefab 和 RenderPrefab 存在，十项加载失败阻止了其余项目刷新。0.6.1 改为导入结束后分别刷新已存在的项目，并列出缺失身份。

### Surface 不可见尚未确认唯一原因

本包六项 Surface 均有导入成功记录，六张基色贴图均生成缓存；全局 Surfaces 导入器完成时显示 166 loaded / 0 failed（包含其他资产包）。EAI 新格式文档允许省略 NormalMap 与 MaskMap。

共用设置 `EdgeNoise=(0,0)`、`EdgeFadeRange=(0.02,0.005)` 是重点候选，但没有取得实际着色器输出或运行时材质检查证据，不能宣布原因已证实。0.6.1 恢复默认边缘参数并提供单独对照项目。

来源：[EAI 新 Surface 文档](https://github.com/AlphaGaming7780/ExtraAssetsImporter/wiki/%5BNEW%5D-Surfaces-Importer)、本机 1.7.5 导入器代码、本机游戏 AreaBatchSystem/AreaRenderSystem 代码及 2026-10-01 游戏日志。
