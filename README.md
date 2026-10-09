# Buildify Bundle Dev Skill

开发 Buildify 工作流 Bundle（fat JAR 节点包）的 Agent 技能：生成骨架、写节点与表单、校验、打包发布。

安装后的目录名是 `buildify-bundle-dev`（以 `SKILL.md` 的 `name` 为准），不要用仓库名 `buildify-bundle-dev-skill`。

## 安装

把 [INSTALL.md](INSTALL.md) 交给 Agent，它会克隆或更新到当前 Agent 的 skills 目录。Cursor 默认是 `~/.cursor/skills/buildify-bundle-dev`。

安装或更新完成后，重启 Agent 或新开对话，技能才会被识别。

## 做什么

开发 Bundle 时读 [SKILL.md](SKILL.md)，不要一次读完所有参考文档。

| 场景 | 入口 |
|---|---|
| 新建 Bundle | `scripts/scaffold_bundle.py` |
| 对接三方 HTTP API | `--generic-api ApiCall`，见 [reference/generic-api.md](reference/generic-api.md) |
| 写节点 | [coding-rules.md](coding-rules.md) |
| 写表单 | [reference/forms-schema.md](reference/forms-schema.md) |
| 校验 | `scripts/validate_bundle.py --strict`，0 ERROR 后再 `mvn -q clean package` |
| 发布 | [reference/publishing.md](reference/publishing.md) |

环境：Python 3.8+、JDK 21+、Maven 3.8+。

```bash
python3 scripts/scaffold_bundle.py \
  --dir ./my-bundle \
  --group-id com.example --artifact-id my-bundle \
  --bundle-name example/my-bundle --package com.example.bundle \
  --node MyNode

python3 scripts/validate_bundle.py ./my-bundle --strict
```

对接三方 HTTP 时加上 `--credential MyApiCredential --generic-api ApiCall`。文档里还没有专用节点的接口，用这个通用节点按文档填写 `method`、`path`、`query`、`headers`、`body`。

## 目录

```
SKILL.md                 # 技能入口
INSTALL.md               # 安装说明
coding-rules.md          # 节点编码规范
scripts/                 # scaffold_bundle.py、validate_bundle.py
templates/               # 工程、Java、表单模板
reference/               # 表单、API、生命周期、发布
```
