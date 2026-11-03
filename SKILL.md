---
name: buildify-bundle-dev
description: >-
  Scaffolds, implements, reviews and validates Buildify workflow Bundles (fat JAR
  node packs): FlowNode, MethodExecutor, CredentialsProvider, bundle.json,
  properties forms, SPI registration and publishing. Use when the user develops,
  debugs, reviews or publishes a Buildify bundle; mentions FlowNode, bundle.json,
  @FlowNodeDescription, buildify-bundle-api, credentialsType, MethodExecutor,
  trigger, webhook or credential; or talks about 节点开发, 工作流节点, 动态表单, 凭证,
  触发器, Webhook, 验签, 回调, 微信支付, 支付宝, Stripe or 发布 Bundle.
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
- [ ] 6. 编写 docs.md（平台用户使用文档：用户查看 + 编排 Agent 用节点）与 CHANGELOG.md
- [ ] 7. 校验 → 修复 → 重跑，直到 0 ERROR
- [ ] 8. mvn clean package
- [ ] 9. 检查源码仓库：没有 git 仓库或远程地址时，提示用户提供仓库地址
```

**步骤 7（必须形成闭环）**：执行下方 `validate_bundle.py --strict`；有 ERROR 则按输出定位、
修复后重跑；0 ERROR 后再 `mvn -q clean package`。提交前对照
[reference/checklist.md](reference/checklist.md)（含需人工确认的 🔍 项）。

**步骤 9（开发完成必做）**：执行 `git -C <bundle> rev-parse --is-inside-work-tree` 和
`git -C <bundle> remote -v`。不是仓库或没有远程时，告诉用户“这个 Bundle 还没有源码仓库”，
请他提供地址（GitHub / Gitee / GitLab），说明好处：版本可回滚、可协作、发布版本能对应到提交。
拿到地址后初始化、补 `.gitignore`、提交并推送；用户不提供就只提醒一次，不阻塞发布，
不要自己创建远程仓库。细节见 [reference/publishing.md](reference/publishing.md#源码版本管理)。

**发布时**：只同步用户使用文档 `docs.md`，不要同步 `README.md`。用户在软件包页查看，编排 Agent 用 `bundle doc` 阅读后编排节点。
按本版本更新：适用、凭证类型、每个节点的何时使用 / 参数 / 输出路径 / 出口、错误码；不要写项目结构、
构建、ClassLoader。校验通过后，在 `bundle upload` **之前** `bundle doc set --file docs.md` 并
`bundle doc get` 确认，再上传 JAR。发布时核对 `bundle.json` 的图标名是否已在 `bundle icons` 里，没有的才创建。章节约定见 [reference/publishing.md](reference/publishing.md#docsmd每个-bundle-必须)。

**软件名称与软件描述**（控制台字段，对应 `--display-name` / `--summary`）：编排 Agent 只靠
`bundle list -k` 命中后再读这两项决定用哪个包。建包前先 `bundle namespaces`，优先用已有命名空间，用户选择新建才 `namespace create`。再按已有节点起草，用确认表列出命名空间、名称、描述、
搜包关键词、能覆盖 / 不覆盖，等用户确认再 `bundle create`。名称写「官方中文名 + 能力」
（如「钉钉群机器人」）；描述固定句式：对接对象（含英文名）→ 按节点列出的动作 → 典型场景 →
与相近包的边界（「不含 xxx，请用「yyy」」）。规范、确认表和正反例见
[reference/publishing.md](reference/publishing.md#软件名称与软件描述)。

### 按任务读取（勿一次全读）

| 场景 | 读 / 做 |
|---|---|
| **新建 Bundle** | 执行下方 `scaffold_bundle.py` |
| **对接三方 HTTP API** | 加 `--generic-api ApiCall`，见 [reference/generic-api.md](reference/generic-api.md) |
| **已有项目加节点** | 勿重跑 scaffold；复制 `templates/java/`、`templates/forms/`，并补 SPI；项目里没有 `support/HttpErrors.java`（加触发器时还有 `support/TriggerGuard.java`）时一并复制 |
| **实现 / 审查节点代码** | [coding-rules.md](coding-rules.md) |
| **写 / 改表单 schema** | [reference/forms-schema.md](reference/forms-schema.md) |
| **查某 uiComponent 的 typeOptions** | [reference/forms-components.md](reference/forms-components.md) |
| **查 API** | [reference/api.md](reference/api.md) |
| **节点间 RPC** | [reference/node-service-rpc.md](reference/node-service-rpc.md) |
| **热更新 / ClassLoader 泄漏** | [reference/lifecycle.md](reference/lifecycle.md) |
| **写触发器 / 防背压** | [reference/backpressure.md](reference/backpressure.md)（限流、有界缓冲、429、MQ nack） |
| **按原文验签的回调** | 先确认对不上 `WebhookTriggerNode` 的 `authType`，再读 [coding-rules.md](coding-rules.md)「按原文验签的回调触发器」。不要套通用 Webhook 模板 |
| **写用户使用文档** | [reference/publishing.md](reference/publishing.md#docsmd每个-bundle-必须)（`docs.md`；用户查看 + 编排 Agent 用节点） |
| **发布** | [reference/publishing.md](reference/publishing.md) |

## 工具脚本（执行，勿读源码）

环境：Python 3.8+、JDK 21+、Maven 3.8+。

脚本在 **skill 根目录**的 `scripts/`（与 `SKILL.md` 同级），**不是** Bundle 项目目录。
先解析 skill 根，再拼路径：

- 本仓库项目级：`.cursor/skills/buildify-bundle-dev`
- 全局安装：`~/.cursor/skills/buildify-bundle-dev`

**scaffold_bundle.py** — 生成完整 Bundle 骨架（含 SPI、使用文档、README、CHANGELOG、`.gitignore`）：

```bash
python3 <skill-root>/scripts/scaffold_bundle.py \
  --dir ./my-bundle \
  --group-id com.example --artifact-id my-bundle \
  --bundle-name example/my-bundle --package com.example.bundle \
  --node MyNode
