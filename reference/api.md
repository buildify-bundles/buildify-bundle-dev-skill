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
- [Validator](#validator)

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

    /** 凭证变更；type 为凭证类型标识，name 为用户设置的凭证实例名（不是表单字段 name）。
     *  返回 true 表示已就地生效，false 时框架回退为重启节点 */
    default boolean onCredentialsUpdated(Context context, String type, String name) { return false; }

    /** 输出关系：读取类上的 @NodeRelations，未声明时为 [Success, Failure]。
     *  不要覆盖——平台发布时只读注解，覆盖本方法的软件包会被拒绝发布 */
    default List<Relation> getRelations() { return Relation.declaredBy(getClass()); }

    /** 消息级过滤：返回 false 该消息被跳过，不触发 onMsg */
    default boolean support(Message<?> message) { return true; }

    /** 框架提供的默认实现：取 payload 并转型 */
    default <T> T getPayload(Message<?> message, Class<T> type) { ... }
}
```

> `support()` 返回 false 时消息不会进入 `onMsg()`，**也不是静默跳过**：框架回调消息的
> `onFailure`、记一条 WARN，再抛出 `RuntimeException("msg is not support")`，消息也不会走 Failure 链路。
> 只用它挡掉确实不该到达本节点的消息（如 `CONTENT_TYPE` 不匹配），方法内不要做副作用操作。
> 需要"条件不满足就放行/分流"时，在 `onMsg` 里 `tellNext` 到对应关系。

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
// 触发器：createTriggerMessage 的新消息不在 onMsg 内，必须且只调一次 complete。特殊触发器可按说明调整位置
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

`getCredentials` **不会返回 null**：表单字段没有绑定凭证、或凭证已被删除时直接抛 `RuntimeException`。
在 `onMsg` 中调用要捕获并转成结构化错误，不要写 `== null` 判断：

```java
Credentials cred;
try {
    cred = context.getCredentials("credentialsId");
} catch (RuntimeException e) {
    context.tellFailure(message, new FlowNodeException("MISSING_CREDENTIALS", "未选择访问凭证或凭证不存在", e));
    return;
}
```

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
String eventId = UUID.randomUUID().toString(); // 有外部追踪 ID 时用外部 ID
JsonValue payload = JsonValueFactory.objectNode()
    .put("triggerNodeId", context.getWorkflowNodeId()) // 例：n-u1d6v6we
    .put("eventId", eventId)                           // 例：88724f81-e1a7-47cf-9105-0bffd00a5e98
    .put("workerId", context.getWorkerId());           // 例：wkr-dk7s8awx；不适用时 null
Message<JsonValue> msg = context.createTriggerMessage(payload, eventId);
context.tellSuccess(msg);
context.complete(msg); // 必须且只调一次。特殊触发器可按说明挪到真正结束处
```

对触发器消息，`complete` 只记录触发器节点的执行次数、QPS，以及从创建消息到 `complete` 的耗时，
不调用时这些指标恒为 0，但不会让流程卡住。框架不去重，重复调用会重复计数。
SDK `Context.createTriggerMessage` 的 javadoc 示例只写了 `tellSuccess`，没有 `complete`，以本规范为准。

`triggerNodeId`、`workerId` 在 `initialize()` 取出后复用；`eventId` 每次触发新生成。
第二个参数与 payload 里的 `eventId` 必须是同一个值，这样消息头 `__correlationId` 与根级字段一致。
单参数重载会自己生成 UUID，触发器不要用它，否则根级 `eventId` 和消息头会对不上。

自动注入（`setHeaderIfAbsent` 语义）：`CORRELATION_ID`（等于传入的 `eventId`）、
`BEGIN_RUN_NANOS`（纳秒时刻，不受时钟回拨影响）。

### 响应时间统计

框架在 `complete()`（或同步路径自动收尾）时按 `BEGIN_RUN_NANOS` 自动计算耗时，节点无需处理。

`Context` 接口上虽然声明了 `setAutoRecordResponseTime(boolean)` 与 `recordResponseTime(long)`，
但 Worker 的实现**没有覆写**这两个默认方法，调用后不生效。不要依赖它们关闭或手动记录耗时。

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
// 触发器节点：eventId 同时写入 payload 和追踪 ID，必须且只调一次 complete（位置可按说明调整）
Message<JsonValue> msg = context.createTriggerMessage(payload, eventId);
context.tellSuccess(msg);
context.complete(msg);

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
| `CORRELATION_ID` | `__correlationId` | 触发器传入的 `eventId`；非触发器靠 `copyHeaders` 传递 |
| `SOURCE_NODE_ID` | `__sourceNodeId` | 框架自动，源节点 ID |
| `CONTENT_TYPE` | `__contentType` | 产生消息的节点自行设置，可配合 `support()` 过滤 |
| `BEGIN_TIME` | `__beginTime` | **不由** `createTriggerMessage` 注入，需要时自行设置 |
| `BEGIN_RUN_NANOS` | `__beginRunNanos` | `createTriggerMessage` 注入，精确耗时统计 |

`MessageHeaders` 是只读 Map，`put`/`remove`/`clear` 抛 `UnsupportedOperationException`。

### 失败消息的结构

