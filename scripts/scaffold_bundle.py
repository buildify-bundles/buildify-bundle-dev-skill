#!/usr/bin/env python3
"""生成 Buildify Bundle 项目骨架。

用法：
    python3 scaffold_bundle.py --dir ./my-bundle \
        --group-id com.example --artifact-id my-bundle \
        --bundle-name example/my-bundle --package com.example.bundle \
        --node MyNode [--trigger MyTriggerNode] [--webhook MyWebhookNode] \
        [--credential MyApiCredential] [--method GetTablesExecutor:getTables] \
        [--generic-api ApiCall]

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
    if errors:
        for e in errors:
            print(f"ERROR  {e}", file=sys.stderr)
        raise SystemExit(1)


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

成功时输出 `msg.output.statusCode` 与 `msg.output.body`（含 4xx/5xx）。连接失败或超时走 Failure。
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
