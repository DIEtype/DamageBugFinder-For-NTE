from __future__ import annotations

import ctypes
import html
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any

import webview


# Keep APP_FOLDER stable so existing saved profiles survive the visible rename.
APP_TITLE = "Damage Bug Finder for NTE / 异环NTE数值验算器"
APP_FOLDER = "GameDamageCalculator"


def enable_dpi_awareness() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


class CalculatorApi:
    def __init__(self) -> None:
        # pywebview exposes public js_api attributes recursively. Keeping the
        # Window object public makes it walk the entire WebView2/.NET object
        # graph during startup, which can leave the application unresponsive.
        self._window: Any = None
        self._capture_lock = threading.Lock()
        self._packet_capture_lock = threading.Lock()
        self._packet_capture: Any = None

    def _bind_window(self, window: Any) -> None:
        self._window = window

    def get_capture_windows(self) -> dict[str, Any]:
        try:
            from panel_ocr import list_capture_windows

            return {"ok": True, "windows": list_capture_windows(APP_TITLE)}
        except Exception as exc:
            return {"ok": False, "error": f"无法读取窗口列表：{exc}"}

    def capture_panel(self, window_id: str, delay_seconds: float = 3) -> dict[str, Any]:
        if not self._capture_lock.acquire(blocking=False):
            return {"ok": False, "error": "已有一次截图正在进行。"}
        image = None
        try:
            from panel_ocr import capture_window

            if self._window is not None:
                self._window.hide()
            image = capture_window(window_id, delay_seconds)
        except Exception as exc:
            return {"ok": False, "error": f"截图失败：{exc}"}
        finally:
            if self._window is not None:
                self._window.show()
                self._window.restore()
            self._capture_lock.release()

        try:
            from panel_ocr import analyze_image, thumbnail_data_url

            result = analyze_image(image)
            return {
                "ok": True,
                "name": f"自动截图 {image.width}×{image.height}",
                "preview": thumbnail_data_url(image),
                "analysis": result,
            }
        except Exception as exc:
            return {"ok": False, "error": f"截图成功，但 OCR 识别失败：{exc}"}

    def recognize_uploaded_image(self, data_url: str, name: str = "导入截图") -> dict[str, Any]:
        try:
            from panel_ocr import analyze_image, decode_data_url, thumbnail_data_url

            image = decode_data_url(data_url)
            return {
                "ok": True,
                "name": name,
                "preview": thumbnail_data_url(image),
                "analysis": analyze_image(image),
            }
        except Exception as exc:
            return {"ok": False, "error": f"识别失败：{exc}"}

    def find_packet_capture_sidecars(self) -> dict[str, Any]:
        candidates: list[Path] = []
        configured = os.environ.get("NTE_CORE_PATH")
        if configured:
            candidates.append(Path(configured))
        candidates.extend(
            (
                Path(sys.executable).resolve().parent / "nte-core.exe",
                Path.cwd() / "nte-core.exe",
                app_data_dir() / "capture" / "nte-core.exe",
            )
        )
        found: list[str] = []
        for candidate in candidates:
            try:
                resolved = candidate.expanduser().resolve()
            except OSError:
                continue
            value = str(resolved)
            if resolved.is_file() and value not in found:
                found.append(value)
        return {"ok": True, "paths": found}

    def choose_packet_capture_sidecar(self) -> dict[str, Any]:
        if self._window is None:
            return {"ok": False, "error": "桌面窗口尚未就绪。"}
        try:
            selected = self._window.create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=False,
                file_types=("Windows executable (*.exe)",),
            )
            return {"ok": True, "path": selected[0] if selected else ""}
        except Exception as exc:
            return {"ok": False, "error": f"无法打开文件选择器：{exc}"}

    def start_packet_capture(self, executable: str) -> dict[str, Any]:
        if not self._packet_capture_lock.acquire(blocking=False):
            return {"ok": False, "error": "抓包控制正在处理另一项操作。"}
        try:
            from capture_sidecar import NteCoreCapture

            if self._packet_capture is None:
                self._packet_capture = NteCoreCapture(app_data_dir() / "capture")
            result = self._packet_capture.start(executable)
            return {"ok": True, **result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            self._packet_capture_lock.release()

    def poll_packet_capture(self) -> dict[str, Any]:
        if self._packet_capture is None:
            return {"ok": True, "state": "idle", "groups": [], "errors": []}
        try:
            return {"ok": True, **self._packet_capture.poll()}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "groups": [], "errors": []}

    def stop_packet_capture(self) -> dict[str, Any]:
        if not self._packet_capture_lock.acquire(blocking=False):
            return {"ok": False, "error": "抓包控制正在处理另一项操作。"}
        try:
            if self._packet_capture is None:
                return {"ok": True, "state": "idle"}
            return {"ok": True, **self._packet_capture.stop()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            self._packet_capture_lock.release()

    def _shutdown_packet_capture(self) -> None:
        if self._packet_capture is None:
            return
        try:
            self._packet_capture.stop()
        except Exception:
            pass


def bundled_path(filename: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / filename


def app_data_dir() -> Path:
    override = os.environ.get("GAME_DAMAGE_CALCULATOR_DATA_DIR")
    if override:
        return Path(override)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_FOLDER
    return Path.home() / "AppData" / "Local" / APP_FOLDER


def direct_desktop_html(rendered: str) -> str:
    match = re.search(r'<iframe\b[^>]*\bsrcdoc="([\s\S]*?)"[^>]*></iframe>', rendered, re.IGNORECASE)
    if not match:
        return rendered
    direct = html.unescape(match.group(1))
    direct = direct.replace('<html lang="en">', '<html lang="zh-CN">', 1)
    direct = direct.replace('<title>App.Fragment</title>', f'<title>{APP_TITLE}</title>', 1)
    direct = re.sub(
        r'<script\b[^>]*\bid="codex-visualization-lucide"[^>]*>[\s\S]*?</script>',
        "",
        direct,
        flags=re.IGNORECASE,
    )
    return direct.replace('<body>', '<body data-cdc-desktop="true">', 1)


def install_html() -> Path:
    source = bundled_path("index.html")
    target_dir = app_data_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "desktop.html"
    rendered = source.read_text(encoding="utf-8")
    target.write_text(direct_desktop_html(rendered), encoding="utf-8")
    return target


def self_test() -> int:
    html = bundled_path("index.html").read_text(encoding="utf-8")
    required = (
        "<title>Damage Bug Finder for NTE / 异环NTE数值验算器</title>",
        "最符合实测的全局状态",
        "零误差全局状态（最多 3 项）",
        "清空当前",
        "确定并开始验算",
        "狂暴溯源",
        "搜索强度",
        "极限 · 完整 22 / 限宽 50,000",
        "单人治疗",
        "单人伤害",
        "基础治疗加成（%）",
        "浸染与覆纹使用同一公式",
        "独立倍率 = 1 + 20% + 最终环合强度 / 1400",
        "基础环合强度",
        "高触发优先",
        "锁定生效",
        "挂起排除",
        "常规验算固定基础区，只反推当前技能公式实际读取的 Buff",
        "叠层 Buff",
        "自动反推",
        "最大层数",
        "持续伤害",
        "浊燃伤害",
        "倾陷伤害",
        "倾陷小队贡献",
        "设置 Buff 作用范围",
        "自动读取游戏面板",
        "捕获当前面板",
        "确认并填入面板",
        "抓包与事件学习",
        "原始事件预览",
        "游戏显示伤害（可选）",
        "送入常规验算",
    )
    direct = direct_desktop_html(html)
    try:
        from capture_sidecar import CaptureDeltaTracker

        tracker = CaptureDeltaTracker()
        tracker.ingest({"skills": [{"name": "self-test", "hits": 1, "damage": 1}]})
        capture_ready = tracker.drain()[0]["single_hit"] is True
    except Exception:
        capture_ready = False
    desktop_ready = (
        'data-cdc-desktop="true"' in direct
        and "<iframe" not in direct
        and "自动读取游戏面板" in direct
    )
    return 0 if all(marker in html for marker in required) and desktop_ready and capture_ready else 2


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    if "--ocr-test" in sys.argv:
        try:
            from panel_ocr import analyze_path

            index = sys.argv.index("--ocr-test")
            result = analyze_path(sys.argv[index + 1])
            return 0 if result.get("fields") else 3
        except Exception:
            return 4

    enable_dpi_awareness()

    html_path = install_html()
    smoke_mode = "--smoke-test" in sys.argv
    storage_path = app_data_dir() / ("SmokeWebView2" if smoke_mode else "WebView2")
    storage_path.mkdir(parents=True, exist_ok=True)

    api = CalculatorApi()
    smoke_result = {"code": 5}
    window = webview.create_window(
        APP_TITLE,
        html_path.as_uri(),
        width=1800,
        height=980,
        x=-32000 if smoke_mode else None,
        y=-32000 if smoke_mode else None,
        min_size=(1180, 700),
        resizable=True,
        confirm_close=False,
        js_api=api,
        hidden=False,
        minimized=smoke_mode,
        focus=not smoke_mode,
    )
    api._bind_window(window)
    window.events.closed += api._shutdown_packet_capture
    if smoke_mode:
        loaded_event = threading.Event()
        window.events.loaded += lambda: loaded_event.set()

        def verify_loaded() -> None:
            try:
                if not loaded_event.wait(timeout=30):
                    smoke_result["code"] = 8
                    return
                checks = window.evaluate_js("""[
                  document.readyState,
                  Boolean(document.getElementById('compact-damage-calculator')),
                  Boolean(document.getElementById('cdc-open-ocr')),
                  document.getElementById('cdc-ocr-entry')?.hidden === false,
                  document.getElementById('cdc-open-capture')?.hidden === false,
                  Boolean(document.getElementById('cdc-capture-timeline')),
                  Boolean(document.getElementById('cdc-raw-event-preview')),
                  Boolean(document.getElementById('cdc-raw-event-damage')),
                  Boolean(document.getElementById('cdc-open-formula')),
                  Boolean(document.getElementById('cdc-formula-dialog')),
                  document.getElementById('cdc-formula-turbid-base')?.value === '2700',
                  document.getElementById('cdc-formula-special-base-bonus')?.value === '20',
                  document.getElementById('cdc-formula-special-fusion-divisor')?.value === '1400',
                  document.getElementById('cdc-formula-inclination-base')?.value === '3603',
                  document.getElementById('cdc-formula-inclination-cap-divisor')?.value === '3',
                  Boolean(document.querySelector('[data-special-effect-option="overlay"]')),
                  Boolean(document.querySelector('[data-skill-model] option[value="darkstar"]')),
                  Boolean(document.querySelector('[data-skill-model] option[value="inclination"]')),
                  Boolean(document.querySelector('[data-calculator-type="inclination"]')),
                  Boolean(document.querySelector('[data-skill-preview]')),
                  Boolean(document.querySelector('iframe'))
                ]""")
                expected_checks = [
                    "complete", True, True, True, True, True, True, True,
                    True, True, True, True, True, True, True, True, True, True, True, True, False
                ]
                if checks != expected_checks:
                    smoke_result["code"] = 6
                    return
                prepared = window.evaluate_js("""(() => {
                  const root = document.getElementById('compact-damage-calculator');
                  const skills = document.getElementById('cdc-skills');
                  const effects = document.getElementById('cdc-effects');
                  let skill = skills.querySelector('[data-skill-row]');
                  let effect = effects.querySelector('[data-effect-row]');
                  if (!skill) {
                    document.getElementById('cdc-add-skill').click();
                    skill = skills.querySelector('[data-skill-row]');
                  }
                  if (!effect) {
                    document.getElementById('cdc-add-effect').click();
                    effect = effects.querySelector('[data-effect-row]');
                  }
                  if (!skill || !effect) return false;
                  document.querySelector('[data-calculator-type="damage"]').click();
                  document.querySelector('[data-verification-mode="normal"]').click();
                  Array.from(skills.querySelectorAll('[data-skill-row]')).slice(1).forEach((row) => row.remove());
                  Array.from(effects.querySelectorAll('[data-effect-row]')).slice(1).forEach((row) => row.remove());
                  skill.querySelector('[data-skill-model]').value = 'darkstar';
                  skill.querySelector('[data-skill-model]').dispatchEvent(new Event('change', { bubbles: true }));
                  skill.querySelector('[data-skill-name]').value = '黯星自检';
                  skill.querySelector('[data-skill-observed]').value = '86400';
                  skill.querySelector('[data-skill-critical]').checked = false;
                  skill.querySelector('[data-skill-enabled]').checked = true;
                  effect.querySelectorAll('[data-effect-attack], [data-effect-penetration], [data-effect-res-shred], [data-effect-damage], [data-effect-dot-damage], [data-effect-crit], [data-effect-skill], [data-effect-fusion-percent], [data-effect-fusion-flat]')
                    .forEach((input) => { input.value = '0'; });
                  effect.querySelector('[data-effect-damage]').value = '20';
                  effect.querySelector('[data-effect-stack-enabled]').checked = false;
                  effect.dataset.scopeMode = 'custom';
                  effect.dataset.scopeSkillIds = JSON.stringify([skill.dataset.skillId]);
                  document.getElementById('cdc-fusion').value = '360';
                  document.getElementById('cdc-resistance').value = '0';
                  document.getElementById('cdc-res-shred').value = '0';
                  document.getElementById('cdc-general').value = '0';
                  document.getElementById('cdc-elemental').value = '0';
                  document.getElementById('cdc-extra').value = '0';
                  document.getElementById('cdc-run-verification').click();
                  return true;
                })()""")
                if not prepared:
                    smoke_result["code"] = 9
                    return
                time.sleep(1.5)
                dynamic_checks = window.evaluate_js("""[
                  document.getElementById('cdc-run-status')?.textContent === '验算完成',
                  document.getElementById('cdc-best-details')?.textContent.includes('黯星伤害'),
                  document.getElementById('cdc-best-details')?.textContent.includes('86,400'),
                  document.getElementById('cdc-best-details')?.textContent.includes('自定义点名增伤'),
                  document.getElementById('cdc-best-details')?.textContent.includes('45,000')
                ]""")
                if dynamic_checks != [True, True, True, True, True]:
                    smoke_result["code"] = 10
                    return
                turbid_prepared = window.evaluate_js("""(() => {
                  const skill = document.querySelector('[data-skill-row]');
                  const effect = document.querySelector('[data-effect-row]');
                  if (!skill || !effect) return false;
                  skill.querySelector('[data-skill-model]').value = 'turbid';
                  skill.querySelector('[data-skill-model]').dispatchEvent(new Event('change', { bubbles: true }));
                  skill.querySelector('[data-skill-name]').value = '浊燃自检';
                  skill.querySelector('[data-skill-observed]').value = '3240';
                  effect.querySelector('[data-effect-damage]').value = '50';
                  effect.querySelector('[data-effect-dot-damage]').value = '50';
                  effect.dataset.scopeMode = 'all';
                  effect.dataset.scopeSkillIds = '[]';
                  document.getElementById('cdc-char-level').value = '80';
                  document.getElementById('cdc-enemy-level').value = '80';
                  document.getElementById('cdc-penetration').value = '0';
                  document.getElementById('cdc-run-verification').click();
                  return true;
                })()""")
                if not turbid_prepared:
                    smoke_result["code"] = 11
                    return
                time.sleep(1.5)
                turbid_checks = window.evaluate_js("""[
                  document.getElementById('cdc-run-status')?.textContent === '验算完成',
                  document.getElementById('cdc-best-details')?.textContent.includes('浊燃伤害'),
                  document.getElementById('cdc-best-details')?.textContent.includes('3,240'),
                  document.getElementById('cdc-best-details')?.textContent.includes('2,700'),
                  document.getElementById('cdc-best-details')?.textContent.includes('持续伤害区'),
                  !document.getElementById('cdc-best-details')?.textContent.includes('自定义点名增伤')
                ]""")
                if turbid_checks != [True, True, True, True, True, True]:
                    smoke_result["code"] = 12
                    return
                creation_prepared = window.evaluate_js("""(() => {
                  const skill = document.querySelector('[data-skill-row]');
                  if (!skill) return false;
                  skill.querySelector('[data-skill-model]').value = 'creation';
                  skill.querySelector('[data-skill-model]').dispatchEvent(new Event('change', { bubbles: true }));
                  skill.querySelector('[data-skill-name]').value = '创生花自检';
                  skill.querySelector('[data-skill-observed]').value = '7200';
                  document.getElementById('cdc-run-verification').click();
                  return true;
                })()""")
                if not creation_prepared:
                    smoke_result["code"] = 13
                    return
                time.sleep(1.5)
                creation_checks = window.evaluate_js("""[
                  document.getElementById('cdc-run-status')?.textContent === '验算完成',
                  document.getElementById('cdc-best-details')?.textContent.includes('创生花伤害'),
                  document.getElementById('cdc-best-details')?.textContent.includes('7,200'),
                  document.getElementById('cdc-best-details')?.textContent.includes('9,000'),
                  !document.getElementById('cdc-best-details')?.textContent.includes('持续伤害区'),
                  !document.getElementById('cdc-best-details')?.textContent.includes('自定义点名增伤')
                ]""")
                if creation_checks != [True, True, True, True, True, True]:
                    smoke_result["code"] = 14
                    return
                special_prepared = window.evaluate_js("""(() => {
                  const skill = document.querySelector('[data-skill-row]');
                  const effect = document.querySelector('[data-effect-row]');
                  const overlay = document.querySelector('[data-special-effect-option="overlay"]');
                  if (!skill || !effect || !overlay) return false;
                  skill.querySelector('[data-skill-model]').value = 'skill';
                  skill.querySelector('[data-skill-model]').dispatchEvent(new Event('change', { bubbles: true }));
                  skill.querySelector('[data-skill-name]').value = '覆纹与额外环合自检';
                  skill.querySelector('[data-skill-multiplier]').value = '100';
                  skill.querySelector('[data-skill-observed]').value = '707';
                  skill.querySelector('[data-skill-critical]').checked = false;
                  effect.querySelectorAll('[data-effect-attack], [data-effect-penetration], [data-effect-res-shred], [data-effect-damage], [data-effect-dot-damage], [data-effect-crit], [data-effect-skill], [data-effect-fusion-percent], [data-effect-fusion-flat]')
                    .forEach((input) => { input.value = '0'; });
                  effect.querySelector('[data-effect-fusion-flat]').value = '100';
                  effect.dataset.scopeMode = 'all';
                  effect.dataset.scopeSkillIds = '[]';
                  document.getElementById('cdc-panel').value = '1000';
                  document.getElementById('cdc-base').value = '0';
                  document.getElementById('cdc-atk-bonus').value = '0';
                  document.getElementById('cdc-fusion').value = '200';
                  document.getElementById('cdc-general').value = '0';
                  document.getElementById('cdc-elemental').value = '0';
                  document.getElementById('cdc-extra').value = '0';
                  overlay.click();
                  document.getElementById('cdc-run-verification').click();
                  return true;
                })()""")
                if not special_prepared:
                    smoke_result["code"] = 15
                    return
                time.sleep(1.5)
                special_checks = window.evaluate_js("""[
                  document.getElementById('cdc-run-status')?.textContent === '验算完成',
                  document.getElementById('cdc-special-effect-card')?.hidden === false,
                  document.getElementById('cdc-special-effect-name')?.textContent === '覆纹',
                  document.getElementById('cdc-best-details')?.textContent.includes('707'),
                  document.getElementById('cdc-best-details')?.textContent.includes('覆纹区'),
                  document.getElementById('cdc-best-details')?.textContent.includes('1.414286')
                ]""")
                if special_checks != [True, True, True, True, True, True]:
                    smoke_result["code"] = 16
                    return
                search_state_prepared = window.evaluate_js("""(() => {
                  const add = document.getElementById('cdc-add-effect');
                  while (document.querySelectorAll('[data-effect-row]').length < 3) add.click();
                  const [locked, suspended, irrelevant] = document.querySelectorAll('[data-effect-row]');
                  const skill = document.querySelector('[data-skill-row]');
                  const clear = (row) => row.querySelectorAll('[data-effect-attack], [data-effect-penetration], [data-effect-res-shred], [data-effect-damage], [data-effect-dot-damage], [data-effect-crit], [data-effect-skill], [data-effect-fusion-percent], [data-effect-fusion-flat]')
                    .forEach((input) => { input.value = '0'; });
                  [locked, suspended, irrelevant].forEach(clear);
                  locked.querySelector('[data-effect-name]').value = '锁定持续强化';
                  locked.querySelector('[data-effect-dot-damage]').value = '100';
                  locked.querySelector('[data-effect-search-state]').value = 'locked';
                  locked.querySelector('[data-effect-search-state]').dispatchEvent(new Event('change', { bubbles: true }));
                  suspended.querySelector('[data-effect-name]').value = '挂起攻击';
                  suspended.querySelector('[data-effect-attack]').value = '900';
                  suspended.querySelector('[data-effect-search-state]').value = 'suspended';
                  suspended.querySelector('[data-effect-search-state]').dispatchEvent(new Event('change', { bubbles: true }));
                  irrelevant.querySelector('[data-effect-name]').value = '未读取环合';
                  irrelevant.querySelector('[data-effect-fusion-flat]').value = '999';
                  irrelevant.querySelector('[data-effect-search-state]').value = 'auto';
                  irrelevant.querySelector('[data-effect-search-state]').dispatchEvent(new Event('change', { bubbles: true }));
                  skill.querySelector('[data-skill-model]').value = 'skill';
                  skill.querySelector('[data-skill-model]').dispatchEvent(new Event('change', { bubbles: true }));
                  skill.querySelector('[data-skill-name]').value = '持续伤害裁剪自检';
                  skill.querySelector('[data-skill-tag]').value = 'dot';
                  skill.querySelector('[data-skill-multiplier]').value = '100';
                  skill.querySelector('[data-skill-observed]').value = '1000';
                  skill.querySelector('[data-skill-critical]').checked = false;
                  document.getElementById('cdc-panel').value = '1000';
                  document.getElementById('cdc-base').value = '0';
                  document.getElementById('cdc-char-level').value = '80';
                  document.getElementById('cdc-enemy-level').value = '80';
                  document.getElementById('cdc-resistance').value = '0';
                  document.getElementById('cdc-penetration').value = '0';
                  document.getElementById('cdc-res-shred').value = '0';
                  document.querySelector('[data-special-effect-option="none"]').click();
                  document.querySelector('[data-verification-mode="normal"]').click();
                  document.getElementById('cdc-run-verification').click();
                  return true;
                })()""")
                if not search_state_prepared:
                    smoke_result["code"] = 17
                    return
                time.sleep(1.5)
                search_state_checks = window.evaluate_js("""[
                  document.getElementById('cdc-run-status')?.textContent === '验算完成',
                  document.getElementById('cdc-best-details')?.textContent.includes('1,000'),
                  document.getElementById('cdc-best-combination')?.textContent.includes('锁定持续强化锁定生效'),
                  document.getElementById('cdc-best-combination')?.textContent.includes('基础区锁定（仅验算 Buff）'),
                  !document.getElementById('cdc-best-combination')?.textContent.includes('挂起攻击'),
                  !document.getElementById('cdc-best-combination')?.textContent.includes('未读取环合'),
                  document.getElementById('cdc-combination-count')?.textContent.includes('1 / 1'),
                  document.querySelector('[data-effect-row][data-search-state="suspended"]') !== null
                ]""")
                if search_state_checks != [True, True, True, True, True, True, True, True]:
                    smoke_result["code"] = 18
                    return
                inclination_prepared = window.evaluate_js("""(() => {
                  const skill = document.querySelector('[data-skill-row]');
                  const effects = Array.from(document.querySelectorAll('[data-effect-row]'));
                  if (!skill || !effects.length) return false;
                  skill.querySelector('[data-skill-model]').value = 'inclination';
                  skill.querySelector('[data-skill-model]').dispatchEvent(new Event('change', { bubbles: true }));
                  skill.querySelector('[data-skill-name]').value = '倾陷小队自检';
                  skill.querySelector('[data-skill-observed]').value = '70346';
                  effects.forEach((effect, index) => {
                    effect.querySelectorAll('[data-effect-attack], [data-effect-penetration], [data-effect-res-shred], [data-effect-damage], [data-effect-dot-damage], [data-effect-inclination-damage], [data-effect-crit], [data-effect-skill], [data-effect-fusion-percent], [data-effect-fusion-flat]')
                      .forEach((input) => { input.value = '0'; });
                    effect.querySelector('[data-effect-search-state]').value = index === 0 ? 'locked' : 'suspended';
                    effect.querySelector('[data-effect-search-state]').dispatchEvent(new Event('change', { bubbles: true }));
                  });
                  const effect = effects[0];
                  effect.querySelector('[data-effect-name]').value = '仅角色甲倾陷增伤';
                  effect.querySelector('[data-effect-inclination-damage]').value = '10';
                  document.getElementById('cdc-inclination-contributors').innerHTML = '';
                  document.getElementById('cdc-add-inclination-contributor').click();
                  document.getElementById('cdc-add-inclination-contributor').click();
                  const contributors = Array.from(document.querySelectorAll('[data-inclination-row]'));
                  if (contributors.length !== 2) return false;
                  contributors[0].querySelector('[data-inclination-name]').value = '角色甲';
                  contributors[0].querySelector('[data-inclination-attribute]').value = 'light';
                  contributors[1].querySelector('[data-inclination-name]').value = '角色乙';
                  contributors[1].querySelector('[data-inclination-attribute]').value = 'curse';
                  contributors.forEach((row) => {
                    row.querySelector('[data-inclination-level]').value = '80';
                    row.querySelector('[data-inclination-damage]').value = '0';
                    row.querySelector('[data-inclination-penetration]').value = '0';
                    row.querySelector('[data-inclination-res-shred]').value = '0';
                    row.querySelector('[data-inclination-special]').value = '0';
                    row.querySelector('[data-inclination-enabled]').checked = true;
                  });
                  effect.dataset.inclinationScopeMode = 'custom';
                  effect.dataset.inclinationContributorIds = JSON.stringify([contributors[0].dataset.inclinationId]);
                  document.querySelector('[data-verification-mode="normal"]').click();
                  skill.querySelector('[data-skill-observed]').dispatchEvent(new Event('input', { bubbles: true }));
                  document.getElementById('cdc-run-verification').click();
                  return true;
                })()""")
                if not inclination_prepared:
                    smoke_result["code"] = 19
                    return
                time.sleep(1.5)
                inclination_checks = window.evaluate_js("""[
                  document.getElementById('cdc-run-status')?.textContent === '倾陷验算完成',
                  document.getElementById('cdc-best-details')?.textContent.includes('倾陷伤害（小队合计）'),
                  document.getElementById('cdc-best-details')?.textContent.includes('70,346'),
                  document.getElementById('cdc-best-details')?.textContent.includes('角色甲'),
                  document.getElementById('cdc-best-details')?.textContent.includes('角色乙'),
                  document.getElementById('cdc-best-details')?.textContent.includes('+'),
                  document.getElementById('cdc-combination-count')?.textContent.includes('1 / 1'),
                  document.querySelector('[data-skill-critical-field]')?.hidden === true,
                  document.querySelector('[data-skill-preview]')?.textContent.includes('70,346'),
                  document.querySelector('[data-skill-preview]')?.textContent.includes('自动叠层满层'),
                  document.getElementById('compact-damage-calculator')?.dataset.workspaceMode === 'inclination',
                  document.getElementById('cdc-panel-section')?.hidden === true,
                  document.getElementById('cdc-inclination-section')?.hidden === false,
                  document.getElementById('cdc-skill-section-title')?.textContent === '倾陷实测值',
                  document.querySelector('[data-inclination-special]')?.value === '0',
                  document.querySelector('.special-effect-picker')?.hidden === true,
                  getComputedStyle(document.getElementById('cdc-inclination-contributors')).gridTemplateColumns.split(' ').length === 2,
                  (() => {
                    const calculator = document.getElementById('compact-damage-calculator');
                    calculator.style.width = '886px';
                    const fits = calculator.scrollWidth <= calculator.clientWidth;
                    calculator.style.width = '';
                    return fits;
                  })()
                ]""")
                if inclination_checks != [True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, True]:
                    smoke_result["code"] = 21
                    return
                rage_base_prepared = window.evaluate_js("""(() => {
                  document.querySelector('[data-calculator-type="damage"]').click();
                  document.querySelector('[data-verification-mode="rage"]').click();
                  document.getElementById('cdc-rage-values').value = '1000';
                  document.getElementById('cdc-run-verification').click();
                  return true;
                })()""")
                if not rage_base_prepared:
                    smoke_result["code"] = 22
                    return
                time.sleep(1.5)
                rage_base_checks = window.evaluate_js("""[
                  document.getElementById('cdc-run-status')?.textContent === '溯源完成',
                  document.getElementById('cdc-search-scope-note')?.textContent.includes('基础区失效'),
                  !document.getElementById('cdc-combination-count')?.textContent.includes('1 / 1')
                ]""")
                smoke_result["code"] = 0 if rage_base_checks == [True, True, True] else 23
            except Exception:
                smoke_result["code"] = 7
            finally:
                window.destroy()
    webview.start(
        func=verify_loaded if smoke_mode else None,
        gui="edgechromium",
        debug=False,
        private_mode=False,
        storage_path=str(storage_path),
    )
    return smoke_result["code"] if smoke_mode else 0


if __name__ == "__main__":
    raise SystemExit(main())
