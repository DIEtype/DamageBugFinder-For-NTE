from __future__ import annotations

import json
import ipaddress
import math
import re
import struct
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any


MAX_CAPTURED_GROUPS = 500
MAX_RAW_EVENTS = 500
MAX_CORE_AUDIT_RECORDS = 1000

_AUDIT_SENSITIVE_KEY_RE = re.compile(
    r"(?:payload|packet[_-]?data|raw[_-]?data|endpoint|remote[_-]?(?:ip|address)|"
    r"local[_-]?(?:ip|address)|authorization|cookie|account|uid|access[_-]?token)",
    re.IGNORECASE,
)

_EVENT_TOKEN_RE = re.compile(rb"[A-Za-z_][A-Za-z0-9_./:-]{4,}")
_EVENT_HINTS = (
    "melee",
    "attack",
    "skill",
    "ultra",
    "qte",
    "reaction",
    "damage",
    "critical",
    "critdamage",
    "buff",
    "debuff",
    "abilitysystem",
    "characterfornet",
)

_STRONG_EVENT_PREFIXES = (
    "ga_",
    "ge_",
    "default__buff_",
    "gameplaycue.",
    "ability.",
)
_STRONG_EVENT_NAMES = {
    "abilitysystemcomponent",
    "fcharacterfornet",
}


