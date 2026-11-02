# README、CHANGELOG 与发布

## 目录

- [README.md（每个 Bundle 必须）](#readmemd每个-bundle-必须)
- [CHANGELOG.md 与平台 releaseNote](#changelogmd-与平台-releasenote)
- [buildify-publish CLI](#buildify-publish-cli)
- [命名与图标](#命名与图标)（软件名称与软件描述见[发布流程](#软件名称与软件描述)）
- [发布流程](#发布流程)
- [源码版本管理](#源码版本管理)

## README.md（每个 Bundle 必须）

放在模块根目录。每次发布用 `bundle doc set` **整份**同步到平台，用户在软件包页阅读，编排 Agent
用 `bundle doc` 阅读后决定怎么用节点。所以 README **只写用法**，不要写给 Bundle 开发者看的内容
（项目结构、`mvn`、依赖表格、ClassLoader、SPI、Java 类名实现细节）。那些在本 skill 的
`coding-rules.md` 里，不要进平台文档。

读者有两种，一节里同时照顾到：

| 读者 | 来文档找什么 |
|---|---|
| **用户** | 要不要装这个包、凭证怎么配、每个节点填什么、失败了怎么查 |
| **编排 Agent** | 用哪个 `name`、凭证类型字符串、参数字段名、表达式写法、输出 JSON 路径、Success / Failure 何时走、和相近节点怎么选 |

脚手架已按下面的顺序生成，补 TODO 时不要打乱标题（Agent 靠标题定位）。

| 章节 | 写什么 |
|---|---|
| **标题 + 第一段** | 标题 = 软件名称；第一段与 `--summary` 逐字相同 |
| **适用** | 两条：「用这个包」典型场景；「不要用这个包」做不到的事，并写请用「另一软件名称」 |
| **凭证** | 类型标识与 `@CredentialsDescription(type)` / 表单 `credentialsType` 逐字一致；字段表；不需要凭证就写明 |
| **节点一览** | 全部节点：`name`（编排写入 `data.name`）、类型、**何时使用**。校验脚本对照 `bundle.json` 检查 `name` |
| **每个节点一节** | 标题是 `` `Name` ``；何时使用、参数表、输出 JSON、出口、编排要点。通用调用节点写在「通用调用」一节 |
| **通用调用** | 有 `*ApiCall` 时保留：按厂商文档填 `method` / `path` / `query` / `headers` / `body` |
| **错误码** | 代码里每个 `FlowNodeException` 码：含义 + 排查建议 |

每次改了节点、参数、输出或错误码，都要在同一次改动里更新 README，不要留到发布时补。

### 每个节点一节（给 Agent 能直接抄）

标题用 bundle.json 的 `name`，不要只写中文 label。按这个顺序写：

1. **何时使用**：一句话。有更合适的专用节点就写「不要用本节点凑」。
2. **参数表**：`name`（与表单字段逐字一致）、必填、默认、是否支持表达式、说明。只在 `initialize()` 读取的字段标明「否（修改会重启）」或「否（只在启动时读取）」。
3. **输出**：JSON 代码块 + 下游引用路径。普通节点成功数据在 `output`；触发器 / Webhook 的 payload 在**根级**，并带 `triggerNodeId`、`eventId`、`workerId`。
4. **出口**：何时 **Success**、何时 **Failure**。调用三方接口的节点还要给出 `msg.error` 示例，说明 `metadata.statusCode` 与 `metadata.body`。
5. **编排**（可选）：绑定哪种凭证、典型上游、一条真实参数示例。

````markdown
## `SendText`

**何时使用**：往钉钉群发一条文本。发 Markdown / 卡片请用 `SendMarkdown` / `SendActionCard`。

### 参数

| 参数 | 必填 | 默认 | 表达式 | 说明 |
|------|------|------|--------|------|
| `content` | 是 | — | 是 `={{ msg.xxx }}` | 文本正文 |

### 输出

成功走 **Success**：

```json
{ "output": { "errcode": 0, "errmsg": "ok" } }
```

下游：`={{ msg.output.errcode }}`。失败走 **Failure**，见「错误码」。
````

调用三方接口失败时的 `msg.error` 示例：

```json
{
  "error": {
    "code": "DINGTALK_HTTP_ERROR",
    "message": "请求无效（HTTP 400），请检查请求参数。响应：{\"errcode\":40035,\"errmsg\":\"...\"}",
    "metadata": { "statusCode": 400, "body": { "errcode": 40035, "errmsg": "..." } }
  }
}
```

错误码表示例（`Validator` 失败统一是 `VALIDATION_ERROR`；带业务码写成 `<前缀>_API_<业务码>` 一行即可）：

```markdown
| 错误码 | 含义 | 排查建议 |
|--------|------|----------|
| `DINGTALK_HTTP_ERROR` | 接口返回非 2xx | 查看 `metadata.statusCode` 与 `metadata.body` |
| `DINGTALK_API_<业务码>` | HTTP 2xx 但返回业务错误码 | 对照钉钉错误码文档 |
| `HTTP_IO_ERROR` | 连接失败或超时 | 检查网络与超时设置 |
```

### 写法约定

- 节点 `name`、参数 `name`、凭证类型用反引号，必须与 `bundle.json` / 表单 / `@CredentialsDescription(type)` 逐字一致；Agent 会原样写入 `flow.json`
- 表达式按组件：JSON / `JsonExpressionInput` 为 `={{ msg.xxx }}`（`=` 必须是第一个字符）；SQL `#{msg.xxx}` / `${msg.xxx}`；文本 `{{ msg.xxx }}`。占位名一律 `msg`，**不要**用 `$json`
- 只写当前版本已经有的行为，不写计划、不写「见源码」
- 不写营销词，不写 Java / Vert.x / fat JAR / SDK 版本

| 应写 | 不要写 |
|---|---|
| `credentials.type` = `DingTalkRobot` | 「在代码里配置一下凭证」 |
| 下游 `={{ msg.output.body.msgid }}` | 「返回钉钉的响应」 |
| 发卡片请用 `SendActionCard` | 把所有能力堆在一个节点说明里 |
| 失败走 Failure，码是 `DINGTALK_HTTP_ERROR` | 项目结构、`mvn package`、ClassLoader |

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
| `bundle create --namespace <slug> --name <short> --display-name <软件名称> [--summary] [--visibility] [--icon]` | `POST /v1/bundles` | 创建软件包，完整名为 `slug/short`；`--summary` 为软件描述 |
| `bundle update --name <ns/name> [--display-name] [--summary] [--visibility] [--icon]` | `POST /v1/bundles/metadata` | 只改传入的字段；`--summary ''` 清空软件描述 |
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

### 图标目录 `icons/`

所有图片放在 Bundle 根目录的 `icons/`（不放 `src/main/resources`，不打进 JAR），
支持 png/jpg/jpeg/gif/webp/svg，≤ 1MB。**文件名就是名字**，用户打开目录就能对上：

| 文件 | 用途 | 对应关系 |
|---|---|---|
| `icons/cover.svg`（或 `cover.png` 等） | 软件包封面 | `bundle create` / `bundle update` 的 `--icon` |
| `icons/<图标名>.<扩展名>` | 节点图标 | 文件名 = 节点 `icon` 值 = 平台存储名，如 `icons/DingTalk.svg` ↔ `"icon": "DingTalk.svg"` |

图标名只能用字母、数字、`_`、`-`，`cover` 留给封面。`bundle.json` 里引用的每个非
`default.svg` 图标都必须在 `icons/` 下有同名文件，`icons/` 下也不要放没人引用的图片，
校验脚本会两头检查。几个节点用同一个图标时共用一个文件。

### 找图

软件包封面和节点图标都按下面的顺序找，**不要自己画 SVG**：

1. 用户给了图片就用用户的。
2. 对接的厂商 / 产品的官网：品牌资源页（brand、press、media kit、logo 下载）提供的官方 SVG Logo。
3. 图标站，优先 SVG：
   - [Simple Icons](https://simpleicons.org)：品牌 Logo，`https://cdn.simpleicons.org/<slug>` 直接返回带品牌色的 SVG
   - [Iconify](https://icon-sets.iconify.design)：`logos` 集收彩色品牌 Logo，`https://api.iconify.design/logos/<name>.svg`；
     没有品牌的功能型 Bundle（HTTP、定时、文件等）用 `tabler`、`lucide`、`mdi` 等集里语义贴切的图标，
     加 `?color=%23<十六进制色>` 指定颜色
   - [svgl](https://svgl.app)：常见 SaaS / 开发工具的彩色 Logo

   图标站对不少国内厂商没有收录（例如 Simple Icons 没有钉钉、飞书，返回 404），返回 404 就换下一个来源，
   不要拿名字相近的别家图标凑数。
4. 都没有合适的，用默认图标 `https://bundles.buildify.cn/icons/default.svg`，并告诉用户可以之后补图：
   - 封面：`curl -fsSL https://bundles.buildify.cn/icons/default.svg -o icons/cover.svg`，照常用 `--icon` 上传
   - 节点：保持 `"icon": "default.svg"`（平台自带的就是这张图），不用在 `icons/` 下放文件

下载后检查：文件确实是图片（SVG 以 `<svg` 或 `<?xml` 开头，不是 HTML 错误页），不含 `<script>`、
外链资源，≤ 1MB，画的是对应厂商的标识。找到的图标放进 `icons/` 后，向用户列出每个文件的
用途和来源地址，例如：

| 文件 | 用途 | 来源 |
|---|---|---|
| `icons/cover.svg` | 软件包封面 | `https://cdn.simpleicons.org/wechat` |
| `icons/WeChat.svg` | `SendMessage`、`ApiCall` 节点 | 同上 |

厂商 Bundle 的节点通常共用品牌图标；只有用户要求或节点差异明显时才为单个节点另找图标。

### 上传图标

```bash
# 节点图标：--icon-name 取文件名去掉扩展名，平台存储名 = 图标名 + 原扩展名，同名覆盖
for f in icons/*; do
  n=$(basename "$f"); [ "${n%.*}" = cover ] && continue
  buildify-publish bundle icon upload --name acme/dingtalk --icon-name "${n%.*}" --file "$f"
done
buildify-publish --json bundle icons --name acme/dingtalk     # 核对 bundle.json 里每个非 default.svg 的 icon 都在列表里

# 封面：新包在 bundle create 时带 --icon，已有的包用 bundle update
buildify-publish bundle update --name acme/dingtalk --icon icons/cover.svg

buildify-publish bundle icon delete --name acme/dingtalk --icon-name DingTalk.svg   # 删除要带扩展名
```

图标上传依赖软件包已存在；新包先 `bundle create` 再传节点图标。

## 发布流程

版本的单一事实来源是该模块 `pom.xml` 的 `<version>`，须与 `-v/--version` 和 JAR 文件名一致。

| 步骤 | 动作 |
|---|---|
| 1 | `buildify-publish --json key test`，向用户确认 `tenantName` 就是目标工作空间 |
| 2 | `bundle info --name <bundleName>`。存在就跳到第 4 步 |
| 3 | 不存在时建包：先按[找图](#找图)准备 `icons/cover.*`，再按下文「新建软件包」创建 |
| 4 | 图标：`icons/` 与 `bundle.json` 的 `icon` 一一对应（缺图按[找图](#找图)补，找不到改回 `default.svg`）；上传节点图标，封面缺失或有变化时 `bundle update --icon`，见[上传图标](#上传图标) |
| 5 | 读当前版本：`mvn -q -Dexpression=project.version -DforceStdout help:evaluate`，按 SemVer 修改 `pom.xml` 的 `<version>` |
| 6 | 重写 `CHANGELOG.md`，仅本 bundle、本版本一节 |
| 7 | 更新 README（平台使用文档，给用户和编排 Agent）：对照本版本逐项改适用、凭证类型、每个节点的何时使用 / 参数 / 输出路径 / 出口、错误码。CHANGELOG 里提到的变化都要体现。节点增删或对接范围变了时，按[软件名称与软件描述](#软件名称与软件描述)重写，经用户确认后 `bundle update --display-name / --summary`，并同步 README 标题和第一段 |
| 8 | `validate_bundle.py --strict` 0 ERROR / 0 WARNING（含 README 节点与错误码、图标文件检查），再构建：`mvn -q clean package`（monorepo 用 `mvn -pl <artifact> -am clean package -DskipTests`，**必须含 `clean`**） |
| 9 | **先同步文档**：`bundle doc set --file README.md`，再用 `bundle doc get` 确认平台上是本次内容 |
| 10 | `bundle upload`，必须带 `--release-notes-file` |
| 11 | `bundle info` 核对版本、releaseNote 与 latest 标记 |

必须先 `clean` 再 `package`，避免旧 JAR / 过时 class 混入发布产物。

文档在上传 JAR 之前同步，用户和编排 Agent 拿到新版本时看到的已经是对应内容。第 10 步失败时修复后重传即可；
决定放弃这次发布时，用上一版 README（`git show <上次发布的提交>:README.md > /tmp/README.prev.md`）
再执行一次 `doc set` 回退，不要让平台文档描述一个不存在的版本。

### 新建软件包

`bundle info` 返回 404 时说明平台上还没有这个包。按下文[软件名称与软件描述](#软件名称与软件描述)
根据**已经实现或即将实现的节点**起草，用确认表给用户看**一次**，等确认再执行命令。
不要自己编名字，也不要照抄 README 标题或「xxx 工具」。

```markdown
将创建软件包：

| 字段 | 内容 |
|------|------|
| 完整名 | acme/dingtalk-robot |
| 软件名称 | 钉钉群机器人 |
| 软件描述 | 对接钉钉（DingTalk）自定义群机器人 Webhook：向群聊发送文本、Markdown、链接和 ActionCard 卡片消息，支持 @ 指定成员或所有人，加签校验。用于告警通知、审批结果、日报推送。不含企业内部应用的通讯录、审批（请用「钉钉应用」）。 |
| 搜包关键词 | 钉钉、DingTalk、群机器人、Webhook、告警、Markdown、ActionCard |
| 能覆盖 | 向钉钉群发文本 / Markdown / 链接 / ActionCard，@ 成员或所有人 |
| 不覆盖 | 通讯录、审批、钉钉企业内部应用 OpenAPI |
| 可见性 | internal |
| 封面 | icons/cover.svg（来源：…） |
```

确认后：

```bash
buildify-publish --json bundle namespaces                       # 命名空间已存在就跳过下一行
buildify-publish --json bundle namespace create --name acme
buildify-publish --json bundle create --namespace acme --name dingtalk-robot \
  --display-name '钉钉群机器人' \
  --summary '对接钉钉（DingTalk）自定义群机器人 Webhook：向群聊发送文本、Markdown、链接和 ActionCard 卡片消息，支持 @ 指定成员或所有人，加签校验。用于告警通知、审批结果、日报推送。不含企业内部应用的通讯录、审批（请用「钉钉应用」）。' \
  --icon icons/cover.svg                                        # 找不到图时 cover.svg 为下载的默认图标
```

`namespace create` 返回 409 表示该命名空间已被其他工作空间占用，请用户换一个，并同步修改
`bundle.json` 的 `bundleName`；每个工作空间最多 5 个命名空间。`bundle create` 返回 409 表示同名包已存在。

### 软件名称与软件描述

控制台「开发中心 → 软件包」里的**软件名称**是 `--display-name`，**软件描述**是 `--summary`。
这两项会出现在 `buildify bundle list` 的结果里，是编排 Agent 判断「用哪个包实现需求」的主要依据；
选中之后才去看 `bundle nodes` 和 README。写不清楚，后续编排就会选错包、漏包，或者误判环境里没有对应能力。

#### 编排 Agent 怎么用这两项

1. 从用户需求里抽出厂商名、产品名、动作词，调 `bundle list -k <词>`，再换两三个同义词查。
2. 在命中的包里读软件名称和软件描述，判断能不能覆盖需求、和旁边那个相近包有何不同。
3. 选定后再 `bundle nodes`，用节点 `label` / `summary` 挑具体节点。

所以：名称要短、能被关键词命中；描述要写清对接谁、已经能做什么、明确不能做什么；同一厂商多个包时，
名称靠能力区分，描述用「不含 …（请用「另一个软件名称」）」互指。

#### 起草（对着节点写，不要先起名再开发）

1. 列出 `bundle.json` 里的全部节点：`name`、拟用中文 `label`、类型（普通 / 触发器 / Webhook / 通用调用）。
2. 判定对接对象和接入方式（群机器人 Webhook、企业内部应用 OpenAPI、数据库直连、通用 HTTP …）。
3. 按下面的格式写出软件名称、软件描述，并列出搜包关键词（中文名、英文名、别名、动作、场景都要能在名称或描述里搜到）。
4. 用上一节的确认表给用户看，等确认再 `bundle create`；以后改范围则 `bundle update`。

**包名（`bundleName` 第二段）**：`<厂商或产品>-<能力>`，小写英文，如 `dingtalk-robot`、`dingtalk-app`、
`mysql`、`http`。不要用 `utils`、`tools`、`demo`、`test`、`v2`、`new` 这类看不出用途的词。

**软件名称（`--display-name`）**：`<官方中文名><能力>`，2–16 个字。

| ✅ | ❌ |
|---|---|
| 钉钉群机器人 | 钉钉工具、钉钉插件、DingTalk Bundle |
| 钉钉应用 | 钉钉（看不出是机器人还是 OpenAPI） |
| 企业微信应用消息 | 企微、企业微信软件包 |
| MySQL 数据库 | 数据库工具集 |
| HTTP 请求 | HTTP 连接器、官方 HTTP |

- 用官方叫法：「企业微信」不写「企微」，「飞书」不写「Lark 机器人工具」
- 同一厂商有多个包时，名称里必须带上能力差异（群机器人 / 应用 / 审批）
- 不加「插件」「软件包」「工具集」「Bundle」「连接器」等后缀，不加版本号、公司名、「官方」「专业版」

**软件描述（`--summary`）**：一段话，40–150 字，固定句式，不要换顺序、不要拆成列表
（`bundle list` 里按一行展示）：

```
对接{中文名}（{英文名或别名}）{接入方式}：{按节点列出的动词+对象}。用于{场景1}、{场景2}。不含{边界}（请用「{另一个软件名称}」）。
```

| 部分 | 怎么写 |
|---|---|
| 对接对象 | 中文名 + 括号里的英文名或常用别名，如「钉钉（DingTalk）」「企业微信（WeCom）」；有多种接入方式时写明是哪一种 |
| 能做什么 | 每个节点至少对应一个「动词 + 对象」，如「发送文本 / Markdown 消息、查询部门成员、创建审批实例」。触发器写「监听 / 接收 xxx 事件」。有通用调用节点时加「其余接口可按官方文档通用调用」 |
| 典型场景 | 一句「用于 xxx、xxx」，用用户会说的话（告警通知、订单同步、日报推送），不要写实现细节 |
| 边界 | 有容易混淆的相近包时必写「不含 xxx（请用「yyy」）」；没有相近包可省略最后一句 |

约束：

- 只写当前版本**已经有**的节点能力，不写计划中的功能
- 中文名、英文名、别名、动作、场景这些搜包关键词，必须出现在名称或描述里，否则 `-k` 搜不到
- 不写营销词（强大、便捷、一站式、高效），不写实现细节（Java、Vert.x、fat JAR、SDK 版本）
- 不写用法、参数、错误码，这些在 README 里

| | 软件名称 | 软件描述 |
|---|---|---|
| ✅ | 钉钉群机器人 | 对接钉钉（DingTalk）自定义群机器人 Webhook：向群聊发送文本、Markdown、链接和 ActionCard 卡片消息，支持 @ 指定成员或所有人，加签校验。用于告警通知、审批结果、日报推送。不含企业内部应用的通讯录、审批（请用「钉钉应用」）。 |
| ✅ | 钉钉应用 | 对接钉钉（DingTalk）企业内部应用 OpenAPI：查询通讯录与部门成员、发送工作通知、创建审批实例；其余接口可按官方文档通用调用。用于人事同步、审批、工作通知。不含群机器人 Webhook（请用「钉钉群机器人」）。 |
| ✅ | MySQL 数据库 | 连接 MySQL（兼容 MariaDB、TiDB）：执行查询、插入、更新、删除和批量写入，支持参数化 SQL 与事务；可按定时轮询监听新增行。用于数据同步、报表查询、业务数据落库。 |
| ✅ | HTTP 请求 | 发送 HTTP（REST）请求：自定义方法、URL、Header、Query 和 JSON 正文，接收状态码与响应体。用于调用没有专用软件包的 HTTP 接口。 |
| ❌ | 钉钉工具 | 钉钉相关功能 |
| ❌ | DingTalk Bundle | 基于 Java 的高效钉钉插件，一站式解决消息问题 |

README 标题用软件名称，第一段（标题下面那句）与软件描述逐字相同，这样 `bundle list` 和 `bundle doc` 看到的是同一段话。

**节点 `label` / `summary`（选节点用）**：软件描述负责选包；目录里的节点文案负责选节点。
`label` 写中文短名（「发送文本」「通用调用」「接收 Webhook」），不要用类名 `SendTextMessage`。
`summary` ≤ 10 字，写这颗节点做什么（「发群消息」「按文档调接口」），不要留「待补充」。

**什么时候更新**：节点增删、对接范围变化（新增触发器、通用调用、新的接入方式）时，同一次发布里用
`bundle update --display-name / --summary` 改平台信息，并同步 README 标题和第一段；先把新旧内容列给用户确认。

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
buildify-publish bundle update --name official/wecom-bot --display-name '企业微信群机器人' \
  --summary '对接企业微信（WeCom）群机器人 Webhook：向群聊发送文本、Markdown、图片、图文和模板卡片消息，支持 @ 成员。用于告警通知、日报推送。不含应用消息与通讯录（请用「企业微信应用消息」）。'
buildify-publish bundle update --name official/wecom-bot --icon ./bundle-wecom-bot/icons/cover.svg   # 换封面图标
buildify-publish bundle doc set --name official/wecom-bot --file ./bundle-wecom-bot/README.md
buildify-publish --json bundle doc get --name official/wecom-bot   # 确认已同步
```

`bundle update` 只改传入的字段。`bundle doc set` 整份覆盖，内容上限约 4Mi 字符。
只改了 README、没有代码变化时，单独 `doc set` 即可，不必发新版本。

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
