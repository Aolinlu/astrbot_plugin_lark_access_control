"""
飞书访问控制插件入口。

仅包含 AstrBot 框架绑定（filter 装饰器、命令注册、生命周期钩子）。
规则判定逻辑位于 _acl/rules.py，配置封装位于 _acl/config_helper.py。
"""
from typing import Optional

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from ._acl import (
    BlockReason,
    ConfigHelper,
    evaluate,
    get_group_id,
    get_user_id,
    is_bot_mentioned,
    is_lark_event,
    is_private,
)


@register("lark_access_control", "Aolinlu", "飞书访问控制插件", "0.1.0")
class LarkAccessControlPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.cfg = ConfigHelper(config)

    async def initialize(self) -> None:
        logger.info("[lark_access_control] initialized")

    # internal helpers
    @staticmethod
    def _is_acl_command(event: AstrMessageEvent) -> bool:
        text = str(getattr(event, "message_str", "") or "").strip().lower()
        return (
            text == "/acl"
            or text.startswith("/acl ")
            or text == "acl"
            or text.startswith("acl ")
        )

    @staticmethod
    def _to_bool(value: str) -> Optional[bool]:
        low = value.strip().lower()
        if low in ("1", "true", "yes", "on", "y"):
            return True
        if low in ("0", "false", "no", "off", "n"):
            return False
        return None

    @staticmethod
    def _trailing_text(event: AstrMessageEvent, prefix: str) -> Optional[str]:
        """去掉命令前缀，返回剩余文案；用于含空格的自由文本参数。"""
        raw = str(getattr(event, "message_str", "") or "").strip()
        if not raw.lower().startswith(prefix.lower()):
            return None
        tail = raw[len(prefix):].strip()
        return tail or None

    async def _handle_block(self, event: AstrMessageEvent, reason: BlockReason) -> None:
        logger.info(
            f"[lark_access_control] blocked reason={reason.value}"
            f" user={get_user_id(event)} group={get_group_id(event) or '-'}"
            f" private={is_private(event)}"
        )
        # 双重守卫：仅在 @机器人 且回复文案非空时才发送，防止空消息 bug
        if self.cfg.get_bool("reply_on_block", False) and is_bot_mentioned(event):
            text = self.cfg.get_reply_text(reason)
            if text.strip():
                await event.send(event.plain_result(text))
        event.stop_event()

    # access filter
    @filter.event_message_type(filter.EventMessageType.ALL, priority=100)
    async def access_filter(self, event: AstrMessageEvent) -> None:
        if not is_lark_event(event):
            return

        if self.cfg.get_bool("allow_acl_command_bypass", True) and self._is_acl_command(event):
            return

        reason = evaluate(event, self.cfg)
        if reason is None:
            if self.cfg.get_bool("enable_debug_log", False):
                logger.info(
                    f"[lark_access_control] allowed"
                    f" user={get_user_id(event)} group={get_group_id(event) or '-'}"
                )
            return

        await self._handle_block(event, reason)

    # admin commands
    @filter.command_group("acl")
    def acl(self) -> None:
        pass

    @acl.command("status")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def acl_status(self, event: AstrMessageEvent):
        cfg = self.cfg
        blocked = cfg.get_list("blocked_users")
        allowed = cfg.get_list("allowed_users")
        groups = cfg.get_list("allowed_groups")
        lines = [
            "ACL 当前配置:",
            f"  disable_dm           : {cfg.get_bool('disable_dm', True)}",
            f"  reply_on_block       : {cfg.get_bool('reply_on_block', False)}",
            f"  blocked_users  ({len(blocked):3}): {', '.join(blocked) or '(empty)'}",
            f"  allowed_users  ({len(allowed):3}): {', '.join(allowed) or '(empty)'}",
            f"  allowed_groups ({len(groups):3}): {', '.join(groups) or '(empty)'}",
        ]
        yield event.plain_result("\n".join(lines))

    @acl.command("add_blocked_user")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def add_blocked_user(self, event: AstrMessageEvent, user_id: str):
        ok = await self.cfg.add_to_list("blocked_users", user_id)
        yield event.plain_result("已添加 blocked_user" if ok else "blocked_user 已存在或参数为空")

    @acl.command("remove_blocked_user")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def remove_blocked_user(self, event: AstrMessageEvent, user_id: str):
        ok = await self.cfg.remove_from_list("blocked_users", user_id)
        yield event.plain_result("已移除 blocked_user" if ok else "blocked_user 不存在")

    @acl.command("list_blocked_users")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def list_blocked_users(self, event: AstrMessageEvent):
        users = self.cfg.get_list("blocked_users")
        yield event.plain_result("blocked_users:\n" + ("\n".join(f"  {u}" for u in users) if users else "  (empty)"))

    @acl.command("add_allowed_user")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def add_allowed_user(self, event: AstrMessageEvent, user_id: str):
        ok = await self.cfg.add_to_list("allowed_users", user_id)
        yield event.plain_result("已添加 allowed_user" if ok else "allowed_user 已存在或参数为空")

    @acl.command("remove_allowed_user")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def remove_allowed_user(self, event: AstrMessageEvent, user_id: str):
        ok = await self.cfg.remove_from_list("allowed_users", user_id)
        yield event.plain_result("已移除 allowed_user" if ok else "allowed_user 不存在")

    @acl.command("list_allowed_users")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def list_allowed_users(self, event: AstrMessageEvent):
        users = self.cfg.get_list("allowed_users")
        yield event.plain_result("allowed_users:\n" + ("\n".join(f"  {u}" for u in users) if users else "  (empty)"))

    @acl.command("add_allowed_group")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def add_allowed_group(self, event: AstrMessageEvent, group_id: str):
        ok = await self.cfg.add_to_list("allowed_groups", group_id)
        yield event.plain_result("已添加 allowed_group" if ok else "allowed_group 已存在或参数为空")

    @acl.command("remove_allowed_group")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def remove_allowed_group(self, event: AstrMessageEvent, group_id: str):
        ok = await self.cfg.remove_from_list("allowed_groups", group_id)
        yield event.plain_result("已移除 allowed_group" if ok else "allowed_group 不存在")

    @acl.command("list_allowed_groups")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def list_allowed_groups(self, event: AstrMessageEvent):
        groups = self.cfg.get_list("allowed_groups")
        yield event.plain_result("allowed_groups:\n" + ("\n".join(f"  {g}" for g in groups) if groups else "  (empty)"))

    @acl.command("set_disable_dm")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def set_disable_dm(self, event: AstrMessageEvent, value: str):
        parsed = self._to_bool(value)
        if parsed is None:
            yield event.plain_result("参数错误，请使用 true/false")
            return
        await self.cfg.set_value("disable_dm", parsed)
        yield event.plain_result(f"disable_dm 已设置为 {parsed}")

    @acl.command("set_reply_on_block")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def set_reply_on_block(self, event: AstrMessageEvent, value: str):
        parsed = self._to_bool(value)
        if parsed is None:
            yield event.plain_result("参数错误，请使用 true/false")
            return
        await self.cfg.set_value("reply_on_block", parsed)
        yield event.plain_result(f"reply_on_block 已设置为 {parsed}")

    @acl.command("set_reply_blocked_user")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def set_reply_blocked_user(self, event: AstrMessageEvent):
        text = self._trailing_text(event, "/acl set_reply_blocked_user")
        if text is None:
            yield event.plain_result("用法: /acl set_reply_blocked_user <文案>")
            return
        await self.cfg.set_value(f"reply_text_{BlockReason.BLOCKED_USER.value}", text)
        yield event.plain_result("blocked_user 回复文案已更新")

    @acl.command("set_reply_not_in_allowed_users")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def set_reply_not_in_allowed_users(self, event: AstrMessageEvent):
        text = self._trailing_text(event, "/acl set_reply_not_in_allowed_users")
        if text is None:
            yield event.plain_result("用法: /acl set_reply_not_in_allowed_users <文案>")
            return
        await self.cfg.set_value(f"reply_text_{BlockReason.NOT_IN_ALLOWED_USERS.value}", text)
        yield event.plain_result("not_in_allowed_users 回复文案已更新")

    @acl.command("set_reply_private_disabled")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def set_reply_private_disabled(self, event: AstrMessageEvent):
        text = self._trailing_text(event, "/acl set_reply_private_disabled")
        if text is None:
            yield event.plain_result("用法: /acl set_reply_private_disabled <文案>")
            return
        await self.cfg.set_value(f"reply_text_{BlockReason.PRIVATE_MESSAGE_DISABLED.value}", text)
        yield event.plain_result("private_message_disabled 回复文案已更新")

    @acl.command("set_reply_group_not_allowed")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def set_reply_group_not_allowed(self, event: AstrMessageEvent):
        text = self._trailing_text(event, "/acl set_reply_group_not_allowed")
        if text is None:
            yield event.plain_result("用法: /acl set_reply_group_not_allowed <文案>")
            return
        await self.cfg.set_value(f"reply_text_{BlockReason.GROUP_NOT_ALLOWED.value}", text)
        yield event.plain_result("group_not_allowed 回复文案已更新")

    @acl.command("inspect")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def acl_inspect(self, event: AstrMessageEvent):
        lines = [
            "ACL 事件探测:",
            f"  user_id            : {get_user_id(event)}",
            f"  group_id           : {get_group_id(event) or '-'}",
            f"  private            : {is_private(event)}",
            f"  bot_mentioned      : {is_bot_mentioned(event)}",
            f"  unified_msg_origin : {getattr(event, 'unified_msg_origin', '-')}",
        ]
        yield event.plain_result("\n".join(lines))

    async def terminate(self) -> None:
        logger.info("[lark_access_control] terminated")
