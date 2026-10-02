---
name: buildify-bundle-dev
description: >-
  Scaffolds, implements, reviews and validates Buildify workflow Bundles (fat JAR
  node packs): FlowNode, MethodExecutor, CredentialsProvider, bundle.json,
  properties forms, SPI registration and publishing. Use when the user develops,
  debugs, reviews or publishes a Buildify bundle; mentions FlowNode, bundle.json,
  @FlowNodeDescription, buildify-bundle-api, credentialsType, MethodExecutor,
  trigger, webhook or credential; or talks about 节点开发, 工作流节点, 动态表单, 凭证,
  触发器, Webhook or 发布 Bundle.
---

# Buildify Bundle 开发

Bundle 是 Buildify 工作流引擎的节点包（fat JAR），由独立 `BundleClassLoader` 加载。

本 skill 目录内的文档是 Bundle 开发的**唯一权威来源**。不要去读仓库里的
`docs/spec/dev-spec.md`、`spec/bundle-spec/bundle-development-spec.md` 等旧文档
（其中 `credentialsName` 已废弃，以本 skill 的 `credentialsType` 为准）。

## 工作流

复制清单并逐项勾选：

```
Bundle 开发进度：
- [ ] 1. 生成/确认骨架（scaffold 或 templates/）
- [ ] 2. 编写 bundle.json 与 properties 表单
- [ ] 3. 实现 FlowNode（遵守 coding-rules.md）
- [ ] 4. 按需实现凭证 / MethodExecutor / Node Service
- [ ] 5. 确认 META-INF/services/ 已注册实现类
- [ ] 6. 编写 README.md 与 CHANGELOG.md
- [ ] 7. 校验 → 修复 → 重跑，直到 0 ERROR
- [ ] 8. mvn clean package
```

**步骤 7（必须形成闭环）**：执行下方 `validate_bundle.py --strict`；有 ERROR 则按输出定位、
修复后重跑；0 ERROR 后再 `mvn -q clean package`。提交前对照
[reference/checklist.md](reference/checklist.md)（含需人工确认的 🔍 项）。

### 按任务读取（勿一次全读）

| 场景 | 读 / 做 |
|---|---|
| **新建 Bundle** | 执行下方 `scaffold_bundle.py` |
| **已有项目加节点** | 勿重跑 scaffold；复制 `templates/java/`、`templates/forms/`，并补 SPI |
| **实现 / 审查节点代码** | [coding-rules.md](coding-rules.md) |
| **写 / 改表单 schema** | [reference/forms-schema.md](reference/forms-schema.md) |
| **查某 uiComponent 的 typeOptions** | [reference/forms-components.md](reference/forms-components.md) |
| **查 API** | [reference/api.md](reference/api.md) |
| **节点间 RPC** | [reference/node-service-rpc.md](reference/node-service-rpc.md) |
| **热更新 / ClassLoader 泄漏** | [reference/lifecycle.md](reference/lifecycle.md) |
| **发布** | [reference/publishing.md](reference/publishing.md) |

## 工具脚本（执行，勿读源码）

环境：Python 3.8+、JDK 21+、Maven 3.8+。

脚本在 **skill 根目录**的 `scripts/`（与 `SKILL.md` 同级），**不是** Bundle 项目目录。
先解析 skill 根，再拼路径：

- 本仓库项目级：`.cursor/skills/buildify-bundle-dev`
- 全局安装：`~/.cursor/skills/buildify-bundle-dev`

**scaffold_bundle.py** — 生成完整 Bundle 骨架（含 SPI、README、CHANGELOG）：

```bash
python3 <skill-root>/scripts/scaffold_bundle.py \
  --dir ./my-bundle \
  --group-id com.example --artifact-id my-bundle \
  --bundle-name example/my-bundle --package com.example.bundle \
  --node MyNode
```

可重复：`--node` / `--trigger` / `--webhook` / `--credential PascalCase` /
`--method ClassName:methodName`。至少提供一个节点类选项。

**validate_bundle.py** — 校验命名、SPI、pom、表单、凭证、complete、RPC、资源泄漏；
`bundle.json` 中的 `icon` 与 resources 下的 SVG 记 WARNING（图标由平台上传管理）：

```bash
python3 <skill-root>/scripts/validate_bundle.py ./my-bundle           # ERROR 时 exit 1
python3 <skill-root>/scripts/validate_bundle.py ./my-bundle --strict  # WARNING 也失败
```

## 项目骨架要点

```
my-bundle/
├── pom.xml                          # buildify-bundle-api scope=provided；release=21；shade+SPI transformer
├── README.md / CHANGELOG.md         # 必须
└── src/main/
    ├── java/.../nodes|methods|credentials/
    └── resources/
        ├── bundle.json
        ├── properties/*.json
        ├── credentials/*.json
        └── META-INF/services/
```

Maven 依赖：`cn.buildify:buildify-bundle-api`（版本见 `templates/project/pom.xml`），`scope=provided`。

## 编码规范（摘要）

完整示例见 [coding-rules.md](coding-rules.md)：

1. 参数读 `path()`，不用 `get()`
2. 同步路径在 `onMsg` 返回前 `tell*` 即可，框架自动 `complete`；异步路径必须对入站 `message` 调用 `context.complete()`
3. 表达式参数：`dynamicParameters` + `resolveExpressions`
4. 普通节点输出放 `output`；触发器 payload 放根级
5. 凭证类型 PascalCase；`credentialsType` 三处一致；`getCredentials` 用表单字段 `name`
6. 已知错误用 `FlowNodeException`（含 `initialize` 参数校验）；触发器遵守
   `isTest()` / `createTriggerMessage` / `destroy()`
7. **不要生成 SVG 图标**，也不要在 `bundle.json` 写 `icon`。节点图标由平台上传管理，
   不打进 JAR、不放在 `src/main/resources`

## 代码模板

占位符 `{{PACKAGE}}`、`{{NODE_NAME}}` 等：

| 目录 | 内容 |
|---|---|
| `templates/project/` | `pom.xml`、`bundle.json`、README / CHANGELOG 骨架 |
| `templates/java/` | Node / Trigger / Webhook / CredentialsProvider / MethodExecutor |
| `templates/forms/` | 节点 / 触发器 / Webhook / 凭证 properties JSON |
