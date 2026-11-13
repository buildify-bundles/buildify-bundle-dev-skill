# Buildify Bundle Dev Skill

开发 Buildify 工作流 Bundle（fat JAR 节点包）的 Agent 技能：生成骨架、写节点与表单、校验、打包发布。

安装后的目录名是 `buildify-bundle-dev`（以 `SKILL.md` 的 `name` 为准），不要用仓库名 `buildify-bundle-dev-skill`。

## 安装

把 [INSTALL.md](INSTALL.md) 交给 Agent。它只装到这次会话实际加载技能的目录；同时认出多个 Agent 时会停下来问路径，不会猜。Cursor 的个人目录是 `~/.cursor/skills/buildify-bundle-dev`。

安装或更新完成后，重启 Agent 或新开对话，技能才会被识别。本地改过的技能文件会先 `git stash` 备份再更新。

发布 Bundle 需要发布密钥：在控制台 **系统设置 → API Keys → buildify-publish-cli 密钥** 创建，首次发布时交给 Agent 即可。

## 更新

Agent 每次开始 Bundle 任务时跑 `scripts/update_check.py`：先读 GitHub raw 上的 `version.json`，失败再读 Gitee，每个 3 秒超时，结果缓存 24 小时（`~/.cache/buildify/bundle-dev-update.json`）。有新版本时在回复开头提示一句，然后照常工作；本地版本低于 `minVersion` 时先停下请你确认更新。说「更新 skill」，Agent 就按 [INSTALL.md](INSTALL.md) 在原目录 `git pull --ff-only`（本地改动先 stash）。网络不通时不提示，也不影响开发；设置 `BUILDIFY_SKILL_NO_UPDATE_CHECK=1` 可关闭检查。

## 做什么

开发 Bundle 时读 [SKILL.md](SKILL.md)，不要一次读完所有参考文档。

| 场景 | 入口 |
|---|---|
| 新建 Bundle | `scripts/scaffold_bundle.py` |
| 对接三方 HTTP API | `--generic-api ApiCall`，见 [reference/generic-api.md](reference/generic-api.md) |
| 写节点 | [coding-rules.md](coding-rules.md) |
| 写表单 | [reference/forms-schema.md](reference/forms-schema.md) |
| 写触发器 | 限流、有界缓冲、`tryTellSuccess`、Webhook 429，见 [reference/backpressure.md](reference/backpressure.md) |
| 校验 | `scripts/validate_bundle.py --strict`，0 ERROR 后再 `mvn -q clean package` |
| 发布 | `buildify-publish` CLI 建软件包（确认表给出默认可改的命名空间和包名，优先用已有命名空间；软件名称 / 软件描述按规范写）。发布时核对 `bundle.json` 图标：先拿到图，再上传，成功后才设置 `icon`；找不到就保持原值。封面找不到就不传 `--icon`。同时把 `docs.md` 同步到平台，不同步 README，见 [reference/publishing.md](reference/publishing.md) |
| 版本管理 | 开发完成后检查 git 仓库，没有远程地址时请用户提供 |

环境：Python 3.8+、JDK 21+、Maven 3.8+。

```bash
python3 scripts/scaffold_bundle.py \
  --dir ./my-bundle \
  --group-id com.example --artifact-id my-bundle \
  --bundle-name example/my-bundle --package com.example.bundle \
  --node MyNode

python3 scripts/validate_bundle.py ./my-bundle --strict
```

对接三方 HTTP 时加上 `--credential MyApiCredential --generic-api ApiCall`。文档里还没有专用节点的接口，用这个通用节点按文档填写 `method`、`path`、`query`、`headers`、`body`。

## 目录

```
SKILL.md                 # 技能入口
INSTALL.md               # 安装说明
version.json             # 技能版本号、最低版本与更新要点
coding-rules.md          # 节点编码规范
scripts/                 # scaffold_bundle.py、validate_bundle.py、update_check.py
templates/               # 工程、Java、表单模板
reference/               # 表单、API、生命周期、触发器背压、发布
tests/                   # 脚本回归测试
```

## 维护本技能

改了 `scripts/` 或 `templates/` 后跑回归测试：脚手架产物须 0 ERROR / 0 WARNING，故意写错的变体须被校验器拦下。

```bash
python3 -m unittest discover -s tests -v
RUN_MAVEN=1 python3 -m unittest discover -s tests -v   # 额外编译脚手架产物，需 JDK 21 与 Maven
```

新增校验规则时，在 `tests/test_scripts.py` 的 `MUTATIONS` 或 `WARNING_MUTATIONS` 里补一条对应的错误写法。

### 发布新版本

1. 改 `version.json`：`version` 按 semver 递增；`notes` 写 1–3 条用户能看懂的要点（会原样展示给用户）；`date` 写当天。
2. 只有旧版本会把事情做错时（CLI 参数变了、平台规则变了、旧规则会生成错误的 Bundle）才把 `minVersion` 提到新版本，平时不动。
3. 跑回归测试，提交，打 tag：`git tag vX.Y.Z`。
4. 推到 GitHub 和 Gitee：`git push origin main --tags`，Gitee 没有自动同步时再推一次 Gitee 远端。

raw.githubusercontent 有约 5 分钟 CDN 缓存，加上本地 24 小时缓存，用户最晚约一天内看到提示。
