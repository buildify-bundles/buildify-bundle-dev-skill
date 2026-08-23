# 生命周期、热更新与资源释放

## 目录

- [节点生命周期](#节点生命周期)
- [参数热更新](#参数热更新)
- [凭证热更新](#凭证热更新)
- [ClassLoader 回收生命周期](#classloader-回收生命周期)
- [开发者必须释放的资源](#开发者必须释放的资源)
- [常见泄漏写法](#常见泄漏写法)
- [如何验证可回收](#如何验证可回收)
- [诊断 JVM 参数](#诊断-jvm-参数)

## 节点生命周期

```
Bundle 加载
    ↓
initialize(context, parameters)          ← 参数初始化、资源申请
    ↓
[RUNNING]
    ↓
support(message) → onMsg(context, message) × N
    ↓
┌── 参数变更 ─────────────────────────────────────────┐
│ isRestartRequired() = false                         │
│   → onParametersUpdated(ctx, newParams, oldParams)  │ 就地刷新，不重启
│ isRestartRequired() = true                          │
│   → destroy(context) → initialize(context, newParams)│ 重建资源
└─────────────────────────────────────────────────────┘
┌── 凭证变更 ─────────────────────────────────────────┐
│ onCredentialsUpdated() = true  → 回到 [RUNNING]     │
│ onCredentialsUpdated() = false → destroy + initialize│
└─────────────────────────────────────────────────────┘
    ↓
destroy(context)                          ← 资源释放，必须幂等
```

联调（Test）环境下 `context.complete(message)` 只表示**本条入站消息**处理完毕，不会销毁节点
Host。同一 `executionId` 内节点实例保持到 workflow 结束（`shutdown` 时统一 `destroy()`），
与生产 Actor 常驻语义一致。异步路径仍须每条分支调用 `complete`，以便引擎统计在途消息。

## 参数热更新

节点重启 = `destroy()` + `initialize()`，会丢失瞬态状态并重新申请资源。只影响内存中轻量配置的
变更应走热更新。推荐把参数应用逻辑抽成 `applyParameters()`，由两处复用：

```java
@Override
public void initialize(Context context, JsonValue parameters) {
    applyParameters(parameters);
}

@Override
public boolean isRestartRequired(JsonValue newParameters, JsonValue oldParameters) {
    // cron 变化需要取消旧定时任务并重新注册，交给重启流程
    return !Objects.equals(newParameters.path("cron"), oldParameters.path("cron"));
}

@Override
public void onParametersUpdated(Context context, JsonValue newParameters, JsonValue oldParameters) {
    applyParameters(newParameters);
}

private void applyParameters(JsonValue parameters) {
    this.limit = parameters.path("limit").asInt(100);
    this.dynamicParameters = JsonValueFactory.objectNode()
        .put("template", parameters.path("template"));
}
```

**判断标准**：
- 只影响内存字段（label、limit、表达式模板）→ 热更新，返回 `false`
- 影响生命周期资源（Webhook 路由、cron、监听 topic、连接地址、连接池、凭证）→ 返回 `true`

热更新只承诺影响后续消息，**不保证**处理中的消息立即切到新参数。需要强一致切换时返回 `true`。

## 凭证热更新

框架优先调用 `onCredentialsUpdated()`，默认实现返回 `false` 触发重启。基于凭证构建了可替换客户端
的节点可就地重建：

```java
@Override
public boolean onCredentialsUpdated(Context context, String type, String name) {
    if (!"MyApiCredential".equals(type)) {
        return false;      // 无关凭证类型，交回框架处理
    }
    this.client = buildClient(context.getCredentials("apiKey"));
    return true;
}
```

方法内抛异常时框架同样回退为重启节点，无需自行兜底。

## ClassLoader 回收生命周期

每个 Bundle 由独立 `BundleClassLoader` 加载。**只要还有一处强引用指向 Bundle 中的任意类或对象，
整个 ClassLoader 及其加载的全部类都无法回收**，表现为 Metaspace 持续增长，最终 Worker 需重启。

```
ACTIVE      引用计数 > 0，节点正在使用
   ↓ 最后一个节点释放引用
IDLE        引用计数 = 0，开始计空闲时长
   ↓ 连续空闲超过 idle-retention（默认 30 分钟），BundleCleaner 关闭
CLOSED      已执行 BundleLoader.close()，WeakReference 追踪等待 GC
   ↓ JVM 回收
COLLECTED   正常终态
```

对外可观测阶段 `reclaimPhase`：

| 值 | 含义 |
|---|---|
| `zero_ref` | 引用计数为 0，尚未 close，等待 idle 阈值 |
| `pending_gc` | 已 close，等待时长未超阈值，正常状态 |
| `awaiting_gc_cycle` | 已 close 超阈值但期间 JVM 未执行过 old gen GC —— 不告警 |
| `gc_timeout` | 已 close 超阈值且**确认执行过** GC 仍未回收 —— **疑似泄漏** |

只有 `gc_timeout` 需要排查。同名同版本 Bundle 已重新加载并在使用时，旧 ClassLoader 的
pending / timeout 状态不会对外展示，避免升级过程误报。

### 默认阈值

| 配置项 | 默认值 | 环境变量 |
|---|---|---|
| `worker.bundle.reclaim.idle-retention` | `30m` | `BUNDLE_IDLE_RETENTION` |
| `worker.bundle.reclaim.cleanup-interval` | `1m` | `BUNDLE_CLEANUP_INTERVAL` |
| `worker.bundle.reclaim.cleanup-initial-delay` | `5m` | `BUNDLE_CLEANUP_INITIAL_DELAY` |
| GC 超时阈值 | `30s` | — |

默认配置下自动回收窗口约 31 分钟。开发联调时可调小 `idle-retention` 快速复现。

### 框架在 close 时做了什么

1. 调用所有 `BundleActivator.stop(context)`
2. 清空框架缓存的 FlowNode / MethodExecutor / CredentialsProvider 实例
3. 注销由本 ClassLoader 加载的 JDBC 驱动
4. 尽力清除各线程上钉住本 ClassLoader 的 `ThreadLocal`（含 Netty `FastThreadLocal` slow path）
5. 关闭 `BundleClassLoader`，释放 JAR 句柄

之后宿主兜底注销该 ClassLoader 遗留的 HTTP 路由，再用 `WeakReference` 追踪等待 GC。
**这些是兜底不是免责**：步骤 3、4 依赖反射，缺少 `--add-opens` 时静默跳过；路由兜底只覆盖
HTTP Router 一处注册表。

## 开发者必须释放的资源

在 `FlowNode.destroy()` 和 `BundleActivator.stop()` 中逐项确认：

| 资源 | 释放方式 | 不释放的后果 |
|---|---|---|
| Webhook 路由 | `context.getRouter().unregister(route)` | 路由表持有 handler lambda |
| Cron 定时任务 | `future.cancel(true)` | 任务持有 Runnable 引用直到原定时刻 |
| `getExecutor()` 延迟任务 | `future.cancel(true)` | 同上 |
| 自建线程 / 线程池 | `shutdownNow()` 并 `join` | Runnable、TCCL、ACC 都会钉住 |
| `ThreadLocal` | `threadLocal.remove()` | 线程存活期间永久持有 value |
| 静态缓存 / 单例 Map | 显式 `clear()` 并置 `null` | 静态字段属于 Class，Class 属于 ClassLoader |
| 数据库连接池 | `close()` | 池内线程 + JDBC 驱动 |
| `SandboxExecutor` | `executor.close()` | 脚本引擎上下文常驻 |
| 节点服务 handler | `context.nodeService().unregisterHandler(name)` | 注册表持有 handler |
| HTTP 客户端 / SDK | 按 SDK 文档关闭 | 内部线程常驻 |

`destroy()` 必须**幂等**，框架可能在异常路径上重复调用：

```java
@Override
public void destroy(Context context) {
    if (route != null) { context.getRouter().unregister(route); route = null; }
    if (future != null) { future.cancel(true); future = null; }
    if (sandboxExecutor != null) {
        try { sandboxExecutor.close(); }
        catch (Exception e) { log.warn("[MyNode] 关闭沙箱失败", e); }
        sandboxExecutor = null;
    }
    if (httpClient != null) { httpClient.close(); httpClient = null; }
    CACHE.clear();
}
```

## 常见泄漏写法

```java
// ❌ 静态缓存永不清理 —— 最常见的泄漏源
private static final Map<String, Client> CLIENTS = new ConcurrentHashMap<>();
// ✅ 在 BundleActivator.stop() 或 destroy() 中 clear()

// ❌ 自建线程未停止，且 Runnable 由 bundle 加载
new Thread(() -> pollForever()).start();
// ✅ 保存引用，destroy() 中中断并 join；或改用 context.getExecutor()

// ❌ ThreadLocal 只 set 不 remove
SESSION.set(session);
// ✅ try-finally 中 SESSION.remove()

// ❌ 注册了路由却没在 destroy() 中注销
context.getRouter().register(route);
```

> **Netty 提示**：Bundle 自带 Netty 时 `io.netty.*` 类名与宿主重名。框架诊断只统计能唯一归属于
> Bundle 的栈帧，宿主 Netty 线程停在 `takeTask` 不算 pin。日志出现大量 Netty 栈帧却无 CONFIRMED
> 结论时，真正原因通常是 `FastThreadLocal`、静态缓存或线程 ACC。

框架已对 JDK 层面的坑做了兜底：`CompletableFuture.orTimeout` / `delayedExecutor` 的进程级调度线程
在加载任何 Bundle 之前预创建，避免其 `AccessControlContext` 钉住首个 BundleClassLoader；
Worker 自建线程统一使用宿主 ACC 与 TCCL。Bundle 侧无需特殊处理。

## 如何验证可回收

### 方式一：控制台接口（推荐）

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/v1/workers/{workerId}/bundles/reclaimable` | GET | 列出待回收 Bundle 及 `reclaimPhase` |
| `/api/v1/workers/{workerId}/bundles/reclaimable/gc` | POST | 强制关闭引用为 0 的 ClassLoader 并触发 GC |

列表字段：`bundleName`、`bundleVersion`、`sha256`、`reclaimPhase`、`reclaimPhaseLabel`、
`idleMs`、`gcPendingMs`。手动 GC 返回：`closedLoaderCount`、`collectedCount`、`gcTimeoutCount`。

流程：停用使用该 Bundle 的全部工作流 → 调手动 GC 接口 → 查列表。
Bundle 消失即回收成功；停在 `gc_timeout` 说明存在泄漏。

### 方式二：Worker 日志

```
ERROR c.b.bundle.core.ClassLoaderGcTracker : ClassLoader GC timeout for bundle <name>:<version>:<sha256> ...
```

日志会指出具体持有者（JDBC 驱动、静态字段、ThreadLocal、线程 Runnable、TCCL、线程 ACC）。

### 方式三：单元测试（开发自测）

关键在于**断开测试代码本身对 ClassLoader 的所有强引用**后再触发 GC：

```java
@Test
void bundleClassLoaderIsCollectedAfterDestroy() throws Exception {
    WeakReference<ClassLoader> loaderRef = runAndRelease();
    awaitCollected(loaderRef);
    assertThat(loaderRef.get())
        .as("BundleClassLoader 必须在节点 destroy 后被回收").isNull();
}

/** 独立方法中完成加载与释放，返回后局部变量全部出栈 */
private WeakReference<ClassLoader> runAndRelease() throws Exception {
    URLClassLoader loader = new URLClassLoader(new URL[]{bundleJarUrl},
        getClass().getClassLoader());
    Class<?> nodeType = Class.forName("com.example.bundle.nodes.MyNode", true, loader);
    FlowNode node = (FlowNode) nodeType.getDeclaredConstructor().newInstance();

    node.initialize(context, parameters);
    node.onMsg(context, message);
    node.destroy(context);                        // ← 被验证的资源释放逻辑

    WeakReference<ClassLoader> ref = new WeakReference<>(loader);
    loader.close();
    return ref;
}

private static void awaitCollected(WeakReference<ClassLoader> reference) throws InterruptedException {
    for (int i = 0; i < 40 && reference.get() != null; i++) {
        System.gc();
        Thread.sleep(50);
    }
}
```

> 常见误区：把 `node`、`Class` 对象或 `loader` 存在测试类字段里，或被 lambda 捕获，
> 会导致断言必然失败。`System.gc()` 只是建议，需循环重试；测试时不要加 `-XX:+DisableExplicitGC`。

## 诊断 JVM 参数

框架的反射诊断在 JDK 17+ 需显式开放模块，否则降级为"疑似"结论：

```
--add-opens java.base/java.lang=ALL-UNNAMED
--add-opens java.base/java.lang.ref=ALL-UNNAMED
--add-opens java.base/java.security=ALL-UNNAMED
```

反射仍找不到持有者时，让框架在 GC 超时时自动写堆转储，再用 MAT 对 `BundleClassLoader` 做
Path-to-GC-Roots 分析：

```
-Dbuildify.bundle.gc-diagnostics.heap-dump-dir=/tmp/bundle-dumps
```

> 堆转储会暂停 JVM 并产生与堆等大的文件，仅限排障，生产慎用。
> `-Dbuildify.bundle.gc-diagnostics.defined-class-log-limit`（默认 30）控制超时日志中展示的类数量。
