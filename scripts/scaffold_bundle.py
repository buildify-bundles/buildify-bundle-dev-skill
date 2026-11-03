#!/usr/bin/env python3
"""生成 Buildify Bundle 项目骨架。

用法：
    python3 scaffold_bundle.py --dir ./my-bundle \
        --group-id com.example --artifact-id my-bundle \
        --bundle-name example/my-bundle --package com.example.bundle \
        --node MyNode [--trigger MyTriggerNode] [--webhook MyWebhookNode] \
        [--credential MyApiCredential] [--method GetTablesExecutor:getTables] \
        [--generic-api ApiCall] [--error-prefix DEMO]

同时提供 --credential 时，普通节点表单会自动生成 CredentialSelect 字段；
再配合 --method 时会生成一个通过 credentialsRef 联动的远程 Select 字段。

仅依赖 Python 3.8+ 标准库。
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

NODE_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
PACKAGE_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")
BUNDLE_NAME_RE = re.compile(r"^[a-z0-9]+([._-][a-z0-9]+)*/[a-z0-9]+([._-][a-z0-9]+)*$")
ERROR_PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

CREDENTIAL_FIELD = "credentialsId"
GITIGNORE = "target/\n*.jar\n.idea/\n*.iml\n.vscode/\n.DS_Store\n"


def render(template_name: str, mapping: dict) -> str:
    text = (TEMPLATES / template_name).read_text(encoding="utf-8")
    for key, value in mapping.items():
        text = text.replace("{{%s}}" % key, value)
    leftover = re.findall(r"\{\{([A-Z_]+)\}\}", text)
    if leftover:
        raise SystemExit(f"模板 {template_name} 存在未替换占位符: {sorted(set(leftover))}")
    return text


def write(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        print(f"  skip   {path} (已存在，加 --force 覆盖)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  write  {path}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="生成 Buildify Bundle 项目骨架")
    p.add_argument("--dir", required=True, help="项目输出目录")
    p.add_argument("--group-id", required=True, help="Maven groupId，如 com.example")
    p.add_argument("--artifact-id", required=True, help="Maven artifactId，如 my-bundle")
    p.add_argument("--bundle-name", required=True, help="Bundle 唯一名称，格式 组织/名称")
    p.add_argument("--package", required=True, help="Java 根包名，如 com.example.bundle")
    p.add_argument("--node", action="append", default=[], help="普通节点类名，可重复")
    p.add_argument("--trigger", action="append", default=[], help="定时触发器节点类名，可重复")
    p.add_argument("--webhook", action="append", default=[], help="Webhook 触发器类名，可重复")
    p.add_argument("--credential", action="append", default=[],
                   help="凭证类型标识（PascalCase，如 MyApiCredential），可重复")
    p.add_argument("--generic-api", action="append", default=[],
                   help="三方接口通用调用节点类名，须以 ApiCall 结尾，可重复。"
                        "未做成专用节点的接口按文档填 method/path/query/headers/body。"
                        "需同时提供 --credential")
    p.add_argument("--method", action="append", default=[],
                   help="动态方法，格式 类名:方法名（如 GetTablesExecutor:getTables），可重复")
    p.add_argument("--error-prefix",
                   help="错误码前缀（大写下划线，如 DINGTALK），生成 DINGTALK_HTTP_ERROR 等。"
                        "默认由 artifactId 推导")
    p.add_argument("--group-label", default="通用", help="bundle.json 中的分组显示名")
    p.add_argument("--version", default="1.0.0-SNAPSHOT", help="初始版本号")
    p.add_argument("--force", action="store_true", help="覆盖已存在的文件")
    return p.parse_args()


def validate(args: argparse.Namespace) -> None:
    errors = []
    if not BUNDLE_NAME_RE.match(args.bundle_name):
        errors.append(f"--bundle-name 应为 '命名空间/包名'，两段只含小写字母、数字和 . _ -"
                      f"（不连续、不在首尾），实际: {args.bundle_name}")
    if not PACKAGE_RE.match(args.package):
        errors.append(f"--package 不是合法的 Java 包名: {args.package}")
    all_nodes = args.node + args.trigger + args.webhook + args.generic_api
    if not all_nodes:
        errors.append("至少需要一个 --node / --trigger / --webhook / --generic-api")
    if args.generic_api and not args.credential:
        errors.append("--generic-api 需要同时提供 --credential，鉴权从凭证读取")
    for name in all_nodes:
        if not NODE_NAME_RE.match(name):
            errors.append(f"节点类名必须是 PascalCase: {name}")
    for name in args.generic_api:
        if NODE_NAME_RE.match(name) and not name.endswith("ApiCall"):
            errors.append(f"--generic-api 类名必须以 ApiCall 结尾，便于按文档找到通用调用: {name}")
    for name in args.credential:
        if not NODE_NAME_RE.match(name):
            errors.append(f"凭证类型标识必须是 PascalCase（与 propertiesFile 文件名一致）: {name}")
    dupes = {n for n in all_nodes if all_nodes.count(n) > 1}
    if dupes:
        errors.append(f"节点名重复: {sorted(dupes)}")
    for spec in args.method:
        if ":" not in spec:
            errors.append(f"--method 格式应为 类名:方法名，实际: {spec}")
            continue
        cls, method = spec.split(":", 1)
        if not NODE_NAME_RE.match(cls):
            errors.append(f"--method 类名必须是 PascalCase: {cls}")
        if not method or not method[0].islower():
            errors.append(f"--method 方法名应为 camelCase: {method}")
    if args.error_prefix is not None and not ERROR_PREFIX_RE.match(args.error_prefix):
        errors.append(f"--error-prefix 应为大写字母开头的大写下划线格式（如 DINGTALK），"
                      f"实际: {args.error_prefix}")
    if errors:
        for e in errors:
            print(f"ERROR  {e}", file=sys.stderr)
        raise SystemExit(1)


def derive_error_prefix(artifact_id: str) -> str:
    """bundle-dingtalk-bot → DINGTALK_BOT。"""
    name = re.sub(r"^bundle[-_.]|[-_.]bundle$", "", artifact_id.lower())
    prefix = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
    return prefix if prefix and prefix[0].isalpha() else "API"


VALIDATION_CODE = ("VALIDATION_ERROR", "节点参数校验失败，节点未启动",
                   "按 `metadata.field` / `metadata.constraint` 修正节点配置")
HTTP_CODES = [
    ("INVALID_URL", "请求地址格式错误", "检查 url / path 及其表达式结果"),
    ("HTTP_IO_ERROR", "连接失败或超时，没有拿到响应", "检查网络、地址与超时设置"),
    ("{p}_HTTP_ERROR", "接口返回非 2xx",
     "查看 `metadata.statusCode` 与 `metadata.body`，按提示检查凭证或参数"),
    ("RESPONSE_ERROR", "处理响应时出错", "查看节点日志"),
]
NODE_CODES = [
    ("MISSING_URL", "url 表达式求值为空", "检查上游消息是否提供该字段"),
    ("{p}_API_<业务码>", "HTTP 2xx 但接口返回业务错误码",
     "对照厂商文档的错误码；`metadata.body` 为原始响应"),
]
GENERIC_API_CODES = [
    ("MISSING_CREDENTIALS", "未选择访问凭证，或凭证已被删除", "在节点中重新选择凭证"),
    ("MISSING_HOST", "凭证 host 为空", "编辑凭证补全 host"),
    ("MISSING_API_KEY", "凭证 apiKey 为空，且请求头未提供鉴权", "补全凭证 apiKey，或在 headers 中写鉴权头"),
]


def error_codes_table(args: argparse.Namespace, prefix: str) -> str:
    rows = []
    if args.node or args.generic_api or args.webhook:
        rows.append(VALIDATION_CODE)
    if args.node or args.generic_api:
        rows += HTTP_CODES
    if args.node:
        rows += NODE_CODES
    if args.generic_api:
        rows += GENERIC_API_CODES
    if not rows:
        return "本 Bundle 的节点不产生结构化错误码。"
    seen, lines = set(), ["| 错误码 | 含义 | 排查建议 |", "|--------|------|----------|"]
    for code, meaning, advice in rows:
        code = code.format(p=prefix)
        if code not in seen:
            seen.add(code)
            lines.append(f"| `{code}` | {meaning} | {advice} |")
    return "\n".join(lines)


def node_rows(args: argparse.Namespace) -> str:
    kinds = ([(n, "普通节点", "TODO 什么时候选这个节点（不要用类名代替）") for n in args.node]
             + [(n, "通用调用", "厂商文档里有、但没有专用节点的接口") for n in args.generic_api]
             + [(n, "触发器", "TODO 何时启动这条流程（定时、轮询…）") for n in args.trigger]
             + [(n, "Webhook 触发器", "外部 HTTP 请求到达时启动流程") for n in args.webhook])
    return "\n".join(f"| `{name}` | {kind} | {desc} |" for name, kind, desc in kinds)


def credential_section(args: argparse.Namespace) -> str:
    if not args.credential:
        return "本软件包节点不需要访问凭证。\n"
    ctype = args.credential[0]
    lines = [
        f"凭证类型标识是 `{ctype}`（编排写入 `credentials.type` 时必须与此逐字一致）。",
        "",
        "在控制台「凭证」中创建后，节点里选择这一条；创建后点击「测试连接」确认连通。",
        "",
        "| 字段 | 必填 | 说明 |",
        "|------|------|------|",
        "| `host` | 是 | 服务地址，不要末尾斜杠 |",
        "| `apiKey` | 是 | API 密钥，不要写进节点参数或 Header |",
    ]
    if len(args.credential) > 1:
        others = "、".join(f"`{c}`" for c in args.credential[1:])
        lines += ["", f"同包还有凭证类型 {others}，按节点表单的 `credentialsType` 选用。"]
    return "\n".join(lines) + "\n"


def node_sections(args: argparse.Namespace, prefix: str) -> str:
    parts = ([_regular_node_readme(n, prefix) for n in args.node]
             + [_trigger_node_readme(n) for n in args.trigger]
             + [_webhook_node_readme(n) for n in args.webhook])
    return "\n".join(parts)


def _regular_node_readme(name: str, prefix: str) -> str:
    return f"""
