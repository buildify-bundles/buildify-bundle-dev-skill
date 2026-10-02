# Buildify Bundle API 参考

所有接口位于 `cn.buildify.bundle.api` 及其子包。

## 目录

- [FlowNode 接口](#flownode-接口)
- [@FlowNodeDescription](#flownodedescription)
- [Context](#context)
- [Node Service RPC](#node-service-rpc节点间调用)
- [AsyncResult](#asyncresult)
- [Message 与 MessageBuilder](#message-与-messagebuilder)
- [JsonValue](#jsonvalue)
- [Relation](#relation)
- [MethodExecutor](#methodexecutor)
- [CredentialsProvider](#credentialsprovider)
- [BundleActivator](#bundleactivator)
- [HTTP 路由（Webhook）](#http-路由webhook)
- [SandboxExecutor](#sandboxexecutor)
- [FlowNodeException](#flownodeexception)

## FlowNode 接口

```java
public interface FlowNode {
    /** 节点启动时调用一次：读参数、初始化连接（可选） */
    default void initialize(Context context, JsonValue parameters) {}

    /** 每条消息到达时调用（必须实现） */
    void onMsg(Context context, Message<?> msg);

    /** 节点停止/重启时调用：释放资源（可选，必须幂等） */
    default void destroy(Context context) {}

    /** 参数变更是否需要重启，默认任何变化都重启 */
    default boolean isRestartRequired(JsonValue newParameters, JsonValue oldParameters) {
        return !Objects.equals(newParameters, oldParameters);
    }

    /** isRestartRequired()=false 时调用，就地刷新轻量配置 */
    default void onParametersUpdated(Context context, JsonValue newParameters, JsonValue oldParameters) {}

    /** 凭证变更；返回 true 表示已就地生效，false 时框架回退为重启节点 */
    default boolean onCredentialsUpdated(Context context, String type, String name) { return false; }

    /** 输出关系，默认 [Success, Failure] */
    default List<Relation> getRelations() { return Relation.DEFAULT; }

    /** 消息级过滤：返回 false 该消息被跳过，不触发 onMsg */
    default boolean support(Message<?> message) { return true; }

    /** 框架提供的默认实现：取 payload 并转型 */
    default <T> T getPayload(Message<?> message, Class<T> type) { ... }
}
```

> `support()` 返回 false 的消息不会进入 `onMsg()`，也就没有配对的 `complete()`，
> 因此该方法内不要做副作用操作。

## @FlowNodeDescription

```java
@FlowNodeDescription(
    name              = "MyNode",                  // 必填，bundle 内唯一，发布后不可修改
    propertiesFile    = "properties/MyNode.json",  // 表单配置路径（resources 下）
    isTrigger         = false,                     // 触发器必须同时 hasInput=false
    hasInput          = true,
    hasOutput         = true,
    isLayoutNode      = false,                     // 分支/循环容器设 true
    isShowConfigOnAdd = true,                      // 添加到画布后自动弹配置面板
    documentUrl       = ""                         // 节点文档链接
)
```

## Context

### 消息传递

```java
context.tellSuccess(newMsg);                       // 向 Success 链路
context.tellNext(message, "BranchName");           // 向指定关系名
context.tellNext(message, Set.of("A", "B"));       // 广播到多个关系
context.tellFailure(message, throwable);
// 同步：onMsg 返回前 tell* 即可，框架自动 complete
// 异步：每条结束路径对入站 message 调用 context.complete(message)
```

### 凭证

`getCredentials` 的入参是**节点表单中 `CredentialSelect` 字段的 `name`**（camelCase），
不是凭证类型标识。二者语义不同：`typeOptions.credentialsType` 决定"选哪一类凭证"，
字段 `name` 决定"从本节点表单的哪个框读取用户已选中的凭证实例"。

```java
// 表单：{ "name": "credentialsId", "uiComponent": "CredentialSelect",
//        "typeOptions": { "credentialsType": "MysqlCredential" } }

Credentials cred = context.getCredentials("credentialsId");   // ✅ 字段 name
Credentials bad  = context.getCredentials("MysqlCredential"); // ❌ 凭证类型标识

Map<String, Object> data = cred.getData();   // key 为凭证表单字段 name
String apiKey = (String) data.get("apiKey");
String type   = cred.getType();              // 凭证实现类型，由框架绑定
```

同一节点有多个凭证框时（如机器人凭证 + 应用凭证），各自有独立 `name`，需分别调用。

### 节点与工作流信息

```java
String  nodeId     = context.getWorkflowNodeId();
String  workflowId = context.getWorkflowId();
String  tenantId   = context.getTenantId();
String  workerId   = context.getWorkerId();      // 不适用时 null
String  bundleName = context.getBundleName();    // 不可用时 null
boolean isTest     = context.isTest();

String apiUrl = switch (context.getEnvironment()) {   // EnvironmentType
    case Production -> "https://api.example.com";
    case Test       -> "https://sandbox.example.com";
};

Set<String> inbound = context.getInboundNodeIds();  // 直接上游节点 ID，聚合节点用
```

### 表达式

```java
JsonValue resolved = context.resolveExpressions(dynamicParameters, payload);  // 最常用
JsonValue result   = context.evaluateExpression("={{msg.name}}", payload);
Map<String, Object> env = context.getEnvironmentVariables();
```

### 节点状态显示

```java
context.setStatus(NodeStatus.builder().color("green").text("已连接").build());
// color: green / red / yellow
```

### 异步执行

```java
context.<String>executeBlocking(() -> syncHttpCall())
    .onSuccess(r -> context.tellSuccess(buildMsg(r, message)))
    .onFailure(e -> context.tellFailure(message, e))
    .onComplete(() -> context.complete(message));

// 带超时：超时后任务被中断并走 onFailure(TimeoutException)
context.<byte[]>executeBlocking(() -> readFile(), Duration.ofSeconds(10))

// 无返回值（纯副作用），结果值为 null
context.executeBlocking(() -> writeToDatabase(data))
```

### 定时调度

```java
// Cron 定时（Quartz 表达式）
ScheduledFuture<?> future = context.schedule(
    () -> triggerOnce(context), "0 */5 * * * ?", "Asia/Shanghai");

// 非 Cron 的延迟/周期调度；返回节点 Actor 绑定的事件循环，同节点任务串行
ScheduledFuture<?> retry = context.getExecutor()
    .schedule(() -> retryOnce(context), 30, TimeUnit.SECONDS);
```

> 两类 `ScheduledFuture` 都**必须**在 `destroy()` 中 `cancel(true)`，否则钉住 ClassLoader。

### 触发器消息

```java
Message<JsonValue> msg = context.createTriggerMessage(payload);
Message<JsonValue> msg = context.createTriggerMessage(payload, externalTraceId);
```

自动注入（`setHeaderIfAbsent` 语义）：`CORRELATION_ID`（单参数重载自动生成 UUID）、
`BEGIN_RUN_NANOS`（纳秒时刻，不受时钟回拨影响）。

### 响应时间统计

`isAutoRecordResponseTime()` 定义在 **Context** 上（不是 FlowNode），默认 `true`：
框架在 `complete()` 时按 `BEGIN_RUN_NANOS` 自动计算耗时。

```java
context.setAutoRecordResponseTime(false);            // 关闭自动统计
context.recordResponseTime(elapsedMillis);           // 手动记录
```

### 执行统计查询

```java
JsonValue snapshot = context.getNodeMetrics(targetWorkflowId, targetNodeId);
if (snapshot.path("found").asBoolean()) {
    long   executed = snapshot.path("executedCount").asLong();
    double avgMs    = snapshot.path("avgResponseTimeMs").asDouble();
    long   backlog  = snapshot.path("backlog").asLong();
}
```

字段：`found`、`workflowId`、`workflowNodeId`、`qps`、`avgResponseTimeMs`、`maxResponseTimeMs`、
`minResponseTimeMs`、`backlog`、`executedCount`、`queueFull`、`outputRelations`、`collectedAt`。
**仅限本 Worker 进程**，跨 Worker 查询返回 `found=false`。

## Node Service RPC（节点间调用）

节点间 RPC 的完整命名规则、自动/手动注册、调用与测试态语义见
[node-service-rpc.md](node-service-rpc.md)。要点：唯一入口 `context.nodeService()`；
旧的 `sendRequestEvent` / `RequestEvent` / `onRequestEvent` 等事件 API 已移除，禁止使用。

## AsyncResult

```java
public interface AsyncResult<T> {
    AsyncResult<T> onSuccess(Consumer<T> handler);
    AsyncResult<T> onFailure(Consumer<Throwable> handler);
    AsyncResult<T> onComplete(Runnable action);        // 类似 try-finally，推荐放 complete()
    <U> AsyncResult<U> map(Function<? super T, ? extends U> mapper);
    <U> AsyncResult<U> flatMap(Function<? super T, AsyncResult<U>> mapper);
    CompletableFuture<T> toFuture();
    static <T> AsyncResult<T> from(CompletableFuture<T> future, Executor executor);
}
```

## Message 与 MessageBuilder

```java
// 触发器节点
Message<JsonValue> msg = context.createTriggerMessage(payload);

// 普通节点：透传上游 headers（保留 CORRELATION_ID）
Message<JsonValue> msg = MessageBuilder.withPayload(newPayload)
    .copyHeaders(originalMsg.getHeaders()).build();

// 在原消息基础上追加 header
Message<JsonValue> msg = MessageBuilder.fromMessage(originalMsg)
    .setHeader("myKey", "myValue").build();

// 读取
JsonValue payload = getPayload(message, JsonValue.class);
String corrId = (String) message.getHeaders().get(MessageHeaders.CORRELATION_ID);
Long   ts     = message.getHeaders().get(MessageHeaders.TIMESTAMP, Long.class);
```

### MessageHeaders 常量

| 常量 | key | 注入方式 |
|---|---|---|
| `ID` | `__id` | 框架自动，消息 UUID |
| `TIMESTAMP` | `__timestamp` | 框架自动，创建毫秒时间戳 |
| `CORRELATION_ID` | `__correlationId` | `createTriggerMessage` 注入；非触发器靠 `copyHeaders` 传递 |
| `SOURCE_NODE_ID` | `__sourceNodeId` | 框架自动，源节点 ID |
| `CONTENT_TYPE` | `__contentType` | 产生消息的节点自行设置，可配合 `support()` 过滤 |
| `BEGIN_TIME` | `__beginTime` | **不由** `createTriggerMessage` 注入，需要时自行设置 |
| `BEGIN_RUN_NANOS` | `__beginRunNanos` | `createTriggerMessage` 注入，精确耗时统计 |

`MessageHeaders` 是只读 Map，`put`/`remove`/`clear` 抛 `UnsupportedOperationException`。

### ErrorMessage

payload 为 `Throwable` 时 `MessageBuilder` 自动创建 `ErrorMessage`：

```java
if (message instanceof ErrorMessage err) {
    Throwable cause    = err.getPayload();
    Message<?> original = err.getOriginalMessage();
}
```

## JsonValue

```java
// 创建
JsonValue obj = JsonValueFactory.objectNode();
JsonValue arr = JsonValueFactory.arrayNode();
JsonValue v1  = JsonValueFactory.fromJson("{\"name\":\"Alice\"}");
JsonValue v2  = JsonValueFactory.fromObject(myPojo);

// 读取（始终 path()，不用 get()）
String  name = obj.path("name").asText("default");
int     age  = obj.path("age").asInt(0);
boolean flag = obj.path("enabled").asBoolean(false);
long    ts   = obj.path("ts").asLong(0L);
String  city = obj.path("address").path("city").asText();

boolean missing = obj.path("x").isMissingNode();
boolean isNull  = obj.path("x").isNull();
boolean hasVal  = obj.hasNonNull("x");

// 写入
obj.put("name", "Alice").put("age", 30)
   .put("nested", JsonValueFactory.objectNode().put("k", "v"));
arr.add("item1");
for (JsonValue item : arr.asArray()) { }

// 其他
JsonValue copy = original.deepCopy();   // 防止污染上游 payload
String json    = obj.toJson();
Map<String, Object> map = obj.toMap();
```

### JsonExpressionInput 叶子节点处理

组装 `dynamicParameters` 时按值类型分别处理：

| 值类型 | 处理 |
|---|---|
| 已是对象/数组节点 | 直接 `put` |
| 文本且为静态 JSON | `JsonValueFactory.fromJson(text)` 后 `put`；解析失败保留原文本 |
| POJO（`isPojo()=true`） | `JsonValueFactory.fromObject(value.rawValue())` 后 `put` |
| 含 `{{` / `={{` 的表达式 | **原样 `put`**，留待 `resolveExpressions` 后二次解析 |

## Relation

```java
public static final List<Relation> RELATIONSHIPS = List.of(
    Relation.builder().name("True").label("是").description("条件成立").build(),
    Relation.builder().name("False").label("否").description("条件不成立").build(),
    Relation.RELATIONSHIP_FAILURE);

// 或用 RelationBuilder
public static final List<Relation> RELATIONSHIPS = RelationBuilder.create()
    .add("True", "是", "条件成立")
    .add("False", "否", "条件不成立")
    .addFailure()      // 另有 addSuccess()、addDefault()
    .build();
```

| 常量 | 值 |
|---|---|
| `Relation.RELATIONSHIP_SUCCESS` | `name = "Success"` |
| `Relation.RELATIONSHIP_FAILURE` | `name = "Failure"` |
| `Relation.SUCCESS_NAME` / `FAILURE_NAME` | `"Success"` / `"Failure"` |
| `Relation.DEFAULT` | `[Success, Failure]` |

自定义关系建议定义为 `static final` 常量，所有实例共享。

## MethodExecutor

```java
public interface MethodExecutor {
    CompletableFuture<Object> execute(ExecutorContext context);
    String getMethodName();                          // 与表单 loadOptions.method 一致
    default boolean isRemoteInvocable() { return true; }  // 仅内部使用时返回 false
}
```

`ExecutorContext`（位于顶层包 `cn.buildify.bundle.api`）辅助方法：

```java
// 表单参数（对应 dependsOn 收集的字段值）
context.requireParam("appToken", String.class)   // 不存在抛 IllegalArgumentException
context.getParam("schema", String.class)         // 不存在返回 null
context.getParam("pageSize", Integer.class, 20)
context.requireString("host"); context.getString("host"); context.getString("host", "localhost")
context.requireInteger("port"); context.getInteger("port"); context.getInteger("port", 5432)
context.getBoolean("ssl", false)                 // 必须传默认值

// 凭证字段（框架已解密）
context.requireCredential("appId", String.class) // 不存在抛 IllegalStateException
context.getCredential("database", String.class)
context.requireCredentialString("apiKey"); context.getCredentialString("password")
context.getCredentialString("schema", "public")
context.getCredentialInteger("port", 5432)       // 必须传默认值，无单参数重载
context.getCredentialBoolean("useSsl", true)     // 必须传默认值

context.isMethod("getDatabases")
context.nodeService()                            // 节点服务 RPC 客户端，不可在此注册 handler
```

> `getInteger` / `getBoolean` 及凭证版本**没有**单参数重载，必须传默认值；
> `getCredentialInteger(key)` 不存在。

返回下拉选项的格式：`List<Map<String,Object>>`，每项 `{"label": ..., "value": ...}`。

SPI：`META-INF/services/cn.buildify.bundle.api.MethodExecutor`

## CredentialsProvider

```java
@CredentialsDescription(
    type           = "MysqlCredential",                    // 唯一标识（PascalCase）
    label          = "MySQL",                              // UI 显示名
    propertiesFile = "credentials/MysqlCredential.json")   // 文件名 == type，含大小写
public class MysqlCredentialsProvider implements CredentialsProvider {

    @Override
    public CompletableFuture<Object> execute(CredentialsMethodRequest request) {
        if (request.isTestConnection()) {         // 方法名固定 "test"
            return CompletableFuture.supplyAsync(() -> {
                testConnect(request.requireString("host"), request.getInteger("port", 3306));
                return Map.of("success", true, "message", "连接成功");
            });
        }
        if (request.is("getDatabases")) {
            return CompletableFuture.supplyAsync(
                () -> List.of(Map.of("label", "mydb", "value", "mydb")));
        }
        return CompletableFuture.failedFuture(
            new UnsupportedOperationException("不支持的方法: " + request.getMethod()));
    }
}
```

无动态方法时空实现即可。测试连接返回格式固定为 `{"success": bool, "message": string}`。

`CredentialsMethodRequest` 辅助方法：

```java
request.isTestConnection(); request.is("getDatabases");   // 大小写敏感
request.requireString("host"); request.getString("host"); request.getString("host", "localhost")
request.getInteger("port"); request.getInteger("port", 3306)   // 返回 Integer，可为 null
request.getBoolean("ssl");  request.getBoolean("ssl", false)
request.get("timeout", Long.class); request.get("timeout", Long.class, 5000L)
request.require("host", String.class)
```

SPI：`META-INF/services/cn.buildify.bundle.api.credentials.CredentialsProvider`

## BundleActivator

```java
public class MyBundleActivator implements BundleActivator {
    @Override
    public void start(BundleContext context) throws Exception {
        // 所有 FlowNode.initialize 之前调用
        log.info("Bundle {} v{} sha256={} 启动",
            context.getBundleName(), context.getBundleVersion(), context.getSha256());
        SharedConnectionPool.initialize();
    }

    @Override
    public void stop(BundleContext context) throws Exception {
        // 所有 FlowNode.destroy 之后调用；卸载前最后一次清理机会
        SharedConnectionPool.shutdown();
    }
}
```

SPI：`META-INF/services/cn.buildify.bundle.api.BundleActivator`

## HTTP 路由（Webhook）

```java
this.route = Route.create(Set.of(HttpMethod.POST, HttpMethod.GET), "/webhook/my-path")
    .timeout(parameters.path("timeout").asInt(5000))
    .handler(rc -> handleRequest(context, rc));
context.getRouter().register(route);        // initialize()
context.getRouter().unregister(route);      // destroy()，必须

// handler 内
String body     = rc.request().body();
String clientIp = rc.getClientIP();
String token    = rc.request().getHeader("Authorization");
rc.response().statusCode(200).contentType("application/json").write("{\"ok\":true}").end();
rc.fail(500, message);
```

### CORS

```java
.cors(CorsConfiguration.builder()
    .enabled(true)
    .allowedOrigins(Set.of("https://example.com"))
    .allowedMethods(Set.of("POST", "OPTIONS"))
    .allowedHeaders(Set.of("Content-Type", "Authorization"))
    .allowCredentials(true).maxAge(3600L).build())
```

### IP 访问控制

```java
.routeAcl(RouteAcl.builder()
    .policy(RouteAcl.Policy.WHITELIST_ONLY)
    .whitelist(Set.of("10.0.0.0/8", "192.168.0.0/16")).build())
.failureHandler((ctx, failure) -> log.warn("访问被拒绝: {}", ((AccessBlockedException) failure.cause()).getClientIP()))
.authenticator(ctx -> AuthResult.passed("apiKey", "principal", null))
```

### 流式文件上传

```java
Route.create(Set.of(HttpMethod.POST), "/upload/file")
    .streaming(true)
    .uploadHandler(rc -> new UploadHandler() {
        public void onFileBegin(RoutingContext ctx, UploadFileContext upload) { }
        public void onFileData(RoutingContext ctx, UploadFileContext upload) {
            out.write(upload.getBuffer().bytes());
            upload.getBuffer().release();     // 必须释放，否则内存泄漏
        }
        public void onFileEnd(RoutingContext ctx, UploadFileContext upload) { }
    });
```

## SandboxExecutor

```java
String wrapped = "(function jsFunction(msg, headers, env){ %s })".formatted(code);
this.sandboxExecutor = context.createSandboxExecutor("js", wrapped);
this.sandboxExecutor.setTimeout(Duration.ofSeconds(5));

context.executeBlocking(() -> {
    try {
        return sandboxExecutor.execute(payload, message.getHeaders(),
            context.getEnvironmentVariables());
    } catch (TimeoutException e) {
        throw new CompletionException(e);      // 受检异常需包裹
    }
}).onSuccess(r -> context.tellSuccess(MessageBuilder.withPayload(r)
        .copyHeaders(message.getHeaders()).build()))
  .onFailure(e -> context.tellFailure(message, e))
  .onComplete(() -> context.complete(message));

// destroy() 中 sandboxExecutor.close()
```

用户编写的 JS 代码体签名：`msg` = payload，`headers` = 消息头 Map，`env` = 环境变量 Map，
`return { output: msg }` 的返回值作为新 payload。用具名函数包裹以便报错堆栈显示函数名。

## FlowNodeException

```java
throw new FlowNodeException("HTTP_IO_ERROR", "HTTP 请求失败: " + e.getMessage(), e)
    .with("url", url);

// 捕获 InterruptedException 时必须恢复中断状态
catch (InterruptedException e) {
    Thread.currentThread().interrupt();
    throw new FlowNodeException("HTTP_INTERRUPTED", "请求被中断", e);
}
```
