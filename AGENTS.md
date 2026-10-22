# 技能仓库

本仓库管理三个产品图片技能和 weekly-work-report 的源码、参考说明、测试及选定 UML/验证记录。系统自带技能、产品测试资料、缓存和安装 ZIP 不纳入版本控制。

## 修改与记录

- 修改前查看 `git status --short` 和涉及文件的差异，确认当前基线，不凭对话记忆推断文件状态。
- 用户授权的每轮修改完成后，执行与改动相关的检查，更新根目录 `CHANGELOG.md`，并做一次本地提交。提交说明写清具体变化；未做实图验证时不能写成视觉效果已通过。
- 只暂存本轮涉及的修改，保留其他任务或用户的未提交工作；同一文件混有既有修改时先检查差异，避免将无关改动一并提交。
- 用户要求安装包时，从当前源码更新包并核对一致性；安装压缩包统一输出到根目录 `dist/`，只跟踪 `dist/.gitkeep`，包文件留在本地交付。`dist/` 不放解压后的 `SKILL.md` 或技能副本。
- 用户已授权绑定远程 `origin`：`https://github.com/LXE123/HYT-image-skill.git`。日常修改仍先做本地提交；fetch/pull/push 和远程 PR 按用户明确授权执行，不因绑定远程而自动同步。
- Git 历史从首次基线提交开始。初始化前的版本只按已核实事实记录在变更说明中，不倒填为历史提交。

## 检查入口

- 产品图片技能的脚本行为变更：`python3 -B -m unittest discover -s product-amazon-image-set-generator/scripts/tests -p 'test_*.py'`。
- 周报归档脚本变更：`python3 -B -m unittest discover -s weekly-work-report/scripts -p 'test_*.py'`。
- 说明文档变更检查引用路径和规则一致性；技能入口变更按 skill-creator 的校验流程检查。只修改记录或忽略规则无需重跑无关业务测试。
