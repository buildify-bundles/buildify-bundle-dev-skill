# 触发器背压

触发器是流程的入口，产生事件的速度不受下游约束。下游处理不过来时，引擎会拒收并丢弃消息，
如果触发器还在本地攒事件，内存会一直涨。本文规定触发器怎么限流、怎么缓冲、超限时怎么处理。

需要 `buildify-bundle-api` **3.1.0** 及对应版本的 Worker。用 3.1.0 编译的 Bundle 部署到旧 Worker 会报
`NoSuchMethodError`。

## 目录

- [引擎做了什么](#引擎做了什么)
- [API](#api)
- [通用规则](#通用规则)
- [拉取型：Cron、轮询、MQ、数据库监听](#拉取型cron轮询mq数据库监听)
- [推送型：WebSocket、Stream、SDK 回调](#推送型websocketstreamsdk-回调)
- [Webhook](#webhook)
- [MQ：用回调 nack](#mq用回调-nack)
- [禁止写法](#禁止写法)
- [使用文档怎么写](#使用文档怎么写)

## 引擎做了什么

| 层 | 上限 | 满了之后 |
|----|------|----------|
| 流程邮箱（触发器、节点回传都进这里） | 高优先级 1024 条，另有与普通队列共享的溢出区 1024 条 | 拒收 |
| 节点邮箱 | 4096 条，另有溢出区 1024 条 | 拒收 |
| Worker 全局积压（所有流程、节点的数据消息合计） | 默认 200000 条（`actors.system.max_total_pending`） | 拒收 |
| 执行池（`executeBlocking`） | 有界队列，到 75% 视为饱和 | 任务以 `RejectedExecutionException` 失败 |

拒收的消息会回调 `MsgCallback.onFailure`，打一条节流后的 warn 日志，并计入节点指标 `rejectedCount`。
消息**不会**重投。所以触发器必须在源头控制速度，而不是指望引擎缓冲。

## API

| 方法 | 用途 |
|------|------|
| `context.isBackpressured()` | 流程邮箱、任一直接下游节点邮箱过载，执行池饱和，或全局积压超过 80%，任一成立即为 `true`；回落到 50% 才恢复 |
| `context.tryTellSuccess(msg)` / `tryTellNext(msg, relations)` | 背压中或邮箱已满时**不入队**，返回 `false`，不回调 `onFailure` |
| `context.createTriggerMessage(payload, eventId, callback)` | 带回调的触发消息；下游拒收或处理失败时调 `onFailure` |
| `support/TriggerGuard`（脚手架生成） | `admit(context)`：同时判断背压与每秒上限，失败时自动计数；`tryEnter()` / `exit()`：防重叠；`recordDropped` / `recordEmitted`：节流后的黄色 / 绿色状态 |

返回 `false` 的消息没有发出，但仍要 `context.complete(msg)`（只统计触发器指标）。

## 通用规则

1. 发消息只用 `tryTellSuccess` / `tryTellNext`。`tellSuccess` 被拒收时触发器感知不到。
2. 每个触发器都带表单字段 `maxPerSecond`（默认 `0`，不限速；设为 1–1000 时才按该速率限速），用 `TriggerGuard` 实现。`0` 只关掉令牌桶，下游背压仍然生效。
3. 本地缓冲只能有界：`new ArrayBlockingQueue<>(容量)`，用 `offer` 写入，`offer` 返回 `false` 时丢弃计数。
4. 状态提示要节流：`TriggerGuard` 最多每 5 秒刷新一次「限流丢弃 N 条」，不要每条事件都调 `setStatus`。
5. `destroy()` 清空本地缓冲，调 `guard.reset()`，取消调度、关闭连接。

## 拉取型：Cron、轮询、MQ、数据库监听

拉取型能控制「什么时候拉」，背压时**不要拉**，而不是拉了再丢。

```java
private void poll(Context context) {
    if (!guard.tryEnter()) {          // 上一轮还在跑：跳过本轮
        guard.recordDropped(context);
        return;
    }
    try {
        int sent = 0;
        while (sent < MAX_EVENTS_PER_TICK) {
            if (!guard.admit(context)) {
                break;                    // 背压或超速：剩下的留给下一轮，不要先拉到内存
            }
            Record record = source.next(); // 一次只拉一条或一小批
            if (record == null) {
                break;
            }
            Message<JsonValue> msg = context.createTriggerMessage(toPayload(record), record.id());
            try {
                if (!context.tryTellSuccess(msg)) {
                    guard.recordDropped(context);
                    break;                // 游标不前进，下一轮重拉
                }
                source.commit(record);    // 入队成功后再推进游标 / 提交 offset
                guard.recordEmitted(context, "已调度");
                sent++;
            } finally {
                context.complete(msg);
            }
        }
    } finally {
        guard.exit();
    }
}
```

- 每轮条数有上限（`MAX_EVENTS_PER_TICK`，如 100），不要一次把所有分页拉完。
- 能控制游标的源（数据库增量、分页接口）在 `tryTellSuccess` 成功后再推进游标，被拒时下一轮重拉，不丢数据。
- MQ 消费者用客户端的 pause / resume 或 prefetch 上限：`isBackpressured()` 为 `true` 时 pause，恢复后 resume。

## 推送型：WebSocket、Stream、SDK 回调

推送型控制不了对方的速度，只能**限流并丢弃**。回调线程里直接判断，不要先塞进无界队列。

```java
client.onEvent(event -> {
    if (!guard.admit(context)) {
        return;                           // 已计数，状态显示黄色
    }
    Message<JsonValue> msg = context.createTriggerMessage(toPayload(event), event.id());
    try {
        if (context.tryTellSuccess(msg)) {
            guard.recordEmitted(context, "已连接");
        } else {
            guard.recordDropped(context);
        }
    } finally {
        context.complete(msg);
    }
});
```

确实需要把回调线程和发送解耦时，用有界队列，满了就丢：

```java
private final BlockingQueue<Event> buffer = new ArrayBlockingQueue<>(1000);

client.onEvent(event -> {
    if (!buffer.offer(event)) {
        guard.recordDropped(context);
    }
});
```

对方协议支持 ack 的（如钉钉 Stream、飞书长连接），能不 ack 就不 ack，让对方重投，比本地丢弃好。

## Webhook

能用核心包 `WebhookTriggerNode` 已有认证的接口不要做成这里的路由。只有按原文验签、对不上那些方式时才走 [coding-rules.md](../coding-rules.md)「按原文验签的回调触发器」。限流规则相同：在**读 body 之前**判断，超限直接返回 429，让调用方退避重试：

```java
if (!guard.admit(context)) {
    rc.response().statusCode(429).putHeader("Retry-After", "1")
            .contentType("application/json").write("{\"code\":429,\"msg\":\"too many requests\"}").end();
    return;
}
// ... 构建消息
if (!context.tryTellSuccess(msg)) {      // 与 admit 之间下游刚好满了
    guard.recordDropped(context);
    // 同样返回 429
}
```

节点已停止（`destroy` 后仍有请求进来）返回 503。只有 `tryTellSuccess` 返回 `true` 才回 200。

## MQ：用回调 nack

```java
Message<JsonValue> msg = context.createTriggerMessage(payload, record.id(), new MsgCallback() {
    @Override public void onSuccess() { }
    @Override public void onFailure(Throwable e) { consumer.nack(record); }  // 下游拒收或处理失败
});
try {
    if (context.tryTellSuccess(msg)) {
        consumer.ack(record);
    } else {
        consumer.nack(record);            // 没有入队：让 Broker 重投
    }
} finally {
    context.complete(msg);
}
```

回调随 `MessageBuilder.fromMessage(...)` 逐跳传递；下游节点用 `MessageBuilder.withPayload(...)` 生成的新消息不再带回调。
`onSuccess` 目前只在目标节点被禁用或不存在时调用，不代表整条流程跑完，**不要**在 `onSuccess` 里 ack。

## 禁止写法

| 写法 | 问题 | 改成 |
|------|------|------|
| `context.tellSuccess(msg)` | 被拒收时触发器不知道 | `tryTellSuccess` 并处理 `false` |
| `new LinkedBlockingQueue<>()`、`ConcurrentLinkedQueue`、`ArrayList` 当缓冲 | 无界，下游一慢就堆到 OOM | `new ArrayBlockingQueue<>(容量)` + `offer` |
| `Executors.newFixedThreadPool` / `newCachedThreadPool` / `newSingleThreadExecutor` | 内部队列无界 | `context.executeBlocking` 或 `context.getExecutor()` |
| `while (true) { ... tellSuccess ... }` | 以最快速度灌给下游 | 循环内 `guard.admit` + `tryTellSuccess` |
| 一次拉完所有分页再逐条发 | 全部数据先进内存 | 每轮最多 `MAX_EVENTS_PER_TICK` 条，游标续拉 |
| 每条事件都 `setStatus` | 高频刷状态拖慢 Worker | `TriggerGuard` 节流 |

校验脚本会对前四种记 WARNING。

## 使用文档怎么写

每个触发器节点在 `docs.md` 里写明：

- 参数表里的 `maxPerSecond`；
- 超限时的行为：丢弃并计数 / 跳过本轮 / 返回 429 + `Retry-After` / nack 重投；
- 被丢弃的事件会不会补发。

编排 Agent 据此判断是否需要在上游加重试，或调大 `maxPerSecond`。
