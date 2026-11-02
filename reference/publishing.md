# README、CHANGELOG 与发布

## 目录

- [README.md（每个 Bundle 必须）](#readmemd每个-bundle-必须)
- [CHANGELOG.md 与平台 releaseNote](#changelogmd-与平台-releasenote)
- [buildify-publish CLI](#buildify-publish-cli)
- [命名与图标](#命名与图标)
- [发布流程](#发布流程)
- [源码版本管理](#源码版本管理)

## README.md（每个 Bundle 必须）

放在模块根目录，需包含以下章节（顺序不限）：

| 章节 | 内容 |
|---|---|
| **节点一览** | 表格列出所有节点名称、类型（触发器/普通）、一句话说明 |
| **快速开始** | 凭证配置步骤 + 每个节点的参数说明和输出字段示例 |
| **项目结构** | 目录树，标注各文件职责 |
| **构建** | `mvn package` 命令及产物路径 |
| **依赖** | 表格列出关键依赖、版本和 scope |
| **错误码** | 表格列出代码中出现的每个错误码：错误码、含义、排查建议（`FlowNodeException` 约定，校验脚本会对照检查） |
| **技术说明** | 设计要点（连接管理、异步模型、重连策略等） |

输出字段示例必须是 JSON 代码块。普通节点带 `output` 包裹，触发器不带：

````markdown
成功后输出：

```json
{ "output": { "statusCode": 200, "body": "..." } }
```
````

调用三方接口的节点还要写出失败时的 `msg.error` 示例，说明 `metadata.statusCode` 与 `metadata.body`。

错误码表示例（`Validator` 校验失败统一是 `VALIDATION_ERROR`；带业务码的写成 `<前缀>_API_<业务码>` 一行即可）：

```markdown
| 错误码 | 含义 | 排查建议 |
|--------|------|----------|
| `DINGTALK_HTTP_ERROR` | 接口返回非 2xx | 查看 `metadata.statusCode` 与 `metadata.body` |
| `DINGTALK_API_<业务码>` | HTTP 2xx 但返回业务错误码 | 对照钉钉错误码文档 |
| `HTTP_IO_ERROR` | 连接失败或超时 | 检查网络与超时设置 |
```

引用规范：节点参数名、字段名用反引号；表达式按组件写（JSON `={{msg.xxx}}`，
SQL `#{msg.xxx}` / `${msg.xxx}`，文本 `{{msg.xxx}}`）；占位名统一用 `msg`，**不要**用 `$json`。

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
需要 Python 3.10+，入口命令 `buildify-publish`。一把密钥对应一个工作空间，
本地用命名 profile 保存多把密钥。除了上传版本，还能创建命名空间和软件包、修改包信息、
上传节点图标、设置平台上的说明文档，不必再让用户去控制台操作。

权威参考是包内 `usage.md`（等同 `buildify-publish help` 的输出）。命令和本文不一致时以它为准。

```bash
pip install -U buildify-publish-cli   # 或 pipx / uv tool install；旧版本没有建包、图标命令
buildify-publish help
```

### 子命令

完整名 `namespace/name` 一律用 `--name` 传，不拼在 URL 里。

| 子命令 | HTTP | 作用 |
|---|---|---|
| `health` | `GET /v1/health` | 连通性检查，无需密钥 |
| `key test` | `GET /v1/publish-key/test` | 返回 `tenantId`、`tenantName`（工作空间名）、`keyPrefix`、`scopes`，并缓存到 profile |
| `bundle namespaces` | `GET /v1/bundles/namespaces` | 列出本工作空间的命名空间 |
| `bundle namespace create --name <slug> [--remark]` | `POST /v1/bundles/namespaces` | 创建命名空间；slug 全平台唯一，每个工作空间最多 5 个 |
| `bundle namespace delete --name <slug>` | `DELETE /v1/bundles/namespaces/{slug}` | 下面还有软件包时失败 |
| `bundle create --namespace <slug> --name <short> --display-name <显示名> [--summary] [--visibility] [--icon]` | `POST /v1/bundles` | 创建软件包，完整名为 `slug/short` |
| `bundle update --name <ns/name> [--display-name] [--summary] [--visibility] [--icon]` | `POST /v1/bundles/metadata` | 只改传入的字段；`--summary ''` 清空简介 |
| `bundle info --name <ns/name>` | `GET /v1/bundles/info` | 查询软件包与版本 |
| `bundle icons --name <ns/name>` | `GET /v1/bundles/icons` | 列出已上传的节点图标 |
| `bundle icon upload --name <ns/name> --icon-name <名> --file <图片>` | `POST /v1/bundles/icons` | 上传节点图标；同名覆盖 |
| `bundle icon delete --name <ns/name> --icon-name <存储名>` | `DELETE /v1/bundles/icons` | 删除图标，名字**带扩展名** |
| `bundle doc get --name <ns/name>` | `GET /v1/bundles/document` | 读取平台说明文档 |
| `bundle doc set --name <ns/name> --file README.md` | `PUT /v1/bundles/document` | 用 UTF-8 Markdown 覆盖说明文档；空文件即清空 |
| `bundle upload` | `POST /v1/bundles/versions` | 上传 JAR 版本（multipart），见下文 |
| `config` | — | 读写 `~/.buildifyrc`，见下表 |

`--visibility` 只能是 `internal`（默认）或 `restricted`，不能设为公开。
`--icon` 是软件包封面图标（png/jpg/jpeg/gif/webp/svg，≤ 1MB），与节点图标无关。

密钥的 `scopes` 列出它能用的权限，`null` 表示全部权限。权限不足返回 HTTP 403、退出码 2：
告诉用户缺哪项操作，请他在控制台给这把密钥加权限或换一把，不要换别的工作空间的密钥绕过。

`config` 子命令：

| 子命令 | 作用 |
|---|---|
| `add-profile <name>` | 经 stdin 保存一把工作空间密钥；**不**改默认 profile |
| `profiles` | 列出已保存 profile（无密钥明文）；`--json` 含 `tenantId` / `tenantName` |
| `use <name>` | 把该 profile 写成 `[publish].current`（机器默认） |
| `remove-profile <name>` | 删除一把密钥；若它是 current，则清空默认 |
| `set-base-url` / `set-key base_url` | 写 `[publish].base_url` |
| `set-api-key` / `set-key api_key` | 更新 **当前** profile；没有 current 时写 `[publish].api_key`（列出时名为 `default`） |
| `init` / `show` | 初始化 / 查看（`show` 只显示文件内容与掩码，不含环境变量合并结果） |

### 配置与认证

全局选项 `--base-url`、`--api-key`、`--profile`、`--json`（单行 JSON 信封）、`--quiet`。

环境变量 `BUILDIFY_PUBLISH_BASE_URL`、`BUILDIFY_PUBLISH_API_KEY`、`BUILDIFY_PUBLISH_PROFILE`、
`BUILDIFY_PUBLISH_JSON`、`BUILDIFY_PUBLISH_NO_PROMPT`、`NO_COLOR`。

认证头 `Authorization: Bearer <keyId>.<secret>`。密钥在控制台当前工作空间的
**系统设置 → API Keys → buildify-publish-cli 密钥** 创建/轮换，CLI 不签发密钥。

配置文件 `~/.buildifyrc`（Windows 为 `%USERPROFILE%\.buildifyrc`），模式 `600`，
与编排 CLI `buildify` 共用。发布配置只读写 `[publish]`，不写文件根，也**不**写入 `[openapi]`；
文件根上的 `base_url` / `api_key` 不再读取，老配置要用 `config set-key` 重新写一次。

| 位置 | 内容 |
|---|---|
| `[publish].base_url` | 发布 API 主机 |
| `[publish].api_key` | 单密钥，profile 名固定为 `default` |
| `[publish].current` | `config use` 写入的默认 profile 名 |
| `[publish].profiles.<name>` | `api_key`，以及 `key test` 缓存的 `tenant_id` / `tenant_name` / `key_prefix` |

**Base URL：** `--base-url` → `BUILDIFY_PUBLISH_BASE_URL` → 文件 → 默认 `https://publish.buildify.cn`。

**选钥：**

1. `--api-key` 或 `BUILDIFY_PUBLISH_API_KEY`（忽略已保存的 profile）
2. `--profile` 或 `BUILDIFY_PUBLISH_PROFILE`
3. 从当前目录向上找到的 `.buildify-workspace`（文件只含一行公开 `tenantId`，来自 `key test`）
4. `[publish].current`
5. 仅保存了一把密钥时用这一把

没有密钥时：交互终端会提示创建并写入 `~/.buildifyrc`；`--json`、CI、管道或
`BUILDIFY_PUBLISH_NO_PROMPT=1` 则退出码 2，`data.reason=missing_api_key`。

多把密钥且上面 1–4 都没选定时，退出码 2，`data.reason=profile_required`，
`data.profiles` 不含密钥。`--profile` 名称不存在时 `data.reason=profile_not_found`。
仓库钉了工作空间、本地没有 `tenant_id` 匹配的密钥时，`data.reason=workspace_key_missing`。

密钥经 stdin 写入，避免出现在进程列表和 shell 历史里：

```bash
printf '%s' 'keyId.secret' | buildify-publish config add-profile acme
buildify-publish --profile acme --json key test
buildify-publish --json config profiles
```

代用户发布时：

- `missing_api_key`：按下方模板向用户要密钥，拿到后用上面的 stdin 命令 `add-profile`，再 `key test`
- `profile_required`：展示列表（无密钥），问一次，之后的命令都带 `--profile <name>`
- 用户没有要求改这台机器的默认工作空间时，保持 `[publish].current` 不变
- `workspace_key_missing`：按下方模板要 `.buildify-workspace` 里那个工作空间的密钥再 `add-profile`；上传使用与该 id 匹配的密钥
- HTTP 401 / 403：密钥失效或被轮换，按下方模板请用户重新创建

向用户要密钥时照这个说法，不要只说「请提供 API Key」：

> 发布需要一把发布密钥。请在 Buildify 控制台切到要发布的工作空间，打开
> **系统设置 → API Keys → buildify-publish-cli 密钥**，点创建（已有可直接复制），
> 把完整密钥（形如 `keyId.secret`）发给我。我会通过 stdin 保存到本机 `~/.buildifyrc`，
> 不会写进代码仓库或命令历史。

拿到密钥后不要回显明文；`key test` 成功后告诉用户密钥对应的工作空间名（`tenantName`），
确认是要发布的那个空间再继续。

没有密钥时 `--json` 输出的 `data.userMessage` 是给用户看的中文操作说明，可以直接转述；
`data.agentInstructions` 是给 Agent 的处理建议。

### 退出码

| Code | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 通用失败 |
| 2 | 缺密钥、profile 未选定或名称不存在、工作空间无本地密钥、HTTP 401 / 403 |
| 3 | 本地校验失败（文件不存在、说明超长、`--visibility` 非法、profile 名非法等） |
| 4 | HTTP 4xx（如 404 软件包或命名空间不存在、409 名称已被占用） |
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

## 命名与图标

**软件包名。** `bundle.json` 根级 `bundleName` 是唯一事实来源，格式固定为 `命名空间/包名`，
必须等于平台上的完整名和所有命令的 `--name`。两段都由服务端校验：只能用小写字母、数字和
`. _ -`，符号不能连续、不能在首尾。不符合时先改 `bundle.json`，不要在命令里另起一个名字。
文件未声明时须先补全，**禁止臆造**。

**节点图标。** 节点 `icon` 默认 `"default.svg"`。要自定义时：

1. 图片放在 Bundle 根目录的 `icons/`（不放 `src/main/resources`，不打进 JAR）。
   支持 png/jpg/jpeg/gif/webp/svg，≤ 1MB。
2. 上传：`--icon-name` 不带扩展名，只能用字母、数字、`_`、`-`。
   平台存储名是「图标名 + 原文件扩展名」，同名再传会覆盖。
3. 把节点 `icon` 写成存储名，并用 `bundle icons` 确认它在列表里。

```bash
buildify-publish bundle icon upload --name acme/http --icon-name HttpTrigger --file icons/http.svg
# 存储名为 HttpTrigger.svg → bundle.json 节点写 "icon": "HttpTrigger.svg"
buildify-publish --json bundle icons --name acme/http
buildify-publish bundle icon delete --name acme/http --icon-name HttpTrigger.svg   # 删除要带扩展名
```

图标上传依赖软件包已存在；新包先 `bundle create` 再传图标。

## 发布流程

版本的单一事实来源是该模块 `pom.xml` 的 `<version>`，须与 `-v/--version` 和 JAR 文件名一致。

| 步骤 | 动作 |
|---|---|
| 1 | `buildify-publish --json key test`，向用户确认 `tenantName` 就是目标工作空间 |
| 2 | `bundle info --name <bundleName>`。存在就跳到第 4 步 |
| 3 | 不存在时建包，见下文「新建软件包」 |
| 4 | 有自定义图标时 `bundle icon upload`，并核对 `bundle.json` 中的 `icon` |
| 5 | 读当前版本：`mvn -q -Dexpression=project.version -DforceStdout help:evaluate`，按 SemVer 修改 `pom.xml` 的 `<version>` |
| 6 | 重写 `CHANGELOG.md`，仅本 bundle、本版本一节 |
| 7 | 构建：`mvn -q clean package`（monorepo 用 `mvn -pl <artifact> -am clean package -DskipTests`，**必须含 `clean`**） |
| 8 | `bundle upload`，必须带 `--release-notes-file` |
| 9 | `bundle doc set --file README.md`，让平台说明文档与本版本 README 一致 |
| 10 | `bundle info` 核对版本、releaseNote 与 latest 标记 |

必须先 `clean` 再 `package`，避免旧 JAR / 过时 class 混入发布产物。

### 新建软件包

`bundle info` 返回 404 时说明平台上还没有这个包。不要自己编名字，把下面的信息列给用户确认**一次**：

- 完整名：取自 `bundle.json` 的 `bundleName`（`命名空间/包名`）
- 显示名、一句话简介（默认取 README 标题和第一段）
- 可见性：`internal`（默认，工作空间内可用）或 `restricted`

确认后：

```bash
buildify-publish --json bundle namespaces                       # 命名空间已存在就跳过下一行
buildify-publish --json bundle namespace create --name acme
buildify-publish --json bundle create --namespace acme --name http \
  --display-name 'HTTP 工具' --summary '收发 HTTP 请求'
```

`namespace create` 返回 409 表示该命名空间已被其他工作空间占用，请用户换一个，并同步修改
`bundle.json` 的 `bundleName`；每个工作空间最多 5 个命名空间。`bundle create` 返回 409 表示同名包已存在。

### 上传

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

CI 用 `BUILDIFY_PUBLISH_API_KEY`（忽略本机 profile）或 `BUILDIFY_PUBLISH_PROFILE`；
设 `BUILDIFY_PUBLISH_NO_PROMPT=1`，避免缺密钥时进入交互提示。需要机器解析输出时加
`BUILDIFY_PUBLISH_JSON=1` 或 `--json`，按退出码和 `data.reason` 分支。多把密钥时上传命令带
`--profile <name>`。

### 更新包信息与说明文档

```bash
buildify-publish bundle update --name official/wecom-bot --summary '企业微信群机器人消息'
buildify-publish bundle update --name official/wecom-bot --icon ./icons/cover.png   # 换封面图标
buildify-publish bundle doc set --name official/wecom-bot --file ./bundle-wecom-bot/README.md
```

`bundle update` 只改传入的字段。`bundle doc set` 整份覆盖，内容上限约 4Mi 字符。

## 源码版本管理

开发完成（校验 0 ERROR、打包通过）后、发布前，检查 Bundle 目录是否在 git 仓库里并且有远程地址：

```bash
git -C <bundle 目录> rev-parse --is-inside-work-tree && git -C <bundle 目录> remote -v
```

不是 git 仓库，或 `remote -v` 为空时，照这个说法提示用户，不要跳过：

> 这个 Bundle 还没有放进源码仓库。建议提供一个仓库地址（GitHub / Gitee / 公司 GitLab 均可），
> 我来初始化并推送。这样每个发布版本都能对应到一次提交，出问题可以回滚，也方便多人协作。

- 用户给了地址：`git init`（已是仓库则跳过），确认 `.gitignore` 存在（脚手架会生成；没有就补上
  `target/`、`*.jar`、`.idea/`、`*.iml`、`.vscode/`、`.DS_Store`），提交后 `git remote add origin <地址>`
  并推送。推送失败就贴出错误，不要改用别的地址。
- 用户不提供：只提醒这一次，不阻塞发布，也不要自己去创建远程仓库。
- 可以提交 `.buildify-workspace`（只有公开的 `tenantId`）；**不要**提交发布密钥、`~/.buildifyrc`
  或凭证明文。
- 已有仓库时，发布前确认改动已提交，便于把版本号和提交对应起来。
