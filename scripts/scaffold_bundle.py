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
BUNDLE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*$")
ERROR_PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

CREDENTIAL_FIELD = "credentialsId"


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
        errors.append(f"--bundle-name 应为 '组织/名称' 小写格式，实际: {args.bundle_name}")
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


def generic_api_readme(names: list) -> str:
    rows = "\n".join(
        f"| `{name}` | 通用调用 | 文档中尚未做成专用节点的接口 |" for name in names)
    return f"""
## 通用调用

厂商文档里有、但还没有专用节点的接口，用下列节点按文档调用。不要另造节点名。

| 节点 | 类型 | 说明 |
|------|------|------|
{rows}

| 参数 | 怎么填 |
|------|--------|
| `method` | 文档中的 HTTP 方法 |
| `path` | 文档中的路径，以 `/` 开头，不含域名。支持 `={{{{ msg.xxx }}}}` |
| `query` | 文档中的查询参数，一项一行 |
| `headers` | 文档要求的额外请求头。未写鉴权头时自动加 `Authorization: Bearer <凭证 apiKey>` |
| `body` | 文档中的 JSON 正文。GET 不显示此项 |

域名和密钥来自凭证的 `host`、`port`、`apiKey`。`path` 以 `http://` 或 `https://` 开头时当作完整地址。

HTTP 2xx 时输出 `msg.output.statusCode` 与 `msg.output.body`。
HTTP 非 2xx 走 Failure，状态码和响应体在 `msg.error.metadata.statusCode` 与 `msg.error.metadata.body`。
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
                "summary": "按文档调用" if node_name in generic_names else "待补充",
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

    # 文档
    first_node = node_specs[0][0]
    readme = render("project/README.md.tmpl", {
        "ARTIFACT_ID": args.artifact_id,
        "NODE_NAME": first_node,
        "PACKAGE_PATH": "/".join(args.package.split(".")),
        "ERROR_PREFIX": error_prefix,
        "ERROR_CODES": error_codes_table(args, error_prefix),
    })
    if args.generic_api:
        readme += generic_api_readme(args.generic_api)
    write(root / "README.md", readme, args.force)
    write(root / "CHANGELOG.md", render("project/CHANGELOG.md.tmpl", {
        "VERSION": args.version,
        "DATE": datetime.date.today().isoformat(),
        "NODE_NAME": first_node,
    }), args.force)

    print("\n完成。后续步骤：")
    print("  1. 编辑 src/main/resources/bundle.json 补全 label / summary")
    print("     节点 icon 默认为 default.svg，需要自定义图标时再改文件名")
    print("  2. 编辑 src/main/resources/properties/*.json 定义表单字段")
    print("  3. 实现节点 onMsg 业务逻辑")
    if args.generic_api:
        print("     通用调用节点已生成：未实现的接口按厂商文档填 method/path/query/headers/body")
    print("  4. 补全 README.md 与 CHANGELOG.md 中的 TODO")
    print(f"  5. python3 {Path(__file__).parent / 'validate_bundle.py'} {root}")
    print("  6. mvn -q clean package")


if __name__ == "__main__":
    main()
