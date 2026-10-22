# Buildify Bundle Dev Skill 安装

用户把本文交给你，即表示：**立刻安装或更新 `buildify-bundle-dev`，然后用一句话回报结果。**

不要解释背景，不要询问选源，不要询问是否安装。装到**这次会话会加载技能的那个目录**。磁盘上有很多 Agent 目录时，存在不能当理由。对不上就停，只问一次路径。

## 源（主源失败再用备用，不改 origin）

```bash
PRIMARY="https://github.com/buildify-bundles/buildify-bundle-dev-skill.git"
FALLBACK="https://gitee.com/buildify/buildify-bundle-dev-skill.git"
```

目录名必须是 **`buildify-bundle-dev/`**（以 `SKILL.md` 的 `name` 为准）。不要用仓库名 `buildify-bundle-dev-skill`。沙箱限网时用允许联网的权限执行 `git clone` / `git pull`。

## 1. 得到唯一的 skills 根目录

用户指定了目录 → 用该目录。用户拒绝 → 停止，不要改任何目录。

否则只接受下面两种证据。两种都有时必须指向**同一个**目录，不同就停止并问一次。

**证据 A：这次会话已经加载技能的路径。** 从系统提示、技能列表、工具说明里摘出每个 `.../skills/<名字>/SKILL.md`，去掉技能名得到 skills 根目录。忽略 `skills-cursor` 等内置目录。

- 只剩一个根目录 → 用它。
- 多个根目录但产品标记相同（都是 `.cursor/skills`，或都是 `.claude/skills`）→ 用个人目录（家目录下的那个）。用户明确说「只装当前项目 / 项目级」时才用仓库里的那个。
- 多个根目录且产品标记不同（例如既有 `.cursor/skills` 又有 `.claude/skills`）→ 停止并问一次。不要选一个。

**证据 B：产品名与最近的父进程一致。** 系统提示写明了你是哪个产品，并且下面的探测打印出同一个目录。只看最近的父进程，不看更外层的 IDE，也不看环境变量：在 Cursor 终端里跑 Claude Code 时，环境里常有 `CURSOR_*`，但技能属于 Claude Code。

| 你是 | 个人 skills 目录 | 仅当用户要求项目级 |
|---|---|---|
| Cursor | `~/.cursor/skills/` | `<仓库>/.cursor/skills/` |
| Claude Code | `~/.claude/skills/` | `<仓库>/.claude/skills/` |
| Windsurf | `~/.codeium/windsurf/skills/` | `<仓库>/.windsurf/skills/` |
| Codex | `~/.codex/skills/` | `<仓库>/.agents/skills/` |
| Google Antigravity | `~/.gemini/antigravity/skills/` | 同个人目录 |
| Gemini CLI | `~/.gemini/skills/` | 同个人目录 |
| QoderWork | `~/.qoderwork/skills/` | 同个人目录 |
| workbuddy | `~/.workbuddy/skills/` | 同个人目录 |

OpenClaw 及变体（NanoBot、PicoClaw、memUBot、MaxClaw、CoPaw、AutoClaw、KimiClaw、QClaw、EasyClaw 等）没有统一目录。只有证据 A 给出了路径才安装；没有就问一次，不要猜 `~/.openclaw/skills` 这类路径。

探测在你正在运行的这台机器、当前用户下执行。`ps` 被拒绝时视为没有进程证据。

```bash
python3 - <<'PY'
import subprocess, os
from pathlib import Path

home = Path.home()
# 更具体的名字放前面，避免被更短的名字截走。
agents = [
    ("antigravity", home / ".gemini/antigravity/skills", ("antigravity",)),
    ("windsurf", home / ".codeium/windsurf/skills", ("windsurf",)),
    ("qoder", home / ".qoderwork/skills", ("qoderwork", "qoder")),
    ("workbuddy", home / ".workbuddy/skills", ("workbuddy",)),
    ("cursor", home / ".cursor/skills", ("cursor",)),
    ("claude", home / ".claude/skills", ("claude",)),
    ("codex", home / ".codex/skills", ("codex",)),
    ("gemini", home / ".gemini/skills", ("gemini",)),
]

pid = os.getpid()
for _ in range(8):
    try:
        parent = subprocess.check_output(
            ["ps", "-o", "ppid=", "-p", str(pid)], text=True, stderr=subprocess.DEVNULL)
        pid = int(parent.strip() or "0")
        if pid <= 1:
            break
        command = subprocess.check_output(
            ["ps", "-o", "comm=", "-p", str(pid)], text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        break
    comm = command.strip().lower()
    hits = [item for item in agents if any(needle in comm for needle in item[2])]
    if len(hits) == 1:
        print(hits[0][1])
        raise SystemExit
    if len(hits) > 1:
        break
raise SystemExit("unknown")
PY
```

`unknown`、没有证据、或 A 与 B 不一致：只问一次 skills 根目录。不要列出 Agent 菜单。

## 2. 安装前必须全部成立

`SKILL_DIR="<skills 根目录>/buildify-bundle-dev"`。下面有一条不成立就停止，不要 `mkdir` 或 `clone`：

- skills 根目录来自证据 A，或来自「提示中的产品名 = 探测结果」
- `SKILL_DIR` 以 `/buildify-bundle-dev` 结尾，而不是 `buildify-bundle-dev-skill`
- 路径里没有 `skills-cursor`
- `SKILL_DIR` 不是你正在读的这份源码仓库
- 没有第二个不同的候选目录

## 3. 安装或更新

**检查**

```bash
test -f "$SKILL_DIR/SKILL.md" && echo "installed: $SKILL_DIR" || echo "missing"
```

**未安装则 clone，已安装则更新**

```bash
mkdir -p "$(dirname "$SKILL_DIR")"
git clone --depth 1 "$PRIMARY" "$SKILL_DIR" || git clone --depth 1 "$FALLBACK" "$SKILL_DIR"
```

```bash
git -C "$SKILL_DIR" pull --ff-only || git -C "$SKILL_DIR" pull --ff-only "$FALLBACK"
```

目录已存在但不是 git 仓库：停止并报告，不要覆盖。

**校验（必须同时成立）**

```bash
test -f "$SKILL_DIR/SKILL.md" && test -f "$SKILL_DIR/scripts/scaffold_bundle.py" \
  && grep -q '^name: buildify-bundle-dev$' "$SKILL_DIR/SKILL.md"
```

## 4. 回报

成功：写明证据（本会话技能路径，或产品名与父进程一致）和 `$SKILL_DIR`，并提示用户**重启 Agent / 新开对话**后技能才会被识别。  
失败：贴命令输出，停止，不要改其他目录。

用户若同时提出 Bundle 开发任务：读 `$SKILL_DIR/SKILL.md` 再继续。仅安装时到此结束。
