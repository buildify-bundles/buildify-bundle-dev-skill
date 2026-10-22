# Bundle 编码硬性规范

七条通用规范 + 触发器三条 + 命名一致性表。表单与 API 细节见 `reference/`。

## 目录

- [规范 1：读参数用 path()](#规范-1读参数用-path绝不用-get)
- [规范 2：异步路径必须 complete](#规范-2异步路径必须-contextcomplete同步路径框架自动收尾)
- [规范 3：dynamicParameters + resolveExpressions](#规范-3dynamicparameters--resolveexpressions)
- [规范 4：普通节点输出放 output](#规范-4普通节点输出放-output触发器放根级)
- [规范 5：凭证标识 PascalCase](#规范-5凭证标识-pascalcase三处逐字一致)
- [规范 6：已知错误用 FlowNodeException](#规范-6已知错误用-flownodeexception)
- [规范 7：参数变更必须重启或热更新](#规范-7参数变更必须重启或热更新)
- [触发器节点三条额外规范](#触发器节点三条额外规范)
- [命名一致性](#命名一致性最常见的低级错误)

## 规范 1：读参数用 `path()`，绝不用 `get()`

`path()` 字段缺失时返回 `MissingNode`；`get()` 返回 `null`，会 NPE。对所有 `JsonValue`
（`parameters`、`newParameters`、`payload`、`path(...)` 链）都一样。必填项为空时抛 / 回
`FlowNodeException`，不要用 `Objects.requireNonNull`。

```java
String url   = parameters.path("url").asText(null);
int timeout  = parameters.path("timeout").asInt(30);
boolean flag = parameters.path("enabled").asBoolean(false);
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
框架不会自动收尾，必须对**这条新消息**调用 `context.complete`，否则本次触发无法结束。
普通触发器在 `tellSuccess` / `tellNext` / `tellFailure` 之后立刻调用。特殊触发器按自身说明
把 `complete` 挪到真正结束的位置（例如等待回执、批量刷出、异步回调结束），但不能省略。

## 规范 3：`dynamicParameters` + `resolveExpressions`

节点表单里，除访问凭证（`CredentialSelect`）外，可传值字段默认
`"expression": true` 与 `"droppable": true`。`expression` 表示这个控件能否在固定值和
`={{ msg.xxx }}` 之间切换，`CodeEditor` / `SqlEditor` / `JsonEditor` 也一样。
`CodeEditor` 的 `typeOptions.enableExpression` 是编辑器自己的属性，决定内容是否带 `=` 前缀存储，
不能用来代替顶层 `expression`。访问凭证和 `credentials/*.json` 不要开 `expression`。

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

`JsonExpressionInput` 字段由编排器提前规整为 `JsonValue`，**不要**在服务端再做
`JsonValueFactory.fromJson(...asText())`，直接 `path()` 填入 `dynamicParameters`。

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
context.tellSuccess(triggered);
context.complete(triggered);   // 必须有。特殊触发器可按说明挪到真正结束处

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
里的参数校验）。`onFailure` 中分级：`FlowNodeException` 用 `log.warn`，其余用 `log.error`
保留堆栈。日志前缀统一 `[NodeName]`。禁止把凭证字段写入日志或 payload。

```java
throw new FlowNodeException("API_ERROR_" + code, "API 调用失败: " + apiMsg)
    .with("code", code).with("message", apiMsg);
```

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

## 触发器节点三条额外规范

1. `initialize()` 中用 `context.isTest()` 区分：测试模式立即触发一次，生产模式注册定时任务
   或监听器（Webhook 等被动触发器两种模式都要注册路由）。
2. 每条消息必须用 `context.createTriggerMessage(payload, eventId)` 创建。payload 根级写
   `triggerNodeId`（`getWorkflowNodeId()`）、`eventId`（本次触发 UUID；有外部追踪 ID 时用它）、
   `workerId`（`getWorkerId()`，不适用时 `null`）。`eventId` 就是第二个参数，与 `__correlationId` 相同。
   必须 `context.complete` 这条新消息。普通触发器紧接在 `tell*` 之后；特殊触发器可按说明调整位置，但不能省略。
3. `destroy()` 中取消定时任务、注销 HTTP 路由。注解必须同时设 `isTrigger=true, hasInput=false`。

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
