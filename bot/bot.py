"""
Splatoon 3 Gear Reminder QQ Bot — 启动入口

用法:
    python bot/bot.py                      # 使用默认配置(.env)
    NB_ENV=prod python bot/bot.py          # 使用生产配置(.env.prod)

需要先启动 OneBot 后端(Lagrange / go-cqhttp / LLOneBot 等),
确保 .env 中的 ONEBOT_WS_URLS 指向正确的地址。
"""

from __future__ import annotations

import os
import sys

# 将项目根目录加入 sys.path,确保核心模块可被导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter


def main() -> None:
    """初始化并运行 NoneBot 实例."""
    # 设置环境变量,让 nonebot 读取项目根目录的 .env
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    nonebot.init()
    driver = nonebot.get_driver()
    driver.register_adapter(OneBotV11Adapter)

    # 自动加载 pyproject.toml 中配置的插件
    nonebot.load_from_toml("pyproject.toml")

    nonebot.run()


if __name__ == "__main__":
    main()
