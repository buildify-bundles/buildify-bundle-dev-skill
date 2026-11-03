# Bundle 编码硬性规范

七条通用规范 + 触发器四条 + 命名一致性表。表单与 API 细节见 `reference/`。

## 目录

- [规范 1：读参数用 path()](#规范-1读参数用-path绝不用-get)
- [规范 2：异步路径必须 complete](#规范-2异步路径必须-contextcomplete同步路径框架自动收尾)
- [规范 3：dynamicParameters + resolveExpressions](#规范-3dynamicparameters--resolveexpressions)
- [规范 4：普通节点输出放 output](#规范-4普通节点输出放-output触发器放根级)
- [规范 5：凭证标识 PascalCase](#规范-5凭证标识-pascalcase三处逐字一致)
- [规范 6：已知错误用 FlowNodeException](#规范-6已知错误用-flownodeexception)
- [规范 7：参数变更必须重启或热更新](#规范-7参数变更必须重启或热更新)
- [节点状态](#节点状态)
- [触发器节点四条额外规范](#触发器节点四条额外规范)
- [命名一致性](#命名一致性最常见的低级错误)

## 规范 1：读参数用 `path()`，绝不用 `get()`

`path()` 字段缺失时返回 `MissingNode`；`get()` 返回 `null`，会 NPE。对所有 `JsonValue`
（`parameters`、`newParameters`、`payload`、`path(...)` 链）都一样。必填项为空时抛 / 回
`FlowNodeException`，不要用 `Objects.requireNonNull`。

```java
String url   = parameters.path("url").asText(null);
int timeout  = parameters.path("timeout").asInt(30);
boolean flag = parameters.path("enabled").asBoolean(false);

// initialize() 中的必填 / 范围校验用 Validator，失败抛 FlowNodeException("VALIDATION_ERROR")
int checked = Validator.of(timeout, "timeout").range(1, 300, "timeout 必须在 1~300 秒之间").get();
```

## 规范 2：异步路径必须 `context.complete`，同步路径框架自动收尾

与 `FlowNode` / `Context.complete` 的契约一致（`DefaultContext.endMessageProcessing`）：

- **同步**：在 `onMsg` 返回前已经 `tellSuccess` / `tellNext` / `tellFailure`，且这次
  `onMsg` **没有**调用 `executeBlocking`。框架在 `onMsg` 返回时自动 `complete`，
  **不要**再调。
- **异步**：路由发生在 `onMsg` 返回之后，必须在**每条**结束路径对入站 `message` 调用
  `complete`。`executeBlocking` 会标记异步，框架不再自动收尾；`sendAsync` /
  `whenComplete` / `nodeService().execute()` 的 `tell*` 不在 `onMsg` 线程内，同样不会自动收尾。

```java
// 同步：tell 后直接返回，不要 complete
context.tellSuccess(outMsg);

// executeBlocking：onComplete 统一收尾
context.<String>executeBlocking(() -> doWork())
    .onSuccess(result -> context.tellSuccess(buildMsg(result, message)))
    .onFailure(e -> context.tellFailure(message, e))
    .onComplete(() -> context.complete(message));

// 原生异步：finally 保证必然 complete 入站 message
httpClient.sendAsync(request, BodyHandlers.ofString()).whenComplete((resp, err) -> {
    try {
        if (err != null) context.tellFailure(message, err);
        else context.tellSuccess(buildMsg(resp, message));
    } finally {
        context.complete(message);
    }
});
```

触发器发出的是 `createTriggerMessage` 的新消息，不是 `onMsg` 的入站消息。
框架不会自动收尾，必须对**这条新消息**调用 `context.complete`，**每条消息只调一次**。

对触发器消息，`complete` 只做指标记录：给触发器节点记一次执行（执行次数、QPS），并记录从
`createTriggerMessage` 到 `complete` 的耗时。省略时这些指标恒为 0，试跑面板上触发器的耗时也不准；
下游流程照常执行，不会因此卡住。框架**不去重**，同一条消息调用两次会重复计数，推荐写在 `finally` 里。

普通触发器在 `tellSuccess` / `tellNext` / `tellFailure` 之后立刻调用。特殊触发器按自身说明
把 `complete` 挪到真正结束的位置（例如等待回执、批量刷出、异步回调结束），这样记录的耗时才包含
这段等待，但不能省略。

## 规范 3：`dynamicParameters` + `resolveExpressions`

节点表单里，除访问凭证（`CredentialSelect`）外，可传值字段默认
`"expression": true` 与 `"droppable": true`。`expression` 表示这个控件能否在固定值和
`={{ msg.xxx }}` 之间切换，`SqlEditor` / `JsonEditor` 也一样。
这条默认只适用于放进 `dynamicParameters`、在 `onMsg` 中求值的字段。
只在 `initialize()` / `isRestartRequired()` 中读取的参数（超时、cron、时区、路由路径、连接池大小等）
**不要**开 `expression` / `droppable`：它们在初始化时读一次，`={{ msg.xxx }}` 不会被求值，
`asInt(30)` 之类会静默落回默认值。确实需要按消息变化时，把它放进 `dynamicParameters`。
`CodeEditor` 例外：**不要**设 `expression` / `droppable`，它们和编辑器自身的交互冲突。
`CodeEditor` 是否按表达式存储只由 `typeOptions.enableExpression` 决定（内容是否带 `=` 前缀）。
要编辑的内容是 JSON（`lang: "json"`）时优先改用 `JsonExpressionInput`。
访问凭证和 `credentials/*.json` 不要开 `expression`。

需要人逐项填写的数组（请求头、标签、收件人等）用 `FixedCollection`，值是 JSON 数组，
用 `parameters.path("headers")` 遍历元素。不要用 `JsonEditor` 让用户手写 JSON 数组。

支持表达式的参数在 `initialize()` 存入 `dynamicParameters`，在 `onMsg()` 中按当前消息求值。
文本用 `{{ msg.xxx }}`，JSON（`JsonExpressionInput`）用 `={{ msg.xxx }}`；
SQL（`SqlEditor`）用 `#{msg.xxx}` / `${msg.xxx}`，不要走 `{{ }}`：

```java
public void initialize(Context context, JsonValue parameters) {
    this.timeout = parameters.path("timeout").asInt(30);
    this.dynamicParameters = JsonValueFactory.objectNode()
        .put("url",  parameters.path("url"))
        .put("card", parameters.path("card"));
}

public void onMsg(Context context, Message<?> msg) {
    JsonValue payload    = getPayload(msg, JsonValue.class);
    JsonValue parameters = context.resolveExpressions(dynamicParameters, payload);
    String url = parameters.path("url").asText();
}
```

### JsonExpressionInput：先求值，再按类型处理

`JsonExpressionInput` 字段下发时**不一定是 JSON 对象**。用户可以把整个字段写成一个表达式，
这时它只是一个文本节点 `"={{msg.name}}"`：

| 用户在字段里写 | `parameters.path("body")` 拿到 | `resolveExpressions` 后 |
|---|---|---|
| `{"name": "={{msg.name}}", "age": 1}` | 对象节点 | 对象；`name` 保持 `msg.name` 的原类型 |
| `={{msg.name}}`（整字段） | 文本节点 `"={{msg.name}}"` | `msg.name` 的原类型：字符串、数字、对象都可能 |
| `={{msg.body}}`，而 `msg.body` 本身是 JSON 字符串 | 文本节点 | **文本**节点，内容是 `{"a":1}` 这样的 JSON 文本 |
| `=[{{msg.a}}] {{msg.b}}`（混排） | 文本节点 | 拼接后的字符串 |

只有以 `=` 开头的文本才会求值；`{{msg.name}}` 不带 `=` 会原样保留。

规则：

1. `initialize()` 里**原样** `put(parameters.path("body"))`。不要 `fromJson(...asText())`、`asText()`、
   `toJson()`，也不要断言 `isObject()`。`JsonValueFactory.fromJson("={{msg.name}}")` 会去掉 `=`
   再解析 `{{msg.name}}`，直接抛 `Invalid JSON`，节点启动失败。
2. 只在 `resolveExpressions` 之后按**实际类型**处理：对象 / 数组直接用；数字、布尔保持原类型；
   文本按节点语义决定——需要 JSON 时先尝试 `fromJson`，失败就当普通文本。
3. 文本节点**不要**直接 `toJson()` 当请求体：`{"a":1}` 会被二次转义成 `"{\"a\":1}"`。
4. 表单默认值、使用文档示例里，表达式写在 JSON **字符串值**里：`{"name": "={{msg.name}}"}`。
   不要写成不带引号的 `{"name": ={{msg.name}}}`（不是合法 JSON），也不要再包一层引号
   `"\"={{msg.body}}\""`（求值结果会变成带引号的字符串）。

```java
// initialize()：原样放入，不做任何解析
this.dynamicParameters = JsonValueFactory.objectNode().put("body", parameters.path("body"));

// onMsg()：求值后按类型生成请求体
JsonValue body = context.resolveExpressions(dynamicParameters, payload).path("body");
String requestBody = toRequestBody(body);

private static String toRequestBody(JsonValue body) {
    if (!body.isTextual()) {
        return body.toJson();                  // 对象、数组、数字、布尔
    }
    String text = body.asText();
    try {
        return JsonValueFactory.fromJson(text).toJson();   // 文本本身就是 JSON
    } catch (IllegalArgumentException e) {
        return text;                           // 普通文本，按原样发送
    }
}
```

脚手架生成的 HTTP 节点（`Node.java.tmpl`、`GenericApiNode.java.tmpl`）已按此处理请求体。

## 规范 4：普通节点输出放 `output`，触发器放根级

普通节点把业务结果收敛到 payload 的 `output` 字段，下游用 `{{ msg.output.xxx }}` 引用：

```java
JsonValue out = JsonValueFactory.objectNode()
    .put("output", JsonValueFactory.objectNode()
        .put("statusCode", response.statusCode())
        .put("body", responseBody));
context.tellSuccess(MessageBuilder.withPayload(out)
    .copyHeaders(message.getHeaders()).build());
```

触发器是流程入口，**禁止**再包一层 `output`，业务字段直接放根级，下游用 `{{ msg.xxx }}`：

根级必须带上本次触发的来源字段（在 `initialize()` 取出节点与 Worker，每次触发再生成 `eventId`）：

```java
// ✅ 触发器
String eventId = UUID.randomUUID().toString();
JsonValue payload = JsonValueFactory.objectNode()
    .put("triggerNodeId", triggerNodeId)   // context.getWorkflowNodeId()
    .put("eventId", eventId)               // 本次触发 ID，同时作为追踪 ID
    .put("workerId", workerId)             // context.getWorkerId()，不适用时 null
    .put("cron", cronExpr).put("timestamp", System.currentTimeMillis());
Message<JsonValue> triggered = context.createTriggerMessage(payload, eventId);
try {
    if (!context.tryTellSuccess(triggered)) {  // 下游过载：没有入队，见触发器规范 4
        guard.recordDropped(context);
    }
} finally {
    context.complete(triggered);   // 必须且只调一次：记录触发器的执行次数与耗时。特殊触发器可挪到真正结束处
}

// ❌ 触发器不要包 output
JsonValue bad = JsonValueFactory.objectNode().put("output", payload);
```

`eventId` 与消息头 `__correlationId` 取值相同。宿主不支持多 Worker 时 `workerId` 为 `null`。

文档与表单说明中统一用 `msg` 表示消息 payload，**不要**用 `$json`。

## 规范 5：凭证标识 PascalCase，三处逐字一致

```java
@CredentialsDescription(
    type           = "MysqlCredential",
    label          = "MySQL 数据库",
    propertiesFile = "credentials/MysqlCredential.json")
```

表单引用凭证类型用 `typeOptions.credentialsType`（**不是**已废弃的 `credentialsName`）。
`context.getCredentials(...)` 的入参是**表单字段 `name`**，不是凭证类型标识。
`@CredentialsDescription` 类注释里的 `getCredentials(type)` 示例已过时，以 `Context.getCredentials` 为准：

```json
{ "name": "credentialsId", "uiComponent": "CredentialSelect",
  "typeOptions": { "credentialsType": "MysqlCredential" } }
```

```java
context.getCredentials("credentialsId");        // ✅ 表单字段 name
context.getCredentials("MysqlCredential");      // ❌ 凭证类型标识
```

## 规范 6：已知错误用 `FlowNodeException`

禁止 `throw new RuntimeException(...)` / `IllegalArgumentException(...)`（含 `initialize()`
里的参数校验）。`initialize()` 中的参数校验优先用 SDK 的 `Validator`，失败时自动抛
`FlowNodeException("VALIDATION_ERROR")`（见 `reference/api.md`）。

日志分级：`FlowNodeException`、连接失败 / 超时这类已知错误用 `log.warn`（不打堆栈），
其余未知异常用 `log.error` 保留堆栈。日志前缀统一 `[NodeName]`。禁止把凭证字段写入日志或 payload。

不是 `FlowNodeException` 的异常会被框架包装，`error.code` 变成异常类名（如 `NullPointerException`），
下游无法按错误码分支，所以已知错误一定要结构化。

```java
throw new FlowNodeException("API_ERROR_" + code, "API 调用失败: " + apiMsg)
    .with("code", code).with("message", apiMsg);
```

代码里出现的每个错误码都要写进使用文档的「错误码」一节（含义 + 排查建议），
`validate_bundle.py` 会对照检查。

### 接口调用失败：响应放进 `error.metadata`

调用三方接口拿到了响应、但判定为失败时（HTTP 非 2xx，或业务码如 `errcode` / `code` 非 0），
必须 `tellFailure` 一个 `FlowNodeException`，并用 `with` 带上：

| metadata 键 | 内容 |
|---|---|
| `statusCode` | HTTP 状态码（`int`） |
| `body` | 响应体，能解析成 JSON 时放解析后的 `JsonValue`，否则放 `{ "raw": "<原始文本>" }`，与成功输出的 `body` 同一形态 |

`code` 用 `<厂商>_HTTP_ERROR`（HTTP 非 2xx）或 `<厂商>_API_<业务码>`（HTTP 2xx 但业务失败）。
`message` 先写按状态码分类的中文提示，再附 `响应：<原始响应体>`，响应体过长时截断（约 500 字符）。
响应里的 Token、密钥等字段必须先替换成 `***` 再写入：框架会原样拷贝 `metadata`，不做脱敏。
连接失败、超时等没有响应的错误不写 `statusCode` / `body`。

脚手架会生成 `support/HttpErrors.java`，统一做这几件事，节点里直接调用，不要每个节点各写一份：

| 方法 | 作用 |
|---|---|
| `HttpErrors.PREFIX` | 厂商前缀，由 `--error-prefix` 或 `artifactId` 推导（如 `DINGTALK`） |
| `isSuccess(status)` | 是否 2xx |
| `parseBody(raw)` | 解析响应，非 JSON 时返回 `{ "raw": "..." }` |
| `httpError(status, raw)` | 生成 `<PREFIX>_HTTP_ERROR`，带分类提示、脱敏后的 `statusCode` / `body` |
| `apiError(code, msg, status, body)` | 生成 `<PREFIX>_API_<code>`，同样带 `statusCode` / `body` |
| `hint(status)` / `redact(json)` / `abbreviate(text, max)` | 单独使用的分类提示、脱敏、截断 |

```java
int status = response.statusCode();
if (!HttpErrors.isSuccess(status)) {
    context.tellFailure(message, HttpErrors.httpError(status, response.body()));
    return;
}
JsonValue body = HttpErrors.parseBody(response.body());
if (body.path("errcode").asInt(0) != 0) {
    context.tellFailure(message, HttpErrors.apiError(
            body.path("errcode").asText(), body.path("errmsg").asText(""), status, body));
    return;
}
```

键名固定为 `statusCode`，与成功输出的 `output.statusCode` 对齐。SDK 的 `HttpFailure.toException()`
用的是 `status`，它描述的是 Webhook 等**入站**路由失败，和这里的**出站**调用不是一回事，不要照搬。

`tellFailure` 后下游拿到的 `msg.error`（框架还会在 `metadata` 中补 `env`、`workflowId`、
`workflowNodeId`、`correlationId`、`workerId` 和 `error.id`）：

```json
"error": {
  "code": "DINGTALK_HTTP_ERROR",
  "message": "请求无效（HTTP 400），请检查消息内容。响应：{\"errcode\":40035,\"errmsg\":\"...\"}",
  "metadata": {
    "statusCode": 400,
    "body": { "errcode": 40035, "errmsg": "..." }
  }
}
```

下游用 `={{ msg.error.metadata.statusCode }}`、`={{ msg.error.metadata.body.errcode }}` 取值。
不要把响应只拼进 `message` 而不放进 `metadata`，也不要把 `body` 存成 JSON 字符串。

## 规范 7：参数变更必须重启或热更新

参数保存后，正在运行的节点必须用上新值。框架的规则是：

- `isRestartRequired()` 返回 `true`：`destroy()` 后再 `initialize()`，适合路由、cron、连接、连接池、凭证
- 返回 `false`：只调用 `onParametersUpdated()`。这里必须用 **newParameters** 重新赋值，否则流程仍跑旧配置

未覆写 `isRestartRequired()` 时，任意参数变化都会重启，节点会在 `initialize()` 里读到新值。
一旦改成只比较部分字段，其余在 `initialize()` 里读过的字段都要在 `onParametersUpdated()` 中重新生效。
两边应共用 `applyParameters()`：

```java
@Override
public void initialize(Context context, JsonValue parameters) {
    this.client = buildClient(parameters.path("timeout").asInt(30));
    applyParameters(parameters);
}

@Override
public boolean isRestartRequired(JsonValue newParameters, JsonValue oldParameters) {
    return newParameters.path("timeout").asInt(30) != oldParameters.path("timeout").asInt(30);
}

@Override
public void onParametersUpdated(Context context, JsonValue newParameters, JsonValue oldParameters) {
    applyParameters(newParameters);
}
```

不要 `return false` 却留空 `onParametersUpdated()`，也不要把 `oldParameters` 传进 `applyParameters()`。

## 节点状态

请求-响应的接口节点（普通 HTTP 节点、通用调用）不要 `setStatus`。`initialize()` 里写「就绪」「运行中」没有变化可观察，画布上会一直挂着一句空状态。

`setStatus` 只留给有持续运行状态的节点：触发器（已调度、监听中、限流丢弃）、长连接（已连接、已断开）。状态文案要随真实变化更新，不要在启动时设一次就再也不改。

## 触发器节点四条额外规范

1. `initialize()` 中用 `context.isTest()` 区分：测试模式立即触发一次，生产模式注册定时任务
   或监听器（Webhook 等被动触发器两种模式都要注册路由）。
2. 每条消息必须用 `context.createTriggerMessage(payload, eventId)` 创建。payload 根级写
   `triggerNodeId`（`getWorkflowNodeId()`）、`eventId`（本次触发 UUID；有外部追踪 ID 时用它）、
   `workerId`（`getWorkerId()`，不适用时 `null`）。`eventId` 就是第二个参数，与 `__correlationId` 相同。
   必须 `context.complete` 这条新消息，且只调一次（用于统计触发器的执行次数、QPS 与耗时，重复调用会重复计数）。
   普通触发器紧接在 `tell*` 之后；特殊触发器可按说明调整位置，但不能省略。
3. `destroy()` 中取消定时任务、注销 HTTP 路由。注解必须同时设 `isTrigger=true, hasInput=false`。
4. 背压：发消息用 `context.tryTellSuccess` / `tryTellNext`，不用 `tellSuccess`（下游过载时被引擎丢弃，触发器感知不到）。
   用 `support/TriggerGuard` 读取表单 `maxPerSecond`（`0` 表示不限速），轮询类用 `tryEnter` / `exit` 防重叠、每轮条数有上限；
   本地缓冲只用有界队列。超限时推送型丢弃计数、拉取型跳过本轮、Webhook 返回 429 + `Retry-After`、MQ nack。
   `destroy()` 中清空缓冲并 `guard.reset()`。详见 [reference/backpressure.md](reference/backpressure.md)。

## 按原文验签的回调触发器

接口认证先用核心包 `WebhookTriggerNode` 已有的 `authType`（`none` / `httpBasic` / `apiKey` / `jwtAuth`）。只有按原始报文体计算签名、对不上这些方式时，才做下面这个触发器。微信支付、支付宝、Stripe 属于这类。不要在 `WebhookTriggerNode` 后面再加验签节点。`Content-Type: application/json` 时，那个触发器把 `request().body()` 解析成对象，原始字节回不来；表单提交会收成字段。签名对不上。

做成这个渠道自己的触发器（`isTrigger=true, hasInput=false`），验签放在触发器里：

1. `Route.create` 注册官方文档里的方法和路径。handler 用 `rc.request().body()` 拿原始字符串，验签只用这份原文和文档要求的头（时间戳、随机串、序列号、签名）。通过之后才解析业务字段。payload 根级同时放 `rawBody`（原文）和解析后的字段，并带上 `triggerNodeId`、`eventId`、`workerId`。
2. 验签、时间窗、重放都在触发器里做完。失败按官方文档的状态码和正文 `response().write().end()`，不要 `tryTellSuccess`。
3. 返回两种都要支持，用参数选择（如 `responseMode`）。eventId 一律用 `rc.getRequestId()`，与消息头 `__correlationId` 相同。
   - **直接返回**：验签通过后立刻按官方文档的状态码、Content-Type 和正文写回，不要写成 `{"code":200,"msg":"success"}`。流程在后台继续。
   - **处理完再返回**：不要 `end()`。下游用核心包 `WebhookResponseNode`，靠 `__correlationId` 找到这次 HTTP 并写回。`Route.timeout` 要盖住下游处理时间，默认 5000 毫秒不够就加大。
4. 测试运行（`isTest()`）仍注册路由。成功请求立刻返回测试确认，不挂起连接，也不回文档要求的正式正文。正式环境才按 `responseMode`。
5. 限流仍在读 body 之前：超限或 `tryTellSuccess` 为 false 时返回 429 和 `Retry-After`，不进入流程。
6. 脚手架 `templates/java/WebhookNode.java.tmpl` 会把 JSON 解析成对象并立刻回通用成功，不能用来做验签回调。

## 命名一致性（最常见的低级错误）

| 位置 A | 必须完全等于 | 位置 B |
|---|---|---|
| `@FlowNodeDescription(name)` | == | `bundle.json` 节点 `name` |
| `@FlowNodeDescription(propertiesFile)` | == | `resources/` 下实际文件路径 |
| `@CredentialsDescription(type)` | == | 表单 `typeOptions.credentialsType` |
| `@CredentialsDescription(type)` | == | `propertiesFile` 文件名 `credentials/<type>.json` |
| `MethodExecutor.getMethodName()` | == | 表单 `loadOptions.method`（`provider=bundle`） |
| `loadOptions.credentialsRef` | == | 同表单内 `CredentialSelect` 字段的 `name` |
| 每个实现类 | 出现在 | `META-INF/services/` 对应文件 |

节点 `name` 发布后不可修改。`bundle.json` **不需要** `credentials` 数组，凭证通过 SPI 自动发现。
