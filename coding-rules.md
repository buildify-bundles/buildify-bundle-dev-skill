# Bundle 编码硬性规范

六条通用规范 + 触发器三条 + 命名一致性表。表单与 API 细节见 `reference/`。

## 目录

- [规范 1：读参数用 path()](#规范-1读参数用-path绝不用-get)
- [规范 2：路由后必须 complete](#规范-2路由后必须-contextcomplete入站-message)
- [规范 3：dynamicParameters + resolveExpressions](#规范-3dynamicparameters--resolveexpressions)
- [规范 4：普通节点输出放 output](#规范-4普通节点输出放-output触发器放根级)
- [规范 5：凭证标识 PascalCase](#规范-5凭证标识-pascalcase三处逐字一致)
- [规范 6：已知错误用 FlowNodeException](#规范-6已知错误用-flownodeexception)
- [触发器节点三条额外规范](#触发器节点三条额外规范)
- [命名一致性](#命名一致性最常见的低级错误)

## 规范 1：读参数用 `path()`，绝不用 `get()`

`path()` 字段缺失时返回 `MissingNode`；`get()` 返回 `null`，会 NPE。

```java
String url   = parameters.path("url").asText(null);
int timeout  = parameters.path("timeout").asInt(30);
boolean flag = parameters.path("enabled").asBoolean(false);
```

## 规范 2：路由后必须 `context.complete(入站 message)`

在 `tellSuccess` / `tellFailure` / `tellNext` 完成路由决策后，**同步和异步路径都必须**对
`onMsg` 的入参 `message` 调用 `complete`，否则框架无法释放消息与异步句柄。

```java
// 同步路径
context.tellSuccess(outMsg);
context.complete(message);

// 异步路径：用 onComplete 统一收尾
context.<String>executeBlocking(() -> doWork())
    .onSuccess(result -> context.tellSuccess(buildMsg(result, message)))
    .onFailure(e -> context.tellFailure(message, e))
    .onComplete(() -> context.complete(message));

// 原生异步：finally 保证必然 complete
httpClient.sendAsync(request, BodyHandlers.ofString()).whenComplete((resp, err) -> {
    try {
        if (err != null) context.tellFailure(message, err);
        else context.tellSuccess(buildMsg(resp, message));
    } finally {
        context.complete(message);
    }
});
```

## 规范 3：`dynamicParameters` + `resolveExpressions`

支持表达式（`={{ msg.url }}`）的参数在 `initialize()` 存入 `dynamicParameters`，
在 `onMsg()` 中按当前消息求值：

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

```java
// ✅ 触发器
JsonValue payload = JsonValueFactory.objectNode()
    .put("cron", cronExpr).put("timestamp", System.currentTimeMillis());

// ❌ 触发器不要包 output
JsonValue bad = JsonValueFactory.objectNode().put("output", payload);
```

文档与表单说明中统一用 `msg` 表示消息 payload，**不要**用 `$json`。

## 规范 5：凭证标识 PascalCase，三处逐字一致

```java
@CredentialsDescription(
    type           = "MysqlCredential",
    label          = "MySQL 数据库",
    propertiesFile = "credentials/MysqlCredential.json")
```

表单引用凭证类型用 `typeOptions.credentialsType`（**不是**已废弃的 `credentialsName`）。
`context.getCredentials(...)` 的入参是**表单字段 `name`**，不是凭证类型标识：

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

## 触发器节点三条额外规范

1. `initialize()` 中用 `context.isTest()` 区分：测试模式立即触发一次，生产模式注册定时任务
   或监听器（Webhook 等被动触发器两种模式都要注册路由）。
2. 每条消息必须用 `context.createTriggerMessage(payload)` 创建；透传外部追踪 ID 用
   `createTriggerMessage(payload, externalTraceId)`。
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
