"""scaffold_bundle.py 与 validate_bundle.py 的回归测试。

    python3 -m unittest discover -s tests -v
    RUN_MAVEN=1 python3 -m unittest discover -s tests -v   # 额外执行 mvn package

仅依赖 Python 3.8+ 标准库。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = ROOT / "scripts" / "scaffold_bundle.py"
VALIDATE = ROOT / "scripts" / "validate_bundle.py"

BASE_ARGS = ["--group-id", "com.example", "--artifact-id", "demo",
             "--bundle-name", "example/demo", "--package", "com.example.bundle"]
FULL_ARGS = BASE_ARGS + ["--node", "MyNode", "--trigger", "MyTrigger", "--webhook", "MyHook",
                         "--credential", "MyApiCredential",
                         "--method", "GetTablesExecutor:getTables", "--generic-api", "ApiCall"]

NODES = "src/main/java/com/example/bundle/nodes"
RES = "src/main/resources"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, encoding="utf-8")


class ScriptTestCase(unittest.TestCase):
    full: Path

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="bundle-skill-test-"))
        cls.full = cls.tmp / "full"
        result = run(SCAFFOLD, "--dir", str(cls.full), *FULL_ARGS)
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def copy_full(self) -> Path:
        dest = Path(tempfile.mkdtemp(dir=self.tmp)) / "project"
        shutil.copytree(self.full, dest)
        return dest

    def validate(self, project: Path, *extra: str) -> subprocess.CompletedProcess:
        return run(VALIDATE, str(project), *extra)


class ScaffoldTest(ScriptTestCase):

    def test_full_scaffold_passes_strict(self):
        result = self.validate(self.full, "--strict")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("0 ERROR, 0 WARNING", result.stdout)

    def test_minimal_scaffold_passes_strict(self):
        project = self.tmp / "minimal"
        self.assertEqual(run(SCAFFOLD, "--dir", str(project), *BASE_ARGS, "--node", "MyNode")
                         .returncode, 0)
        result = self.validate(project, "--strict")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_scaffold_leaves_no_placeholders(self):
        for path in self.full.rglob("*"):
            if path.is_file():
                self.assertNotIn("{{", path.read_text(encoding="utf-8").replace("={{", "")
                                 .replace("{{ msg", ""), str(path))

    def test_scaffold_does_not_overwrite_without_force(self):
        target = self.full / "README.md"
        original = target.read_text(encoding="utf-8")
        target.write_text("edited", encoding="utf-8")
        try:
            run(SCAFFOLD, "--dir", str(self.full), *FULL_ARGS)
            self.assertEqual(target.read_text(encoding="utf-8"), "edited")
        finally:
            target.write_text(original, encoding="utf-8")

    def test_scaffold_rejects_invalid_arguments(self):
        cases = {
            "generic api without credential": ["--generic-api", "ApiCall"],
            "generic api without ApiCall suffix": ["--credential", "C", "--generic-api", "Http"],
            "no node": ["--credential", "C"],
            "lowercase node": ["--node", "myNode"],
            "duplicate node": ["--node", "A", "--trigger", "A"],
            "bad method spec": ["--node", "A", "--method", "NoColon"],
        }
        for label, extra in cases.items():
            with self.subTest(label):
                result = run(SCAFFOLD, "--dir", str(self.tmp / "rejected"), *BASE_ARGS, *extra)
                self.assertEqual(result.returncode, 1)
                self.assertIn("ERROR", result.stderr)
        self.assertFalse((self.tmp / "rejected").exists())


# (说明, 文件, 原文, 替换为, 期望出现在输出中的片段)
MUTATIONS = [
    ("get() on JsonValue",
     f"{NODES}/MyNode.java", 'parameters.path("timeout").asInt(30);',
     'parameters.get("timeout").asInt();', "JsonValue 读取必须用 path()"),
    ("get() on another JsonValue name",
     f"{NODES}/MyNode.java", "JsonValue parameters = context.resolveExpressions",
     'JsonValue p = payload; p.get("x"); JsonValue parameters = context.resolveExpressions',
     "p.get(...)"),
    ("hot update with old parameters",
     f"{NODES}/MyNode.java", "applyParameters(newParameters);",
     "applyParameters(oldParameters);", "把旧参数传给了更新逻辑"),
    ("hot update left empty",
     f"{NODES}/MyNode.java", "applyParameters(newParameters);", "",
     "onParametersUpdated() 也没有用新参数重新赋值"),
    ("async without complete",
     f"{NODES}/MyNode.java", "context.complete(message);", "", "未调用 context.complete"),
    ("getRelations override",
     f"{NODES}/MyNode.java", "    /** 幂等释放 */",
     "    public java.util.List<cn.buildify.bundle.api.Relation> getRelations() { return null; }\n"
     "    /** 幂等释放 */", "不要覆盖 getRelations()"),
    ("trigger missing eventId",
     f"{NODES}/MyTrigger.java", '.put("eventId", eventId)', "", "根级必须包含 eventId"),
    ("trigger single-arg createTriggerMessage",
     f"{NODES}/MyTrigger.java", "createTriggerMessage(payload, eventId)",
     "createTriggerMessage(payload)", "必须传两个参数"),
    ("trigger wraps output",
     f"{NODES}/MyTrigger.java", '.put("triggeredAt", System.currentTimeMillis());',
     '.put("output", System.currentTimeMillis());', "禁止再包一层 output"),
    ("trigger without cancel",
     f"{NODES}/MyTrigger.java", "scheduledFuture.cancel(true);", "", "ScheduledFuture.cancel"),
    ("trigger restart ignores cron",
     f"{NODES}/MyTrigger.java", "!newParameters.path(\"cron\").equals(oldParameters.path(\"cron\"))\n"
                                "                || ", "", "cron"),
    ("webhook without unregister",
     f"{NODES}/MyHook.java", "context.getRouter().unregister(route);", "", "unregister"),
    ("getCredentials with type",
     f"{NODES}/ApiCall.java", 'context.getCredentials("credentialsId")',
     'context.getCredentials("MyApiCredential")', "传入的是凭证类型标识"),
    ("api scope not provided",
     "pom.xml", "<scope>provided</scope>", "", "scope 必须为 provided"),
    ("bundle.json name mismatch",
     f"{RES}/bundle.json", '"name": "MyNode"', '"name": "Other"', "未在 bundle.json 中声明"),
    ("SPI missing node",
     f"{RES}/META-INF/services/cn.buildify.bundle.api.FlowNode",
     "com.example.bundle.nodes.MyNode\n", "", "实现类未注册"),
    ("deprecated credentialsName",
     f"{RES}/properties/MyNode.json", '"credentialsType": "MyApiCredential"',
     '"credentialsName": "MyApiCredential"', "credentialsName 已废弃"),
    ("credentialsRef duplicated in dependsOn",
     f"{RES}/properties/MyNode.json", '"dependsOn": []', '"dependsOn": ["credentialsId"]',
     "不要把 'credentialsId' 重复写进 dependsOn"),
    ("unknown MethodExecutor",
     f"{RES}/properties/MyNode.json", '"method": "getTables"', '"method": "nope"',
     "无对应 MethodExecutor"),
]

WARNING_MUTATIONS = [
    ("requireNonNull in node",
     f"{NODES}/MyNode.java", 'String method = parameters.path("method").asText("GET");',
     'String method = java.util.Objects.requireNonNull(parameters.path("method").asText(null));',
     "Objects.requireNonNull"),
    ("expression disabled",
     f"{RES}/properties/MyNode.json", '"expression": true,', "", "expression: true 与 droppable"),
    ("icon missing",
     f"{RES}/bundle.json", '"icon": "default.svg",', "", "缺少 icon"),
]


class ValidatorMutationTest(ScriptTestCase):

    def mutate(self, rel: str, old: str, new: str) -> Path:
        project = self.copy_full()
        path = project / rel
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, f"fixture drifted: '{old}' not found in {rel}")
        path.write_text(text.replace(old, new), encoding="utf-8")
        return project

    def test_errors_are_reported(self):
        for label, rel, old, new, expected in MUTATIONS:
            with self.subTest(label):
                result = self.validate(self.mutate(rel, old, new))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(expected, result.stdout)

    def test_warnings_fail_only_in_strict_mode(self):
        for label, rel, old, new, expected in WARNING_MUTATIONS:
            with self.subTest(label):
                project = self.mutate(rel, old, new)
                relaxed = self.validate(project)
                self.assertEqual(relaxed.returncode, 0, relaxed.stdout)
                self.assertIn(expected, relaxed.stdout)
                self.assertEqual(self.validate(project, "--strict").returncode, 1)

    def test_svg_in_resources_is_flagged(self):
        project = self.copy_full()
        (project / RES / "icon.svg").write_text("<svg/>", encoding="utf-8")
        result = self.validate(project, "--strict")
        self.assertEqual(result.returncode, 1)
        self.assertIn("不要把节点图标打进 Bundle", result.stdout)

    def test_map_get_is_not_flagged(self):
        result = self.validate(self.full, "--strict")
        self.assertNotIn("JsonValue 读取必须用 path()", result.stdout)

    def test_missing_directory(self):
        result = self.validate(self.tmp / "does-not-exist")
        self.assertEqual(result.returncode, 1)


@unittest.skipUnless(os.environ.get("RUN_MAVEN") == "1" and shutil.which("mvn"),
                     "设置 RUN_MAVEN=1 且安装 Maven 后执行")
class MavenBuildTest(ScriptTestCase):

    def test_full_scaffold_builds(self):
        project = self.copy_full()
        result = subprocess.run(["mvn", "-q", "-B", "clean", "package"], cwd=project,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        jars = [p for p in (project / "target").glob("demo-*.jar")
                if not p.name.startswith("original-")]
        self.assertTrue(jars, "未生成 fat JAR")


if __name__ == "__main__":
    unittest.main()