## `{name}`

**何时使用**：TODO 一句话。有更合适的专用节点时不要用本节点凑。

### 参数

| 参数 | 必填 | 默认 | 表达式 | 说明 |
|------|------|------|--------|------|
| `url` | 是 | — | 是 `={{{{ msg.xxx }}}}` | 请求地址 |
| `method` | 是 | `GET` | 是 | 请求方法 |
| `timeout` | 否 | `30` | 否（只在启动时读取） | 超时秒数 |
| `body` | 否 | — | 是 `={{{{ msg.xxx }}}}` | JSON 正文；GET 不显示 |

### 输出

成功走 **Success**，业务数据在 `output`（不要写到根级）：

```json
{{
  "output": {{
    "statusCode": 200,
    "body": {{ "id": 1, "name": "example" }}
  }}
}}
```

下游引用：`={{{{ msg.output.statusCode }}}}`、`={{{{ msg.output.body }}}}`。

失败走 **Failure**，状态码和响应体在 `msg.error.metadata`：

```json
{{
  "error": {{
    "code": "{prefix}_HTTP_ERROR",
    "message": "请求无效（HTTP 400），请检查请求参数。响应：{{\\"errcode\\":40035,\\"errmsg\\":\\"...\\"}}",
    "metadata": {{
      "statusCode": 400,
      "body": {{ "errcode": 40035, "errmsg": "..." }}
    }}
  }}
}}
```

