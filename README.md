# HYT-image-skill

基于真实产品资料制作商品单图、Amazon Gallery 主副图和 Premium A+ 套图。产品资料在首次建包时整理，后续生成、续做和纠图复用同一产品包。

仓库还包含独立的日报与周会归档技能 `weekly-work-report`。

## 选择技能

| 技能 | 用途 | 什么时候使用 |
| --- | --- | --- |
| [product-image-project-builder](product-image-project-builder/SKILL.md) | 整理产品原图、规格、特征、卖点与证据 | 首次接收产品资料，或补充、纠正资料 |
| [product-single-image-generator](product-single-image-generator/SKILL.md) | 设计、生成和检查一张图片 | 已有产品包，需要单图或修改某张图 |
| [product-amazon-image-set-generator](product-amazon-image-set-generator/SKILL.md) | 规划并逐张制作 Gallery 或 A+ 套图 | 已有产品包，需要完整套图、续做或局部调整 |
| [weekly-work-report](weekly-work-report/SKILL.md) | 归档上午、下午日报并汇总周会报告 | 与图片生成独立，按需安装使用 |

图片工作流：**上传资料 → 建立产品包 → 选择单图或套图 → 生成并检查 → 反馈纠正**。也可以在一条请求中说明先建包，再继续制作套图。

## 安装与调用

### 在 Codex 中使用

在支持 `$skill-installer` 的 Codex 环境中，可以发送：

```text
使用 $skill-installer，从仓库 https://github.com/LXE123/HYT-image-skill
安装以下三个技能目录：
product-image-project-builder
product-single-image-generator
product-amazon-image-set-generator
```

需要工作汇报归档时，再安装 `weekly-work-report`。如果技能已经出现在列表中，直接使用即可。安装后在下一轮对话检查技能列表；未显示时可重启客户端。已有同名技能时，先核对版本，再明确要求更新，避免重复安装。