```

可重复：`--node` / `--trigger` / `--webhook` / `--credential PascalCase` /
`--method ClassName:methodName` / `--generic-api ApiCall`。至少提供一个节点类选项。
`--error-prefix DINGTALK` 指定错误码前缀（默认由 `artifactId` 推导，`bundle-dingtalk-bot` → `DINGTALK_BOT`）。
对接三方 HTTP 时加上 `--generic-api`（类名以 `ApiCall` 结尾，且要有 `--credential`）：
文档里还没有专用节点的接口，Agent 用这个节点按文档填 `method` / `path` / `query` / `headers` / `body`。

**validate_bundle.py** — 校验命名、SPI、pom、表单、凭证、complete、RPC、资源泄漏、
参数变更后的重启 / `onParametersUpdated` 热更新；
`bundle.json` 节点缺 `icon`（默认应为 `"default.svg"`）、自定义 `icon` 在 `icons/` 下没有同名文件、
`icons/` 下有没人引用的图片、使用文档漏列节点或凭证类型、使用文档写入了开发内容、`bundleName` 不符合平台命名规则，
触发器用了无界队列 / 无界线程池、在循环里直接 `tell*`、用 `tellSuccess` 而不是 `tryTellSuccess`、没有任何限流，
以及 resources 下的 SVG 记 WARNING（图标放 `icons/`，发布时平台还没有才上传，不要打进 JAR）：

```bash
python3 <skill-root>/scripts/validate_bundle.py ./my-bundle           # ERROR 时 exit 1
python3 <skill-root>/scripts/validate_bundle.py ./my-bundle --strict  # WARNING 也失败
```

## 项目骨架要点

```
my-bundle/
├── pom.xml                          # buildify-bundle-api scope=provided；release=21；shade+SPI transformer
├── docs.md                      # 平台用户使用文档，发布时 doc set 同步；README.md 不上传
├── README.md / CHANGELOG.md        # README 给开发者；CHANGELOG 给 releaseNote
├── icons/                           # cover.* 仅创建时作封面；节点图标发布时缺了才上传；不打进 JAR
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

1. `JsonValue` 读字段用 `path()`，不用 `get()`；也不要用 `Objects.requireNonNull` 做参数校验
2. 同步路径在 `onMsg` 返回前 `tell*` 即可，框架自动 `complete`；异步路径必须对入站 `message` 调用 `context.complete()`。触发器的新消息不在 `onMsg` 内，必须且只 `complete` 一次（用于统计触发器的执行次数与耗时，重复调用会重复计数）；特殊触发器可按说明调整调用位置，但不能省略
3. 在 `onMsg` 中求值的字段默认 `expression: true` + `droppable: true`（能否切换到表达式）。只在 `initialize()` 读取的参数（超时、cron、路由路径）不开。访问凭证和 `CodeEditor` 也除外：`CodeEditor` 设了会和编辑器交互冲突，只用 `typeOptions.enableExpression`；`lang` 为 `json` 时优先改用 `JsonExpressionInput`。代码侧 `dynamicParameters` + `resolveExpressions`。
   `JsonExpressionInput` 可能整字段就是 `={{msg.name}}`（文本，不是 JSON）：原样放入，**不要** `fromJson`；
   求值后按实际类型处理，文本不要直接 `toJson()` 当请求体
