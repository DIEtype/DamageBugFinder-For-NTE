from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
DESKTOP_DIR = ROOT / "desktop"
OUTPUT_DIR = ROOT / "docs" / "images"

sys.path.insert(0, str(DESKTOP_DIR))
from main import direct_desktop_html  # noqa: E402


def find_edge() -> Path:
    candidates = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("未找到 Microsoft Edge，无法生成 README 截图。")


def with_demo_action(page: str, action: str) -> str:
    if not action:
        return page
    script = f"""
<script>
window.addEventListener('load', () => {{
  setTimeout(() => {{ {action} }}, 240);
}});
</script>
"""
    return page.replace("</body>", script + "</body>", 1)


def render(
    edge: Path,
    workspace: Path,
    base_page: str,
    filename: str,
    *,
    action: str = "",
    height: int = 980,
    crop: tuple[int, int, int, int] | None = None,
) -> None:
    page_path = workspace / f"{Path(filename).stem}.html"
    profile_path = workspace / f"profile-{Path(filename).stem}"
    target = OUTPUT_DIR / filename
    page_path.write_text(with_demo_action(base_page, action), encoding="utf-8")
    target.unlink(missing_ok=True)

    command = (
        str(edge),
        "--headless=new",
        "--disable-gpu",
        "--disable-background-mode",
        "--no-first-run",
        "--hide-scrollbars",
        f"--window-size=1800,{height}",
        "--virtual-time-budget=5000",
        f"--user-data-dir={profile_path}",
        f"--screenshot={target}",
        page_path.as_uri(),
    )
    subprocess.run(
        command,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
    )
    for _ in range(30):
        if target.exists() and target.stat().st_size > 0:
            break
        time.sleep(0.2)
    else:
        raise RuntimeError(f"截图生成失败：{filename}")

    if crop:
        with Image.open(target) as image:
            image.crop(crop).save(target, optimize=True)
    print(f"Generated: {target.relative_to(ROOT)}")


def main() -> int:
    edge = find_edge()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_page = direct_desktop_html((ROOT / "index.html").read_text(encoding="utf-8"))
    workspace = Path(tempfile.mkdtemp(prefix="nte-readme-screenshots-"))
    try:
        render(edge, workspace, base_page, "01-overview.png")
        render(
            edge,
            workspace,
            base_page,
            "02-profile-panel.png",
            crop=(0, 0, 1800, 455),
        )
        render(
            edge,
            workspace,
            base_page,
            "03-verification-results.png",
            height=1180,
            action="document.getElementById('cdc-run-verification').click();",
        )
        render(
            edge,
            workspace,
            base_page,
            "04-rage-tracing.png",
            height=1180,
            action="""
const rageButton = document.querySelector('[data-verification-mode="rage"]');
rageButton.click();
const values = document.getElementById('cdc-rage-values');
values.value = '4413 5793 4413';
values.dispatchEvent(new Event('input', { bubbles: true }));
document.getElementById('cdc-run-verification').click();
""",
        )
        render(
            edge,
            workspace,
            base_page,
            "05-healing-mode.png",
            action="document.querySelector('[data-calculator-type=\"heal\"]').click();",
        )
        render(
            edge,
            workspace,
            base_page,
            "06-ocr-dialog.png",
            height=1080,
            action="""
document.getElementById('cdc-open-ocr').click();
setTimeout(() => {
  const windows = document.getElementById('cdc-ocr-window');
  windows.innerHTML = '<option>异环 · 2560×1440</option>';
  document.getElementById('cdc-ocr-status').textContent = '等待捕获面板截图';
  document.getElementById('cdc-capture-panel').disabled = false;
}, 800);
""",
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