调用时写出 `$技能名称` 并描述任务，下面的示例可直接复制，产品编号、语言、图数和风格按实际需求替换。安装与发现机制可参阅 [OpenAI 官方技能说明](https://learn.chatgpt.com/docs/build-skills)。

### 在网页环境中使用

通过网页实际提供的技能或插件导入入口安装对应包。普通对话上传 ZIP 只提供本次任务资料，不等于完成安装，也不会增加图像生成工具。

本地打好的安装包位于 `dist/`，不提交 Git，因此从 GitHub 克隆或下载本仓库后不会自带这些安装包。需要网页导入时，使用维护者提供的包；网页执行说明见 [browser-testing.md](product-amazon-image-set-generator/references/browser-testing.md)。

图片生成需要当前环境能够查看产品原图，并把选中的原图传给图像工具。仓库中的 Python 脚本负责资料、计划和审核记录，不会自行调用图像生成服务。

## 准备产品资料

首次建包时尽量一次提供：

- 产品多角度原图，以及扣具、连接处、纹理等与当前任务有关的细节图。
- 已确认的材质、尺寸、适配信息、颜色或 SKU，以及实际售卖范围。
- 卖点资料和需要出现在图片中的原文文案，标明目标语言。
- 本次要做的图片类型、数量、用途，以及明确的品牌或风格要求。
- 涉及安装、调节或释放动作时，提供能说明动作和状态的照片或视频。

产品原图用于确定产品真实结构；风格参考只用于配色、光线或构图。缺少的事实会记录为缺口，不从竞品图片或旧成图中补猜。

## 产品图片使用示例

### 1. 首次建立产品包

上传资料后发送：

```text
使用 $product-image-project-builder，为产品 DP2512271 建立可复用的产品图片工程。
根据本次上传的原图和需求表整理产品特征、规格、卖点、文案及依据，保留未确认项。
先完成资料建包，不开始出图。
```

本地产品包默认保存到系统桌面的 `ProductVisualWorkspace/products/<product_id>/<version>/`。网页使用当前会话的可用存储。后续提供同一产品编号或产品包路径，继续使用已有资料；有新增资料时明确说明补充或纠正内容。

### 2. 制作完整 A+ 套图

产品包就绪后发送：

```text
使用 $product-amazon-image-set-generator，基于 DP2512271 的现有产品包制作完整 A+。
本次需要 13 张独立图片，仅 1464×600，使用我提供的英文原文文案。
覆盖需求表中的产品特点、材质、扣具、使用方式和选购信息，缺证据的任务保留原因。
整套采用浅暖中性色，保持背景明暗、色温、对比度与字体统一；构图和场景按各图任务设计。
卖点能自然通过画面表达时再结合，其他已确认信息可只做文字排版，不强画性能效果。
逐张生成并自查，最后交付图片文件、数量核对和剩余问题。
```

浅暖色仅是此示例的选择，可替换为当前品牌或已认可的风格。技能会先确定整套视觉范围，再让各图在范围内变化。

要做 Gallery 主副图，将任务写为“生成 13 张 Gallery 主副图”，并提供该渠道的画布要求；要两类一起做，明确写出各自数量。

当前 A+ 交付约定：

- 最终仅交付 **1464×600 PNG**：每张生成后保留原图，由代码导出并校验实际像素；同比例直接等比例缩放，异比例裁剪后等比例缩放，不依赖模型精确控制尺寸；不拉伸宽高、补边或自动增加手机版。
- 生成阶段将 **2.44:1（1464:600）横幅**放在提示词开头，优先于参考图画幅、风格与局部排版；当前工具支持比例/尺寸参数时同步设置，减少后续裁剪，仍须代码导出。
- 完整套图通常每类 13 张，可按内容在 9–15 张调整；明确数量、范围、单图或小样请求优先。
- 内容组与实际图片数分开计算，七个模块描述不等于七张照片。
- 只使用当前选定的交付语言，不因资料包含多种语言就自动生成多个版本；指定文案未经授权不翻译或改写。
- 同图可结合产品细节、文字和图形；每张独立交付，最终 A+ 页面由设计部组装。

A+ 的尺寸转换使用 [finalize_a_plus_image.py](product-single-image-generator/scripts/finalize_a_plus_image.py)，需要 Pillow。同比例原图保留完整画面缩放，例如 2928×1200 → 1464×600；异比例时先选择包含产品和文案的保留区域，由代码裁剪并等比例缩放。导出后检查内容完整、细字与纹理清晰度；具体命令和参数见 [代码导出说明](product-single-image-generator/references/state-and-contract.md#mandatory-a-code-export)。无法保留关键内容时调整构图或重新生成，代码执行不可用时标注导出未完成。

### 3. 只生成一张图片

```text
使用 $product-single-image-generator，基于现有产品包生成一张 1464×600 的 A+ 材质图。
用真实纹理和产品细节说明材质特点，文案使用已提供的原文。
延续现有套图的背景、光线和字体范围，按本图内容安排构图。
```

### 4. 继续生成或纠正某张图

继续未完成任务：

```text
继续 DP2512271 的现有 A+ 套图，从下一张尚未生成的子图开始。
复用产品资料、任务清单和共享风格，保留已经生成的候选。
```

根据设计反馈修改：

```text
第 3 张背景偏暗，请调整到现有套图的浅暖色范围。
保留产品结构、文案和有效构图，只纠正这张图的背景与光线。
```

反馈中提供图片编号或子图 ID，并指出背景、产品结构、文案或排版的具体问题。候选图先保留待审核；脚本校验通过不代表产品结构、视觉效果或人工验收已经通过。

新 QA 报告将目标布局与最终图片的实际区域分开，并记录标注方式与不确定项。恢复时先读取报告有效性：图片、所用证据和规则未变就复用已有结论，已有失败先修正，避免重复视觉检查。构图按当前任务判断，不对特写、完整商品和佩戴场景统一套用主体占比。具体字段、查询命令和真实样图基准说明见 [视觉审核规范](product-single-image-generator/references/visual-quality.md#actual-composition-and-review-reuse)。

## 工作汇报归档

此技能独立于产品图片工作流。发送日期、时段和真实工作内容即可，例如：

```text
使用 $weekly-work-report，归档今天上午的工作计划：
- 优化 A+ 套图生成规则
- 测试产品单图审核流程
- 整理产品资料缺口
```

已有当前工作上下文时，也可以发送 `$weekly-work-report 下午归档`。周会汇总可发送“使用 `$weekly-work-report`，根据本周期日报生成本周四周会报告”。示例中的工作内容应替换为实际计划或进展。

默认保存到系统桌面的 `weekMessage/`，按周五至周四归档；日报保存 Markdown，周会报告生成 Markdown 和 HTML。同日同一时段的补充会合并到原文件。详细规则见 [技能入口](weekly-work-report/SKILL.md)。

## 仓库目录与安装包

```text
product-image-project-builder/        产品资料、事实与证据建包
product-single-image-generator/       单图设计、生成与审核
product-amazon-image-set-generator/   Amazon Gallery / A+ 套图规划
weekly-work-report/                  日报与周会归档
deliverables/                        UML、验证记录和本地实验资料
dist/                                本地安装压缩包，仅跟踪 .gitkeep
AGENTS.md                            仓库协作与提交规则
CHANGELOG.md                         变更记录
```

`deliverables/` 保存 UML、验证记录和本地实验资料，Git 仅跟踪忽略规则中选定的 UML 与验证记录；`dist/` 保存本地安装压缩包，仅跟踪 `.gitkeep`。

合并安装包的位置为 `dist/product-image-skills.zip`，三个产品技能的分包及历史包也放在 `dist/`。合并图片技能包不包含独立的 `weekly-work-report`。

`dist/` 不放解压后的 `SKILL.md` 或技能副本，原技能源码目录保持独立。Git 忽略规则只控制版本跟踪，不能用来禁止技能发现。

需要重新打包时，从当前源码生成到 `dist/` 并核对一致性。变更记录见 [CHANGELOG.md](CHANGELOG.md)，修改、检查和提交约定见 [AGENTS.md](AGENTS.md)。
