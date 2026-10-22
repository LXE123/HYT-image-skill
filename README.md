# HYT-image-skill

产品图片工作流技能及工作汇报归档技能的源码仓库。

## 目录

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

`deliverables/` 只跟踪 `.gitignore` 中选定的 UML 和验证记录，其余实验资料保留在本地。

## 安装包与技能读取

安装压缩包统一放入 `dist/`；当前合并包为 `dist/product-image-skills.zip`，分包及历史包也位于此目录。包文件不提交 Git，不随源码推送。

技能源码保留在上面的四个目录中。`dist/` 只存压缩包和占位文件，不在其中解压或复制 `SKILL.md`，避免产生额外的技能入口。Git 忽略规则只控制版本跟踪，不能用来禁止技能发现。

需要重新打包时，以当前源码为准，输出到 `dist/` 并核对包内文件与源码一致；修改和提交流程见 [AGENTS.md](AGENTS.md)。
