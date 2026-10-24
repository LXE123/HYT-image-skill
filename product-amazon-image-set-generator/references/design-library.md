# 融合设计库：版式、风格与购买叙事

仅在主动使用目录版式、风格或叙事配置时读取。默认 adaptive 设计无需读取全部目录。用于新套图的设计规划。保留既有产品证据、真实声明、主副图/A+ 功能选择、主图默认 9 张（2+3+1+3）、A+ 仍为 9–15 张通常 13 张、扩展模式及逐图审核。这里增加可选择、可进入提示词的设计方法，不接入外部生图网关，也不安装第三方 skill。

## 默认按输入设计

新草稿默认 `design_system.mode: adaptive`，具体工作流见 [自主设计与效果测试](autonomous-design.md)。本库的版式和六种风格是可选起点，不能要求用户先选一个风格，也不能自动把材质、适配品牌映射到固定风格。共享 `visual_system` 根据当前输入形成，当前图片可在 `creative_brief.design_adjustments` 中细化配色、光线、字体、背景和图形，但须留在共享背景明暗、冷暖、对比度和字体范围内；目录风格也服从这一边界。具体规则见 [共享风格边界](visual-direction.md#shared-boundaries-varied-images)。非主图 `layout_id: adaptive` 允许直接写构图；主图保留 `main_clean`。`DIRECT/single_message` 是默认图片任务标记，不规定整套销售顺序；按实际买家问题安排内容。

参考只对相关元素产生影响；`reference_influences` 指向本图已登记的参考来源，写清借鉴元素、程度与原因。可不使用外部参考，也可局部改善已有方案。完整目录不进入生成提示词。下方目录选择规则适用于主动选用目录的情况；旧版无 `mode` 的计划继续按 catalog 解析，不自动迁移。

需要把摄影、光影、材质、景深等风格融入产品和整套 A+ 时，读 [产品主导的风格融合](product-led-style-integration.md)。技能保留通用设计方法，不内置具体产品样图或自动取用历史实验图；需要参考时，按当前输入与图片任务选择相关来源。

```text
python3 scripts/configure_design.py <package> --set-id <set> configure --mode adaptive --rationale "依据本产品和本次任务拟定方向"
```

## 来源与取舍

以下是设计思路的参考来源；本目录的 JSON、脚本与说明重新编写，没有复制这些项目的供应商代码、默认交互或提示词全文。

- [OnestarQQ / amazon-listing-skill](https://github.com/OnestarQQ/amazon-listing-skill/blob/main/SKILL.md)：借鉴按卖点任务选择版式、统一视觉识别的方法。
- [wzj177 / ecommerce-image-suite](https://github.com/wzj177/ecommerce-image-suite/blob/main/SKILL.md)：借鉴同一视觉风格在不同图片类型中采用不同表达的方法。
- [misty1999sd / amazon-image-design-skill](https://github.com/misty1999sd/amazon-image-design-skill/blob/main/SKILL.md)：借鉴购买决策叙事、功能到利益再到证据的表达方法。

不继承自动推断尺寸/性能、无来源结构分解、固定图数、强制手机版、固定人群造型或读取密钥/外部 API 的规则。社区项目的尺寸与规范描述不作为 Amazon 官方规则；本任务的 A+ 尺寸继续为 1464 × 600。

## 三个选择彼此独立

`template_id` 负责产品/人物/操作的生成与证据要求。`layout_id` 负责画面组织。`style_id` 负责共享视觉语言。叙事框架和每图 `story_stage` 决定购买信息的顺序。页面展示类型（全幅/轮播）仍由 A+ 分组管理，不能拿这些分类互相替代。

新套图将 [设计目录](../assets/design-patterns.json) 固定为项目内 `DESIGN_PATTERNS.json` 并记录 SHA-256。每图 spec 保存当前构图、任务位置与产品相关创意，可选目录起点和参考元素；生成和审核只解析当前选择，不传入整个库或相邻图片历史。

## 15 种版式

| ID | 适合的任务 | 核心画面关系 |
|---|---|---|
| `main_clean` | 白底主图 | 完整商品轮廓和真实质感，不添加营销图形 |
| `editorial_hero` | 开篇、情境主视觉 | 人物/环境或产品构成主要故事，建立前后景 |
| `benefit_split` | 一个核心卖点 | 主视觉证据与较小的解释区域并置 |
| `detail_context` | 材料、局部结构 | 大特写与较小的整体/部位关联 |
| `proof_cards` | 一项卖点的多处证据 | 大主证据配少量从属细节 |
| `step_sequence` | 调节、安装、使用 | 有实际状态依据的步骤序列 |
| `fit_guide` | 尺寸、适配 | 测量视图与真实选择信息分区 |
| `variant_grid` | 已登记的多款/多色 | 同角度、同尺度的选择矩阵 |
| `evidence_compare` | 真实状态或自有选项对比 | 同尺度比较一个有依据的差异 |
| `asymmetric_story` | 场景加细节 | 较大主景与从属细节列形成主次 |
| `scene_triptych` | 多种使用情境 | 一个主场景与两个较小场景 |
| `radial_detail` | 一项结构特点 | 中心产品与少量不遮挡结构的注释 |
| `type_led` | 文案与产品共同形成焦点 | 已批准短标题与产品轮廓共享构图轴线 |
| `lifestyle_full` | 完整人物生活场景 | 可辨认的人、动作、环境和自然尺度产品 |
| `closing_story` | 收束、拥有体验 | 信息较少的情境画面呼应整套故事 |

每种版式包含方形/宽幅的归一化区域建议，以及构图和文案使用原则。区域只是起点，应按实际产品、姿态和字数调整；不能以框的位置为理由裁掉关键结构。对比、图形、步骤和多款均须有对应证据。布局库不产生产品事实，也不要求每张都有文字、图标或光效。

## 六种风格的图片类型变化

| 风格 | 材质图 | 卖点图 | 人物场景 | 选择说明 |
|---|---|---|---|---|
| 明亮生活杂志 `editorial_daylight` | 真实尺度的侧光纹理 | 情境与证据平衡 | 有层次的自然日常 | 清晰留距与对齐 |
| 明快运动生活 `active_bright` | 明快轮廓和触感 | 对比明确的证据焦点 | 可辨认的活动环境 | 简单醒目的标签 |
| 精密功能表达 `precision_tech` | 真实部件/表面边缘 | 有秩序的证据分区 | 可信的使用交互 | 有来源的参数结构 |
| 温暖日常 `warm_daily` | 触感和熟悉环境关联 | 亲近易懂的信息 | 完整日常动作 | 直白而从容的说明 |
| 轻时尚编辑 `fashion_minimal` | 真实形态与表面节奏 | 单一有力视觉 | 人物服饰与环境协调 | 一致的款式尺度 |
| 戏剧性棚拍 `dramatic_studio` | 真实表面高光 | 稀疏、强主次 | 可见结构的控制光场景 | 高对比可读信息 |

从输入形成共享方向，再按图片任务选择和组合处理方式。六种风格可用于描述和参考，不限定设计空间。品牌已批准的颜色、产品真色和明确要求优先。白底主图只使用适用的照明/尺度处理，不受深色背景、场景或文字装饰影响。

## 叙事选择

- `DIRECT`：单张或简单明确任务，阶段 `single_message`，不强加整套销售漏斗。
- `AIDA`：`recognition → relevance → proof → decision`，从识别到相关场景、证据和购买选择。
- `JTBD`：`situation → solution → proof → outcome`，从用户的实际任务组织内容。
- `PROOF_TO_USE`：`understand → verify → use → choose`，适合先解释结构/材料，再说明使用与选择。

每套选择一个主框架，按实际任务安排阶段和顺序，必要时解释回环。单张卖点图可用“功能 → 实际好处 → 用户利益 → 证据”思考，不强制把四项都写成图中文字，也不虚构数据或生活结果。主副图和 A+ 可采用不同的节奏；共享框架不是复制相同画面。

## 配置与单图设计

从本 skill 目录执行，在已有新套图草稿中查看适配某类图片的选择：

```text
python3 scripts/configure_design.py <package> --set-id <set> catalog --template-id material_macro
python3 scripts/configure_design.py <package> --set-id <set> configure --mode catalog --style-id editorial_daylight --framework-id AIDA --rationale "以真实材料证据和可辨认的日常使用帮助目标顾客理解产品"
python3 scripts/configure_design.py <package> --set-id <set> select --module-id a-plus-03 --layout-id detail_context --story-stage proof
```

`select` 返回当前版式、该风格对此图片类型的处理、叙事任务和画面区域建议。它不会自动填完创意、产品姿态、声明或文案。依据这些规则完善当前图片的 `creative_brief`，并把已验证的确切文案填入 `copy`；有意无字的场景要在创意中说明。同步 `visual_system`，使品牌要求与选定风格一致。空白创意或选择错误的版式不能批准。

要调整叙事顺序，`order --channel gallery --order <全部该类图片ID>` 按图片排列；分组 A+ 的 `order --channel a-plus --order <全部页面模块ID>` 同时更新页面顺序与子图队列。均使用逗号分隔且每个 ID 恰好一次，保留 ID 与验收历史。修改轮播内顺序则在草稿的 `image_ids` 中明确调整，再验证关系。

只改未生成的草稿。批准后仍需新修订；不会迁移或覆写旧验收。目录变化会被哈希检查拦住。

## 应用与验收

按 [内部试图规则](autonomous-design.md#内部检查后继续授权任务) 选择少量代表子图，AI 自查后继续已授权余图；候选保持待人评，不把小样人工接受设为默认前置条件。设计审核检查真实焦点、阅读路径、版式主次、字体/图形融入、场景完整性和整套差异。三张连续重复同一版式会给出节奏复核提示，不以数量配额代替审美判断。

这次融合提供的是可执行的设计方法与上下文传递，不代表新图已经变好看。仍需生成新候选并看实际画面；结构、材质、人体、声明和输出规格的原有检查继续适用。
