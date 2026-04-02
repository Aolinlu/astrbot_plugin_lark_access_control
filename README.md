# astrbot_plugin_lark_access_control

AstrBot 飞书访问控制插件。

功能目标：

- 禁止私聊（可配置）
- 群白名单
- 用户黑名单 / 白名单
- 命中规则后阻断后续处理链（包含 LLM 请求）
- 可选返回提示文本或静默丢弃

## 工作机制

插件监听所有消息事件，在高优先级阶段执行访问控制。

仅对飞书/Lark 事件生效；非飞书来源（如 WebUI 对话）会直接放行。

命中拦截规则时会调用 `event.stop_event()`，停止后续插件与 AI 处理流程。

规则优先级：

1. `blocked_users`（黑名单优先）
2. `allowed_users`（当该配置非空时生效）
3. `disable_dm`（禁用私聊）
4. `allowed_groups`（仅群聊生效，且该配置非空时生效）

## 配置

本插件使用 AstrBot `_conf_schema.json` 机制定义配置。

| key | type | default | 说明 |
| --- | --- | --- | --- |
| `disable_dm` | bool | `true` | 是否禁用私聊 |
| `allowed_groups` | list | `[]` | 群白名单；为空表示不限制群 |
| `blocked_users` | list | `[]` | 用户黑名单 |
| `allowed_users` | list | `[]` | 用户白名单；非空时仅允许名单内用户 |
| `reply_on_block` | bool | `false` | 拦截后是否回复提示 |
| `allow_acl_command_bypass` | bool | `true` | 允许 `/acl` 管理命令绕过 ACL 拦截 |
| `reply_text_blocked_user` | string | 见 schema | 黑名单用户被拦截提示文本 |
| `reply_text_not_in_allowed_users` | string | 见 schema | 用户不在白名单提示文本 |
| `reply_text_private_message_disabled` | string | 见 schema | 私聊被禁用提示文本 |
| `reply_text_group_not_allowed` | string | 见 schema | 群聊不在白名单提示文本 |
| `enable_debug_log` | bool | `false` | 打印调试日志 |

## 管理命令

以下命令要求管理员权限。

- `/acl status`
- `/acl add_blocked_user <user_id>`
- `/acl remove_blocked_user <user_id>`
- `/acl list_blocked_users`
- `/acl add_allowed_user <user_id>`
- `/acl remove_allowed_user <user_id>`
- `/acl list_allowed_users`
- `/acl add_allowed_group <group_id>`
- `/acl remove_allowed_group <group_id>`
- `/acl list_allowed_groups`
- `/acl set_disable_dm <true|false>`
- `/acl set_reply_on_block <true|false>`
- `/acl set_reply_blocked_user <文案>`
- `/acl set_reply_not_in_allowed_users <文案>`
- `/acl set_reply_private_disabled <文案>`
- `/acl set_reply_group_not_allowed <文案>`
- `/acl inspect`

命令修改配置后会自动保存。

`allow_acl_command_bypass` 逻辑说明：

- 仅对管理命令本身生效（`/acl ...` 或 `acl ...`）。
- 作用是在 ACL 规则命中时，仍允许你执行管理命令进行自救（例如在私聊禁用时执行 `/acl set_disable_dm false`）。
- 不会让所有私聊消息都放行；普通聊天消息仍受 ACL 规则约束。

## 调试建议

1. 先开启 `enable_debug_log`，观察日志中的 `user_id` 与 `group_id` 是否符合飞书环境预期。
2. 先只开启 `disable_dm=true` 验证私聊阻断。
3. 再逐步启用 `allowed_groups` 和用户名单规则。

## 参考

- [AstrBot Repo](https://github.com/AstrBotDevs/AstrBot)
- [处理消息事件（含 stop_event）](https://docs.astrbot.app/dev/star/guides/listen-message-event.html)
- [插件配置](https://docs.astrbot.app/dev/star/guides/plugin-config.html)
