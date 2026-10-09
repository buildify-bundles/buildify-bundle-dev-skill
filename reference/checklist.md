# Bundle 提交前检查清单

`scripts/validate_bundle.py` 可自动检查其中大部分项；标注 🔍 的需人工确认。

## 项目结构

- [ ] `buildify-bundle-api` 依赖 `scope` 为 `provided`
- [ ] 使用 `maven.compiler.release=21` 而非 `source`/`target`
- [ ] `maven-shade-plugin` 配置了 `ServicesResourceTransformer`
- [ ] `bundle.json` 位于 `src/main/resources` 根目录
- [ ] 每个节点 `icon` 为 `"default.svg"`，仅在需要自定义图标时修改文件名
- [ ] 未把 SVG 打进 `src/main/resources`（图标文件由平台上传管理）
- [ ] 模块根目录存在 `README.md` 与 `CHANGELOG.md`

## FlowNode

- [ ] 每个 `FlowNode` 标注了 `@FlowNodeDescription(name = "...")`
- [ ] `@FlowNodeDescription.name` 与 `bundle.json` 节点 `name` **完全一致**
      （分组型 `groups[].nodes[]`，扁平型根级 `nodes[]`）
- [ ] 参数读取使用 `parameters.path()`，**不使用** `parameters.get()`
- [ ] 同步路径在 `onMsg` 返回前完成 `tell*`，**没有**再调用 `context.complete()`
      （框架在 `onMsg` 返回时自动收尾；本次 `onMsg` 未调用 `executeBlocking`）
- [ ] 所有异步回调（`sendAsync` / `executeBlocking` / `nodeService().execute()`）在**每条**
      结束路径上都对**入站** `message` 调用了 `complete`；推荐用 `onComplete` 或 `finally` 统一收尾
- [ ] 触发器只 `tellSuccess(createTriggerMessage(...))`，没有对这条新消息 `complete`
- [ ] 含表达式的参数在 `initialize()` 存入 `dynamicParameters`，`onMsg()` 用
      `resolveExpressions` 解析
- [ ] `JsonExpressionInput` 字段直接 `parameters.path(...)` 填入 `dynamicParameters`，
      **未**在服务端多做一次 `JsonValueFactory.fromJson(...asText())`
- [ ] **非触发器**节点输出放入 payload 的 `output` 字段，不散落在根级
- [ ] 已知错误使用 `FlowNodeException` 结构化，不直接 `throw new RuntimeException(...)` /
      `IllegalArgumentException(...)`
- [ ] `destroy()` 中释放所有资源，且实现幂等
- [ ] 未使用已移除的旧事件 API：`sendRequestEvent` / `sendResponseEvent`、
      `RequestEvent` / `ResponseEvent`、`onRequestEvent` / `onResponseEvent`
- [ ] 🔍 无需重启的参数变更实现了 `onParametersUpdated()`，`isRestartRequired()` 做了细粒度判断
- [ ] 🔍 影响生命周期资源（路由、cron、连接池、凭证）的参数变更让 `isRestartRequired()`
      返回 `true`
- [ ] 🔍 `onFailure` 中日志分级：`FlowNodeException` 用 `warn`，未知异常用 `error` 并保留堆栈

## 触发器节点

- [ ] 注解同时设置 `isTrigger = true, hasInput = false`
- [ ] `initialize()` 中区分了 `context.isTest()` 测试/生产模式
      （Webhook 等被动触发器两种模式都要注册路由，不强制分支）
- [ ] 发出的**每条消息**（成功、失败、测试）都通过 `context.createTriggerMessage(payload)` 创建
- [ ] 触发 payload **未**再包一层 `output`，业务字段直接在根级
- [ ] `destroy()` 中取消了定时任务 / 注销了 HTTP 路由

## 凭证

- [ ] 每个 `CredentialsProvider` 标注了 `@CredentialsDescription(type = "...")`
- [ ] 凭证类型标识为 **PascalCase**（如 `MysqlCredential`），未用全小写 / snake_case / kebab-case
- [ ] `propertiesFile` 为 `credentials/<标识>.json`，文件名与标识**逐字一致**（含大小写）
- [ ] 节点表单 `CredentialSelect` 的 `typeOptions.credentialsType` 与该标识逐字一致，
      **未使用**已废弃的 `credentialsName`
- [ ] `context.getCredentials(...)` 入参为表单 `CredentialSelect` 字段的 `name`，
      **未误用**凭证类型标识
- [ ] `TestButton` 配置在 `typeOptions.invokeMethod` 内，**不在** `typeOptions` 根级
- [ ] 测试连接的 `invokeMethod.method` 值为 `"test"`，实现中用 `request.isTestConnection()` 判断
- [ ] `invokeMethod.credentialsType`（provider=credentials 时）与凭证标识一致
- [ ] 凭证 JSON 的 `defaultValue` 与代码里的回落值对齐
      （代码 `getString("region","us-east-1")` → `defaultValue` 也写该值）
- [ ] 🔍 测试连接成功消息含实际连接目标与关键资源数量；失败消息按 HTTP 状态码或网络错误
      **分类提示**，未直接暴露原始异常 `getMessage()`
- [ ] 🔍 凭证字段（密码、Token）未写入日志或消息 payload

## 表单配置

- [ ] 根数组字段名为 `properties`，不是 `parameters`
- [ ] 字段使用 `uiComponent` 属性（**不是** `type`）
- [ ] `defaultValue` 只写有意义的非空默认值，语义为空的字符串省略该键
- [ ] `bundle.json` 的 `parameters` 与各节点 `defaultValue` 保持对齐
- [ ] `required` 写在字段顶层，未塞进 `rules`
- [ ] `loadOptions`：`provider=credentials` 配 `credentialsType`；`provider=bundle` 配
      `credentialsRef`（指向同表单 `CredentialSelect` 的 `name`）且 `dependsOn` 显式写出
      （无依赖写 `[]`）
