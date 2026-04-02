"""
配置辅助层：封装 AstrBotConfig 的读写，管理异步锁与持久化。
"""
from __future__ import annotations

import asyncio

from astrbot.api import AstrBotConfig

from .rules import BlockReason

# 每种拦截原因对应的默认回复文案
_REPLY_DEFAULTS: dict[BlockReason, str] = {
    BlockReason.BLOCKED_USER: "你已被列入黑名单，无法使用机器人。",
    BlockReason.NOT_IN_ALLOWED_USERS: "你不在允许使用机器人的用户列表中。",
    BlockReason.PRIVATE_MESSAGE_DISABLED: "当前不接受私聊，请在指定群聊中使用。",
    BlockReason.GROUP_NOT_ALLOWED: "当前群聊未被允许访问机器人。",
}


class ConfigHelper:
    """对 AstrBotConfig 的薄封装，提供类型安全的读取和带锁的写入。"""

    def __init__(self, config: AstrBotConfig) -> None:
        self._cfg = config
        self._lock = asyncio.Lock()

    # ── read ──────────────────────────────────────────────────────────

    def get_bool(self, key: str, default: bool) -> bool:
        return bool(self._cfg.get(key, default))

    def get_list(self, key: str) -> list[str]:
        raw = self._cfg.get(key, [])
        if not isinstance(raw, list):
            return []
        return [str(item).strip() for item in raw if str(item).strip()]

    def get_reply_text(self, reason: BlockReason) -> str:
        """返回对应原因的回复文案；未配置时返回内置默认值。"""
        return str(self._cfg.get(f"reply_text_{reason.value}", _REPLY_DEFAULTS[reason]))

    # ── write (thread-safe) ───────────────────────────────────────────

    def _save(self) -> None:
        fn = getattr(self._cfg, "save_config", None)
        if callable(fn):
            fn()

    async def add_to_list(self, key: str, value: str) -> bool:
        """幂等添加，已存在返回 False，成功添加返回 True。"""
        clean = value.strip()
        if not clean:
            return False
        async with self._lock:
            current = self.get_list(key)
            if clean in current:
                return False
            current.append(clean)
            self._cfg[key] = current
            self._save()
            return True

    async def remove_from_list(self, key: str, value: str) -> bool:
        """幂等删除，不存在返回 False，成功删除返回 True。"""
        clean = value.strip()
        async with self._lock:
            current = self.get_list(key)
            if clean not in current:
                return False
            current.remove(clean)
            self._cfg[key] = current
            self._save()
            return True

    async def set_value(self, key: str, value: object) -> None:
        async with self._lock:
            self._cfg[key] = value
            self._save()
