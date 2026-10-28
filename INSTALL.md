# Buildify Bundle Dev Skill 安装

用户把本文交给你，即表示：**立刻安装或更新 `buildify-bundle-dev`，然后简短回报结果。**

不要解释背景，不要询问选源，不要询问是否安装。只装到**这次会话会加载技能的那个目录**；磁盘上存在别的 Agent 目录不是理由。对不上就停，只问一次路径。

## 源

公开仓库，无需登录。主源失败再用备用源，不改 `origin`：

```bash
PRIMARY="https://github.com/buildify-bundles/buildify-bundle-dev-skill.git"
FALLBACK="https://gitee.com/buildify/buildify-bundle-dev-skill.git"
export GIT_TERMINAL_PROMPT=0   # 不弹用户名/密码提示，失败就直接换源
```

目录名必须是 **`buildify-bundle-dev/`**（以 `SKILL.md` 的 `name` 为准），不是仓库名 `buildify-bundle-dev-skill`。沙箱限网时用允许联网的权限执行 `git`。

## 1. 确定 skills 根目录

用户指定了目录就用它；用户拒绝安装就停止，不改任何目录。否则只认下面两种证据。两种都有时必须指向**同一个**目录，不同就停止并问一次。

**证据 A：本会话已加载的技能路径。** 从系统提示、技能列表、工具说明里找 `.../skills/<名字>/SKILL.md`，去掉技能名得到根目录。忽略 `skills-cursor` 等内置目录。

- 只有一个根目录：用它。
- 多个根目录、产品相同（都是 `.cursor/skills` 或都是 `.claude/skills`）：用家目录下的个人目录；用户明确说「项目级」时才用仓库里的。
- 多个根目录、产品不同：停止并问一次，不要自己选。

**证据 B：产品名与最近的父进程一致。** 系统提示写明你是哪个产品，且下面的探测打印出同一目录。只看最近的父进程，不看外层 IDE 和环境变量（在 Cursor 终端里跑 Claude Code 时环境里常有 `CURSOR_*`，但技能属于 Claude Code）。

| 你是 | 个人 skills 目录 | 用户要求项目级时 |
|---|---|---|
| Cursor | `~/.cursor/skills/` | `<仓库>/.cursor/skills/` |
| Claude Code | `~/.claude/skills/` | `<仓库>/.claude/skills/` |
| Windsurf | `~/.codeium/windsurf/skills/` | `<仓库>/.windsurf/skills/` |
| Codex | `~/.codex/skills/` | `<仓库>/.agents/skills/` |
| Google Antigravity | `~/.gemini/antigravity/skills/` | 同个人目录 |
| Gemini CLI | `~/.gemini/skills/` | 同个人目录 |
| QoderWork | `~/.qoderwork/skills/` | 同个人目录 |
| workbuddy | `~/.workbuddy/skills/` | 同个人目录 |

OpenClaw 及变体（NanoBot、PicoClaw、memUBot、MaxClaw、CoPaw、AutoClaw、KimiClaw、QClaw、EasyClaw 等）没有统一目录：只有证据 A 给出路径才安装，否则问一次，不要猜。

在当前机器、当前用户下探测（`ps` 被拒绝视为没有进程证据）：

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

输出 `unknown`、没有任何证据、或 A 与 B 不一致：只问一次 skills 根目录，不要列 Agent 菜单。

## 2. 动手前检查

`SKILL_DIR="<skills 根目录>/buildify-bundle-dev"`。下面任一条不成立就停止，不要 `mkdir` 或 `clone`：

- 根目录来自证据 A，或来自「提示中的产品名 = 探测结果」
- `SKILL_DIR` 以 `/buildify-bundle-dev` 结尾
- 路径里没有 `skills-cursor`
- `SKILL_DIR` 不是你正在读的这份源码仓库
- 没有第二个不同的候选目录

## 3. 安装或更新

一次执行，脚本会自己判断是新装还是更新（在子 shell 里跑，出错不会退出当前会话）：

```bash
(
set -e
SKILL_DIR="<skills 根目录>/buildify-bundle-dev"
PRIMARY="https://github.com/buildify-bundles/buildify-bundle-dev-skill.git"
FALLBACK="https://gitee.com/buildify/buildify-bundle-dev-skill.git"
export GIT_TERMINAL_PROMPT=0

if [ ! -e "$SKILL_DIR" ]; then
  mkdir -p "$(dirname "$SKILL_DIR")"
  git clone --depth 1 "$PRIMARY" "$SKILL_DIR" || git clone --depth 1 "$FALLBACK" "$SKILL_DIR"
  echo "ACTION=installed"
elif ! git -C "$SKILL_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: $SKILL_DIR 已存在但不是 git 仓库，未做任何修改"; exit 1
else
  OLD=$(git -C "$SKILL_DIR" rev-parse --short HEAD)
  if [ -n "$(git -C "$SKILL_DIR" status --porcelain)" ]; then
    STASH_MSG="buildify-bundle-dev 更新前备份 $(date +%Y%m%d-%H%M%S)"
    git -C "$SKILL_DIR" stash push -u -m "$STASH_MSG"
    echo "STASHED=$STASH_MSG"
  fi
  git -C "$SKILL_DIR" pull --ff-only \
    || git -C "$SKILL_DIR" pull --ff-only "$FALLBACK" main
  echo "ACTION=updated $OLD -> $(git -C "$SKILL_DIR" rev-parse --short HEAD)"
fi

test -f "$SKILL_DIR/SKILL.md" && test -f "$SKILL_DIR/scripts/scaffold_bundle.py" \
  && grep -q '^name: buildify-bundle-dev$' "$SKILL_DIR/SKILL.md" && echo "VERIFY=ok"
)
```

- **本地有改动**：脚本先 `git stash` 备份再更新，不会丢。回报时写出 `STASHED=` 那一行，并告诉用户恢复命令 `git -C "$SKILL_DIR" stash pop`。
- **`pull --ff-only` 失败**（本地有自己的提交、两个源都连不上）：停止并贴输出，不要 `reset`、不要删目录重装。
- 没有打印 `VERIFY=ok` 就算失败。

## 4. 回报

成功时用三四句话说清：

1. 结果：新装还是更新（带上 `旧版本 -> 新版本`）、`$SKILL_DIR`、依据的证据（本会话技能路径，或产品名与父进程一致）。
2. 有备份时：备份名和 `stash pop` 恢复命令。
3. **重启 Agent 或新开对话**后技能才会生效。
4. 发布 Bundle 要用发布密钥。提前告诉用户在控制台 **系统设置 → API Keys → buildify-publish-cli 密钥** 里创建；第一次发布时把密钥（`keyId.secret`）发给你就行。

失败时：贴命令输出，说明卡在哪一步，不要改其他目录。

用户同时提了 Bundle 开发任务：读 `$SKILL_DIR/SKILL.md` 后继续；只要求安装时到此结束。
