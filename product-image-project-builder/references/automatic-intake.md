# 自动拆解、少打断与独立交接

适用于运营需求表、混合主副图/A+/视频的文档，以及要求重新设计而不沿用旧样式的任务。工作人员提供现有资料、收到图片、指出需要修改的那张即可；不要让其逐项确认解析结果、模块、设计方向和小样。当前任务和既有授权优先，不能因为减少确认扩大图数、渠道或编造产品事实。

## 默认流程

1. 程序提取文字、图片与位置，AI 结合语义归属模块；不凭行号邻近强行匹配文案、参考图和后补版本。
2. AI 自行区分产品事实、内容任务、交付约束和旧表现建议，并记录来源与取舍。重新设计时，旧配色、版式、特效、成品参考及其文字描述只存原始档案（Gallery 当前明确展示要求按下节保留）；只保留当前明确要求的品牌规则。不要把旧图转写成文字再传给设计环节。
3. 一次内部检查遗漏、冲突和资料依据，形成有效需求包。排版、受众细分、拍摄情境、字体和视觉手法由 AI 自行拟定为可修改的设计假设，无需人工勾选。分析交付不能只展示 role 标签：同时列出各模块适用的设计语言原则、图文职责和不能替代该任务的做法。原则来自模块功能，不复制旧图的具体配色和构图；具体视觉方案由独立设计环节从有效需求包形成，明确标为 AI 提案而非原表事实。
4. 独立设计上下文只接收有效需求包和已登记的必要原始产品证据，形成共享视觉规则及各模块自己的表达，再逐张生成、自查和有限修正。已经授权的套图内可内部先试代表图，效果可执行就继续余图，不把小样人评设为默认开关。
5. 集中交付候选和必要的未完成说明，保留 PENDING_REVIEW。用户指出具体图片后交给单图技能纠正；需要时局部修订计划，不重跑整套，不重新询问已知信息。

## Gallery current-state handoff

本节仅补充主图套图（Gallery），不改变 A+ 现有骨架、数量或设计规则。产品初始化可先于交付模式选择；进入套图规划/生成前，若当前指令和已有状态仍未明确，集中询问主图、A+ 或两者并保存选择，不逐张重复询问。

多张产品图片加需求表/文档是正常输入，不要求另附平铺、参数图或生活场景的成品示例。首次整理时区分产品事实依据、当前必需内容/展示要求、可选视觉参考和未指定的创意空间；事实和原始来源沿用已有记录。初始化只确认产品及需求状态，具体设计由后续套图技能完成。

Gallery 当前明确要求的展示方式属于有效需求：将可观察的约束写入既有 `must_show`，例如必须露出的纹样、弯折状态、参数对应关系或明确指定的排布。不能将这些要求误当旧样式过滤；旧图中没有被当前任务要求的配色/构图仍只归档。指定方式与产品依据冲突时保留具体冲突，不能转成自由发挥。未指定的角度、排列、图文组合和场景由 AI 自主设计，不在建包阶段写死。

按每张任务判断产品依据是否足够。没有设计示例不等于缺少产品证据，也不自动降级执行模式；两种执行策略都允许补全未指定的设计选择。缺真实尺寸、多款配色信息、必需结构或操作状态才登记相应事实缺口；先判断是否能换用仍完成原职责的有依据表达，仅受影响任务等待。不为凑展示编造款式或参数，不用文字代替已明确要求的视觉展示。

