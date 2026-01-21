"""
Slackモジュール。

Slack Botの実装とハンドラを提供する。
"""

from src.slack.app import SlackBot, SlackBotImpl
from src.slack.handlers import handle_app_mention, handle_claude_command
from src.slack.result_formatter import SLACK_MESSAGE_LIMIT, post_result

__all__ = [
    "SLACK_MESSAGE_LIMIT",
    "SlackBot",
    "SlackBotImpl",
    "handle_app_mention",
    "handle_claude_command",
    "post_result",
]
