"""
Splatoon 3 装备查询命令插件

提供手动指令供用户即时查询当前在售装备。
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any

from nonebot import get_plugin_config, logger, on_command
from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me
from pydantic import BaseModel, Field

# 导入核心模块
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from splatoon3_gear_reminders import (  # type: ignore
    GEAR_API_URL,
    LOCALE_API_URL,
    POWER_TRANSLATION,
    fetch_json,
    lookup_chinese_name,
    parse_sale_end_time,
)


class CmdConfig(BaseModel):
    gear_api_url: str = GEAR_API_URL
    locale_api_url: str = LOCALE_API_URL


cmd_config = get_plugin_config(CmdConfig)

KEY_POWERS = {"Comeback", "Stealth Jump", "Last-Ditch Effort"}
CLOTHING_POWERS = {"Run Speed Up", "Swim Speed Up"}

__plugin_meta__ = PluginMetadata(
    name="装备查询指令",
    description="手动查询 Splatoon 3 当前在售装备",
    usage="查装备 / 装备 / gear",
    config=CmdConfig,
)

# ── 注册命令 ────────────────────────────────────────────────────────────
gear_cmd = on_command("查装备", aliases={"装备", "gear"}, rule=to_me(), priority=5)
all_cmd = on_command("全部装备", aliases={"全部gear", "全装备"}, rule=to_me(), priority=5)


def fetch_all_gears() -> list[dict[str, Any]]:
    """拉取全部在售装备(不过滤)。"""
    gear_data = fetch_json(cmd_config.gear_api_url, "装备数据")
    if gear_data is None:
        return []
    locale_data = fetch_json(cmd_config.locale_api_url, "中文翻译")

    items: list[dict[str, Any]] = []
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
            gear_name = lookup_chinese_name(
                g["__splatoon3ink_id"], g["name"], locale_data
            )
            items.append(
                {
                    "gear_name": gear_name,
                    "primary_gear_power": g["primaryGearPower"]["name"],
                    "gear_type": gear_type,
                    "price": gear.get("price", 0),
                    "typename": g["__typename"],
                    "brand": g.get("brand", {}).get("name", ""),
                    "sale_end_time": end_time,
                }
            )
    return items


def format_gear_list(items: list[dict[str, Any]]) -> str:
    """格式化装备列表."""
    if not items:
        return "📭 当前没有在售装备数据。"

    import pytz

    limited = [i for i in items if i["gear_type"] == "Limited"]
    brand = [i for i in items if i["gear_type"] == "Brand"]
    tz = pytz.timezone("Asia/Shanghai")

    lines: list[str] = ["🎮 Splatoon 3 当前在售装备\n"]

    if limited:
        lines.append("【限时装备】")
        for i in limited:
            local_end: datetime = i["sale_end_time"].astimezone(tz)
            translated = POWER_TRANSLATION.get(
                i["primary_gear_power"], i["primary_gear_power"]
            )
            mark = "⭐" if i["primary_gear_power"] in KEY_POWERS or \
                (i["typename"] == "ClothingGear" and i["primary_gear_power"] in CLOTHING_POWERS) else "  "
            lines.append(
                f"  {mark} {i['gear_name']:20s} | {translated:12s}"
                f"\n     💰 {i['price']}鱿钞 | 截止 {local_end.strftime('%m-%d %H:%M')}"
            )
        lines.append("")

    if brand:
        lines.append("【品牌装备】")
        for i in brand:
            local_end: datetime = i["sale_end_time"].astimezone(tz)
            translated = POWER_TRANSLATION.get(
                i["primary_gear_power"], i["primary_gear_power"]
            )
            mark = "⭐" if i["primary_gear_power"] in KEY_POWERS or \
                (i["typename"] == "ClothingGear" and i["primary_gear_power"] in CLOTHING_POWERS) else "  "
            lines.append(
                f"  {mark} {i['gear_name']:20s} | {translated:12s}"
                f"\n     💰 {i['price']}鱿钞 | {i.get('brand', '')} | 截止 {local_end.strftime('%m-%d %H:%M')}"
            )

    lines.append(f"\n{'═' * 30}")
    lines.append("⭐ = 目标技能装备")
    return "\n".join(lines)


def format_target_only(items: list[dict[str, Any]]) -> str:
    """只显示目标技能装备."""
    import pytz

    tz = pytz.timezone("Asia/Shanghai")
    targets = [
        i
        for i in items
        if i["primary_gear_power"] in KEY_POWERS
        or (
            i["typename"] == "ClothingGear"
            and i["primary_gear_power"] in CLOTHING_POWERS
        )
    ]

    if not targets:
        return "📭 当前没有符合条件的装备在售。\n发送「全部装备」查看所有。"

    lines: list[str] = ["🎯 目标技能装备 (共 %d 件)\n" % len(targets)]
    for i in targets:
        local_end: datetime = i["sale_end_time"].astimezone(tz)
        translated = POWER_TRANSLATION.get(
            i["primary_gear_power"], i["primary_gear_power"]
        )
        lines.append(
            f"🛒 {translated}: {i['gear_name']}"
            f"\n   类型: {'限时' if i['gear_type'] == 'Limited' else '品牌'}"
            f"\n   价格: {i['price']} 鱿钞"
            f"\n   截止: {local_end.strftime('%m-%d %H:%M')}"
        )
        lines.append("")

    return "\n".join(lines).rstrip()


@gear_cmd.handle()
async def handle_gear_query(bot: Bot, event: Event) -> None:
    """处理「查装备」命令,显示目标技能装备。"""
    logger.info(f"收到查装备请求 from {event.get_user_id()}")
    items = fetch_all_gears()
    msg = format_target_only(items)
    await gear_cmd.finish(MessageSegment.text(msg))


@all_cmd.handle()
async def handle_all_gear_query(bot: Bot, event: Event) -> None:
    """处理「全部装备」命令,显示所有装备。"""
    logger.info(f"收到全部装备请求 from {event.get_user_id()}")
    items = fetch_all_gears()
    msg = format_gear_list(items)
    await all_cmd.finish(MessageSegment.text(msg))