连接失败、超时同样走 Failure，这时 `metadata` 中没有 `statusCode` / `body`。
响应中的 Token、密钥等字段写入前已替换为 `***`。

### 编排

- 绑定凭证类型见上文「凭证」
- 典型上游：Webhook / 触发器 / 上一个查询节点
- TODO 补一条本节点的真实参数示例（字段名与表单一致）
"""


def _trigger_node_readme(name: str) -> str:
    return f"""
## `{name}`

**何时使用**：TODO 用这条触发器启动流程的时机（例如每 5 分钟拉一次增量）。

### 参数

| 参数 | 必填 | 默认 | 表达式 | 说明 |
|------|------|------|--------|------|
| `cron` | 是 | `0 */5 * * * ?` | 否（修改会重启） | Quartz Cron |
| `timezone` | 否 | `Asia/Shanghai` | 否 | 时区 |
| `maxPerSecond` | 否 | `0` | 否（修改即时生效） | 每秒最多触发次数，`0` 表示不限速 |

触发器没有输入连接点，不要把上游连进来。

### 限流

上一轮还没结束时跳过本轮。`maxPerSecond` 为 `0` 时不按速率丢弃；设为正整数后，超过该值时本次触发**丢弃并计数**。
下游处理不过来时同样丢弃并计数，节点状态显示黄色「限流丢弃 N 条」，下游恢复后自动转绿。被丢弃的触发不会补发。

