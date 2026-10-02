# Buildify Bundle Dev Skill 安装

用户把本文交给你，即表示：**立刻安装或更新 `buildify-bundle-dev`，然后用一句话回报结果。**

不要解释背景，不要询问选源，不要询问是否安装。只有「无法判断当前 Agent 的 skills 目录」时才问一次安装位置。

## 源（主源失败再用备用，不改 origin）

```bash
PRIMARY="https://github.com/buildify-bundles/buildify-bundle-dev-skill.git"
FALLBACK="https://gitee.com/buildify/buildify-bundle-dev-skill.git"
```

目录名必须是 **`buildify-bundle-dev/`**（以 `SKILL.md` 的 `name` 为准）。不要用仓库名 `buildify-bundle-dev-skill`。

`SKILL_DIR="<当前 Agent 的 skills 目录>/buildify-bundle-dev"`。常见路径见文末；Cursor 默认 `~/.cursor/skills/`。沙箱限网时用允许联网的权限执行 `git clone` / `git pull`。

## 执行

**1. 检查**

```bash
test -f "$SKILL_DIR/SKILL.md" && echo "installed: $SKILL_DIR" || echo "missing"
```

**2. 未安装则 clone，已安装则更新**

```bash
git clone --depth 1 "$PRIMARY" "$SKILL_DIR" || git clone --depth 1 "$FALLBACK" "$SKILL_DIR"
```

```bash
git -C "$SKILL_DIR" pull --ff-only || git -C "$SKILL_DIR" pull --ff-only "$FALLBACK"
```

**3. 校验（必须同时成立）**

```bash
test -f "$SKILL_DIR/SKILL.md" && test -f "$SKILL_DIR/scripts/scaffold_bundle.py"
```

**4. 回报**

成功：写出 `$SKILL_DIR`，并提示用户**重启 Agent / 新开对话**后技能才会被识别。  
失败：贴命令输出，停止，不要改其他目录。

用户若同时提出 Bundle 开发任务：读 `$SKILL_DIR/SKILL.md` 再继续。仅安装时到此结束。

## 安装目录（仅无法判断时才问）

本技能路径 = `<skills 目录>/buildify-bundle-dev`。

- Cursor: `~/.cursor/skills/`（项目级：`.cursor/skills/`）
- Claude Code: `~/.claude/skills/`
- Windsurf: `~/.codeium/windsurf/skills/` 或项目下 `.windsurf/skills/`
- Codex: `~/.codex/skills/` 或项目下 `.agents/skills/`
- Google Antigravity: `~/.gemini/antigravity/skills/`
- Gemini CLI: `~/.gemini/skills/`
- QoderWork: `~/.qoderwork/skills/`
- workbuddy: `~/.workbuddy/skills/`
- OpenClaw 及变体（NanoBot、PicoClaw、memUBot、MaxClaw、CoPaw、AutoClaw、KimiClaw、QClaw、EasyClaw 等）：用该 Agent 自己的 skills 目录

用户指定了目录 → 用该目录立即执行，不要再问。用户拒绝 → 停止，不要改任何目录。
