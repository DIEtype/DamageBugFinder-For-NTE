from __future__ import annotations

import asyncio
import base64
import ctypes
import ctypes.wintypes
import io
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PIL import Image, ImageGrab
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter


GAME_ATTRIBUTES = ("光", "灵", "咒", "暗", "魂", "相", "心灵")
FIELD_SPECS = {
    "panel_attack": ("攻击力", "非战斗面板攻击"),
    "base_attack": ("基础攻击",),
    "character_level": ("角色等级", "等级"),
    "crit_damage": ("暴击伤害",),
    "general_bonus": ("通用伤害增强", "通用增伤"),
    "elemental_bonus": tuple(
        [f"{name}属性异能伤害增强" for name in GAME_ATTRIBUTES[:-1]]
        + ["心灵伤害增强"]
    ),
    "fusion_strength": ("环合强度",),
    "healing_bonus": ("治疗加成",),
}
@dataclass
class OcrLine:
    text: str
    x: float
    y: float
    width: float
    height: float


def _software_bitmap(image: Image.Image) -> SoftwareBitmap:
    rgba = image.convert("RGBA")
    writer = DataWriter()
    writer.write_bytes(rgba.tobytes())
    bitmap = SoftwareBitmap(BitmapPixelFormat.RGBA8, rgba.width, rgba.height)
    bitmap.copy_from_buffer(writer.detach_buffer())
    return bitmap


async def _recognize(image: Image.Image) -> list[OcrLine]:
    engine = None
    try:
        language = Language("zh-Hans")
        if OcrEngine.is_language_supported(language):
            engine = OcrEngine.try_create_from_language(language)
    except OSError:
        engine = None
    engine = engine or OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise RuntimeError("Windows 未安装可用的简体中文 OCR 语言包。")

    max_dim = int(OcrEngine.max_image_dimension)
    scale = min(1.0, max_dim / max(image.size))
    if scale < 1:
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            Image.Resampling.LANCZOS,
        )

    result = await engine.recognize_async(_software_bitmap(image))
    lines: list[OcrLine] = []
    for line in result.lines:
        words = list(line.words)
        if not words:
            continue
        left = min(word.bounding_rect.x for word in words)
        top = min(word.bounding_rect.y for word in words)
        right = max(word.bounding_rect.x + word.bounding_rect.width for word in words)
        bottom = max(word.bounding_rect.y + word.bounding_rect.height for word in words)
        lines.append(OcrLine(line.text.strip(), left, top, right - left, bottom - top))
    return lines


def recognize_image(image: Image.Image) -> list[OcrLine]:
    return asyncio.run(_recognize(image))


def _normalized(text: str) -> str:
    return re.sub(r"[\s：:·•]", "", text).replace("異", "异").replace("傷", "伤")


