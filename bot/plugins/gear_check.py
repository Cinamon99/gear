"""
Splatoon 3 装备定时检查 & 推送插件

每 N 分钟检查一次装备商店,发现符合条件的装备时,
向指定的 QQ 群/好友推送通知。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from nonebot import get_driver, get_plugin_config, logger
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.plugin import PluginMetadata
from pydantic import BaseModel, Field

# ── APScheduler 懒加载 ─────────────────────────────────────────────────
# require() 只能放在函数/事件处理器内部,不能出现在模块顶层。
# 通过 on_startup 事件来注册定时任务。

# ── 导入核心模块 ────────────────────────────────────────────────────────
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
# 需要做个兼容 import —— 核心模块在父目录
from splatoon3_gear_reminders import (  # type: ignore
    GEAR_API_URL,
    LOCALE_API_URL,
    fetch_json,
    parse_sale_end_time,
    lookup_chinese_name,
    POWER_TRANSLATION,
)


# ── 配置 ────────────────────────────────────────────────────────────────
class GearBotConfig(BaseModel):
    """从 .env 读取的 bot 配置"""

    gear_target_groups: list[str] = Field(default_factory=list)
    gear_target_users: list[str] = Field(default_factory=list)
    gear_check_interval: int = 30
    gear_api_url: str = GEAR_API_URL
    locale_api_url: str = LOCALE_API_URL


plugin_config = get_plugin_config(GearBotConfig)

# 已推送过的装备 ID 缓存,避免重复推送
# 格式: {"gear_name|power_name|end_timestamp": True}
_seen_gear: dict[str, bool] = {}

# 技能判断规则(与核心模块保持一致)
KEY_POWERS = {"Comeback", "Stealth Jump", "Last-Ditch Effort"}
CLOTHING_POWERS = {"Run Speed Up", "Swim Speed Up"}


__plugin_meta__ = PluginMetadata(
    name="Splatoon3 装备检查",
    description="定时检查 Splatoon 3 装备商店并推送通知",
    usage="自动运行,无需手动触发",
    config=GearBotConfig,
)


# ── 核心检查逻辑 ────────────────────────────────────────────────────────
def check_current_gears() -> list[dict[str, Any]]:
    """
    拉取最新装备数据,返回符合条件的装备列表。
    每项包含 gear_name, primary_gear_power, price, sale_end_time, gear_type。
    """
    gear_data = fetch_json(plugin_config.gear_api_url, "装备数据")
    if gear_data is None:
        return []

    locale_data = fetch_json(plugin_config.locale_api_url, "中文翻译")

    found: list[dict[str, Any]] = []

    categories = [
        ("Limited", gear_data["data"]["gesotown"]["limitedGears"]),
        ("Brand", gear_data["data"]["gesotown"]["pickupBrand"]["brandGears"]),
    ]

    for gear_type, gears in categories:
        for gear in gears:
            end_time = parse_sale_end_time(gear["saleEndTime"])
            if end_time is None:
                continue

            g = gear["gear"]
            power_name = g["primaryGearPower"]["name"]
            typename = g["__typename"]

            # 筛选
            if power_name in KEY_POWERS:
                pass  # 合格
            elif typename == "ClothingGear" and power_name in CLOTHING_POWERS:
                pass  # 合格
            else:
                continue

            gear_name = lookup_chinese_name(
                g["__splatoon3ink_id"], g["name"], locale_data
            )

            found.append(
                {
                    "gear_name": gear_name,
                    "primary_gear_power": power_name,
                    "gear_type": gear_type,
                    "price": gear.get("price", 0),
                    "sale_end_time": end_time,
                }
            )

    return found


def format_gear_message(items: list[dict[str, Any]]) -> str:
    """将装备列表格式化为 QQ 消息文本."""
    lines: list[str] = [
        "🎯 Splatoon 3 装备提醒 — 目标技能上架!",
        "═" * 30,
    ]
    for item in items:
        local_end: datetime = item["sale_end_time"].astimezone(
            __import__("pytz").timezone("Asia/Shanghai")
        )
        translated = POWER_TRANSLATION.get(
            item["primary_gear_power"], item["primary_gear_power"]
        )
        lines.append(
            f"\n🛒 {translated}: {item['gear_name']}"
            f"\n   📦 类型: {'限时' if item['gear_type'] == 'Limited' else '品牌'}"
            f"\n   💰 价格: {item['price']} 鱿钞"
            f"\n   ⏰ 截止: {local_end.strftime('%m-%d %H:%M')}"
        )
    lines.append(
        f"\n{'═' * 30}"
        f"\n💡 导入日历可获取更多提醒"
        f"\n📌 发送「查装备」手动查看"
    )
    return "\n".join(lines)


def make_item_key(item: dict[str, Any]) -> str:
    """生成装备唯一标识,用于去重."""
    ts = int(item["sale_end_time"].timestamp())
    return f"{item['gear_name']}|{item['primary_gear_power']}|{ts}"


# ── 推送逻辑 ────────────────────────────────────────────────────────────
async def push_to_targets(bot: Bot, message: str) -> None:
    """向所有配置的目标推送消息."""
    for group_id in plugin_config.gear_target_groups:
        if not group_id.strip():
            continue
        try:
            await bot.send_group_msg(
                group_id=int(group_id.strip()),
                message=MessageSegment.text(message),
            )
            logger.info(f"已推送至群 {group_id}")
        except Exception as e:
            logger.error(f"推送至群 {group_id} 失败: {e}")

    for user_id in plugin_config.gear_target_users:
        if not user_id.strip():
            continue
        try:
            await bot.send_private_msg(
                user_id=int(user_id.strip()),
                message=MessageSegment.text(message),
            )
            logger.info(f"已推送至用户 {user_id}")
        except Exception as e:
            logger.error(f"推送至用户 {user_id} 失败: {e}")


# ── 定时任务 ────────────────────────────────────────────────────────────
async def gear_check_task() -> None:
    """定时检查装备并推送."""
    logger.info("开始定时检查装备...")
    items = check_current_gears()
    logger.info(f"检查完成,当前有 {len(items)} 件符合条件的装备")

    if not items:
        return

    # 过滤已推送过的
    new_items = [
        item
        for item in items
        if make_item_key(item) not in _seen_gear
    ]
    if not new_items:
        logger.debug("没有新装备,跳过推送")
        return

    # 标记为已推送
    for item in new_items:
        _seen_gear[make_item_key(item)] = True

    message = format_gear_message(new_items)
    logger.info(f"发现 {len(new_items)} 件新装备,准备推送")

    # 获取所有 bot 实例并推送
    from nonebot import get_bots

    bots = get_bots()
    if not bots:
        logger.warning("没有可用的 Bot 连接,无法推送")
        return

    for bot in bots.values():
        await push_to_targets(bot, message)


# ── bot 启动时清理旧记录 ──────────────────────────────────────────────
@get_driver().on_startup
async def _startup() -> None:
    """
    Bot 启动时清理缓存 & 注册定时任务。
    require() 在这里调用是安全的,因为 nonebot 已初始化。
    """
    # 注册 APScheduler 定时任务
    from nonebot import require

    require("nonebot_plugin_apscheduler")
    from nonebot_plugin_apscheduler import scheduler

    scheduler.add_job(
        gear_check_task,
        "interval",
        minutes=plugin_config.gear_check_interval,
        id="gear_check",
        misfire_grace_time=60,
    )
    logger.info(
        f"定时任务已注册,间隔 {plugin_config.gear_check_interval} 分钟"
    )

    # 清空已推送缓存
    _seen_gear.clear()
    logger.info("装备缓存已清空,准备开始监控")

    # 缓存当前装备,启动时不重复推送
    items = check_current_gears()
    if items:
        for item in items:
            _seen_gear[make_item_key(item)] = True
        logger.info(f"已缓存 {len(items)} 件当前在售装备(启动时不重复推送)")
    else:
        logger.info("当前没有符合条件的装备在售")