### 输出

payload 放在**根级**（不要包 `output`），并带 `triggerNodeId`、`eventId`、`workerId`：

```json
{{
  "triggerNodeId": "n-xxxxxxxx",
  "eventId": "…",
  "workerId": "…",
  "triggeredAt": 0
}}
```

下游引用：`={{{{ msg.eventId }}}}`、`={{{{ msg.triggeredAt }}}}`。走 **Success**。
"""


def _webhook_node_readme(name: str) -> str:
    return f"""
## `{name}`

**何时使用**：外部系统用 HTTP 回调启动流程（Slack、支付、自建服务）。

### 参数

| 参数 | 必填 | 默认 | 表达式 | 说明 |
|------|------|------|--------|------|
| `path` | 是 | — | 否（修改会重启并重注册路由） | 监听路径，如 `/webhook/order` |
| `timeout` | 否 | `5000` | 否 | 超时毫秒 |
| `maxPerSecond` | 否 | `0` | 否（修改会重启） | 每秒最多接收的请求数，`0` 表示不限速 |

### 响应与限流

| 状态码 | 含义 | 调用方怎么做 |
|--------|------|--------------|
| `200` | 已接收，流程已启动 | — |
| `429` | `maxPerSecond` 大于 0 且超过该值，或下游处理不过来，请求**未处理** | 按 `Retry-After`（秒）退避后重试 |
| `503` | 节点已停止 | 稍后重试或检查流程是否已发布 |
| `500` | 处理请求失败 | 查看 Worker 日志 |

### 输出

请求体放在**根级**（不要包 `output`），并带 `triggerNodeId`、`eventId`、`workerId`。
下游引用请求字段用 `={{{{ msg.xxx }}}}`。走 **Success**；校验失败走 **Failure**。
"""


def generic_api_readme(names: list) -> str:
    listed = "、".join(f"`{name}`" for name in names)
    return f"""
## 通用调用

**何时使用**：厂商文档里有、但本包还没有专用节点的接口。用 {listed}，按文档填下面字段，不要另造节点名。已有专用节点的操作不要走通用调用。

| 参数 | 必填 | 表达式 | 怎么填 |
|------|------|--------|--------|
| `method` | 是 | 否 | 文档中的 HTTP 方法 |
| `path` | 是 | 是 `={{{{ msg.xxx }}}}` | 以 `/` 开头，不含域名 |
| `query` | 否 | 是 | 文档中的查询参数，一项一行 |
| `headers` | 否 | 是 | 文档要求的额外请求头。未写鉴权头时自动加 `Authorization: Bearer <凭证 apiKey>` |
| `body` | 否 | 是 `={{{{ msg.xxx }}}}` | 文档中的 JSON 正文。GET 不显示 |

域名和密钥来自凭证的 `host`、`port`、`apiKey`。`path` 以 `http://` 或 `https://` 开头时当作完整地址。

