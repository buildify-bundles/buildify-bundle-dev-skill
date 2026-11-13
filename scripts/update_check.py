#!/usr/bin/env python3
"""检查本 skill 有没有新版本：本地 ../version.json 对比仓库 main 分支上的 version.json。

用法：
    python3 update_check.py [--force] [--url URL]

先读 GitHub raw，失败再读 Gitee raw，每个 3 秒超时；结果缓存 24 小时
（~/.cache/buildify/bundle-dev-update.json），--force 跳过缓存。
--url 指定远端（http(s):// 或 file://，离线测试用），此时不读写缓存。
环境变量 BUILDIFY_SKILL_NO_UPDATE_CHECK=1 时不联网，只报本地版本。

输出一行 JSON：current、latest、updateAvailable、required（本地低于 minVersion）、notes、date、
skillDir、checked（cache / github / gitee / url / skipped / failed）。
退出码永远是 0：网络不通不能拖住开发。
仅依赖 Python 3.8+ 标准库。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = Path.home() / ".cache" / "buildify" / "bundle-dev-update.json"
TTL_SECONDS = 24 * 60 * 60
TIMEOUT_SECONDS = 3
SOURCES = [
    ("github", "https://raw.githubusercontent.com/buildify-bundles/buildify-bundle-dev-skill/main/version.json"),
    ("gitee", "https://gitee.com/buildify/buildify-bundle-dev-skill/raw/main/version.json"),
]
VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def parse_version(text):
    match = VERSION.match(str(text if text is not None else "").strip())
    return tuple(int(p) for p in match.groups()) if match else None


def compare(a, b) -> int:
    left = parse_version(a) or (0, 0, 0)
    right = parse_version(b) or (0, 0, 0)
    return (left > right) - (left < right)


def is_manifest(data) -> bool:
    return isinstance(data, dict) and parse_version(data.get("version")) is not None


def fetch_manifest(url: str):
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache",
                                                   "User-Agent": "buildify-bundle-dev-update-check"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def remote_manifest(url, force: bool):
    if url:
        try:
            data = fetch_manifest(url)
        except Exception:
            return None, "failed"
        return (data, "url") if is_manifest(data) else (None, "failed")
    if not force:
        cache = read_json(CACHE_FILE)
        if isinstance(cache, dict) and is_manifest(cache.get("data")):
            try:
                fresh = time.time() - float(cache.get("checkedAt", 0)) < TTL_SECONDS
            except (TypeError, ValueError):
                fresh = False
            if fresh:
                return cache["data"], "cache"
    for name, source in SOURCES:
        try:
            data = fetch_manifest(source)
        except Exception:
            continue
        if not is_manifest(data):
            continue
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text(json.dumps({"checkedAt": time.time(), "source": name, "data": data},
                                             ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError:
            pass
        return data, name
    return None, "failed"


def check(url, force: bool) -> dict:
    local = read_json(SKILL_DIR / "version.json")
    current = local["version"] if is_manifest(local) else None
    result = {"current": current, "latest": None, "updateAvailable": False, "required": False,
              "notes": [], "date": None, "skillDir": str(SKILL_DIR), "checked": "skipped"}
    if os.environ.get("BUILDIFY_SKILL_NO_UPDATE_CHECK") == "1" and not url:
        return result

    data, checked = remote_manifest(url, force)
    result["checked"] = checked
    if not data:
        return result
    result["latest"] = data["version"]
    result["date"] = data.get("date")
    result["updateAvailable"] = current is None or compare(data["version"], current) > 0
    result["required"] = (current is not None and data.get("minVersion") is not None
                          and compare(current, data["minVersion"]) < 0)
    if result["updateAvailable"] and isinstance(data.get("notes"), list):
        result["notes"] = [str(n) for n in data["notes"]]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 buildify-bundle-dev 有没有新版本")
    parser.add_argument("--force", action="store_true", help="跳过 24 小时缓存")
    parser.add_argument("--url", help="指定远端 version.json（http(s):// 或 file://），不读写缓存")
    args, unknown = parser.parse_known_args()
    if unknown:
        print("update_check: 忽略未知参数 " + " ".join(unknown), file=sys.stderr)
    try:
        result = check(args.url, args.force)
    except Exception as exc:
        result = {"current": None, "latest": None, "updateAvailable": False, "required": False,
                  "notes": [], "date": None, "skillDir": str(SKILL_DIR), "checked": "failed",
                  "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
