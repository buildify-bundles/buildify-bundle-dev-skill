# README、CHANGELOG 与发布

## 目录

- [README.md（每个 Bundle 必须）](#readmemd每个-bundle-必须)
- [CHANGELOG.md 与平台 releaseNote](#changelogmd-与平台-releasenote)
- [buildify-publish CLI](#buildify-publish-cli)
- [发布流程](#发布流程)

## README.md（每个 Bundle 必须）

放在模块根目录，需包含以下章节（顺序不限）：

| 章节 | 内容 |
|---|---|
| **节点一览** | 表格列出所有节点名称、类型（触发器/普通）、一句话说明 |
| **快速开始** | 凭证配置步骤 + 每个节点的参数说明和输出字段示例 |
| **项目结构** | 目录树，标注各文件职责 |
| **构建** | `mvn package` 命令及产物路径 |
| **依赖** | 表格列出关键依赖、版本和 scope |
| **技术说明** | 设计要点（连接管理、异步模型、重连策略等） |

输出字段示例必须是 JSON 代码块。普通节点带 `output` 包裹，触发器不带：

````markdown
成功后输出：

```json
{ "output": { "statusCode": 200, "body": "..." } }
```
````

引用规范：节点参数名、字段名用反引号；表达式写作 `={{ msg.output.xxx }}`；
消息 payload 的占位名统一用 `msg`，**不要**用 `$json`。

## CHANGELOG.md 与平台 releaseNote

`buildify-publish bundle upload` 的 multipart 字段 `releaseNote` 来源于 CLI 的
`--release-notes-file`。**不传则平台侧发布说明为空**，控制台和 API 都看不到本次变更说明。

### 强制规则

- 每次执行 `bundle upload`（含 AI / CI 自动化）**必须**带 `--release-notes-file <path>`，
  指向 UTF-8 Markdown。仅 `*-SNAPSHOT` 纯内部迭代可豁免，且需在 MR / 提交说明中写明"无 releaseNote"
- **monorepo（本仓库）**：每个 `bundle-<artifact>/CHANGELOG.md` 与对应 `pom.xml` 同级，
  **全文仅保留一节**，标题 `## x.y.z - YYYY-MM-DD` 必须与该模块当前 `pom.xml` 的 `<version>`
  和本次 `-v/--version` 完全一致。发新版本时**整文件重写**，历史以 Git 为准
- **禁止**在同一 `releaseNote` 文件中混入其他 bundle、其他产品或与本版本无关的仓库历史
- 仓库根 `CHANGELOG.md` 若存在，宜作为索引指向各模块，**不宜**作为默认上传目标（容易串包）

### 正文写法

读者是**安装和编排的用户**，要让他们一眼看懂"装上这一版后，本 Bundle 的行为有什么不同"。

| 应写 | 禁止写 |
|---|---|
| 功能新增 / 废弃 | 文件路径说明 |
| 节点默认值或字段语义变化 | `buildify-publish` / CLI 参数用法 |
| 输出 JSON 结构变化 | `spec.md` 章节引用 |
| 兼容性或破坏性变更 | 仓库目录约定 |
| 用户可见的缺陷修复 | "某次发布同步规范"等元信息 |
| 对接设备 / API 的注意事项 | |

确实没有用户可见差异时，用一句"与上一版本行为一致"或"仅文档更新"即可，
不要堆模板。该节**不得为空**，禁止只写"见 README"。

## buildify-publish CLI

仓库内维护的官方 CLI，目录 `tools/buildify-publish-cli`，PyPI 包名 `buildify-publish-cli`，
需要 Python 3.10+，入口命令 `buildify-publish`。

权威参考是包内 `usage.md`（等同 `buildify-publish help` 的输出）。

```bash
pip install buildify-publish-cli      # 或 pipx / uv tool install
```

### 子命令

| 子命令 | HTTP |
|---|---|
| `health` | `GET /v1/health`（无需 API Key） |
| `key test` | `GET /v1/publish-key/test` |
| `bundle info` | `GET /v1/bundles/info?bundleName=...` |
| `bundle upload` | `POST /v1/bundles/versions`（multipart） |
| `config` | 读写 `~/.buildifyrc`：`init` / `set-base-url` / `set-api-key` / `set-key` / `show` |

### 配置与认证

全局选项 `--base-url`、`--api-key`、`--json`（单行 JSON 信封）、`--quiet`。

环境变量 `BUILDIFY_PUBLISH_BASE_URL`、`BUILDIFY_PUBLISH_API_KEY`、`BUILDIFY_PUBLISH_JSON`、`NO_COLOR`。

解析优先级：命令行参数 → 环境变量 → `~/.buildifyrc`（TOML，仅允许 `base_url` / `api_key`）
→ 默认 `https://publish.buildify.cn`。

认证头 `Authorization: Bearer <keyId>.<secret>`，密钥在控制台创建/轮换。

```bash
printf '%s' 'keyId.secret' | buildify-publish config set-api-key   # 推荐走 stdin
buildify-publish key test
```

### 退出码

| Code | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 通用失败 |
| 2 | 缺配置 / 鉴权失败 / HTTP 401、403 |
| 3 | 本地校验失败（文件不存在、api_key 为空） |
| 4 | HTTP 4xx |
| 5 | 网络超时、连接错误 |

### upload multipart 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `bundleName` | 是 | 逻辑名，可含 `/` |
| `bundleVersion` | 是 | 须与 JAR 内版本一致 |
| `file` | 是 | JAR 文件 |
| `overwrite` | 否 | **仅 `-SNAPSHOT` 版本**可覆盖 |
| `latestVersion` | 否 | 不传则服从服务端默认 |
| `releaseNote` | 否 | Markdown 正文，上限约 4Mi 字符 |

## 发布流程

`bundleName` 的单一事实来源是该模块 `src/main/resources/bundle.json` 根级的 `bundleName`，
必须与平台注册名和 `-n/--name` 一致。文件未声明时须先补全，或在发布脚本中显式维护
「artifactId → bundleName」映射，**禁止臆造**。

版本的单一事实来源是该模块 `pom.xml` 的 `<version>`，须与 `-v/--version` 和 JAR 文件名一致。

| 步骤 | 动作 |
|---|---|
| 1 | 读当前版本：`mvn -q -Dexpression=project.version -DforceStdout help:evaluate` |
| 2 | 按 SemVer 修改 `pom.xml` 的 `<version>` |
| 3 | 构建：`mvn -pl <artifact> -am clean package -DskipTests`（**必须含 `clean`**） |
| 4 | 重写 `bundle-<artifact>/CHANGELOG.md`，仅本 bundle、本版本一节 |
| 5 | 上传，必须带 `--release-notes-file` |
| 6 | 用 `bundle info` 或控制台确认版本、releaseNote 与 latest 标记 |

必须先 `clean` 再 `package`，避免旧 JAR / 过时 class 混入发布产物。

```bash
# SNAPSHOT 允许覆盖
buildify-publish bundle upload \
  -n 'official/wecom-bot' \
  -v '1.0.1-SNAPSHOT' \
  -f ./bundle-wecom-bot/target/bundle-wecom-bot-1.0.1-SNAPSHOT.jar \
  --overwrite \
  --release-notes-file ./bundle-wecom-bot/CHANGELOG.md

# 正式版本不要加 --overwrite
buildify-publish bundle upload \
  -n 'official/wecom-bot' -v '1.0.1' \
  -f ./bundle-wecom-bot/target/bundle-wecom-bot-1.0.1.jar \
  --release-notes-file ./bundle-wecom-bot/CHANGELOG.md
```

CI 中设置 `BUILDIFY_PUBLISH_API_KEY`；需要机器解析输出时加 `BUILDIFY_PUBLISH_JSON=1`
或 `--json`，按退出码分支。
