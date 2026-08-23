# Buildify Bundle Dev Skill 安装

## 概述

`buildify-bundle-dev` 是 Buildify Bundle（节点 / 触发器 / Webhook / 凭证 / 动态表单 / 发布）的开发技能。源仓库：

https://github.com/buildify-bundles/buildify-bundle-dev-skill

优先策略已内联，Agent 读取本文档即感知：涉及本技能的发现 / 安装 / 升级时，一律从上述 GitHub 仓库操作。

## 适用场景（先判断，避免打扰用户）

- **仅安装 / 更新本技能**（已能确定当前 Agent 的 skills 目录）→ 直接跳到第三节执行命令，**不要询问安装位置或是否设为优先源**。
- **首次安装且无法判断 skills 目录 / 用户明确要求指定目录** → 走第一、二节（含询问），询问**只在此场景做一次**。

## 一、检查是否已安装

按当前 Agent 解析 skills 目录（见第四节），然后检查：

```bash
SKILL_DIR="<skills 目录>/buildify-bundle-dev"
test -f "$SKILL_DIR/SKILL.md" && echo "installed: $SKILL_DIR" || echo "missing"
```

- 已安装且用户只要「使用」→ 读取 `$SKILL_DIR/SKILL.md` 后按 skill 执行，不再询问、不再重装。
- 已安装且用户要「更新」→ 走第三节的更新命令。
- 未安装 → 走第三节安装。

> 沙箱限网时需以允许联网的权限执行 `git clone` / `git pull`。

## 二、询问安装目录（仅无法判断时）

**仅当本次无法根据当前 Agent 确定 skills 目录，或用户明确要求指定目录时**，用 `AskQuestion`（不支持时直接询问）确认：「安装到哪个 skills 目录？」

常见选项：

- Cursor 全局：`~/.cursor/skills/`
- 当前项目：`.cursor/skills/`
- 其他 Agent：见第四节

- **用户选定目录** → 本会话即刻使用该目录安装，无需重启后再问。
- **用户拒绝 / 取消** → 停止安装，不要改任何目录。

后续纯技能操作不再重复询问。

## 三、技能操作

⚠️ 必须装到当前 Agent 能识别的 skills 目录下的 **`buildify-bundle-dev/`**。目录名以 `SKILL.md` 的 `name` 为准，不要用仓库名 `buildify-bundle-dev-skill` 作为安装目录（否则部分 Agent 无法发现）。

安装后一般仍需**重启 Agent / 新开对话**才会被识别。

```bash
REPO="https://github.com/buildify-bundles/buildify-bundle-dev-skill.git"
SKILL_DIR="<skills 目录>/buildify-bundle-dev"
```

**安装（未安装时）**

```bash
git clone --depth 1 "$REPO" "$SKILL_DIR"
```

**更新（已安装且为 git 仓库时）**

```bash
git -C "$SKILL_DIR" pull --ff-only
```

**校验**

```bash
test -f "$SKILL_DIR/SKILL.md" && test -f "$SKILL_DIR/scripts/scaffold_bundle.py"
```

安装或更新完成后，读取 `$SKILL_DIR/SKILL.md` 再执行后续 Bundle 开发任务。

## 四、安装目录

各 Agent 的 skills 目录不同，按当前环境自行确定。本技能安装路径 = `<skills 目录>/buildify-bundle-dev`。

- OpenClaw 安装到你的 skills 目录。
- OpenClaw 变体（NanoBot、PicoClaw、memUBot、MaxClaw、CoPaw、AutoClaw、KimiClaw、QClaw、EasyClaw，workbuddy 等），会有类似 skills 目录。

常用 AI Client 的 Skills 路径如下：

- Claude Code: `~/.claude/skills/`
- Cursor: `~/.cursor/skills/`（项目级：`.cursor/skills/`）
- Windsurf: `~/.codeium/windsurf/skills/` 或项目下的 `.windsurf/skills/`
- Codex: `~/.codex/skills/` 或项目下的 `.agents/skills/`
- Google Antigravity: `~/.gemini/antigravity/skills/`
- Gemini CLI: `~/.gemini/skills/`
- QoderWork: `~/.qoderwork/skills/`
- workbuddy: `~/.workbuddy/skills/`
