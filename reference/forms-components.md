# uiComponent 逐组件速查

每个控件的 `typeOptions` 字段、值格式与注意事项。schema 通用结构见
[forms-schema.md](forms-schema.md)。

## 目录

- [文本类](#文本类)
- [数值与开关](#数值与开关)
- [选择类](#选择类)
- [日期时间](#日期时间)
- [集合类](#集合类)
- [操作与展示](#操作与展示)

`typeOptions` 里的字段会**直接展开为 attrs** 传给底层 Element Plus 控件，因此该控件原生支持的
属性（`clearable`、`disabled`、`size` 等）通常都可以直接写。

## 文本类

### Input / Password

值类型 `String`。底层 `el-input`。

```jsonc
"typeOptions": {
  "maxlength": 200,
  "showWordLimit": true,
  "clearable": true,
  "type": "textarea",   // 多行文本域
  "rows": 4             // 配合 type:textarea
}
```

### CodeEditor

Monaco 多语言编辑器，值为 `String`。

```jsonc
"typeOptions": {
  "lang": "text",            // javascript | python | java | sql | json | html | text（默认 text）
  "height": "200px",
  "title": "CA 证书",         // 工具栏标题
  "enableExpression": true   // 默认 true
}
```

**`enableExpression` 决定存储值形态，最容易出错的一点：**

| 值 | 存储 | 适用 |
|---|---|---|
| `true`（默认） | 自动加 `=` 前缀：`"=SELECT * FROM t"` | 内容含 `{{ }}` 模板变量 |
| `false` | 原始文本：`"SELECT * FROM t"` | 证书、固定脚本等纯文本 |

存证书 / 私钥 / 固定脚本时**必须**显式设 `false`，否则后端拿到的值带 `=` 前缀，解析失败。

不要给 `CodeEditor` 设顶层 `expression: true`，该字段对编辑器类组件无效。

### SqlEditor

```jsonc
"typeOptions": { "height": "200px", "title": "SQL 查询语句" }
```

用 `#{msg.xxx}`（预编译参数，防注入）和 `${msg.xxx}`（表名/列名直接替换）。**禁止** `{{ }}` / `={{ }}`。`enableExpression` 不适用。

### JsonEditor / JsonExpressionInput

```jsonc
"typeOptions": { "height": "300px", "title": "请求体" }
```

`JsonEditor` 存原始 JSON 字符串，不要往里塞表达式。
`JsonExpressionInput` 在 JSON **字符串值**里用 `={{msg.xxx}}` 做整字段替换（保留类型）；混排写成 `"=[{{msg.a}}] {{msg.b}}"`。
编排器会把值规整为 `JsonValue` 树下发——服务端直接 `parameters.path("字段")` 放进
`dynamicParameters` 即可，**不要**再 `JsonValueFactory.fromJson(...asText())`。

### ExpressionInput（TemplateExpressionInput）

始终工作在表达式模式，存储值**始终带 `=` 前缀**。

```jsonc
"typeOptions": {
  "placeholder": "请输入表达式",
  "height": "120px",        // 固定高度；设置后不自动伸缩
  "minHeight": "36px",      // 不设 height 时生效
  "maxHeight": "200px",
  "title": "变量表达式",
  "showFullScreen": true    // 默认 true
}
```

### BooleanExpressionInput

布尔 / SpEL 逻辑表达式，值**不带** `=` 前缀，直接是表达式字符串（如 `"msg.age > 18"`）。

```jsonc
"typeOptions": { "height": "80px", "placeholder": "msg.status == \"active\" and msg.age > 18" }
```

## 数值与开关

### InputNumber

```jsonc
"typeOptions": {
  "min": 0, "max": 9999, "step": 1,
  "precision": 2,
  "controlsPosition": "right",
  "style": "width:200px"
}
```

### Slider

值为 `Number`，`range: true` 时为 `[Number, Number]`。

```jsonc
"typeOptions": {
  "min": 0, "max": 100, "step": 1,
  "range": false,        // 双滑块范围模式
  "showInput": true,     // 默认 true
  "showStops": false,
  "showTooltip": true,
  "vertical": false,
  "marks": { "0": "0°C", "100": "100°C" }
}
```

### Switch

值为 `Boolean`，无需 `typeOptions`。

## 选择类

### Select（SelectPlus）

静态选项写在 `parameter.options`（**不是** `typeOptions.options`）：

```json
{ "name": "charset", "uiComponent": "Select",
  "options": [{ "value": "utf8mb4", "label": "utf8mb4", "description": "可选说明" }] }
```

选项 ≥8 项时推荐插入分组标题项提升可读性：`{ "label": "── 亚太 ──", "value": "", "disabled": true }`。
分组标题不可选中，但代码里仍要对空值做过滤（`if (v == null || v.isBlank()) return;`），
防止用户通过表达式注入空值。

远程动态选项用 `typeOptions.loadOptions`，详见 [forms-schema.md](forms-schema.md) §7。
凡用了 `loadOptions` 必须同时给 `allow-create` + `clearable`。

> `trigger` 缺省行为按平台实现可能是 `manual`，需要挂载即加载时**显式写** `"trigger": "auto"`。

### Cascader

```jsonc
"typeOptions": {
  "cascaderProps": { "value": "id", "label": "name", "children": "sub", "leaf": "isLeaf" },
  "multiple": false,
  "filterable": true,        // 默认 true
  "checkStrictly": false,    // true 时任意层级可选
  "emitPath": true,          // 默认 true，值为路径数组
  "showAllLevels": true,
  "clearable": true,
  "collapseTags": false,
  "expandTrigger": "click",  // click | hover
  "lazy": true,
  "loadOptions": {
    "method": "getRegions",
    "childrenMethod": "getSubRegions",   // 懒加载子级
    "parentParam": "parentId",           // 默认 parentId
    "provider": "bundle",
    "credentialsRef": "apiCredential"
  }
}
```

值格式：`emitPath: true` → `["zj","hz","xihu"]`；`false` → 叶子 `value`；`multiple` → 数组。

### RadioGroup / RadioButtonGroup / CheckboxGroup

原生控件，选项写 `parameter.options`。前两者值为 `String`，`CheckboxGroup` 值为 `Array`。
选项 ≤5 且固定不变时优先用 RadioButtonGroup，比 Select 少一次点击。

### CredentialSelect

```jsonc
"typeOptions": {
  "credentialsType": "MysqlCredential",   // 必填，PascalCase，== @CredentialsDescription(type)
  "displayName": "MySQL 凭证"             // 可选，「创建」按钮上的名称
}
```

值不写入 `parameters`，而写入 `data.credentials[<字段 name>]`，结构为
`{ credentialsId, name, type }`。代码侧用 `context.getCredentials("<字段 name>")` 读取。

### NodeSelect / ModelSelect

分别用于从当前画布选节点、选 AI 模型（provider/model），无需额外 `typeOptions`。

## 日期时间

三者值均为**字符串**（或范围时的字符串数组），`valueFormat` 决定存储格式。

| uiComponent | 默认 `valueFormat` | 特有 `typeOptions` |
|---|---|---|
| `DatePicker` | `YYYY-MM-DD` | `type`: `date`(默认)/`daterange`/`week`/`month`/`year` |
| `DateTimePicker` | `YYYY-MM-DD HH:mm:ss` | `type`: `datetime`(默认)/`datetimerange` |
| `TimePicker` | `HH:mm:ss` | `isRange`（别名 `range`）、`arrowControl` |

通用：`format`（展示格式，默认同 `valueFormat`）、`clearable`（默认 true）、
`editable`（默认 true）、`startPlaceholder` / `endPlaceholder`（范围模式）。

## 集合类

四者的子字段都定义在 `options` 数组里，子字段 `name` **不要**带父级路径前缀。

### Fixed — 固定参数组

所有子字段始终渲染，值为**对象**。

```json
{ "name": "ssl", "label": "SSL 配置", "uiComponent": "Fixed",
  "options": [
    { "name": "enabled", "label": "启用 SSL", "uiComponent": "Switch", "default": false },
    { "name": "ca", "label": "CA 证书", "uiComponent": "CodeEditor",
      "typeOptions": { "lang": "text", "enableExpression": false },
      "displayOptions": { "show": { "enabled": [true] } } }
  ] }
```

值：`{ "enabled": true, "ca": "-----BEGIN..." }`。
内部 `displayOptions` 引用的是**同 `options` 内的兄弟字段**（`enabled`），不是父级。

### Collection — 用户按需添加的可选字段集合

值为**对象**，key 为用户已添加的字段名。底部下拉列出未添加的字段，选中即加入并填 `default`。

```json
{ "name": "options", "label": "可选配置", "uiComponent": "Collection",
  "placeholder": "添加可选配置",
  "options": [
    { "name": "connectTimeout", "label": "连接超时（秒）", "uiComponent": "InputNumber",
      "default": 10, "typeOptions": { "min": 1, "max": 300 } }
  ] }
```

下拉展示名优先取 `displayName` → `label` → `name`；**新配置统一用 `label`**，
`displayName` 仅为历史兼容。可嵌套 `Fixed` 等组成多层结构。

### FixedCollection — 固定结构列表

值为**数组**，每条记录结构相同，可增删拖拽排序。

```json
{ "name": "headers", "label": "请求头", "uiComponent": "FixedCollection",
  "defaultValue": { "key": "", "value": "" },
  "typeOptions": { "addText": "添加请求头", "emptyText": "暂未添加",
                   "sortable": true, "border": true },
  "options": [
    { "name": "key", "label": "名称", "uiComponent": "Input", "required": true },
    { "name": "value", "label": "值", "uiComponent": "ExpressionInput" }
  ] }
```

`defaultValue` 是**字段根级**属性（与 `name` 同级，不在 `typeOptions` 内），
且**必须包含 `options` 中所有子字段**，否则新增行缺失字段为 `undefined`。
`addText` / `emptyText` 写在根级或 `typeOptions` 内均被接受，保持项目内一致即可。

### RelationCollection — 路由关系列表

用于分支节点，值为**数组**。变更会同步写入节点 `data.relations`、更新画布连线，
并在改名时迁移样本输出。

```json
{ "name": "relations", "label": "输出关系", "uiComponent": "RelationCollection",
  "typeOptions": { "addText": "添加分支", "border": false,
                   "mapping": { "name": "name", "label": "label" } },
  "options": [
    { "name": "name", "label": "关系名称", "uiComponent": "Input", "required": true },
    { "name": "description", "label": "描述", "uiComponent": "Input" }
  ] }
```

每条记录自动生成 `_id`（`r` 前缀 nanoid），**不要在 `options` 中定义 `_id`**。
连线按 `_id` 匹配，改 `name` 不会断线。schema 通常只需 `name` 字段，此时 `label` 恒等于 `name`。

### DynamicSchemaForm — schema 驱动的对象表单

值为**对象**，与 `Fixed` 相同，区别是字段列表可远程加载，适用于「选了不同操作类型就展示不同参数」。

```jsonc
"typeOptions": {
  "loadSchema": {
    "method": "getOperationParams",
    "provider": "bundle",          // 或 credentials
    "trigger": "auto",
    "dependsOn": ["operationType"],
    "credentialsRef": "apiCredential"
  }
}
```

也可退化为静态：直接写 `options`。远程接口需返回 property 定义数组。

## 操作与展示

### TestButton

```jsonc
"typeOptions": {
  "invokeMethod": {
    "method": "test",                      // 测试连接固定为 "test"
    "provider": "credentials",             // 或 bundle
    "credentialsType": "MysqlCredential",  // provider=credentials 时必填
    "dependsOn": ["host", "port"],
    "buttonText": "测试连接",
    "buttonType": "primary"                // primary | success | default
  }
}
```

配置必须嵌在 `invokeMethod` 内。后端返回 `{ "success": bool, "message": "..." }`。
字段 `name` 建议加 `_` 前缀（如 `_testConn`），表示不产生业务数据。

### ColorPicker

```jsonc
"typeOptions": { "showAlpha": false }
```

### BorderSelect

无需 `typeOptions`，值为对象：

```json
{ "style": "solid", "width": 1, "radius": 4, "color": "#999999" }
```

`style` 取 `none|solid|dashed|dotted|double`，`width` 1~20，`radius` 1~500。

### Space

纯占位，不产生数据，不写进 `defaultValue`。

```jsonc
"typeOptions": { "height": "16px" }
```

### Tag

只读文字展示。