`tellFailure(message, e)` **不会**产生 `ErrorMessage`。框架复制原 payload（不是 `JsonValue` 时用空对象），
在根级写入 `error`，再以普通消息发往 Failure 链路（`MessageUtils.buildErrorMessage`）：

```json
{
  "...": "原 payload 字段",
  "error": {
    "id": "uuid",
    "code": "FlowNodeException.getCode()",
    "message": "FlowNodeException.getMessage()",
    "metadata": {
      "...": "with(...) 写入的字段",
      "env": "Production", "workflowId": "...", "workflowNodeId": "...",
      "correlationId": "...", "workerId": "..."
    }
  }
}
```

不是 `FlowNodeException` 的异常会被包装，`code` 取异常类的简单名（如 `NullPointerException`），
所以已知错误一定要用 `FlowNodeException`。`metadata` 原样拷贝，框架**不会**剔除敏感字段。
`onMsg` 抛出的未捕获异常也会被框架 `tellFailure`，随后回调消息 `onFailure` 并重新抛出。

`ErrorMessage` 只在 `MessageBuilder` 的 payload 本身是 `Throwable` 时出现，节点一般用不到。

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

只有成功 / 失败两个出口的节点什么都不用写。多出口节点在类上用 `@NodeRelations` 声明：

```java
@FlowNodeDescription(name = "if", propertiesFile = "properties/if.json")
@NodeRelations({
    @NodeRelation(name = "True", label = "是", description = "条件成立"),
    @NodeRelation(name = "False", label = "否", description = "条件不成立"),
    @NodeRelation(name = Relation.FAILURE_NAME)   // 标准关系可省略 label / description
})
public class IfNode implements FlowNode { ... }
```

- **不要覆盖 `getRelations()`**：平台发布软件包时只读字节码里的注解，不执行节点代码；覆盖该方法而未声明注解的软件包会被拒绝发布。
- `name` 与 `context.tellNext(message, name)` 的关系名一致，大小写敏感。
- `name` 为 `Success` / `Failure` 且未填 `label`、`description` 时，自动补齐标准显示名称与描述。
- 注解带 `@Inherited`，可标注在抽象父类上由子类继承。

| 常量 | 值 |
|---|---|
| `Relation.SUCCESS_NAME` / `FAILURE_NAME` | `"Success"` / `"Failure"` |
| `Relation.RELATIONSHIP_SUCCESS` / `RELATIONSHIP_FAILURE` | 标准成功 / 失败关系 |
| `Relation.DEFAULT` | `[Success, Failure]`，未声明注解时使用 |

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

// 拿到了响应但判定失败：脚手架生成的 support/HttpErrors 负责分类提示、剔除敏感字段，
// 并把 statusCode 与解析后的 body 放进 metadata
context.tellFailure(message, HttpErrors.httpError(response.statusCode(), response.body()));
context.tellFailure(message, HttpErrors.apiError("40035", errmsg, status, body));  // 业务码失败
```

`tellFailure` 会在原 payload 上写入 `error`，`with(...)` 的内容进入 `error.metadata`，
框架另外补 `env`、`workflowId`、`workflowNodeId`、`correlationId`、`workerId` 与 `error.id`：

```json
"error": {
  "code": "DINGTALK_HTTP_ERROR",
  "message": "请求无效（HTTP 400），请检查消息内容。响应：{\"errcode\":40035,\"errmsg\":\"...\"}",
  "metadata": { "statusCode": 400, "body": { "errcode": 40035, "errmsg": "..." } }
}
```

完整约定（何时写、`code` 命名、敏感字段处理）见 `coding-rules.md` 规范 6。

SDK 的 `cn.buildify.bundle.api.http.HttpFailure.toException()` 描述的是**入站**路由失败
（Webhook 鉴权、方法不允许等），它写入的键是 `status`、`path`、`requestId`。
**出站**调用三方接口失败一律用 `statusCode` / `body`，与成功输出的 `output.statusCode` 对齐，不要混用。

## Validator

`cn.buildify.bundle.api.validation.Validator`：在 `initialize()` 中链式校验参数，失败时抛
`FlowNodeException("VALIDATION_ERROR", message)`，`metadata` 带 `field` 与 `constraint`，节点不会带着错误配置启动。

```java
String url = Validator.of(parameters.path("url").asText(""), "url")
        .notBlank("url 不能为空")
        .matches("^(=|https?://).*", "url 必须以 http(s):// 开头")
        .get();

int timeout = Validator.of(parameters.path("timeout").asInt(30), "timeout")
        .range(1, 300, "timeout 必须在 1~300 秒之间")
        .get();
```

| 方法 | 说明 |
|---|---|
| `of(value)` / `of(value, fieldName)` | 创建；`fieldName` 写入 `metadata.field` |
| `notNull` / `notBlank` / `notEmpty` | 非空校验（字符串、集合） |
| `matches(regex, msg)` | 字符串正则 |
| `min` / `max` / `range` | 数值范围 |
| `must(predicate, msg)` | 自定义条件 |
| `get()` / `orElse(default)` | 取值 |

只在 `initialize()` 中用。`onMsg` 里抛出会被框架当作未捕获异常处理，按消息求值的参数应自己判断后
`tellFailure`。
