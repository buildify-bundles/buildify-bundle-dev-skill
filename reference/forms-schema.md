# 动态表单 Schema 规范

节点表单 `properties/<NodeName>.json` 与凭证表单 `credentials/<CredentialType>.json` 使用同一套
schema。后端原样透传，由前端 `ParameterInputList` 遍历 `properties` 渲染。

## 目录

- [1. 文件根结构](#1-文件根结构)
- [2. Property 字段完整定义](#2-property-字段完整定义)
- [3. uiComponent 选型决策树](#3-uicomponent-选型决策树)
- [4. 必填与校验](#4-必填与校验)
- [5. 表达式模式](#5-表达式模式)
- [6. 访问凭证字段](#6-访问凭证字段)
- [7. loadOptions 远程加载选项](#7-loadoptions-远程加载选项)
- [8. invokeMethod 与 TestButton](#8-invokemethod-与-testbutton)
- [9. displayOptions 条件显示](#9-displayoptions-条件显示)
- [10. bundle.json](#10-bundlejson)
- [11. 常见错误](#11-常见错误)

组件 `typeOptions` 逐项速查见 [forms-components.md](forms-components.md)。

## 1. 文件根结构

```json
{
  "defaultValue": { "method": "GET", "timeout": 30 },
  "properties": [
    { "name": "url", "label": "请求地址", "uiComponent": "Input", "required": true }
  ]
}
```

- 根数组字段名是 **`properties`**，不是 `parameters`
- `defaultValue`（根级，可选）：表单首次打开时预填的值，**必须与代码里的回落值一致**。
  例如代码写 `request.getString("region", "us-east-1")`，`defaultValue` 也要写 `"region": "us-east-1"`
- 只写有意义的非空默认值；语义为"空"的字段**省略该键**，不要写 `""`
- `Space`、`TestButton` 等纯 UI 控件不出现在 `defaultValue` 里

> 字段级还有一个 `default`（与 `name` 同级），用于集合类子字段的初始值。两者可并存：
> 根级 `defaultValue` 面向节点参数整体，字段级 `default` 面向单个字段。

## 2. Property 字段完整定义

```jsonc
{
  // ── 必填 ──
  "name": "fieldName",         // 字段唯一标识，camelCase，同级不重名，不含 . 或 [
  "uiComponent": "Input",      // 控件类型（不是 type）

  // ── 展示 ──
  "label": "字段标签",
  "placeholder": "请输入...",
  "hint": "字段下方小字说明",
  "description": "label 旁 tooltip",

  // ── 值 ──
  "default": null,             // 新建时的初始值

  // ── 校验 ──
  "required": true,            // 默认 false
  "rules": [],                 // 额外 async-validator 规则

  // ── 选项 ──
  "options": [],               // Select / Radio / Segmented 的静态选项，或集合类子字段

  // ── 表达式 ──
  "expression": true,          // 可传值字段默认 true；访问凭证 CredentialSelect 不要设
  "droppable": true,           // 与 expression 同开，便于从变量面板拖入

  // ── 条件显示 ──
  "displayOptions": { "show": { "otherField": ["value1"] } },

  // ── 控件专属 ──
  "typeOptions": {}
}
```

命名约定：`name` 用 camelCase；操作/工具类字段用 `_` 前缀（如 `_testConn`、`_spacer`）；
凭证字段以 `Credential` / `Cred` 结尾或直接用 `credentialsId`。

字段顺序建议：凭证 → 核心必填 → 动态联动 Select → 可选配置 Collection → TestButton/Space → 只读 Tag。

## 3. uiComponent 选型决策树

```
需要输入什么？
├─ 文本
│   ├─ 短单行                → Input
│   ├─ 密码/敏感             → Password
│   ├─ 含模板变量的字符串     → ExpressionInput（或 Input + "expression": true）
│   └─ 长文本/代码
│       ├─ SQL              → SqlEditor（#{msg.xxx} / ${msg.xxx}，禁止 {{ }}）
│       ├─ JS/Python/Java   → CodeEditor（typeOptions.lang）
│       ├─ JSON 文档（自由结构） → JsonEditor
│       ├─ JSON 文档含表达式   → JsonExpressionInput
│       └─ 证书/纯文本       → CodeEditor（lang:"text" + enableExpression:false）
├─ 数字                      → InputNumber ／ 有界调节 → Slider
├─ 布尔                      → Switch
├─ 颜色                      → ColorPicker ／ 边框 → BorderSelect
├─ 布尔逻辑表达式（SpEL）     → BooleanExpressionInput
├─ 从列表选
│   ├─ 单选 2～5 项、文案短   → Segmented（默认铺满宽度）
│   ├─ 单选 ≤5 项、单选按钮   → RadioGroup / RadioButtonGroup
│   ├─ 单选多项、需搜索或远程 → Select
│   ├─ 级联                  → Cascader
│   ├─ 画布节点              → NodeSelect
│   ├─ AI 模型               → ModelSelect
│   └─ 多选                  → CheckboxGroup
├─ 访问凭证                  → CredentialSelect
├─ 日期时间                  → DatePicker / DateTimePicker / TimePicker
├─ 结构化数据
│   ├─ 固定字段对象           → Fixed
│   ├─ 用户按需勾选的可选字段   → Collection（值为对象，不是数组）
│   ├─ 需要人逐项添加的数组    → FixedCollection（可增删行）
│   ├─ 工作流路由关系数组      → RelationCollection
│   └─ schema/远程驱动的对象   → DynamicSchemaForm
├─ 只读文字                  → Tag
├─ 视觉间距                  → Space
└─ 调用后端方法的按钮         → TestButton
```

需要人在界面上逐项维护的数组（请求头、查询参数、标签、收件人等）用 `FixedCollection`：
有添加按钮，可增删、可拖拽排序。不要用 `JsonEditor`、`JsonExpressionInput` 或 `CodeEditor`
让用户手写 JSON 数组。字符串列表同样用 `FixedCollection`，子字段只放一个 `Input`。
`Collection` 是可选字段对象，不能拿来做数组。画布分支连线才用 `RelationCollection`。

## 4. 必填与校验

`required: true` 写在字段顶层，不要写进 `rules`。两者可共存，前端取并集。

```json
{ "name": "port", "uiComponent": "InputNumber", "required": true, "default": 3306,
  "rules": [{ "type": "number", "min": 1, "max": 65535, "message": "端口范围 1~65535" }] }
```

常用 `rules` 格式：

```jsonc
{ "min": 2, "max": 100, "message": "长度 2~100 个字符" }          // 字符串长度
{ "type": "number", "min": 0, "max": 9999, "message": "..." }     // 数字范围
{ "pattern": "^https?://", "message": "必须以 http(s) 开头" }      // 正则（字符串形式）
```

字段值以 `=` 开头（表达式模式）时前端**自动跳过** `rules` 校验。集合子字段的 `rules` 写在子字段
自身上。`CredentialSelect` 校验的是凭证的 `name` 是否有值。

## 5. 表达式模式

节点、触发器、Webhook 表单里，**除访问凭证外，可传值字段默认开启表达式**，方便直接写入
`={{ msg.xxx }}` 或从变量面板拖入。省略 `expression` 时界面把它当 `false`，Agent 就无法传值。

```json
{ "name": "url", "uiComponent": "Input", "expression": true, "droppable": true,
  "placeholder": "https://api.example.com/{{ msg.path }}" }
```

| 状态 | 存储值 |
|---|---|
| 普通文本 | `"https://api.example.com/users"` |
| 表达式 | `"=https://api.example.com/{{ msg.userId }}"` |

| 控件 | 表达式 |
|---|---|
| `Input` / `Password` / `InputNumber` / `Select` / `Segmented` / `RadioGroup` / `RadioButtonGroup` / `CheckboxGroup` / `Switch` / `Slider` / `DatePicker` / `DateTimePicker` / `TimePicker` / `Cascader` / `ColorPicker` | **默认** `"expression": true` 且 `"droppable": true` |
| `CredentialSelect`（访问凭证） | **不要**设 `expression`。选的是已保存的凭证实例，不按消息求值 |
| `ExpressionInput` | 强制表达式模式，值始终带 `=` 前缀，不必再写 `expression` |
| `JsonExpressionInput` | 内置 `={{ }}`，不必再写顶层 `expression` |
| `CodeEditor` / `SqlEditor` / `JsonEditor` | 内置变量语法，**不要**设顶层 `expression`，用 `typeOptions.enableExpression` 控制 |
| `BooleanExpressionInput` | 值**不带** `=` 前缀，直接是表达式字符串 |
| `TestButton` / `Space` / `Tag` | 不产生参数，不要设 `expression` |

凭证表单 `credentials/*.json`（主机、密钥等）在保存时入库，不按消息求值，**不要**开 `expression`。

## 6. 访问凭证字段

```json
{
  "name": "credentialsId",
  "label": "MySQL 凭证",
  "uiComponent": "CredentialSelect",
  "required": true,
  "typeOptions": {
    "credentialsType": "MysqlCredential",
    "displayName": "MySQL 凭证"
  }
}
```

- 字段名是 **`credentialsType`**，`credentialsName` 已废弃，禁止使用
- 值为 **PascalCase**，与 `@CredentialsDescription(type)` 逐字一致（大小写敏感）
- 代码中 `context.getCredentials("credentialsId")` 传的是**本字段的 `name`**，不是 `credentialsType`
- 同一节点有多个凭证框时，各自有独立 `name`，分别 `getCredentials`
- 凭证值不写入 `parameters`，而是写入节点 `data.credentials[<字段 name>]`
- **不要**设 `"expression": true` 或 `"droppable": true`。访问凭证绑定的是控制台里已保存的凭证，不是 `={{ msg.xxx }}`

## 7. loadOptions 远程加载选项

用于 `Select` 动态拉取选项。**两种 provider 的凭证字段完全不同，不要混用**：

```json
// provider = "credentials" —— 调用 CredentialsProvider.execute()
"typeOptions": {
  "loadOptions": {
    "method": "getDatabases",
    "provider": "credentials",
    "trigger": "auto",
    "credentialsType": "MysqlCredential",
    "dependsOn": ["host", "port", "username", "password"]
  }
}

// provider = "bundle" —— 调用 MethodExecutor
"typeOptions": {
  "loadOptions": {
    "method": "getBuckets",
    "provider": "bundle",
    "trigger": "auto",
    "credentialsRef": "credentialsId",
    "dependsOn": []
  }
}
```

| 字段 | provider=credentials | provider=bundle |
|---|---|---|
| `method` | 与 `request.is("...")` 分支一致 | 与 `MethodExecutor.getMethodName()` 一致 |
| `credentialsType` | **必填**，PascalCase 凭证标识 | 不使用 |
| `credentialsRef` | 不使用 | **必填**，同表单内 `CredentialSelect` 字段的 `name` |
| `trigger` | `"auto"` 依赖满足自动加载；`"manual"` 手动刷新 | 同左 |
| `dependsOn` | 凭证表单字段名列表 | **必须显式写出**，无依赖时写 `[]` |

`dependsOn` 读取路径：`provider=bundle` 读 `nodeValues.parameters.*`；
`provider=credentials` 读 `nodeValues.data.*`（凭证表单字段）。

`credentialsRef` 已隐含对凭证字段的依赖，**禁止**把它引用的凭证字段名重复写进 `dependsOn`。

**trigger 选择**：无依赖或依赖全为必填 → `auto`；依赖含可选字段、或接口慢（>2s）→ `manual`。

**离线可用性【强制】**：凡用了 `loadOptions` 的 `Select`，必须在同层 `typeOptions` 声明回退交互，
否则远程不可达时用户无法配置。键名用 kebab-case，与平台前端约定一致：

```json
"typeOptions": {
  "allow-create": true,
  "clearable": true,
  "filterable": true,
  "loadOptions": { "...": "..." }
}
```

后端方法返回格式：`[{ "value": "db1", "label": "database_1", "description": "可选" }]`

## 8. invokeMethod 与 TestButton

```json
{
  "name": "_testConn",
  "label": "测试连接",
  "uiComponent": "TestButton",
  "typeOptions": {
    "invokeMethod": {
      "method": "test",
      "provider": "credentials",
      "credentialsType": "MysqlCredential",
      "dependsOn": ["host", "port", "username", "password"],
      "buttonText": "测试连接",
      "buttonType": "primary"
    }
  }
}
```

- 调用配置**必须**在 `typeOptions.invokeMethod` 内，不能平级写在 `typeOptions` 根上
- 测试连接的 `method` 固定为 **`"test"`**，对应 API 常量
  `CredentialsMethodRequest.TEST_CONNECTION`，实现中用 `request.isTestConnection()` 判断
- `provider="credentials"` 时必须给 `credentialsType`；`provider="bundle"` 时前端自动携带当前
  节点所有凭证的 credentialsId
- 后端返回格式固定：`{ "success": true/false, "message": "说明文字" }`

> 旧写法把 method 写成 `"testConnection"`，与 `isTestConnection()` 实际匹配的 `"test"` 不符。
> 以 API 常量为准，写 `"test"`。

## 9. displayOptions 条件显示

```json
"displayOptions": {
  "show": { "method": ["POST", "PUT"], "sendBody": [true] },
  "hide": { "authType": ["none"] }
}
```

- 引用的字段必须是**同级兄弟**：顶层 `properties` 引用顶层字段，`Fixed.options` 内引用同
  `options` 内的字段。**不支持** `"ssl.enabled"` 这类嵌套路径
- 同一对象内多字段为 **AND**，同一数组内多值为 **OR**
- 条件值必须是数组，单值也要写成 `[true]` / `["mysql"]`

## 10. bundle.json

允许两种顶层结构，**同一文件内不要混用**。

```json
// 分组型：画布按分组标签聚合
{
  "bundleName": "my-org/my-bundle",
  "groups": [{
    "label": "分组名称",
    "nodes": [{
      "name": "MyNode", "label": "节点 UI 名称", "summary": "简述（≤10字）",
      "icon": "default.svg",
      "parameters": { "method": "GET", "timeout": 30 }
    }]
  }]
}

// 扁平型：根级 nodes，适用于机器人等扁平列表
{ "nodes": [{ "name": "SendTextMsgNode",
              "label": "文本消息", "summary": "推送文本消息",
              "icon": "default.svg", "parameters": {} }] }
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `bundleName` | 推荐 | 逻辑名可含 `/`，与发布时 `-n/--name` 一致 |
| 节点 `name` | 是 | 与 `@FlowNodeDescription(name)` 完全一致 |
| 节点 `label` | 是 | UI 显示名 |
| `summary` | 否 | **≤10 字**，超长被截断 |
| `icon` | 推荐 | 默认 `"default.svg"`。需要自定义图标时再改成对应文件名 |
| `parameters` | 否 | 与该节点 `properties` 的 `defaultValue` 对齐；无默认值写 `{}` 或省略 |

每个节点都写 `"icon": "default.svg"`。只有用户明确要换图标时，才把该字段改成其它文件名。
不要在工程里生成或提交 SVG：图标文件仍由控制台上传并管理
（`GET/POST/DELETE .../bundles/{bundleId}/icons`），不打进 JAR，也不放在
`src/main/resources`。

不需要根级 `credentials` 数组，凭证通过 SPI 自动发现。

## 11. 常见错误

| # | 错误 | 正确 |
|---|---|---|
| 1 | 根数组写成 `{"parameters": [...]}` | `{"properties": [...]}` |
| 2 | `CredentialSelect` 用 `credentialsName` | 用 `credentialsType`（PascalCase） |
| 3 | `required` 塞进 `rules` | 写在字段顶层 |
| 4 | 集合子字段写成 `"headers.key"` | 只写 `"key"`，路径由前端拼 |
| 5 | `FixedCollection` 的 `defaultValue` 缺子字段 | 必须包含 `options` 中所有子字段 |
| 6 | `displayOptions` 引用 `"ssl.enabled"` | 只能引用同级兄弟字段 |
| 7 | `provider=credentials` 却写 `credentialsRef` | 该模式不用此字段，改用 `credentialsType` |
| 8 | `RelationCollection` 在 `options` 定义 `_id` | `_id` 由组件自动生成 |
| 9 | `trigger:"auto"` 但 `dependsOn` 含可选字段 | 改 `"manual"` |
| 10 | 给 `CodeEditor` 设顶层 `expression: true` | 用 `typeOptions.enableExpression` |
| 11 | 存证书用 `CodeEditor` 未关表达式 | 必须 `"enableExpression": false`，否则值带 `=` 前缀 |
| 12 | 用了 `loadOptions` 却无 `allow-create`/`clearable` | 远程失败时用户完全无法配置 |
| 13 | `provider=bundle` 省略 `dependsOn` | 必须显式写出，无依赖写 `[]` |
| 14 | 字段用 `type` 而非 `uiComponent` | 一律 `uiComponent` |
| 15 | 省略 `icon`，或在工程里生成 SVG | 默认写 `"icon": "default.svg"`；要自定义再改文件名。SVG 由平台上传，不打进 JAR |
| 16 | 可传值字段省略 `expression` | 默认 `"expression": true` 与 `"droppable": true`，否则无法写入 `={{ msg.xxx }}` |
| 17 | `CredentialSelect` 设了 `expression: true` | 访问凭证不要开表达式 |
| 18 | 数组让用户手写 JSON | 用 `FixedCollection`，界面可动态添加项 |
| 19 | `Segmented` 写了 `loadOptions`，或选项超过 5 个 | 只做静态单选；选项多、要搜索或远程加载时改用 `Select` |
