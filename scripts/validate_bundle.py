#!/usr/bin/env python3
"""校验 Buildify Bundle 项目的一致性与常见违规。

用法：
    python3 validate_bundle.py [项目目录] [--strict]

规则与 SKILL.md、coding-rules.md、reference/forms-schema.md、
reference/forms-components.md 保持一致。

检查项：命名一致性、SPI 注册、pom 配置、表单 schema 合法性、凭证字段规范、
消息 complete、触发器约定、Node Service RPC、资源释放、异常与日志规范、README/CHANGELOG。

退出码：0 = 通过；1 = 存在 ERROR（--strict 时 WARNING 也算失败）。
仅依赖 Python 3.8+ 标准库。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ERRORS = []   # list[tuple[level, location, message]]


def err(location: str, message: str) -> None:
    ERRORS.append(("ERROR", location, message))


def warn(location: str, message: str) -> None:
    ERRORS.append(("WARN", location, message))


PASCAL_CASE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
SERVICE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

# 内置的表单驱动方法名，无需对应 MethodExecutor
BUILTIN_METHODS = {"test"}

# 编辑器类组件：内置变量语法，不接受顶层 expression
EDITOR_COMPONENTS = {"CodeEditor", "SqlEditor", "JsonEditor", "JsonExpressionInput"}

# 不产生业务数据的纯 UI 组件，不应出现在 defaultValue 中
NON_DATA_COMPONENTS = {"TestButton", "Space", "Tag", "FeishuRegisterApp"}


# --------------------------------------------------------------------------- java

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"//[^\n]*")


def strip_comments(text: str) -> str:
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", text))


def annotation_body(text: str, name: str):
    """提取 @Name(...) 的括号内内容，支持嵌套括号。"""
    idx = text.find("@" + name)
    if idx < 0:
        return None
    start = text.find("(", idx)
    if start < 0 or text[idx + len(name) + 1:start].strip():
        return ""
    depth, i = 0, start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
        i += 1
    return None


def attr(body: str, key: str):
    m = re.search(r"\b%s\s*=\s*\"([^\"]*)\"" % key, body)
    if m:
        return m.group(1)
    m = re.search(r"\b%s\s*=\s*(true|false)" % key, body)
    return m.group(1) if m else None


class JavaFile:
    def __init__(self, path: Path, src_root: Path):
        self.path = path
        self.rel = str(path.relative_to(src_root.parent.parent.parent))
        self.raw = path.read_text(encoding="utf-8", errors="replace")
        self.code = strip_comments(self.raw)
        pkg = re.search(r"^\s*package\s+([\w.]+)\s*;", self.code, re.M)
        self.package = pkg.group(1) if pkg else ""
        cls = re.search(r"\b(?:public\s+)?(?:final\s+|abstract\s+)?class\s+(\w+)", self.code)
        self.simple_name = cls.group(1) if cls else path.stem
        self.fqcn = f"{self.package}.{self.simple_name}" if self.package else self.simple_name

    def implements(self, iface: str) -> bool:
        return re.search(r"\bimplements\b[^{]*\b%s\b" % iface, self.code) is not None


def scan_java(project: Path):
    src = project / "src/main/java"
    if not src.is_dir():
        err("项目结构", "缺少 src/main/java 目录")
        return []
    return [JavaFile(p, src) for p in sorted(src.rglob("*.java"))]


# --------------------------------------------------------------------------- pom

def check_pom(project: Path) -> None:
    pom = project / "pom.xml"
    if not pom.is_file():
        err("pom.xml", "文件不存在")
        return
    text = pom.read_text(encoding="utf-8", errors="replace")
    loc = "pom.xml"

    dep = re.search(
        r"<dependency>(?:(?!</dependency>).)*buildify-bundle-api(?:(?!</dependency>).)*</dependency>",
        text, re.S)
    if not dep:
        err(loc, "缺少 buildify-bundle-api 依赖")
    elif "<scope>provided</scope>" not in dep.group(0):
        err(loc, "buildify-bundle-api 的 scope 必须为 provided，否则与宿主类冲突")

    if "maven.compiler.release" not in text and "<release>" not in text:
        err(loc, "必须使用 maven.compiler.release（或 compiler 插件的 <release>），不能只用 source/target")

    if "maven-shade-plugin" not in text:
        err(loc, "缺少 maven-shade-plugin，无法生成 fat JAR")
    elif "ServicesResourceTransformer" not in text:
        err(loc, "maven-shade-plugin 缺少 ServicesResourceTransformer，SPI 文件会被互相覆盖")


def check_docs(project: Path) -> None:
    if not (project / "README.md").is_file():
        err("README.md", "每个 Bundle 必须在模块根目录提供 README.md（节点一览/参数/输出/构建/依赖）")
    changelog = project / "CHANGELOG.md"
    if not changelog.is_file():
        warn("CHANGELOG.md", "缺少 CHANGELOG.md，发布时 --release-notes-file 无文件可指向")
        return
    text = changelog.read_text(encoding="utf-8", errors="replace")
    sections = re.findall(r"^##\s+\S+", text, re.M)
    if not sections:
        warn("CHANGELOG.md", "未找到 '## x.y.z - YYYY-MM-DD' 形式的版本小节")
        return
    if len(sections) > 1:
        warn("CHANGELOG.md", f"本仓库约定全文仅保留当前版本一节，当前有 {len(sections)} 节，"
                             "历史版本以 Git 为准")
    version = project_version(project)
    if version and version not in text:
        warn("CHANGELOG.md", f"未出现 pom.xml 中的版本号 {version}，"
                             "发布说明的版本须与 pom 和 -v 参数一致")


def project_version(project: Path):
    """读取 pom.xml 中项目自身的 <version>（跳过注释、dependencies、build 等子块）。"""
    pom = project / "pom.xml"
    if not pom.is_file():
        return None
    text = re.sub(r"<!--.*?-->", "", pom.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    head = re.split(r"<(?:dependencies|dependencyManagement|build|profiles)\b", text, 1)[0]
    for m in re.finditer(r"<version>\s*([^<\s][^<]*?)\s*</version>", head):
        value = m.group(1)
        if not value.startswith("${"):
            return value
    return None


# --------------------------------------------------------------------------- 表单 schema

def load_json(path: Path, loc: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        err(loc, f"JSON 解析失败: {e}")
        return None


def collect_credential_fields(fields, acc: dict) -> None:
    """收集本表单内所有 CredentialSelect 字段名 → credentialsType。"""
    if not isinstance(fields, list):
        return
    for field in fields:
        if not isinstance(field, dict):
            continue
        if field.get("uiComponent") == "CredentialSelect":
            opts = field.get("typeOptions") or {}
            if isinstance(opts, dict):
                acc[field.get("name")] = opts.get("credentialsType")
        sub = field.get("options")
        if isinstance(sub, list) and sub and isinstance(sub[0], dict) and "uiComponent" in sub[0]:
            collect_credential_fields(sub, acc)


def walk_fields(fields, loc: str, path_prefix: str, ctx: dict) -> None:
    """递归检查表单字段。"""
    if not isinstance(fields, list):
        err(loc, f"{path_prefix} 必须是数组")
        return

    siblings = {f.get("name") for f in fields if isinstance(f, dict)}
    seen = set()

    for i, field in enumerate(fields):
        where = f"{path_prefix}[{i}]"
        if not isinstance(field, dict):
            err(loc, f"{where} 必须是对象")
            continue
        name = field.get("name")
        where = f"{path_prefix}[{name or i}]"

        if not name:
            err(loc, f"{where} 缺少 name")
        elif name in seen:
            err(loc, f"{where} 同级字段 name 重复")
        else:
            seen.add(name)
        if isinstance(name, str) and ("." in name or "[" in name):
            err(loc, f"{where} 字段 name 不能包含父级路径（'.' 或 '['），路径由前端自动拼接")

        if "type" in field and "uiComponent" not in field:
            err(loc, f"{where} 使用了 type，应改为 uiComponent")
        component = field.get("uiComponent")
        if not component:
            err(loc, f"{where} 缺少 uiComponent")

        type_options = field.get("typeOptions") or {}
        if not isinstance(type_options, dict):
            err(loc, f"{where} typeOptions 必须是对象")
            type_options = {}

        # --- required 与 rules
        rules = field.get("rules")
        if isinstance(rules, list):
            for rule in rules:
                if isinstance(rule, dict) and rule.get("required"):
                    warn(loc, f"{where} required 应写在字段顶层，不要放进 rules")

        # --- 表达式
        if component in EDITOR_COMPONENTS and field.get("expression"):
            err(loc, f"{where} {component} 内置变量语法，顶层 expression 无效，"
                     "请改用 typeOptions.enableExpression")
        if component == "CodeEditor":
            lang = type_options.get("lang", "text")
            if lang == "text" and "enableExpression" not in type_options:
                warn(loc, f"{where} CodeEditor(lang=text) 未显式设置 enableExpression；"
                          "存证书/纯文本时必须设为 false，否则存储值会带 '=' 前缀")

        # --- 条件显示
        display = field.get("displayOptions")
        if display is not None:
            if not isinstance(display, dict):
                err(loc, f"{where} displayOptions 必须是对象")
            else:
                for key in ("show", "hide"):
                    cond = display.get(key)
                    if cond is None:
                        continue
                    if not isinstance(cond, dict):
                        err(loc, f"{where} displayOptions.{key} 必须是对象")
                        continue
                    for ref, values in cond.items():
                        if "." in ref:
                            err(loc, f"{where} displayOptions.{key} 不支持嵌套路径 '{ref}'，"
                                     "只能引用同级兄弟字段")
                        elif ref not in siblings:
                            err(loc, f"{where} displayOptions.{key} 引用了非同级字段 '{ref}'，"
                                     f"同级可用: {sorted(n for n in siblings if n)}")
                        if not isinstance(values, list):
                            err(loc, f"{where} displayOptions.{key}.{ref} 的值必须是数组，"
                                     "单值也要写成 [x]")

        # --- 凭证选择器
        if component == "CredentialSelect":
            if "credentialsName" in type_options:
                err(loc, f"{where} credentialsName 已废弃，请改用 typeOptions.credentialsType")
            cred = type_options.get("credentialsType")
            if not cred:
                err(loc, f"{where} CredentialSelect 必须配置 typeOptions.credentialsType")
            else:
                check_credential_type(cred, loc, where, ctx)

        # --- 远程加载选项
        load_options = type_options.get("loadOptions")
        if isinstance(load_options, dict):
            check_invocation(load_options, loc, f"{where}.loadOptions", ctx)
            if component in ("Select", "Cascader"):
                for cap in ("allow-create", "clearable"):
                    if not type_options.get(cap):
                        warn(loc, f"{where} 使用了 loadOptions，建议同时设置 typeOptions.{cap}=true，"
                                  "否则远程不可达时用户无法填写或清空")

        load_schema = type_options.get("loadSchema")
        if isinstance(load_schema, dict):
            check_invocation(load_schema, loc, f"{where}.loadSchema", ctx)

        # --- 测试按钮
        if component == "TestButton":
            invoke = type_options.get("invokeMethod")
            if not isinstance(invoke, dict):
                err(loc, f"{where} TestButton 必须配置 typeOptions.invokeMethod"
                         "（不能平级写在 typeOptions 根上）")
            else:
                check_invocation(invoke, loc, f"{where}.invokeMethod", ctx, is_test_button=True)
            for stray in ("method", "provider", "credentialsType", "credentialsName", "dependsOn"):
                if stray in type_options:
                    err(loc, f"{where} typeOptions.{stray} 必须移入 invokeMethod 内")

        # --- 集合类
        sub_fields = field.get("options")
        is_sub_schema = (isinstance(sub_fields, list) and sub_fields
                         and isinstance(sub_fields[0], dict) and "uiComponent" in sub_fields[0])

        if component == "FixedCollection" and is_sub_schema:
            row_default = field.get("defaultValue")
            if not isinstance(row_default, dict):
                warn(loc, f"{where} FixedCollection 建议配置字段级 defaultValue（与 name 同级），"
                          "否则新增行的子字段为 undefined")
            else:
                missing = [f.get("name") for f in sub_fields
                           if isinstance(f, dict) and f.get("name") not in row_default]
                if missing:
                    err(loc, f"{where} defaultValue 缺少子字段 {missing}，新增行时这些字段为 undefined")

        if component == "RelationCollection" and is_sub_schema:
            for f in sub_fields:
                if isinstance(f, dict) and f.get("name") == "_id":
                    err(loc, f"{where} 不要在 options 中定义 _id，该字段由组件自动生成")

        if is_sub_schema:
            walk_fields(sub_fields, loc, f"{where}.options", ctx)


def check_credential_type(cred: str, loc: str, where: str, ctx: dict) -> None:
    if not PASCAL_CASE.match(str(cred)):
        err(loc, f"{where} 凭证类型标识 '{cred}' 必须是 PascalCase（如 MysqlCredential）")
    if ctx["credential_types"] and cred not in ctx["credential_types"]:
        err(loc, f"{where} credentialsType='{cred}' 无对应 @CredentialsDescription(type)，"
                 f"已知: {sorted(ctx['credential_types'])}")


def check_invocation(spec: dict, loc: str, where: str, ctx: dict,
                     is_test_button: bool = False) -> None:
    method = spec.get("method")
    provider = spec.get("provider")
    if not method:
        err(loc, f"{where} 缺少 method")
    if not provider:
        err(loc, f"{where} 缺少 provider（credentials 或 bundle）")
    elif provider not in ("credentials", "bundle"):
        err(loc, f"{where} provider 只能是 credentials 或 bundle，实际 '{provider}'")

    if "credentialsName" in spec:
        err(loc, f"{where} credentialsName 已废弃：provider=credentials 用 credentialsType，"
                 "provider=bundle 用 credentialsRef")

    depends_on = spec.get("dependsOn")
    if depends_on is not None and not isinstance(depends_on, list):
        err(loc, f"{where} dependsOn 必须是数组")
        depends_on = None

    if provider == "credentials":
        if "credentialsRef" in spec:
            err(loc, f"{where} provider=credentials 时不使用 credentialsRef，"
                     "后端直接经凭证服务访问，请改用 credentialsType")
        cred = spec.get("credentialsType")
        if not cred:
            err(loc, f"{where} provider=credentials 时必须配置 credentialsType")
        else:
            check_credential_type(cred, loc, where, ctx)
            if method and method not in BUILTIN_METHODS \
                    and method not in ctx["credential_methods"].get(cred, set()):
                warn(loc, f"{where} method='{method}' 未在 {cred} 的 Provider 中用 "
                          f"request.is(\"{method}\") 处理")

    if provider == "bundle":
        if "credentialsType" in spec:
            err(loc, f"{where} provider=bundle 时不使用 credentialsType，"
                     "请改用 credentialsRef 指向表单内 CredentialSelect 字段的 name")
        ref = spec.get("credentialsRef")
        cred_fields = ctx.get("form_credential_fields") or {}
        if ref:
            if cred_fields and ref not in cred_fields:
                err(loc, f"{where} credentialsRef='{ref}' 在本表单中找不到对应的 "
                         f"CredentialSelect 字段，已有: {sorted(n for n in cred_fields if n)}")
            if isinstance(depends_on, list) and ref in depends_on:
                err(loc, f"{where} credentialsRef 已隐含凭证依赖，不要把 '{ref}' 重复写进 dependsOn")
        elif cred_fields:
            err(loc, f"{where} provider=bundle 时必须配置 credentialsRef，"
                     f"可选: {sorted(n for n in cred_fields if n)}")
        if depends_on is None:
            err(loc, f"{where} provider=bundle 时 dependsOn 必须显式写出，无其他依赖时写空数组 []")
        if method and ctx["method_names"] and method not in ctx["method_names"]:
            err(loc, f"{where} method='{method}' 无对应 MethodExecutor.getMethodName()，"
                     f"已知: {sorted(ctx['method_names'])}")

    if is_test_button and method and method != "test":
        warn(loc, f"{where} 测试连接的 method 固定为 \"test\"（CredentialsMethodRequest."
                  f"TEST_CONNECTION），实际 '{method}'；用 request.isTestConnection() 判断")


def check_properties_file(path: Path, project: Path, ctx: dict):
    loc = str(path.relative_to(project))
    data = load_json(path, loc)
    if data is None:
        return {}
    if not isinstance(data, dict):
        err(loc, "根节点必须是对象")
        return {}
    if "properties" not in data:
        if "parameters" in data:
            err(loc, "根数组字段名应为 properties，不是 parameters")
        else:
            err(loc, "缺少 properties 数组")
        return {}

    cred_fields: dict = {}
    collect_credential_fields(data["properties"], cred_fields)
    ctx = dict(ctx, form_credential_fields=cred_fields)

    walk_fields(data["properties"], loc, "properties", ctx)

    non_data = {}
    _collect_components(data["properties"], non_data)

    default_value = data.get("defaultValue")
    if default_value is None:
        return {}
    if not isinstance(default_value, dict):
        err(loc, "defaultValue 必须是对象")
        return {}
    for k, v in default_value.items():
        if v == "":
            warn(loc, f"defaultValue.{k} 为空字符串，语义为空的字段应省略该键")
        if non_data.get(k) in NON_DATA_COMPONENTS:
            warn(loc, f"defaultValue.{k} 对应的 {non_data[k]} 不产生业务数据，不应写入 defaultValue")
    return default_value


def _collect_components(fields, acc: dict) -> None:
    if not isinstance(fields, list):
        return
    for field in fields:
        if isinstance(field, dict):
            acc[field.get("name")] = field.get("uiComponent")


# --------------------------------------------------------------------------- spi

SPI_FILES = {
    "FlowNode": "cn.buildify.bundle.api.FlowNode",
    "MethodExecutor": "cn.buildify.bundle.api.MethodExecutor",
    "BundleActivator": "cn.buildify.bundle.api.BundleActivator",
    "CredentialsProvider": "cn.buildify.bundle.api.credentials.CredentialsProvider",
}


def check_spi(project: Path, impls: dict, all_fqcn: set) -> None:
    services = project / "src/main/resources/META-INF/services"
    for iface, filename in SPI_FILES.items():
        expected = {jf.fqcn for jf in impls[iface]}
        spi = services / filename
        loc = f"META-INF/services/{filename}"
        if not expected:
            if spi.is_file() and spi.read_text(encoding="utf-8").strip():
                warn(loc, "存在 SPI 文件但项目中没有对应实现类")
            continue
        if not spi.is_file():
            err(loc, f"缺少 SPI 文件，未注册: {sorted(expected)}")
            continue
        listed = {line.strip() for line in spi.read_text(encoding="utf-8").splitlines()
                  if line.strip() and not line.strip().startswith("#")}
        for missing in sorted(expected - listed):
            err(loc, f"实现类未注册: {missing}")
        for extra in sorted(listed - expected):
            if extra not in all_fqcn:
                err(loc, f"注册了不存在的类: {extra}")
            else:
                warn(loc, f"注册的类未实现 {iface}: {extra}")


# --------------------------------------------------------------------------- 代码规范

REMOVED_APIS = ("sendRequestEvent", "sendResponseEvent", "RequestEvent",
                "ResponseEvent", "onRequestEvent", "onResponseEvent")


def check_common_code(jf: JavaFile) -> None:
    code, loc = jf.code, jf.rel
    for api in REMOVED_APIS:
        if re.search(r"\b%s\b" % api, code):
            err(loc, f"使用了已从 API 移除的事件接口 {api}，节点间 RPC 请改用 context.nodeService()")
    if re.search(r"\$json\b", jf.raw):
        warn(loc, "表达式占位名统一用 msg（如 {{ msg.output.x }}），不要用 $json")
    if re.search(r"log\.\w+\([^)]*(?i:password|apikey|api_key|secret|token)", code):
        warn(loc, "疑似将凭证字段写入日志，请脱敏")


def check_node_service(jf: JavaFile, is_method_executor: bool = False) -> None:
    code, loc = jf.code, jf.rel

    if is_method_executor:
        if "registerHandler(" in code:
            err(loc, "MethodExecutor 不属于 FlowNode 生命周期，只能 nodeService().call(...)，"
                     "不能注册 handler")
        return

    for m in re.finditer(r"registerHandler\(\s*([^)]*)\)", code):
        args = m.group(1).strip()
        if args and "," not in args:
            warn(loc, "registerHandler(handler) 单参数写法只能注册为默认名；"
                      "多实例场景必须用 registerHandler(exposedServiceName, handler)")

    for m in re.finditer(r"\.call\(\s*\"([^\"]+)\"", code):
        svc = m.group(1)
        bare = svc.split(":", 1)[1] if ":" in svc else svc
        if svc.count(":") > 1 or not SERVICE_NAME.match(bare):
            err(loc, f"nodeService().call() 的服务名 '{svc}' 不合法，"
                     "格式应为 exposedServiceName 或 bundleName:exposedServiceName，"
                     "且名称仅含 [A-Za-z0-9._-]")

    body = annotation_body(code, "NodeService")
    if body:
        name_param = attr(body, "nameParameter")
        if name_param and not re.search(r"path\(\s*\"%s\"" % re.escape(name_param), code):
            warn(loc, f"@NodeService(nameParameter=\"{name_param}\") 已声明，但未见 "
                      f"parameters.path(\"{name_param}\") 读取与校验；缺失或非法时必须失败，"
                      "禁止回退到 @NodeService.value()")


def check_node_code(jf: JavaFile, is_trigger: bool) -> None:
    code, loc = jf.code, jf.rel

    if re.search(r"\bparameters\.get\(", code):
        err(loc, "参数读取必须用 parameters.path()，get() 在字段缺失时返回 null 会 NPE")
    if re.search(r"\bnew\s+(?:RuntimeException|IllegalArgumentException)\(", code):
        warn(loc, "已知错误应使用 FlowNodeException 结构化，不要抛出 RuntimeException / IllegalArgumentException")

    routed = re.search(r"\btell(?:Success|Failure|Next)\(", code)
    has_async = re.search(r"\bexecuteBlocking\(|\bsendAsync\(|\bwhenComplete\(|\bthenAccept\(", code)

    if has_async and "complete(" not in code:
        # executeBlocking / sendAsync 等离开 onMsg 后才路由，框架不会自动收尾
        err(loc, "存在异步调用但未调用 context.complete(入站 message)，引擎无法统计在途消息")

    if "getRouter().register(" in code and "unregister(" not in code:
        err(loc, "注册了 HTTP 路由但 destroy() 中没有 unregister，会钉住 ClassLoader")
    if re.search(r"context\.schedule\(|getExecutor\(\)\s*\.\s*schedule\(", code) \
            and "cancel(" not in code:
        err(loc, "注册了定时任务但没有 ScheduledFuture.cancel(true)，会钉住 ClassLoader")
    if "createSandboxExecutor(" in code and ".close()" not in code:
        err(loc, "创建了 SandboxExecutor 但 destroy() 中没有 close()")
    if re.search(r"\bnew\s+Thread\s*\(", code):
        warn(loc, "自建线程需在 destroy() 中中断并 join，建议改用 context.getExecutor()")
    if "ThreadLocal" in code and ".remove()" not in code:
        warn(loc, "使用了 ThreadLocal 但没有 remove()，线程存活期间会永久持有 value")
    if re.search(r"static\s+final\s+(Map|List|Set|ConcurrentHashMap)\w*\s*<", code) \
            and ".clear()" not in code:
        warn(loc, "存在静态集合缓存但未见 clear()，需在 destroy() 或 BundleActivator.stop() 中清理")
    if "registerHandler(" in code and "unregisterHandler(" not in code:
        warn(loc, "注册了节点服务 handler，请确认 destroy() 中已 unregisterHandler()"
                  "（或确认由框架统一注销）")

    if is_trigger:
        if "createTriggerMessage(" not in code:
            err(loc, "触发器节点必须用 context.createTriggerMessage(payload) 创建消息，"
                     "否则遗漏 CORRELATION_ID / BEGIN_RUN_NANOS")
        if re.search(r"put\(\s*\"output\"", code):
            err(loc, "触发器 payload 禁止再包一层 output，业务字段直接放根级"
                     "（下游用 {{ msg.<字段> }} 引用）")
        # 被动触发器（Webhook/监听器）在测试态同样需要注册，不强制分支
        if "isTest()" not in code and "getRouter()" not in code:
            warn(loc, "主动触发器应在 initialize() 中用 context.isTest() 区分测试/生产模式")
        if "destroy" not in code:
            err(loc, "触发器节点必须实现 destroy() 释放定时任务或路由")
    else:
        if routed and not re.search(r"put\(\s*\"output\"", code):
            warn(loc, "非触发器节点应把业务结果收敛到 payload 的 output 字段"
                      "（下游用 {{ msg.output.x }} 引用）")


def check_get_credentials(jf: JavaFile, credential_types: set) -> None:
    for m in re.finditer(r"getCredentials\(\s*\"([^\"]+)\"\s*\)", jf.code):
        arg = m.group(1)
        if arg in credential_types:
            err(jf.rel, f"getCredentials(\"{arg}\") 传入的是凭证类型标识，"
                        "应传节点表单中 CredentialSelect 字段的 name")


# --------------------------------------------------------------------------- bundle.json

def parse_bundle_nodes(data: dict, declared: dict) -> None:
    groups = data.get("groups")
    flat = data.get("nodes")

    if groups and flat:
        warn("bundle.json", "同时存在 groups 与根级 nodes，结构有歧义，请二选一")

    def read_node(node, where):
        name = node.get("name")
        if not name:
            err("bundle.json", f"{where} 缺少 name")
            return
        if not node.get("label"):
            err("bundle.json", f"{where}({name}) 缺少 label")
        summary = node.get("summary") or ""
        if len(summary) > 10:
            warn("bundle.json", f"{where}({name}) summary 建议 ≤ 10 字，当前 {len(summary)} 字")
        if "icon" in node:
            warn("bundle.json", f"{where}({name}) 不要填写 icon；节点图标由平台上传管理，"
                                "不要在工程里生成 SVG")
        declared[name] = node

    if isinstance(groups, list) and groups:
        for gi, group in enumerate(groups):
            if not isinstance(group, dict):
                err("bundle.json", f"groups[{gi}] 必须是对象")
                continue
            if not group.get("label"):
                err("bundle.json", f"groups[{gi}] 缺少 label")
            for ni, node in enumerate(group.get("nodes") or []):
                read_node(node, f"groups[{gi}].nodes[{ni}]")
    elif isinstance(flat, list) and flat:
        for ni, node in enumerate(flat):
            read_node(node, f"nodes[{ni}]")
    else:
        err("bundle.json", "必须提供非空的 groups[].nodes[] 或根级 nodes[]")


# --------------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description="校验 Buildify Bundle 项目")
    parser.add_argument("project", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--strict", action="store_true", help="WARNING 也判定为失败")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    if not project.is_dir():
        print(f"ERROR  目录不存在: {project}", file=sys.stderr)
        return 1

    print(f"校验 Bundle 项目: {project}\n")
    check_pom(project)
    check_docs(project)

    java_files = scan_java(project)
    all_fqcn = {jf.fqcn for jf in java_files}
    impls = {k: [] for k in SPI_FILES}
    for jf in java_files:
        for iface in SPI_FILES:
            if jf.implements(iface):
                impls[iface].append(jf)

    resources = project / "src/main/resources"

    # --- 凭证注解（先扫，供表单校验引用）
    credential_types = set()
    credential_methods = {}
    for jf in impls["CredentialsProvider"]:
        body = annotation_body(jf.code, "CredentialsDescription")
        if body is None:
            err(jf.rel, "CredentialsProvider 实现类缺少 @CredentialsDescription 注解")
            continue
        ctype = attr(body, "type") or attr(body, "name")
        if not ctype:
            err(jf.rel, "@CredentialsDescription 缺少 type 属性")
            continue
        credential_types.add(ctype)
        credential_methods[ctype] = set(re.findall(r"\.is\(\s*\"([^\"]+)\"\s*\)", jf.code))
        if not PASCAL_CASE.match(ctype):
            err(jf.rel, f"凭证类型标识 '{ctype}' 必须是 PascalCase（如 MysqlCredential），"
                        "禁止全小写 / snake_case / kebab-case")
        props = attr(body, "propertiesFile")
        if not props:
            err(jf.rel, f"凭证 '{ctype}' 缺少 propertiesFile")
        else:
            expected = f"credentials/{ctype}.json"
            if props != expected:
                err(jf.rel, f"propertiesFile 必须为 '{expected}'（文件名与 type 逐字一致），"
                            f"实际 '{props}'")
            if not (resources / props).is_file():
                err(jf.rel, f"propertiesFile 指向的文件不存在: src/main/resources/{props}")
        check_common_code(jf)

    # --- MethodExecutor
    method_names = set()
    for jf in impls["MethodExecutor"]:
        m = re.search(r"getMethodName\s*\([^)]*\)\s*\{[^}]*return\s+\"([^\"]+)\"", jf.code, re.S)
        if not m:
            warn(jf.rel, "无法解析 getMethodName() 的返回值，请确认返回字符串字面量")
        else:
            method_names.add(m.group(1))
        check_common_code(jf)
        check_node_service(jf, is_method_executor=True)

    ctx = {"credential_types": credential_types,
           "credential_methods": credential_methods,
           "method_names": method_names,
           "form_credential_fields": {}}

    # --- 节点注解
    nodes = {}
    for jf in impls["FlowNode"]:
        body = annotation_body(jf.code, "FlowNodeDescription")
        if body is None:
            err(jf.rel, "FlowNode 实现类缺少 @FlowNodeDescription 注解")
            continue
        name = attr(body, "name")
        if not name:
            err(jf.rel, "@FlowNodeDescription 缺少 name 属性")
            continue
        if name in nodes:
            err(jf.rel, f"节点 name='{name}' 与 {nodes[name]['file']} 重复")
        is_trigger = attr(body, "isTrigger") == "true"
        has_input = attr(body, "hasInput")
        if is_trigger and has_input != "false":
            err(jf.rel, f"触发器节点 '{name}' 必须同时设置 hasInput = false")
        props = attr(body, "propertiesFile")
        if not props:
            warn(jf.rel, f"节点 '{name}' 未配置 propertiesFile，前端将无配置表单")
        elif not (resources / props).is_file():
            err(jf.rel, f"propertiesFile 指向的文件不存在: src/main/resources/{props}")
        nodes[name] = {"file": jf.rel, "trigger": is_trigger, "properties": props, "java": jf}
        check_node_code(jf, is_trigger)
        check_common_code(jf)
        check_node_service(jf)
        check_get_credentials(jf, credential_types)

    for jf in impls["BundleActivator"]:
        check_common_code(jf)

    # --- bundle.json
    bundle_path = resources / "bundle.json"
    declared = {}
    if not bundle_path.is_file():
        err("bundle.json", "必须位于 src/main/resources 根目录")
    else:
        data = load_json(bundle_path, "bundle.json")
        if isinstance(data, dict):
            if not data.get("bundleName"):
                warn("bundle.json", "缺少根级 bundleName；发布前必须与平台注册名对齐"
                                    "（否则需在发布脚本中显式映射）")
            if "credentials" in data:
                warn("bundle.json", "不需要 credentials 数组，凭证通过 SPI 自动发现")
            parse_bundle_nodes(data, declared)

        for svg in sorted(resources.rglob("*.svg")) + sorted(resources.rglob("*.svgz")):
            rel = svg.relative_to(project)
            warn(str(rel), "不要把节点图标打进 Bundle；图标由平台上传管理，请删除该 SVG")

        for name in sorted(set(declared) - set(nodes)):
            err("bundle.json", f"声明了节点 '{name}' 但没有对应的 "
                               f"@FlowNodeDescription(name=\"{name}\")")
        for name in sorted(set(nodes) - set(declared)):
            err(nodes[name]["file"], f"节点 '{name}' 未在 bundle.json 中声明")

    # --- 表单文件
    for folder in ("properties", "credentials"):
        base = resources / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.json")):
            defaults = check_properties_file(path, project, ctx)
            if folder != "properties" or not isinstance(defaults, dict):
                continue
            rel = f"{folder}/{path.name}"
            node_decl = declared.get(path.stem)
            if node_decl is None:
                continue
            params = node_decl.get("parameters") or {}
            for k, v in defaults.items():
                if k in params and params[k] != v:
                    warn("bundle.json", f"节点 '{path.stem}' parameters.{k}={params[k]!r} 与 "
                                        f"{rel} defaultValue.{k}={v!r} 不一致")
                elif k not in params:
                    warn("bundle.json", f"节点 '{path.stem}' parameters 缺少 {rel} "
                                        f"中的默认值 {k}={v!r}")

    check_spi(project, impls, all_fqcn)

    # --- 输出
    errors = [e for e in ERRORS if e[0] == "ERROR"]
    warnings = [e for e in ERRORS if e[0] == "WARN"]
    by_loc = {}
    for level, loc, msg in ERRORS:
        by_loc.setdefault(loc, []).append((level, msg))

    for loc in sorted(by_loc):
        print(loc)
        for level, msg in by_loc[loc]:
            print(f"  {level:<5} {msg}")
        print()

    print(f"节点 {len(nodes)} 个，凭证 {len(credential_types)} 个，"
          f"动态方法 {len(method_names)} 个，Activator {len(impls['BundleActivator'])} 个")
    print(f"结果: {len(errors)} ERROR, {len(warnings)} WARNING")

    if errors:
        return 1
    if warnings and args.strict:
        return 1
    print("校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
