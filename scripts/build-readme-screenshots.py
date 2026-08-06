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
        render(
            edge,
            workspace,
            base_page,
            "07-buff-scope-dialog.png",
            action="""
document.querySelector('[data-edit-effect-scope]').click();
const scopeMode = document.getElementById('cdc-effect-scope-mode');
scopeMode.value = 'custom';
scopeMode.dispatchEvent(new Event('change', { bubbles: true }));
""",
        )
        render(
            edge,
            workspace,
            base_page,
            "08-stack-inference.png",
            height=1500,
            crop=(0, 430, 1800, 1500),
            action="""
const stackEffect = document.querySelector('[data-effect-row]');
const stackToggle = stackEffect.querySelector('[data-effect-stack-enabled]');
stackToggle.checked = true;
stackToggle.dispatchEvent(new Event('change', { bubbles: true }));
stackEffect.querySelector('[data-effect-max-stacks]').value = '6';
stackEffect.querySelector('[data-effect-damage]').value = '6';
const stackSkills = document.querySelectorAll('[data-skill-row]');
stackSkills[0].querySelector('[data-skill-observed]').value = '4726';
stackSkills[1].querySelector('[data-skill-observed]').value = '6203';
document.getElementById('cdc-run-verification').click();
""",
        )
        render(
            edge,
            workspace,
            base_page,
            "09-capture-event-learning.png",
            height=1080,
            action="""
document.getElementById('cdc-open-capture').click();
const captureStatus = document.getElementById('cdc-capture-status');
captureStatus.dataset.state = 'capturing';
captureStatus.textContent = '正在抓包 · core demo';
document.getElementById('cdc-capture-sidecar').value = 'C:\\Tools\\nte-core.exe';
document.getElementById('cdc-raw-event-damage').value = '4413';
document.getElementById('cdc-raw-event-count').textContent = '3 / 3';
document.getElementById('cdc-raw-event-preview').innerHTML = `
  <div class="raw-event-row" data-category="action"><span class="numeric text-small">14:26:31.220</span><span class="raw-event-direction" data-direction="C2S">C2S</span><span class="raw-event-name">Melee1</span><span class="raw-event-kind">ACTION · 4b</span><span class="raw-event-candidates"><span class="raw-event-candidate is-match">4,413</span></span><button class="btn btn-ghost raw-event-copy">⧉</button></div>
  <div class="raw-event-row" data-category="effect"><span class="numeric text-small">14:26:31.415</span><span class="raw-event-direction" data-direction="S2C">S2C</span><span class="raw-event-name">CritDamageBase</span><span class="raw-event-kind">EFFECT · 3b</span><span class="raw-event-candidates"><span class="raw-event-candidate is-match">4,413</span></span><button class="btn btn-ghost raw-event-copy">⧉</button></div>
  <div class="raw-event-row" data-category="action"><span class="numeric text-small">14:26:31.573</span><span class="raw-event-direction" data-direction="C2S">C2S</span><span class="raw-event-name">Melee2</span><span class="raw-event-kind">ACTION · 4b</span><span class="raw-event-candidates"><span class="raw-event-candidate is-match">4,419</span></span><button class="btn btn-ghost raw-event-copy">⧉</button></div>`;
document.getElementById('cdc-capture-marker-status').textContent = '已标记“真红 E 技能第 2 段”；接下来 12 秒内出现的事件会归到该动作。';
document.getElementById('cdc-capture-timeline').innerHTML = `
  <div class="capture-event">
    <label class="form-check"><input class="form-check-input" type="checkbox" checked><span class="numeric text-small">14:26:31</span></label>
    <div class="capture-source"><strong>真红 E 技能第 2 段 · 技能伤害</strong><div class="text-small result-meta">E技能</div></div>
    <div class="capture-ids">GA_Player_Skill2 · GE_Player_Skill2_Damage</div>
    <div class="capture-value">4,413</div><span class="capture-hit-badge">1 HIT</span>
    <label class="capture-map"><select class="form-select"><option>现有 · 技能一</option></select></label>
  </div>
  <div class="capture-event">
    <label class="form-check"><input class="form-check-input" type="checkbox" checked><span class="numeric text-small">14:26:34</span></label>
    <div class="capture-source"><strong>环合反应 · 创生花</strong><div class="text-small result-meta">创生花</div></div>
    <div class="capture-ids">GE_ActorReaction_1_Damage</div>
    <div class="capture-value">10,842</div><span class="capture-hit-badge">1 HIT</span>
    <label class="capture-map"><select class="form-select"><option>创生花</option></select></label>
  </div>
  <div class="capture-event">
    <label class="form-check"><input class="form-check-input" type="checkbox" disabled><span class="numeric text-small">14:26:37</span></label>
    <div class="capture-source"><strong>多段技能 · 短间隔合并</strong><div class="text-small result-meta">普攻</div></div>
    <div class="capture-ids">GA_Player_NormalAttack · GE_Player_NormalAttack_Damage</div>
    <div class="capture-value">6,821</div><span class="capture-hit-badge is-multihit">4 HIT 合计</span>
    <label class="capture-map"><select class="form-select"><option>新建常规技能</option></select></label>
  </div>`;
""",
        )
        render(
            edge,
            workspace,
            base_page,
            "10-inclination-team.png",
            height=1500,
            action="""
const inclinationSkill = document.querySelector('[data-skill-row]');
inclinationSkill.querySelector('[data-skill-model]').value = 'inclination';
inclinationSkill.querySelector('[data-skill-model]').dispatchEvent(new Event('change', { bubbles: true }));
inclinationSkill.querySelector('[data-skill-name]').value = '倾陷小队合计';
inclinationSkill.querySelector('[data-skill-observed]').value = '70346';
const inclinationEffects = document.querySelectorAll('[data-effect-row]');
inclinationEffects[0].querySelector('[data-effect-name]').value = '仅角色甲倾陷增伤';
inclinationEffects[0].querySelector('[data-effect-damage]').value = '0';
inclinationEffects[0].querySelector('[data-effect-inclination-damage]').value = '10';
inclinationEffects[0].querySelector('[data-effect-search-state]').value = 'locked';
inclinationEffects[0].querySelector('[data-effect-search-state]').dispatchEvent(new Event('change', { bubbles: true }));
inclinationEffects[1].querySelector('[data-effect-search-state]').value = 'suspended';
inclinationEffects[1].querySelector('[data-effect-search-state]').dispatchEvent(new Event('change', { bubbles: true }));
document.getElementById('cdc-add-inclination-contributor').click();
const inclinationRows = document.querySelectorAll('[data-inclination-row]');
inclinationRows[0].querySelector('[data-inclination-name]').value = '角色甲';
inclinationRows[0].querySelector('[data-inclination-attribute]').value = 'light';
inclinationRows[1].querySelector('[data-inclination-name]').value = '角色乙';
inclinationRows[1].querySelector('[data-inclination-attribute]').value = 'curse';
inclinationEffects[0].dataset.inclinationScopeMode = 'custom';
inclinationEffects[0].dataset.inclinationContributorIds = JSON.stringify([inclinationRows[0].dataset.inclinationId]);
inclinationEffects[0].querySelector('[data-edit-inclination-scope]').textContent = '倾陷：角色甲';
document.getElementById('cdc-run-verification').click();
""",
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
