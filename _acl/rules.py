"""
访问控制规则：枚举、事件字段提取、规则判定。
与 AstrBot 框架解耦，不持有配置状态，所有判定均为纯函数。
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Optional

from astrbot.api.event import AstrMessageEvent

if TYPE_CHECKING:
    from .config_helper import ConfigHelper


class BlockReason(str, Enum):
    BLOCKED_USER = "blocked_user"
    NOT_IN_ALLOWED_USERS = "not_in_allowed_users"
    PRIVATE_MESSAGE_DISABLED = "private_message_disabled"
    GROUP_NOT_ALLOWED = "group_not_allowed"


_LARK_PLATFORM_HINTS = ("lark", "feishu")


# ──────────────────────── event field extraction ────────────────────────

def get_group_id(event: AstrMessageEvent) -> str:
    """返回群组 ID，私聊时返回空字符串。"""
    message_obj = getattr(event, "message_obj", None)
    if message_obj is not None:
        gid = getattr(message_obj, "group_id", "")
        if gid:
            return str(gid)
    fn = getattr(event, "get_group_id", None)
    if callable(fn):
        v = fn()
        if v:
            return str(v)
    return ""


def get_user_id(event: AstrMessageEvent) -> str:
    """返回发送者唯一 ID，按多个候选字段依次探测，最终回退到发送者名称。"""
    sender_obj = getattr(getattr(event, "message_obj", None), "sender", None)
    if sender_obj is not None:
        for field in ("sender_id", "user_id", "id", "open_id", "union_id"):
            v = getattr(sender_obj, field, None)
            if v:
                return str(v)
    for field in ("sender_id", "user_id", "from_user_id"):
        v = getattr(event, field, None)
        if v:
            return str(v)
    fn = getattr(event, "get_sender_id", None)
    if callable(fn):
        v = fn()
        if v:
            return str(v)
    unified = getattr(event, "unified_msg_origin", None)
    if unified:
        return str(unified)
    return str(event.get_sender_name())


def is_private(event: AstrMessageEvent) -> bool:
    """是否为私聊消息。"""
    return get_group_id(event) == ""


def is_lark_event(event: AstrMessageEvent) -> bool:
    """仅当事件来自飞书/Lark 平台时返回 True。"""
    candidates: list[str] = []

    for attr in ("platform", "platform_name", "adapter", "adapter_name", "client"):
        value = getattr(event, attr, None)
        if value:
            candidates.append(str(value))

    message_obj = getattr(event, "message_obj", None)
    if message_obj is not None:
        for attr in ("platform", "platform_name", "adapter", "adapter_name", "client"):
            value = getattr(message_obj, attr, None)
            if value:
                candidates.append(str(value))

    for method_name in ("get_platform_name", "get_platform", "get_adapter_name"):
        method = getattr(event, method_name, None)
        if callable(method):
            try:
                value = method()
            except TypeError:
                value = None
            if value:
                candidates.append(str(value))

    origin = str(getattr(event, "unified_msg_origin", "") or "")
    if origin:
        candidates.append(origin)

    lowered = [item.lower() for item in candidates]
    return any(hint in item for item in lowered for hint in _LARK_PLATFORM_HINTS)


def is_bot_mentioned(event: AstrMessageEvent) -> bool:
    """私聊始终返回 True；群聊中仅当消息链里存在 @机器人 时返回 True。

    用于决定是否向用户回复拦截提示：未 @机器人的群消息不应收到回复，
    避免机器人对非定向消息作出响应（即修复"空消息"bug 的核心守卫）。
    """
    if is_private(event):
        return True
    message_obj = getattr(event, "message_obj", None)
    if message_obj is None:
        return False
    self_id = str(getattr(message_obj, "self_id", "") or "")
    if not self_id:
        # 无法获取机器人自身 ID，保守处理：不回复
        return False
    for comp in getattr(message_obj, "message", []):
        for attr in ("qq", "id", "user_id", "open_id"):
            comp_id = str(getattr(comp, attr, "") or "")
            if comp_id and comp_id == self_id:
                return True
    return False


# ──────────────────────── rule evaluation ───────────────────────────────

def evaluate(event: AstrMessageEvent, cfg: ConfigHelper) -> Optional[BlockReason]:
    """按优先级依次评估拦截规则，返回命中的 BlockReason，或 None 表示放行。

    优先级：黑名单 > 用户白名单（非空时）> 禁私聊 > 群白名单（群聊且非空时）
    """
    user_id = get_user_id(event)
    group_id = get_group_id(event)
    private = is_private(event)

    if user_id in set(cfg.get_list("blocked_users")):
        return BlockReason.BLOCKED_USER

    allowed_users = set(cfg.get_list("allowed_users"))
    if allowed_users and user_id not in allowed_users:
        return BlockReason.NOT_IN_ALLOWED_USERS

    if cfg.get_bool("disable_dm", True) and private:
        return BlockReason.PRIVATE_MESSAGE_DISABLED

    allowed_groups = set(cfg.get_list("allowed_groups"))
    if not private and allowed_groups and group_id not in allowed_groups:
        return BlockReason.GROUP_NOT_ALLOWED

    return None