成功走 **Success**：`={{{{ msg.output.statusCode }}}}`、`={{{{ msg.output.body }}}}`。
HTTP 非 2xx 走 **Failure**：`={{{{ msg.error.metadata.statusCode }}}}`、`={{{{ msg.error.metadata.body }}}}`。
连接失败或超时也走 Failure，这时没有 `statusCode` / `body`。
"""


def inject_credential_fields(props: dict, credential_type: str, method_name) -> dict:
    """在节点表单顶部插入 CredentialSelect，并按需插入联动的远程 Select。

    字段顺序遵循规范：凭证 → 核心必填 → 动态联动 → 可选配置 → 操作按钮。
    """
    extra = [{
        "name": CREDENTIAL_FIELD,
        "label": "访问凭证",
        "uiComponent": "CredentialSelect",
        "required": True,
        "typeOptions": {
            "credentialsType": credential_type,
            "displayName": credential_type,
        },
    }]
    if method_name:
        extra.append({
            "name": "resource",
            "label": "资源",
            "uiComponent": "Select",
            "expression": True,
            "droppable": True,
            "placeholder": "请选择资源",
            "typeOptions": {
                # 远程不可达时仍可手输、可清空（见 reference/forms-schema.md §7）
                "allow-create": True,
                "clearable": True,
                "filterable": True,
                "loadOptions": {
                    "method": method_name,
                    "provider": "bundle",
                    "trigger": "auto",
                    # credentialsRef 已隐含凭证依赖，不要重复写进 dependsOn
                    "credentialsRef": CREDENTIAL_FIELD,
                    "dependsOn": [],
                },
            },
        })
    props["properties"] = extra + props.get("properties", [])
    return props


def main() -> None:
    args = parse_args()
    validate(args)

    root = Path(args.dir).resolve()
    pkg_path = root / "src/main/java" / Path(*args.package.split("."))
    res = root / "src/main/resources"
    services = res / "META-INF/services"

    node_specs = ([(n, "java/Node.java.tmpl", "forms/node-properties.json", True)
                   for n in args.node]
                  + [(n, "java/GenericApiNode.java.tmpl", "forms/generic-api-properties.json", True)
                     for n in args.generic_api]
                  + [(n, "java/TriggerNode.java.tmpl", "forms/trigger-properties.json", False)
                     for n in args.trigger]
                  + [(n, "java/WebhookNode.java.tmpl", "forms/webhook-properties.json", False)
                     for n in args.webhook])
    generic_names = set(args.generic_api)

    primary_credential = args.credential[0] if args.credential else None
    primary_method = args.method[0].split(":", 1)[1] if args.method and args.credential else None

    print(f"生成 Bundle 项目: {root}")

    write(root / "pom.xml", render("project/pom.xml", {
        "GROUP_ID": args.group_id,
        "ARTIFACT_ID": args.artifact_id,
        "VERSION": args.version,
    }), args.force)

    # 节点源码 + 表单；bundle.json 的 parameters 与表单 defaultValue 保持一致
    defaults = {}
    for node_name, java_template, props_template, is_regular in node_specs:
        write(pkg_path / "nodes" / f"{node_name}.java",
              render(java_template, {"PACKAGE": args.package, "NODE_NAME": node_name}), args.force)

        props = json.loads((TEMPLATES / props_template).read_text(encoding="utf-8"))
        if is_regular and primary_credential:
            props = inject_credential_fields(props, primary_credential, primary_method)
        write(res / "properties" / f"{node_name}.json",
              json.dumps(props, ensure_ascii=False, indent=2) + "\n", args.force)
        defaults[node_name] = props.get("defaultValue", {})

    # bundle.json
    bundle = {
        "bundleName": args.bundle_name,
        "groups": [{
            "label": args.group_label,
            "nodes": [{
                "name": node_name,
                "label": node_name,
                "summary": "按文档调用" if node_name in generic_names else "处理请求",
                "icon": "default.svg",
                "parameters": defaults[node_name],
            } for node_name, _, _, _ in node_specs],
        }],
    }
    write(res / "bundle.json",
          json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", args.force)

    # SPI: FlowNode
    write(services / "cn.buildify.bundle.api.FlowNode",
          "".join(f"{args.package}.nodes.{n}\n" for n, _, _, _ in node_specs), args.force)

    # 三方接口失败统一写入 msg.error.metadata（statusCode / body）
    error_prefix = args.error_prefix or derive_error_prefix(args.artifact_id)
    if args.node or args.generic_api or args.credential:
        write(pkg_path / "support" / "HttpErrors.java", render("java/HttpErrors.java.tmpl", {
            "PACKAGE": args.package,
            "ERROR_PREFIX": error_prefix,
        }), args.force)

    # 触发器背压：限流、防重叠、丢弃计数
    if args.trigger or args.webhook:
        write(pkg_path / "support" / "TriggerGuard.java",
              render("java/TriggerGuard.java.tmpl", {"PACKAGE": args.package}), args.force)

    # 凭证：propertiesFile 文件名必须与 @CredentialsDescription(type) 逐字一致
    for cred in args.credential:
        write(pkg_path / "credentials" / f"{cred}Provider.java",
              render("java/CredentialsProvider.java.tmpl", {
                  "PACKAGE": args.package,
                  "CREDENTIAL_TYPE": cred,
                  "CREDENTIAL_LABEL": cred,
              }), args.force)
        write(res / "credentials" / f"{cred}.json",
              render("forms/credentials-properties.json", {"CREDENTIAL_TYPE": cred}), args.force)
    if args.credential:
        write(services / "cn.buildify.bundle.api.credentials.CredentialsProvider",
              "".join(f"{args.package}.credentials.{c}Provider\n" for c in args.credential),
              args.force)

    # 动态方法
    for spec in args.method:
        cls, method = spec.split(":", 1)
        write(pkg_path / "methods" / f"{cls}.java",
              render("java/MethodExecutor.java.tmpl", {
                  "PACKAGE": args.package,
                  "METHOD_CLASS": cls,
                  "METHOD_NAME": method,
              }), args.force)
    if args.method:
        write(services / "cn.buildify.bundle.api.MethodExecutor",
              "".join(f"{args.package}.methods.{s.split(':', 1)[0]}\n" for s in args.method),
              args.force)

    # 文档：docs.md 同步到平台；README.md 只给开发这个 Bundle 的人看
    first_node = node_specs[0][0]
    usage = render("project/docs.md.tmpl", {
        "NODE_ROWS": node_rows(args),
        "CREDENTIAL_SECTION": credential_section(args),
        "NODE_SECTIONS": node_sections(args, error_prefix),
        "GENERIC_API": generic_api_readme(args.generic_api) if args.generic_api else "",
        "ERROR_CODES": error_codes_table(args, error_prefix),
    })
    write(root / "docs.md", usage, args.force)
    write(root / "README.md", render("project/README.md.tmpl", {
        "ARTIFACT_ID": args.artifact_id,
    }), args.force)
    write(root / "CHANGELOG.md", render("project/CHANGELOG.md.tmpl", {
        "VERSION": args.version,
        "DATE": datetime.date.today().isoformat(),
        "NODE_NAME": first_node,
    }), args.force)
    write(root / ".gitignore", GITIGNORE, args.force)

    print("\n完成。后续步骤：")
    print("  1. 编辑 src/main/resources/bundle.json：节点 label 写成中文短名，summary ≤10 字写清做什么")
    print("     发布建包时先 bundle namespaces，优先用已有命名空间，用户选择新建才 namespace create；"
          "软件名称（--display-name）= 官方中文名+能力；软件描述（--summary）按"
          "「对接谁：能做什么。用于场景。不含边界」写，见 reference/publishing.md")
    print("     发布时核对 bundle.json 的 icon 是否已在平台图标里：没有才创建。查找用 Devicons API"
          "（https://devicons.io/docs/api/，只接受名称完全匹配）；找不到则该节点改为 default.svg，"
          "告诉用户稍后在控制台替换。封面只在 bundle create --icon 时上传")
    print("  2. 编辑 src/main/resources/properties/*.json 定义表单字段")
    print("  3. 实现节点 onMsg 业务逻辑")
    if args.trigger or args.webhook:
        print("     触发器用 support/TriggerGuard 限流、防重叠，发消息用 tryTellSuccess；"
              "不要用无界队列缓存事件，见 reference/backpressure.md")
    if args.generic_api:
        print("     通用调用节点已生成：未实现的接口按厂商文档填 method/path/query/headers/body")
    print("  4. 按节点补全 docs.md（平台用户使用文档，给用户和编排 Agent 看：何时使用、参数、输出路径、出口）"
          "与 CHANGELOG.md；不要写项目结构、构建、ClassLoader。README.md 不上传到平台")
    print(f"  5. python3 {Path(__file__).parent / 'validate_bundle.py'} {root}")
    print("  6. mvn -q clean package")
    print("  7. 没有 git 仓库或远程地址时，请用户提供源码仓库地址后初始化并推送")


if __name__ == "__main__":
    main()
