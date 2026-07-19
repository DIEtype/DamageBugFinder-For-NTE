from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import webview


APP_TITLE = "游戏数值验算器"
APP_FOLDER = "GameDamageCalculator"


def bundled_path(filename: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / filename


def app_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_FOLDER
    return Path.home() / "AppData" / "Local" / APP_FOLDER


def install_html() -> Path:
    source = bundled_path("index.html")
    target_dir = app_data_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "index.html"
    shutil.copyfile(source, target)
    return target


def self_test() -> int:
    html = bundled_path("index.html").read_text(encoding="utf-8")
    required = (
        "<title>游戏数值验算器</title>",
        "最符合实测的全局状态",
        "零误差全局状态（最多 3 项）",
        "清空当前",
        "确定并开始验算",
        "狂暴溯源",
        "搜索强度",
        "极限 · 完整 22 / 限宽 50,000",
        "治疗计算",
        "基础治疗加成（%）",
        "启用浸染乘区",
        "特殊独立倍率（倍）",
        "基础环合强度",
    )
    return 0 if all(marker in html for marker in required) else 2


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()

    html_path = install_html()
    storage_path = app_data_dir() / "WebView2"
    storage_path.mkdir(parents=True, exist_ok=True)

    webview.create_window(
        APP_TITLE,
        html_path.as_uri(),
        width=1800,
        height=980,
        min_size=(1180, 700),
        resizable=True,
        confirm_close=False,
    )
    webview.start(
        gui="edgechromium",
        debug=False,
        private_mode=False,
        storage_path=str(storage_path),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