def _read_bits_le(data: bytes, bit_offset: int, bit_count: int) -> int | None:
    if bit_offset < 0 or bit_count < 0 or bit_offset + bit_count > len(data) * 8:
        return None
    value = 0
    for index in range(bit_count):
        source = bit_offset + index
        value |= ((data[source // 8] >> (source % 8)) & 1) << index
    return value


def _packet_data_bit_len(data: bytes) -> int | None:
    if not data or data[-1] == 0:
        return None
    return (len(data) - 1) * 8 + data[-1].bit_length() - 1


def _shifted_bytes(data: bytes, bit_shift: int) -> bytes:
    if bit_shift == 0:
        return data
    return bytes(
        (data[index] >> bit_shift) | ((data[index + 1] << (8 - bit_shift)) & 0xFF)
        for index in range(len(data) - 1)
    )


def _event_category(token: str) -> str:
    lowered = token.lower()
    if lowered == "abilitysystemcomponent":
        return "carrier"
    # Buff class names can contain words such as Skill/Ultra.  The explicit
    # Unreal Buff/GameplayEffect prefix is stronger evidence than those words.
    if lowered.startswith(("default__buff_", "ge_")) or any(
        hint in lowered for hint in ("damage", "critical", "buff", "debuff")
    ):
        return "effect"
    if any(hint in lowered for hint in ("melee", "attack", "skill", "ultra", "qte", "reaction")):
        return "action"
    return "system"


def _extract_aligned_strong_event_names(payload: bytes) -> set[str]:
    names: set[str] = set()
    for match in _EVENT_TOKEN_RE.finditer(payload):
        lowered = match.group().decode("ascii", "ignore").lower()
        if lowered in _STRONG_EVENT_NAMES or lowered.startswith(_STRONG_EVENT_PREFIXES):
            names.add(lowered)
    return names


def _extract_event_tokens(payload: bytes) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for bit_shift in range(8):
        shifted = _shifted_bytes(payload, bit_shift)
        for match in _EVENT_TOKEN_RE.finditer(shifted):
            token = match.group().decode("ascii", "ignore")
            lowered = token.lower()
            if len(token) > 120 or token.startswith("Game/"):
                continue
            if not (
                lowered.startswith(("ga_", "ge_"))
                or any(hint in lowered for hint in _EVENT_HINTS)
            ):
                continue
            found.setdefault(
                token,
                {
                    "name": token,
                    "category": _event_category(token),
                    "bit_shift": bit_shift,
                },
            )
    return list(found.values())


def _extract_numeric_candidates(payload: bytes) -> list[float]:
    candidates: dict[int, tuple[float, float]] = {}
    for bit_shift in range(8):
        shifted = _shifted_bytes(payload, bit_shift)
        for offset in range(max(0, len(shifted) - 3)):
            value = struct.unpack_from("<f", shifted, offset)[0]
            if not math.isfinite(value) or not 2 <= value <= 100_000_000:
                continue
            rounded = round(value)
            integer_error = abs(value - rounded)
            if integer_error > 0.08:
                continue
            key = int(rounded)
            if 100 <= key <= 500_000:
                magnitude_penalty = 0.0
            elif 2 <= key < 100 or key <= 5_000_000:
                magnitude_penalty = 0.15
            else:
                magnitude_penalty = 0.4
            score = integer_error + magnitude_penalty
            existing = candidates.get(key)
            if existing is None or score < existing[0]:
                candidates[key] = (score, float(value))
    ranked = sorted(candidates.values(), key=lambda item: (item[0], -item[1]))
    return [value for _, value in ranked[:96]]


def _build_core_audit_record(
    method: Any,
    params: Any,
    observed_at_unix_ms: int | None = None,
) -> dict[str, Any]:
    """Summarize one core notification without retaining packet or identity material."""

    schema: list[str] = []
    schema_seen: set[str] = set()
    identifiers: list[str] = []
    identifier_seen: set[str] = set()
    samples: list[dict[str, Any]] = []
    node_count = 0

    def add_schema(path: str) -> None:
        if path and path not in schema_seen and len(schema) < 240:
            schema_seen.add(path)
            schema.append(path)

    def visit(value: Any, path: str, depth: int = 0) -> None:
        nonlocal node_count
        node_count += 1
        if node_count > 6000 or depth > 8:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                key_text = str(key)
                child_path = f"{path}.{key_text}" if path else key_text
                add_schema(child_path)
                if _AUDIT_SENSITIVE_KEY_RE.search(key_text):
                    if len(samples) < 120:
                        samples.append({"path": child_path, "value": "[已隐藏]"})
                    continue
                visit(child, child_path, depth + 1)
            return
        if isinstance(value, (list, tuple)):
            add_schema(f"{path}[]")
            for child in value[:500]:
                visit(child, f"{path}[]", depth + 1)
            return
        if isinstance(value, str):
            normalized = value[:600]
            if normalized and normalized not in identifier_seen and len(identifiers) < 400:
                identifier_seen.add(normalized)
                identifiers.append(normalized)
            sample_value: Any = normalized[:180]
        elif value is None or isinstance(value, (bool, int, float)):
            sample_value = value
        else:
            sample_value = f"<{type(value).__name__}>"
        if len(samples) < 120:
            samples.append({"path": path, "value": sample_value})

    visit(params, "params")
    return {
        "observed_at_unix_ms": observed_at_unix_ms or round(time.time() * 1000),
        "method": str(method or "(未命名通知)"),
        "schema": schema,
        "identifiers": identifiers,
        "samples": samples,
        "scanned_nodes": node_count,
    }


def _parse_udp_ipv4(frame: bytes) -> tuple[bytes, int, bytes, int, bytes] | None:
    if len(frame) < 14:
        return None
    ether_type = struct.unpack_from("!H", frame, 12)[0]
    offset = 14
    while ether_type in (0x8100, 0x88A8):
        if len(frame) < offset + 4:
            return None
        ether_type = struct.unpack_from("!H", frame, offset + 2)[0]
        offset += 4
    if ether_type != 0x0800 or len(frame) < offset + 20:
        return None
    header_length = (frame[offset] & 0x0F) * 4
    if header_length < 20 or len(frame) < offset + header_length or frame[offset + 9] != 17:
        return None
    total_length = struct.unpack_from("!H", frame, offset + 2)[0]
    source = frame[offset + 12 : offset + 16]
    destination = frame[offset + 16 : offset + 20]
    udp_offset = offset + header_length
    if len(frame) < udp_offset + 8:
        return None
    source_port, destination_port, udp_length = struct.unpack_from("!HHH", frame, udp_offset)
    payload_end = min(len(frame), udp_offset + udp_length, offset + total_length)
    return source, source_port, destination, destination_port, frame[udp_offset + 8 : payload_end]


class PcapEventPreviewTracker:
    """Incrementally discovers readable test-server event names without exposing payloads."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._path: Path | None = None
        self._offset = 0
        self._endian = "<"
        self._interfaces: list[dict[str, Any]] = []
        self._streams: dict[tuple[bytes, bytes], dict[str, Any]] = {}
        self._local_endpoints: dict[tuple[bytes, bytes], bytes] = {}
        self._recent_numbers: deque[tuple[float, list[float]]] = deque(maxlen=300)
        self._pending_events: deque[dict[str, Any]] = deque(maxlen=MAX_RAW_EVENTS)
        self._events: deque[dict[str, Any]] = deque(maxlen=MAX_RAW_EVENTS)
        self._last_event_seen: dict[tuple[str, str], float] = {}
        self._counter = 0

    def _reset_file(self, path: Path) -> None:
        self.reset()
        self._path = path

    @staticmethod
    def _transport_probe(payload: bytes) -> tuple[int, int] | None:
        data_bit_len = _packet_data_bit_len(payload)
        if data_bit_len is None or data_bit_len < 72:
            return None
        if _read_bits_le(payload, 3, 3) != 3:
            return None
        if _read_bits_le(payload, 6, 2) != 0 or _read_bits_le(payload, 8, 2) != 0:
            return None
        packet_id = _read_bits_le(payload, 24, 14)
        if packet_id is None:
            return None
        return packet_id, data_bit_len

    def _infer_local_endpoint(
        self,
        stream_key: tuple[bytes, bytes],
        source_endpoint: bytes,
        destination_endpoint: bytes,
        source_ip: bytes,
        destination_ip: bytes,
    ) -> bytes:
        known = self._local_endpoints.get(stream_key)
        if known is not None:
            return known
        source_private = ipaddress.ip_address(source_ip).is_private
        destination_private = ipaddress.ip_address(destination_ip).is_private
        if source_private != destination_private:
            local = source_endpoint if source_private else destination_endpoint
        else:
            local = source_endpoint
        self._local_endpoints[stream_key] = local
        return local

    def _queue_game_packet(
        self,
        timestamp: float,
        stream_key: tuple[bytes, bytes],
        source_endpoint: bytes,
        destination_endpoint: bytes,
        source_ip: bytes,
        destination_ip: bytes,
        payload: bytes,
    ) -> None:
        local_endpoint = self._infer_local_endpoint(
            stream_key,
            source_endpoint,
            destination_endpoint,
            source_ip,
            destination_ip,
        )
        direction = "C2S" if source_endpoint == local_endpoint else "S2C"
        candidates = _extract_numeric_candidates(payload)
        if candidates:
            self._recent_numbers.append((timestamp, candidates))
        for token in _extract_event_tokens(payload):
            dedup_key = (token["name"], direction)
            previous = self._last_event_seen.get(dedup_key)
            if previous is not None and timestamp - previous < 0.04:
                continue
            self._last_event_seen[dedup_key] = timestamp
            self._counter += 1
            self._pending_events.append(
                {
                    "id": f"raw-event-{self._counter}",
                    "observed_at_unix_ms": round(timestamp * 1000),
                    "name": token["name"],
                    "category": token["category"],
                    "bit_shift": token["bit_shift"],
                    "direction": direction,
                    "packet_size": len(payload),
                    "_capture_timestamp": timestamp,
                    "_queued_at": time.monotonic(),
                }
            )

    def _observe_udp(
        self,
        timestamp: float,
        source_ip: bytes,
        source_port: int,
        destination_ip: bytes,
        destination_port: int,
        payload: bytes,
    ) -> None:
        source_endpoint = source_ip + struct.pack("!H", source_port)
        destination_endpoint = destination_ip + struct.pack("!H", destination_port)
        stream_key = tuple(sorted((source_endpoint, destination_endpoint)))
        state = self._streams.setdefault(
            stream_key,
            {
                "last_pid": {},
                "sequence_hits": 0,
                "signature_names": set(),
                "classified": False,
                "pending": deque(maxlen=80),
            },
        )
        packet = (
            timestamp,
            stream_key,
            source_endpoint,
            destination_endpoint,
            source_ip,
            destination_ip,
            payload,
        )
        if state["classified"]:
            self._queue_game_packet(*packet)
            return
        state["pending"].append(packet)
        state["signature_names"].update(_extract_aligned_strong_event_names(payload))
        signature_confirmed = len(state["signature_names"]) >= 2
        probe = self._transport_probe(payload)
        if probe is None and not signature_confirmed:
            return
        if probe is not None:
            packet_id, _ = probe
            previous = state["last_pid"].get(source_endpoint)
            state["last_pid"][source_endpoint] = packet_id
            if previous is not None and (packet_id - previous) & 0x3FFF == 1:
                state["sequence_hits"] += 1
        if state["sequence_hits"] < 3 and not signature_confirmed:
            return
        state["classified"] = True
        for buffered in state["pending"]:
            self._queue_game_packet(*buffered)
        state["pending"].clear()

    def _process_frame(self, timestamp: float, frame: bytes) -> None:
        parsed = _parse_udp_ipv4(frame)
        if parsed is None:
            return
        source, source_port, destination, destination_port, payload = parsed
        self._observe_udp(
            timestamp,
            source,
            source_port,
            destination,
            destination_port,
            payload,
        )

    def _process_block(self, block_type: int, block: bytes) -> None:
        body = block[8:-4]
        if block_type == 1 and len(body) >= 8:
            link_type, _, snap_length = struct.unpack_from(self._endian + "HHI", body)
            timestamp_resolution = 6
            offset = 8
            while offset + 4 <= len(body):
                option_code, option_length = struct.unpack_from(self._endian + "HH", body, offset)
                offset += 4
                value = body[offset : offset + option_length]
                offset += (option_length + 3) & ~3
                if option_code == 0:
                    break
                if option_code == 9 and value:
                    timestamp_resolution = value[0]
            scale = (
                2 ** -(timestamp_resolution & 0x7F)
                if timestamp_resolution & 0x80
                else 10 ** -timestamp_resolution
            )
            self._interfaces.append(
                {"link_type": link_type, "snap_length": snap_length, "timestamp_scale": scale}
            )
            return
        if block_type != 6 or len(body) < 20:
            return
        interface_id, timestamp_high, timestamp_low, captured_length, _ = struct.unpack_from(
            self._endian + "IIIII", body
        )
        if interface_id >= len(self._interfaces):
            return
        interface = self._interfaces[interface_id]
        if interface["link_type"] != 1:
            return
        frame = body[20 : 20 + captured_length]
        timestamp = ((timestamp_high << 32) | timestamp_low) * interface["timestamp_scale"]
        self._process_frame(timestamp, frame)

    def ingest(self, path: Path, force: bool = False) -> None:
        path = path.expanduser().resolve()
        if self._path != path or not path.is_file() or path.stat().st_size < self._offset:
            if not path.is_file():
                self._flush_pending(force=force)
                return
            self._reset_file(path)
        file_size = path.stat().st_size
        with path.open("rb") as source:
            while self._offset + 12 <= file_size:
                source.seek(self._offset)
                header = source.read(12)
                if len(header) < 12:
                    break
                block_type = struct.unpack_from("<I", header)[0]
                block_endian = self._endian
                if block_type == 0x0A0D0D0A:
                    byte_order_magic = header[8:12]
                    if byte_order_magic == b"\x4d\x3c\x2b\x1a":
                        block_endian = "<"
                    elif byte_order_magic == b"\x1a\x2b\x3c\x4d":
                        block_endian = ">"
                    else:
                        break
                block_length = struct.unpack_from(block_endian + "I", header, 4)[0]
                if block_length < 12 or self._offset + block_length > file_size:
                    break
                source.seek(self._offset)
                block = source.read(block_length)
                if len(block) != block_length:
                    break
                if struct.unpack_from(block_endian + "I", block, block_length - 4)[0] != block_length:
                    break
                self._endian = block_endian
                self._process_block(block_type, block)
                self._offset += block_length
        self._flush_pending(force=force)

    def _flush_pending(self, force: bool = False) -> None:
        now = time.monotonic()
        retained: deque[dict[str, Any]] = deque(maxlen=MAX_RAW_EVENTS)
        while self._pending_events:
            event = self._pending_events.popleft()
            if not force and now - event["_queued_at"] < 0.45:
                retained.append(event)
                continue
            event_timestamp = event["_capture_timestamp"]
            nearby: dict[int, tuple[float, float]] = {}
            for packet_timestamp, values in self._recent_numbers:
                delta = packet_timestamp - event_timestamp
                if not -0.12 <= delta <= 0.35:
                    continue
                for value in values:
                    key = round(value)
                    distance = abs(delta)
                    existing = nearby.get(key)
                    if existing is None or distance < existing[0]:
                        nearby[key] = (distance, value)
            ranked = sorted(
                nearby.values(),
                key=lambda item: (
                    0 if 100 <= item[1] <= 500_000 else 1,
                    item[0],
                    -item[1],
                ),
            )
            event["candidates"] = [value for _, value in ranked[:96]]
            event.pop("_capture_timestamp", None)
            event.pop("_queued_at", None)
            self._events.append(event)
        self._pending_events = retained

    def drain(self, force: bool = False) -> list[dict[str, Any]]:
        self._flush_pending(force=force)
        events = list(self._events)
        self._events.clear()
        return events


def _skill_key(skill: dict[str, Any]) -> tuple[Any, ...]:
    return (
        skill.get("char_id"),
        skill.get("name"),
        skill.get("category"),
        skill.get("ability_name"),
        skill.get("gameplay_effect_name"),
        bool(skill.get("is_follow_up")),
    )


class CaptureDeltaTracker:
    """Turns cumulative battle summaries into bounded newly-observed groups."""

    def __init__(self) -> None:
        self._previous: dict[tuple[Any, ...], tuple[int, float]] = {}
        self._groups: deque[dict[str, Any]] = deque(maxlen=MAX_CAPTURED_GROUPS)
        self._counter = 0

    def reset(self) -> None:
        self._previous.clear()
        self._groups.clear()
        self._counter = 0

    def ingest(self, summary: dict[str, Any]) -> None:
        current: dict[tuple[Any, ...], tuple[int, float]] = {}
        observed_at = int(time.time() * 1000)
        for skill in summary.get("skills") or []:
            if not isinstance(skill, dict):
                continue
            key = _skill_key(skill)
            hits = max(0, int(skill.get("hits") or 0))
            damage = max(0.0, float(skill.get("damage") or 0.0))
            current[key] = (hits, damage)
            old_hits, old_damage = self._previous.get(key, (0, 0.0))
            if hits < old_hits or damage + 0.001 < old_damage:
                old_hits, old_damage = 0, 0.0
            hit_delta = hits - old_hits
            damage_delta = damage - old_damage
            if hit_delta <= 0 or damage_delta <= 0:
                continue
            self._counter += 1
            self._groups.append(
                {
                    "id": f"capture-{self._counter}",
                    "observed_at_unix_ms": observed_at,
                    "char_id": skill.get("char_id"),
                    "char_name": skill.get("char_name") or "未知角色",
                    "name": skill.get("name") or skill.get("category") or "未知伤害来源",
                    "category": skill.get("category") or "未知",
                    "ability_name": skill.get("ability_name"),
                    "gameplay_effect_name": skill.get("gameplay_effect_name"),
                    "is_follow_up": bool(skill.get("is_follow_up")),
                    "hits": hit_delta,
                    "damage": damage_delta,
                    "single_hit": hit_delta == 1,
                }
            )
        self._previous = current

    def drain(self) -> list[dict[str, Any]]:
        groups = list(self._groups)
        self._groups.clear()
        return groups


class NteCoreCapture:
    """Small JSON-RPC/NDJSON client for a user-supplied nte-core executable."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._process: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._responses: dict[str, dict[str, Any]] = {}
        self._notifications: deque[dict[str, Any]] = deque(maxlen=200)
        self._audit_records: deque[dict[str, Any]] = deque(maxlen=MAX_CORE_AUDIT_RECORDS)
        self._errors: deque[str] = deque(maxlen=30)
        self._request_counter = 0
        self._audit_counter = 0
        self._operation_id: str | None = None
        self._state = "idle"
        self._sidecar_path: str | None = None
        self._raw_capture_path: Path | None = None
        self._audit_path: Path | None = None
        self._delta_tracker = CaptureDeltaTracker()
        self._raw_event_tracker = PcapEventPreviewTracker()

    def _record_notification_audit(self, method: Any, params: Any) -> None:
        record = _build_core_audit_record(method, params)
        with self._lock:
            self._audit_counter += 1
            record["id"] = f"core-audit-{self._audit_counter}"
            self._audit_records.append(record)
            audit_path = self._audit_path
        if audit_path is None:
            return
        try:
            with audit_path.open("a", encoding="utf-8") as target:
                target.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError as exc:
            with self._lock:
                self._errors.append(f"core audit log: {exc}")

    def _next_id(self) -> str:
        with self._lock:
            self._request_counter += 1
            return f"dbf-{self._request_counter}"

    def _send_request(
        self, method: str, params: dict[str, Any] | None = None, timeout: float = 12.0
    ) -> dict[str, Any]:
        process = self._process
        if process is None or process.poll() is not None or process.stdin is None:
            raise RuntimeError("解析器尚未运行")
        request_id = self._next_id()
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        with self._write_lock:
            process.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
            process.stdin.flush()
        deadline = time.monotonic() + timeout
        with self._condition:
            while request_id not in self._responses:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"等待 {method} 响应超时")
                self._condition.wait(remaining)
            response = self._responses.pop(request_id)
        if "error" in response:
            data = response["error"].get("data") or {}
            code = data.get("domain_code") or response["error"].get("code")
            detail = data.get("detail") or response["error"].get("message") or "未知错误"
            raise RuntimeError(f"{code}: {detail}")
        return response.get("result") or {}

    def _read_stdout(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            for line in process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                request_id = message.get("id")
                if request_id is not None:
                    with self._condition:
                        self._responses[str(request_id)] = message
                        self._condition.notify_all()
                    continue
                method = message.get("method")
                params = message.get("params") or {}
                self._record_notification_audit(method, params)
                if method == "event.battle.summary" and isinstance(params, dict):
                    with self._lock:
                        summary = params.get("summary") if isinstance(params.get("summary"), dict) else params
                        self._delta_tracker.ingest(summary)
                with self._lock:
                    self._notifications.append({"method": method, "params": params})
        finally:
            with self._condition:
                if self._process is process and self._state not in {"idle", "stopped"}:
                    self._state = "disconnected"
                self._condition.notify_all()

    def _read_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        for line in process.stderr:
            value = line.strip()
            if value:
                with self._lock:
                    self._errors.append(value[-800:])

    @staticmethod
    def _capture_start_params(detected: dict[str, Any]) -> dict[str, Any]:
        recommended = detected.get("recommended_device")
        if isinstance(recommended, str) and recommended.strip():
            device = {"mode": "name", "name": recommended}
        else:
            device = {"mode": "auto"}
        return {
            "profile": "combat",
            "device": device,
            "include_incoming": True,
            "server_damage_calibration": True,
            "raw_capture": "enabled",
        }

    def start(self, executable: str) -> dict[str, Any]:
        path = Path(executable).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() != ".exe":
            raise ValueError("请选择有效的 nte-core.exe")
        if self._process is not None and self._process.poll() is None:
            raise RuntimeError("抓包已经在运行")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        startupinfo = None
        creationflags = 0
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._state = "starting"
        self._sidecar_path = str(path)
        self._raw_capture_path = None
        self._audit_path = self._data_dir / f"core_audit_{time.strftime('%Y%m%d_%H%M%S')}.ndjson"
        self._delta_tracker.reset()
        self._raw_event_tracker.reset()
        self._responses.clear()
        self._notifications.clear()
        self._audit_records.clear()
        self._audit_counter = 0
        self._errors.clear()
        self._process = subprocess.Popen(
            [str(path), "serve", "--stdio", "--data-dir", str(self._data_dir)],
            cwd=str(path.parent),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._reader.start()
        self._stderr_reader.start()
        try:
            hello = self._send_request(
                "core.hello",
                {
                    "client_name": "Damage Bug Finder for NTE",
                    "client_version": "0.9.9-experimental",
                    "protocol_min": 1,
                    "protocol_max": 1,
                },
            )
            detected = self._send_request("capture.detect", {})
            result = self._send_request(
                "capture.start",
                self._capture_start_params(detected),
            )
            status = self._send_request("core.status", {}, timeout=5.0)
        except Exception:
            self._force_stop()
            raise
        raw_capture_path = status.get("raw_capture_path")
        if isinstance(raw_capture_path, str) and raw_capture_path.lower().endswith(".pcapng"):
            self._raw_capture_path = Path(raw_capture_path)
        self._operation_id = str(result.get("operation_id") or "") or None
        self._state = "capturing"
        return {
            "state": self._state,
            "operation_id": self._operation_id,
            "core_version": hello.get("core_version"),
            "recommended_device": detected.get("recommended_device"),
            "event_preview": self._raw_capture_path is not None,
            "audit_path": str(self._audit_path),
        }

    def poll(self) -> dict[str, Any]:
        process = self._process
        with self._lock:
            notifications = list(self._notifications)
            self._notifications.clear()
            audit_records = list(self._audit_records)
            self._audit_records.clear()
            errors = list(self._errors)
            self._errors.clear()
            groups = self._delta_tracker.drain()
            state = self._state
        if process is not None and process.poll() is not None and state not in {"idle", "stopped"}:
            state = "disconnected"
            self._state = state
        if state == "capturing" and self._raw_capture_path is None:
            try:
                status = self._send_request("core.status", {}, timeout=3.0)
                raw_capture_path = status.get("raw_capture_path")
                if isinstance(raw_capture_path, str) and raw_capture_path.lower().endswith(".pcapng"):
                    self._raw_capture_path = Path(raw_capture_path)
            except Exception as exc:
                errors.append(f"event preview status: {exc}")
        if self._raw_capture_path is not None:
            try:
                self._raw_event_tracker.ingest(self._raw_capture_path)
            except Exception as exc:
                errors.append(f"event preview parser: {exc}")
        raw_events = self._raw_event_tracker.drain()
        return {
            "state": state,
            "operation_id": self._operation_id,
            "sidecar_path": self._sidecar_path,
            "groups": groups,
            "raw_events": raw_events,
            "notifications": notifications,
            "audit_records": audit_records,
            "audit_path": str(self._audit_path) if self._audit_path is not None else None,
            "errors": errors,
        }

    def _force_stop(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                process.kill()
        self._state = "stopped"
        self._operation_id = None

    def stop(self) -> dict[str, Any]:
        process = self._process
        if process is None or process.poll() is not None:
            self._state = "stopped"
            return {"state": self._state}
        stop_error = None
        try:
            self._send_request("capture.stop", {}, timeout=15.0)
        except Exception as exc:  # preserve shutdown even when capture already stopped
            stop_error = str(exc)
        try:
            self._send_request("core.shutdown", {}, timeout=8.0)
        except Exception:
            pass
        try:
            process.wait(timeout=8.0)
        except subprocess.TimeoutExpired:
            self._force_stop()
        trailing_raw_events: list[dict[str, Any]] = []
        if self._raw_capture_path is not None:
            try:
                self._raw_event_tracker.ingest(self._raw_capture_path, force=True)
                trailing_raw_events = self._raw_event_tracker.drain(force=True)
            except Exception:
                pass
        self._state = "stopped"
        self._operation_id = None
        result = self.poll()
        result["raw_events"] = trailing_raw_events + result.get("raw_events", [])
        if stop_error:
            result["warning"] = stop_error
        return result