有效交接只保留当前事实、必需内容、约束、文案、证据引用和缺口；来源讨论与旧方案留档。沿用 `required_fact_ids`、`must_show` 和 `execution_policy`，不增加平行状态表。后续主图规划按 [Gallery 框架](../../product-amazon-image-set-generator/references/amazon-planning.md#gallery) 完成内容分配和具体设计，再把当前单图状态交给生成。

## 自行处理与必要例外

可逆的设计选择直接做。相同意思的重复文案合并；有明确图片 ID、语言和修订标记的内容按对应关系使用。没有清晰版本依据时，不以最右、最下或看起来更新作为确认。旧布局冲突在重新设计任务中直接舍弃；可省略的冲突短句、无依据的绝对功效或参数先不用于画面，记在内部取舍中，避免为每条可省内容打断用户。

必要提问仅限当前任务确实无法执行且无法可靠推断的事实或范围，例如无法识别卖的是什么、缺少必需原始产品视图、操作/适配模块所需的参数冲突且无法省略，或渠道数量完全不明。只让受影响任务等待，其余已授权任务继续；把仍然必需的问题合并提出一次。外部环境的权限或工具能力限制应如实报告，不能承诺自动跨越。

建包的证据模式和售卖范围已有明确文字/实拍依据时自行选择并记录；普通警告由 AI 检查、处理或保留说明，不作为确认表单。只在真实不确定处提问。产品 ID 可复用资料明确给出的标识，版本未指定可用首次工作版本；没有可靠标识时先做临时任务，不阻塞单图试稿，不凭图片猜 SKU 或写入永久产品目录。

计划的 --approve 是校验后固定执行快照，可由 AI 在已授权范围内运行，不等于新增的人类批准。人工 ACCEPTED 仍只能记录真实反馈；集中交付草稿和继续生成其他已授权任务都不要求先伪造接受。

## 有效需求包与边界

资料一次上传时，在首次建包分析中就拆出产品特征、规格和卖点，不等到构建 A+ 才重新分析。初始化脚本只建目录和空记录；真正的数据拆解由 AI 结合原图和资料完成。复用 `product.facts[]` 将复合描述拆成可独立核实的条目，原文、来源位置、依据和未确认项留在 intake 档案。卖点原文不等于已验证性能；物理特征与使用收益分别核实，只有有依据的条目标为 SUPPORTED。后续资料更新只修订受影响事实。

表达方式在逐图规划时选择，不在建包时固定构图。任务的 `required_fact_ids` 只列本图确实用于视觉表达或必需选择/操作信息的事实；`must_show` 写可观察的内容。文案项的 `required_fact_ids` 单独列该句的事实依据。仅用于文字的卖点不再同时塞进任务的视觉依赖、`must_show` 或场景说明。可选的 `sales_task` 说明本图要传达的产品价值，不把它写成所有卖点都必须画出的命令。导入时视觉依赖解析进现有 `image_intent.product_facts`，文案依赖仅用于核实文案，不成为额外视觉指令。

同一张图允许一部分卖点自然关联画面，另一部分仅用文字排版；不要求所有卖点都视觉化，也不默认所有图片无字。无法可靠视觉化时用已确认的文案表达，不强加特效或动作。文字同样需要依据，不能用排版绕过声明或操作证据要求。没有文案且任务确实需要说明时，只有已获文案创作授权才能拟写，否则保留缺口，不能默默交成无说明的纯照片。复用已有字段和任务清单，不另建卖点数据库或表达状态机。

本次 A+ 交付仅 1464×600。原表中的手机版、旧画布和未选语言仍留档，不自动增加输出、子图或语言分版。生产前依据当前任务/市场选一种交付语言；仍无法确定且影响出图时只解决这一范围问题，不默认同时制作所有版本。脚本导入会拒绝混合语言的生产包；档案导出仍可保留尚待选择的原文版本。

先分清内容组和图片任务。原表的七个 A+ 模块是七组内容职责，不能直接写成七个 image_id 并视为七张照片。新解析用 `content_groups[]` 保存组级信息（`group_id`、`role`、`buyer_question`、`must_show`、事实依赖、证据 ID 和文案），`modules[]` 只保存实际拆出的逐图任务；有内容组时每张任务用 `content_group_id` 关联所属组。组级文案按语义分配到相关子图，不给每张都重复整组文案。

`job.scope` 记录 `full_set`、`pilot` 或 `single`，`job.target_image_count` 记录本次选定的输出总张数；范围来自用户当前任务，不从标题数量推断。建包时保留用户已给数量；完整套图尚未指定总数时不在资料分析阶段写死，交给套图规划按任务选择（完整 A+ 通常 13 张）。小样和单张任务不扩张。组数、逐图数、缺证据数量和是否完成拆图直接由现有记录计算，不持久化额外的 image_plan/就绪状态。执行入口核对目标与实际子图数及分组覆盖；七个标题不能直接作为七张的完成依据。若一个组需要两到三张，应分别明确各图职责、不同的视觉证明和文案分配。图片可使用卖点设计、比较、步骤、相关细节区或完整场景，独立文件不等于纯照片。

区分“分析说明语言”“设计语言”和“画面文案语言”。分析可用中文，画面原文不能因此翻译、改写或变成中文。默认保留提交文案的语言和完整原文；德语保留德语，英文保留英文，标点、数字、单位、变音符和原有换行均保留。表内多语言按语义关联同一模块并分别保存，不拼进同一张图。目标语言已指定时选对应原文，未指定且只有一种文案语言时沿用；多语并存时保留各语言版本，不擅自固定英文，也不为分析步骤额外提问。后续以当前市场/版本依据选用，不把翻译解释当成原文。

新解析档案使用 copy_policy_version: 1，每条有效文案保留 source_text、source_language，并使 text、language 默认与之逐字相同。仅真实用户授权翻译/改写时才标记 translation_authorized；不能为自动流程自行捏造授权。中文释义放在内部说明，不进入 copy.text。没有原文的模块不能从中文任务说明自动造出一句画面文案。某条原文因声明依据不足而暂不用于画面时，保留原文和暂缓原因，不能默默降级改写。

解析时保存一份内部 intake JSON，包含 job、product、audience、brand_rules、modules；原表位置、参考图、旧样式、冲突和取舍可以作为额外字段留在这份解析档案。`scripts/export_design_brief.py` 只导出允许字段，过滤未支持事实、非当前文案、非当前强制品牌规则，并将依赖缺失事实的模块单独列为 deferred_modules。暂缓模块仍保留 role、buyer_question 与暂缓原因，不能连其职责也丢掉；可以规划说明语言，但不填造参数或动作。脚本不做语义理解，也不证明被标为 SUPPORTED 的内容就是真的；依据仍由 AI 对照真实资料核实。

独立设计环节以有效需求包为入口，使用当前图的 image_intent.module_role 与原有模块语言解析确定功能语言；随后形成每图 creative_brief。分析展示含“任务→语言原则”，设计输出含“具体视觉手法→图文关系→可观察的验收条件”，两者不能互相冒充。不同生活场景也要形成与活动相符的动静、视距和叙事关系，不能只换人和地点重复海报。缺少原始证据的任务保留未就绪状态；语言方案并不代表可以生成。

```text
python3 scripts/export_design_brief.py /absolute/path/intake.json --output /absolute/path/DESIGN_INPUT.json
```

最小结构：

```json
{
  "schema_version": 1,
  "copy_policy_version": 1,
  "job": {"channel": "PREMIUM_A_PLUS", "scope": "single", "target_image_count": 1, "language": "source", "width": 1464, "height": 600},
  "product": {
    "name": "当前售卖产品", "sellable_scope": "已明确的售卖范围",
    "facts": [
      {"fact_id": "material", "text": "已有资料支持的材质", "status": "SUPPORTED"},
      {"fact_id": "comfort", "text": "已有资料确认的柔软舒适特点", "status": "SUPPORTED"}
    ]
  },
  "audience": "当前明确或合理拟定的受众",
  "brand_rules": [],
  "modules": [{
    "image_id": "detail-01", "role": "material",
    "sales_task": "通过实际材质细节与指定文案介绍产品特点",
    "buyer_question": "材质的实际纹理是什么？",
    "must_show": ["可读的真实织纹和产品关系"],
    "required_fact_ids": ["material"], "product_evidence_ids": ["registered-photo-01"],
    "copy": [{"text": "Soft & Comfortable", "language": "en", "source_text": "Soft & Comfortable", "source_language": "en", "status": "CURRENT", "required_fact_ids": ["comfort"]}]
  }]
}
```

文案项使用 `{text, language, source_text, source_language, status: CURRENT, required_fact_ids: []}`；脚本只传最终选用的 text 和 language，原文对照与来源保存在解析档案。job.language 缺省为 source，表示不替原文指定新语言；多语版本仍需分别组织，不能混排。强制品牌项使用 `{text, status: CURRENT_REQUIRED}`。产品图片通过登记的证据 ID 单独解析，不把原表、竞品成品或不明来源图片当作证据。不能以隐藏字段、文件名、否定句或参考元素摘要将旧样式传回设计。自由文本的语义泄漏需要内部检查，字段白名单不能自动识别所有换一种说法的旧构图。

隔离依赖实际执行环境：设计调用不继承解析历史、不接收原表附件，并只允许读取交接资料及选中的产品证据。导出一个文件或在同一对话换角色不等于重置上下文。支持独立调用的环境自动交接；若网页环境只有同一对话，不能冒称隔离。需要严格隔离时一次说明需要把有效需求包与产品原图交给独立设计对话，不要求每张图都换对话。若用户选择同一对话方便测试，记录为有限隔离，继续已授权任务。

## 单图纠正与测试

反馈如“第 3 张扣具不对”“第 5 张太乱”时，先从任务清单定位 ID。复用产品证据、共同视觉规则和这张的职责，AI 自行选择纠正手法；不要重新确认全套方案。布局/文字问题处理当前图，结构错误回到原始证据重新生成。每张保留原候选，沿用一次初稿加最多两次修正；到限后交付现状并指出所缺资料，不无限重试。改变固定构图或文案需自动建立受影响任务的新修订，不偷改已冻结记录；未受影响图片继续保留。

真实测试记录：用户输入/续发/确认次数及原因、从输入到出图的等待、各模块是否独立完成、需要纠正的图片与轮次、最终实际反馈。足够资料的已授权任务，以不额外确认即可交付候选为目标；不要把未知事实留到出图后再编造。结构/文案/审美分别记，不用脚本通过替代实图测试。每次实测只改出现问题的环节，避免增加一轮新的必经确认。


## Automatic execution strategy

AI selects a working strategy from the actual input, then records it on the current image task as `execution_policy`. This is natural-language conditional reasoning, not a code hierarchy, photo-count threshold or another conversation-summary document. Separate this strategy from `PHOTO_EVIDENCE` / `MODEL_ASSISTED` source types and from standard/expanded image quantities. It also does not implement the separate proposed PRECISION/EVIDENCE_SCOPED evidence-mode design.

- **ADVANCED / 高级执行**: requirements are clear and the current task has sufficient relevant evidence. Carry out the supplied roles, exact wording, selection/use information and image relationships faithfully. AI chooses unspecified design details within those boundaries. More files do not justify this mode if they are unclear, redundant or unrelated.
- **AI_ASSISTED / AI 辅助补全**: requirements or useful input are incomplete. AI actively proposes the missing planning, composition, style, scenes and authorized copy, using the supported product identity. Distinguish proposals from confirmed facts; record uncertain product interpretations in gaps rather than production facts. Do not fill missing structure, dimensions, material, performance or operating states with invented evidence.

Choose automatically within the authorized task; do not ask the user to select a mode or approve routine design choices. Assess actual image coverage/clarity and requirement completeness, not 6 versus 16 uploads. A rich design-department package normally supports ADVANCED, while sparse/vague input normally calls for AI_ASSISTED; these are examples, not automatic rules. A clear requirement document can coexist with missing structural evidence. Preserve that requirement, mark only its affected task pending, and continue supported tasks.

First identify which document clauses are requirements and which are suggestions, and each image's evidence/pose/style/old-output role. Preserve provided copy exactly unless an actual rewrite/translation authorization exists. AI_ASSISTED adds to unspecified creative areas; it cannot replace a required installation task with an unrelated beauty shot. Unsupported supplied claims stay visible as gaps; the source document alone does not prove their truth.

Keep the input assessment in the existing module/spec, or in a standalone contract. A chosen decision has:

```json
{
  "execution_policy": {
    "mode": "AI_ASSISTED",
    "reason": "The current task has adequate identity evidence but no supplied scene or image copy; those creative choices were delegated.",
    "requirements": "PARTIAL",
    "evidence": "SUFFICIENT",
    "readiness": "READY",
    "allowed_completion": ["scene", "composition", "copy"],
    "copy_origin": "AI_PROPOSED"
  }
}
```

The reason must describe the current input and task. `requirements` is CLEAR/PARTIAL/UNSPECIFIED; `evidence` is SUFFICIENT/PARTIAL/INSUFFICIENT for the requested task; `readiness` is READY/NEEDS_EVIDENCE/REPLAN. Optional `minimum_mode: ADVANCED` preserves an explicit user minimum: keep it pending when conditions are missing instead of downgrading. `copy_origin: PROVIDED` prevents adding copy to `allowed_completion` unless actual rewrite authority is recorded as `copy_rewrite_authorized: true`. Other completion areas are planning/composition/style/scene. These fields select a strategy and boundary, not a visual-accuracy certificate.

Mode and readiness are separate. AI_ASSISTED may be READY for supported appearance with AI-planned styling, but not for a required unseen mechanism. ADVANCED with an explicit minimum can remain NEEDS_EVIDENCE until its conditions are met. Neither mode bypasses current evidence, structure locks, claims, crop/QA or human-decision requirements. Unclear identity remains intake/planning work under the existing evidence rules.

New script-generated tasks start UNRESOLVED: AI must fill their input assessment before approval/preflight. Exported/imported image tasks preserve a supplied `execution_policy`; omitted decisions still need analysis. Scripts validate the decision's consistency, forward the selected strategy into generation and review state, and block non-READY tasks. They do not inspect photos to select the mode. Individual tasks in one set may use different modes.

When the user supplies clearer requirements/photos, reassess only affected tasks. Update unproduced drafts; use existing revisions for approved tasks or candidate-bound contracts. Keep old decisions/reviews pinned to their inputs. A new mode does not clear a failure, reset retries or upgrade historical acceptance. Web execution follows the same assessment in existing task records without claiming code was run.
