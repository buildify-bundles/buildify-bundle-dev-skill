# Node Service RPC（节点间调用）

`context.nodeService()` 是节点间 RPC 的**唯一入口**。旧的 `sendRequestEvent` / `sendResponseEvent`、
`RequestEvent` / `ResponseEvent`、`FlowNode.onRequestEvent` / `onResponseEvent` **已从 API 移除**，
禁止在新代码、文档、示例中出现。

## 命名规则

服务注册表按 `tenantId + bundleName:exposedServiceName` 唯一定位 endpoint。

- `@NodeService.value()` 是**服务类型/默认名**，不是多实例调用入口
- 调用时第一个参数必须是**实例暴露名**：`call("server1", "send")`，不是 `call("netty", "send")`
- 同 Bundle 内短名自动补当前 `bundleName`；跨 Bundle 传 `call("email-bundle:mailer", "send")`
- `exposedServiceName` 只能是 `[A-Za-z0-9._-]+`，**禁止含 `:`**（该字符仅作 bundle 分隔符）
- 多实例节点必须由节点参数提供实例名（如 `serviceName = "server1"` / `"server2"`）

## 自动注册（handler 无状态时推荐）

框架在 `initialize()` **成功后**扫描 `@NodeService` 内部类并注册；`initialize()` 失败不暴露服务。

```java
@Override
public void initialize(Context context, JsonValue parameters) {
    String serviceName = parameters.path("serviceName").asText(null);
    if (serviceName == null || !serviceName.matches("[A-Za-z0-9._-]+")) {
        throw new FlowNodeException("INVALID_SERVICE_NAME",
            "serviceName 不能为空，且只能包含字母、数字、点、下划线和中划线");
    }
}

@NodeService(value = "netty", nameParameter = "serviceName")
public static class NettyServiceHandler implements NodeServiceHandler {
    @NodeServiceMethod("send")
    public JsonValue send(NodeServiceContext ctx, JsonValue params) {
        return JsonValueFactory.objectNode().put("ok", true);
    }
}
```

`@NodeService.value()` 注释里的「参数为空则用 value」指注解属性 `nameParameter` 本身为空。
一旦写了 `nameParameter`，节点参数缺失、空白或含非法字符都**必须失败**，
**禁止**回退到 `value()`，否则多实例会退化成同一个服务名。扫描器
`AnnotationNodeServiceScanner.resolveExposedServiceName` 就是这个行为。

## 手动注册（handler 持有连接池 / 客户端 / server 实例）

```java
// ✅ 多实例：显式传实例暴露名
context.nodeService().registerHandler(serviceName, new MailerServiceHandler(this.pool));

// ❌ 多实例场景禁止：无法区分 server1 / server2
// context.nodeService().registerHandler(new MailerServiceHandler(this.pool));
```

手动注册与自动扫描命中同名时手动优先。节点 destroy / restart 时框架统一注销 endpoint
并取消 pending 调用。

## 调用

```java
context.nodeService()
    .call("server1", "send")
    .params(JsonValueFactory.objectNode().put("payload", "hello"))
    .timeout(Duration.ofSeconds(10))
    .execute()                                   // 返回 AsyncResult<JsonValue>
    .onSuccess(result -> context.tellSuccess(MessageBuilder
        .withPayload(JsonValueFactory.objectNode().put("output", result))
        .copyHeaders(message.getHeaders()).build()))
    .onFailure(e -> context.tellFailure(message, e))
    .onComplete(() -> context.complete(message));  // 异步路径，必须 complete

// 单向通知：不等响应，但当前节点消息仍按生命周期 complete
context.nodeService().call("server1", "send").params(params).notifyOneWay();
```

`params` 与返回值均为 `JsonValue`。`bundleVersion(version)` 为精确版本匹配；
`minBundleVersion()` 不作为新开发的默认能力。

## 测试态语义

Node Service **没有** `envScope` / `runtimeScope` 隔离维度，测试态与生产态都按
`tenantId + bundleName:exposedServiceName` 解析。流程联调中的调用**不会**把联调临时节点注册为
服务提供方，而是走 Worker 正式 `ActorSystem` 中已启动、已注册的 FlowNode 服务。
找不到 endpoint 或对应节点 actor 不存活时，按 `SERVICE_NOT_FOUND` / `NODE_NOT_ACTIVE` 处理，
不要在测试环境临时拉起 provider 兜底。

`MethodExecutor` 中可用 `ctx.nodeService().call(...)`，但**不能**注册 handler。