- [ ] `credentialsRef` 引用的凭证字段名**未**重复写进 `dependsOn`
- [ ] 凡 `Select` 用了 `loadOptions`，同层 `typeOptions` 配了 `allow-create` 与 `clearable`
      （按需 `filterable`），避免远程不可达时无法配置
- [ ] `displayOptions` 只引用同级兄弟字段，条件值为数组
- [ ] `CodeEditor` 存证书 / 纯文本时设了 `"enableExpression": false`
- [ ] 2～5 个互斥短文案用 `Segmented`；选项多、要搜索或远程加载时用 `Select`（`Segmented` 不支持 `loadOptions`）
- [ ] 节点 / 触发器 / Webhook 表单中，可传值字段设了 `expression: true` 与 `droppable: true`
- [ ] `CredentialSelect`（访问凭证）未设 `expression`；`credentials/*.json` 也未开表达式
- [ ] 未给编辑器类组件（`CodeEditor` / `SqlEditor` / `JsonEditor`）设顶层 `expression: true`
- [ ] 需要人工逐项填写的数组使用 `FixedCollection`（可增删），未用 `JsonEditor` 手写 JSON 数组
- [ ] `FixedCollection` 的 `defaultValue` 包含 `options` 中所有子字段
- [ ] 集合类子字段 `name` 不含父级路径前缀
- [ ] 🔍 `summary` ≤ 10 字

## Node Service RPC（如使用）

- [ ] handler 使用 `@NodeService` / `@NodeServiceMethod`，签名为
      `(NodeServiceContext ctx, JsonValue params)`
- [ ] 多实例服务通过 `@NodeService(nameParameter = "serviceName")` 或
      `registerHandler(serviceName, handler)` 注册实例暴露名
- [ ] `serviceName` 已校验为 `[A-Za-z0-9._-]+`，未含 `:`
- [ ] 配置 `nameParameter` 时，参数缺失或为空会失败，**未**回退到 `@NodeService.value()`
- [ ] 有状态 handler（持连接池 / 客户端 / server 实例）用
      `registerHandler(exposedServiceName, handler)`，未只调用 `registerHandler(handler)`
- [ ] 调用方使用**实例暴露名**：`call("server1", "send")`；跨 Bundle 用
      `call("bundleName:server1", "send")`
- [ ] `execute()` 回调结束后对入站消息 `complete`；`notifyOneWay()` 同样遵守消息生命周期
- [ ] `MethodExecutor` 中只 `call(...)`，未调用任何 `registerHandler(...)`

## SandboxExecutor

- [ ] `destroy()` 中调用了 `executor.close()`

## 资源释放与 ClassLoader 卸载

- [ ] `Router.register()` 的每条路由都在 `destroy()` 中 `unregister()`
- [ ] `schedule()` / `getExecutor().schedule()` 返回的 `ScheduledFuture` 都在 `destroy()` 中
      `cancel(true)`
- [ ] 自建线程 / 线程池在 `destroy()` 或 `BundleActivator.stop()` 中已停止
- [ ] `ThreadLocal` 使用后调用了 `remove()`
- [ ] 静态缓存、单例 Map 在 `BundleActivator.stop()` 中已 `clear()`
- [ ] 数据库连接池、HTTP 客户端等第三方资源已关闭
- [ ] 注册的节点服务 handler 已 `unregisterHandler()`
- [ ] 🔍 已通过控制台待回收接口或 `WeakReference` 单测确认 ClassLoader 可被回收

## SPI 注册

- [ ] 所有 `FlowNode` 已注册到 `META-INF/services/cn.buildify.bundle.api.FlowNode`
- [ ] 所有 `CredentialsProvider` 已注册到
      `META-INF/services/cn.buildify.bundle.api.credentials.CredentialsProvider`
- [ ] 所有 `MethodExecutor` 已注册到 `META-INF/services/cn.buildify.bundle.api.MethodExecutor`
- [ ] `BundleActivator`（若有）已注册
- [ ] SPI 文件每行一个完整类名，UTF-8 编码，无该类型实现时不创建文件
- [ ] `bundle.json` 中无 `credentials` 数组（凭证通过 SPI 自动发现）

## README / CHANGELOG

- [ ] `README.md` 含节点一览表格（名称、类型、说明）
- [ ] 每个节点有参数说明和 JSON 输出字段示例
- [ ] 含构建命令（`mvn package`）与产物路径
- [ ] 关键依赖以表格列出（含版本和 scope）
- [ ] `CHANGELOG.md` 仅一节，标题版本与 `pom.xml` `<version>` 一致，正文为用户可见变更
- [ ] 🔍 CHANGELOG 正文未夹带仓库 / CLI / spec 元信息

## 构建与发布

- [ ] `mvn -q clean package` 通过（必须含 `clean`）
- [ ] 产物 JAR 内含 `bundle.json`、`properties/`、`credentials/`、`META-INF/services/`
- [ ] 上传时 `bundleName` / `-v` / JAR 文件名三者版本一致
- [ ] `bundle upload` 带了 `--release-notes-file`
- [ ] `--overwrite` 仅用于 `-SNAPSHOT` 版本
- [ ] 多把发布密钥时命令带 `--profile`；用户未要求时不改 `[publish].current`
- [ ] 仓库有 `.buildify-workspace` 时，所用密钥的 `tenantId` 与该文件一致