def _number_tokens(text: str) -> list[float]:
    clean = text.replace(",", "").replace("％", "%").replace("O", "0").replace("o", "0")
    clean = re.sub(r"(?<=\d)\s*[．·•。]\s*(?=\d)", ".", clean)
    return [float(value) for value in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", clean)]


def _match_label(text: str) -> tuple[str | None, str | None, float]:
    normalized = _normalized(text)
    best: tuple[str | None, str | None, float] = (None, None, 0.0)
    for key, labels in FIELD_SPECS.items():
        for label in labels:
            candidate = _normalized(label)
            if candidate in normalized:
                score = max(len(candidate) / max(len(normalized), 1), 0.92)
            elif normalized in candidate and len(normalized) >= 4 and len(normalized) / len(candidate) >= 0.55:
                score = len(normalized) / len(candidate)
            else:
                score = SequenceMatcher(None, normalized, candidate).ratio()
            if score > best[2]:
                best = (key, label, score)
    return best


def _nearby_value_line(label: OcrLine, lines: list[OcrLine]) -> OcrLine | None:
    label_mid = label.y + label.height / 2
    candidates = []
    for line in lines:
        if line is label or not _number_tokens(line.text):
            continue
        line_mid = line.y + line.height / 2
        vertical = abs(line_mid - label_mid)
        if vertical <= max(38, label.height * 1.8) and line.x > label.x + label.width * 0.55:
            candidates.append((vertical, -line.x, line))
    return min(candidates, default=(0, 0, None))[2]


def parse_panel(lines: list[OcrLine], image_size: tuple[int, int]) -> dict[str, Any]:
    recognized: list[dict[str, Any]] = []
    ignored: list[str] = []
    width, _ = image_size

    # Overview level is usually recognized as a combined "Lv:80/80" line.
    for line in lines:
        level_match = re.search(r"(?:Lv|LV|lv)[.:：]?\s*(\d{1,3})\s*/", line.text)
        if level_match:
            recognized.append({
                "field": "character_level",
                "label": "角色等级",
                "value": float(level_match.group(1)),
                "confidence": 0.98,
                "raw": line.text,
            })
        elif re.search(r"(?:Lv|LV|lv)", line.text):
            level_numbers = _number_tokens(line.text)
            plausible = [value for value in level_numbers if 1 <= value <= 200]
            if plausible:
                recognized.append({
                    "field": "character_level",
                    "label": "角色等级",
                    "value": plausible[-1],
                    "confidence": 0.82,
                    "raw": line.text,
                })

    for line in lines:
        if "抗性" in _normalized(line.text):
            continue
        key, matched_label, score = _match_label(line.text)
        if key is None or score < 0.61:
            continue
        value_line = _nearby_value_line(line, lines)
        if value_line is None:
            if key in {"fusion_strength", "healing_bonus", "elemental_bonus"}:
                recognized.append({
                    "field": key,
                    "label": matched_label,
                    "attribute": matched_label.replace("属性异能伤害增强", "").replace("伤害增强", "")
                    if key == "elemental_bonus" else None,
                    "value": 0.0,
                    "confidence": 0.64,
                    "raw": f"{line.text} | 未识别到数值，暂按 0",
                })
            continue
        numbers = _number_tokens(value_line.text)
        if not numbers:
            continue

        value = numbers[-1]
        confidence = min(0.99, 0.58 + score * 0.38)
        attribute = None
        if key == "panel_attack":
            # The detail panel writes base + bonus. The overview writes the total.
            if len(numbers) >= 2 and "+" in value_line.text:
                value = sum(numbers[-2:])
                recognized.append({
                    "field": "base_attack",
                    "label": "基础攻击",
                    "value": numbers[-2],
                    "confidence": min(confidence, 0.96),
                    "raw": value_line.text,
                })
        elif key == "elemental_bonus":
            attribute = matched_label.replace("属性异能伤害增强", "").replace("伤害增强", "")
        elif key == "healing_bonus" and "受治疗" in _normalized(line.text):
            ignored.append(line.text)
            continue

        recognized.append({
            "field": key,
            "label": matched_label,
            "attribute": attribute,
            "value": value,
            "confidence": confidence,
            "raw": f"{line.text} | {value_line.text}" if line is not value_line else line.text,
        })

    # If full-screen OCR split a value away from its label, retain diagnostics only.
    return {
        "fields": recognized,
        "ignored": ignored,
        "raw_lines": [line.text for line in lines],
        "image_width": width,
    }


def analyze_image(image: Image.Image) -> dict[str, Any]:
    lines = recognize_image(image)
    return parse_panel(lines, image.size)


def thumbnail_data_url(image: Image.Image) -> str:
    preview = image.copy()
    preview.thumbnail((640, 360), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    preview.convert("RGB").save(output, "JPEG", quality=68, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def decode_data_url(data_url: str) -> Image.Image:
    try:
        encoded = data_url.split(",", 1)[1]
        return Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")
    except (IndexError, ValueError, OSError) as exc:
        raise ValueError("无法读取所选图片。") from exc


def list_capture_windows(excluded_title: str) -> list[dict[str, Any]]:
    user32 = ctypes.windll.user32
    windows: list[dict[str, Any]] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def visit(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if not title or title == excluded_title:
            return True
        rect = ctypes.wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width < 640 or height < 480:
            return True
        windows.append({
            "id": str(int(hwnd)),
            "title": title,
            "width": width,
            "height": height,
            "area": width * height,
        })
        return True

    user32.EnumWindows(callback_type(visit), 0)
    windows.sort(key=lambda item: item["area"], reverse=True)
    for item in windows:
        item.pop("area", None)
    return windows


def capture_window(hwnd_value: str, delay_seconds: float = 3.0) -> Image.Image:
    user32 = ctypes.windll.user32
    hwnd = int(hwnd_value)
    if not user32.IsWindow(hwnd):
        raise ValueError("游戏窗口已经关闭，请刷新窗口列表。")
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(max(0.5, min(float(delay_seconds), 8.0)))
    rect = ctypes.wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise ValueError("无法取得游戏窗口位置。")
    return ImageGrab.grab(
        bbox=(rect.left, rect.top, rect.right, rect.bottom),
        all_screens=True,
    ).convert("RGB")


def analyze_path(path: str | Path) -> dict[str, Any]:
    with Image.open(path) as image:
        return analyze_image(image.convert("RGB"))