4. 普通节点输出放 `output`；触发器 payload 放根级，并带 `triggerNodeId`、`eventId`、`workerId`
5. 凭证类型 PascalCase；`credentialsType` 三处一致；`getCredentials` 用表单字段 `name`
6. 已知错误用 `FlowNodeException`，`initialize` 参数校验优先用 SDK 的 `Validator`。接口调用失败（HTTP 非 2xx 或业务码非 0）时用脚手架生成的 `HttpErrors.httpError` / `apiError`，把 `statusCode` 和脱敏后的 `body` 放进 `msg.error.metadata`；代码中的错误码都要写进使用文档「错误码」一节。触发器遵守
   `isTest()` / `createTriggerMessage(payload, eventId)` / `complete`（位置可按说明调整）/ `destroy()`。`eventId` 同时写入 payload，
   `triggerNodeId` 取 `getWorkflowNodeId()`，`workerId` 取 `getWorkerId()`
7. 发布时核对 `bundle.json` 的 `icon` 是否已在 `bundle icons` 中。已有的不覆盖；没有的才创建：本地 `icons/` 有同名文件就上传，否则用 [Devicons API](https://devicons.io/docs/api/) 查找（只接受名称完全匹配的结果）。找不到就把该节点改成 `default.svg`（`https://bundles.buildify.cn/icons/default.svg`），并告诉用户稍后在控制台替换。不要自己画。封面只在 `bundle create --icon` 时上传。文件名与 `icon` 值逐字一致（`icons/DingTalk.svg` ↔ `"icon": "DingTalk.svg"`），不打进 JAR、不放 `src/main/resources`，见
   [reference/publishing.md](reference/publishing.md#命名与图标)
8. 需要人逐项填写的数组用 `FixedCollection`（可增删），不要用 `JsonEditor` 手写 JSON 数组
9. 参数变更要么 `isRestartRequired` 返回 `true` 并重启，要么 `onParametersUpdated` 用新参数重新赋值。路由、cron、连接必须重启
10. 对接三方 HTTP API 时提供以 `ApiCall` 结尾的通用调用节点。未实现的接口按厂商文档填写，不要为每个接口新做节点。这类接口节点不要 `setStatus`（不要显示「就绪」）；状态只留给触发器和长连接
11. 触发器必须做背压：发消息用 `tryTellSuccess`（`tellSuccess` 在下游过载时会被引擎丢弃，触发器感知不到），
    用脚手架生成的 `support/TriggerGuard` 读取表单 `maxPerSecond`（默认 `0` 不限速）、防止轮询重叠；只用有界缓冲。
    超限时推送型丢弃计数（节点状态黄色）、拉取型跳过本轮或暂停消费、Webhook 返回 429 + `Retry-After`、MQ nack。
    需要 bundle-api 3.1.0 和对应 Worker，见 [reference/backpressure.md](reference/backpressure.md)
12. 接口认证先用核心包 `WebhookTriggerNode` 已有的 `authType`（`none` / `httpBasic` / `apiKey` / `jwtAuth`）。只有按原文验签、对不上这些方式时（微信支付、支付宝、Stripe 等），才做成该渠道自己的触发器：`Route.create`，`request().body()` 保留原文后再验签。验签失败按官方文档直接返回。返回要同时支持按文档直接写回，以及处理完后把 eventId 设为 `getRequestId()`、由核心包 `WebhookResponseNode` 写回。不要做成下游验签节点，也不要套通用 Webhook 模板。见 [coding-rules.md](coding-rules.md)「按原文验签的回调触发器」

## 代码模板

占位符 `{{PACKAGE}}`、`{{NODE_NAME}}` 等：

| 目录 | 内容 |
|---|---|
| `templates/project/` | `pom.xml`、`bundle.json`、使用文档 / README / CHANGELOG 骨架 |
| `templates/java/` | Node / GenericApiNode / Trigger / Webhook / CredentialsProvider / MethodExecutor，以及接口失败处理 `HttpErrors`、触发器背压 `TriggerGuard`（生成到 `support/`） |
| `templates/forms/` | 节点 / 通用调用 / 触发器 / Webhook / 凭证 properties JSON |
