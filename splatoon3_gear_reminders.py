"""
Splatoon 3 Gear Reminder — 斯普拉遁3 装备售卖日历生成器

从 splatoon3.ink API 拉取装备数据,筛选特定技能装备,
生成 .ics 日历文件,可导入手机/电脑日历提醒购买。

用法:
    python splatoon3_gear_reminders.py                   # 默认输出到桌面
    python splatoon3_gear_reminders.py -o /path/to/file  # 指定输出路径
    python splatoon3_gear_reminders.py --no-brand        # 只处理 limitedGears
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import icalendar
import pytz
import requests

# ── 日志配置 ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("splatoon3_gear")

# ── 常量 ────────────────────────────────────────────────────────────────
GEAR_API_URL = "https://splatoon3.ink/data/gear.json"
LOCALE_API_URL = "https://splatoon3.ink/data/locale/zh-CN.json"

# 需要关注的技能列表
# 规则: 全品类关注的技能
KEY_PRIMARY_POWERS: set[str] = {"Comeback", "Stealth Jump", "Last-Ditch Effort"}
# 仅限 ClothGear 关注的技能
CLOTHING_ONLY_POWERS: set[str] = {"Run Speed Up", "Swim Speed Up"}

# 技能中文翻译
POWER_TRANSLATION: dict[str, str] = {
    "Comeback": "回归头",
    "Stealth Jump": "隐跳鞋",
    "Last-Ditch Effort": "终场冲刺头",
    "Run Speed Up": "走速衣服",
    "Swim Speed Up": "游速衣服",
}

# 输出路径: 默认当前目录下的 gear.ics
LOCAL_TIMEZONE = "Asia/Shanghai"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.join(PROJECT_DIR, "gear.ics")


# ── 数据模型 ────────────────────────────────────────────────────────────
@dataclass
class GearItem:
    """单件筛选后的装备信息"""

    sale_end_time: datetime
    gear_name: str
    primary_gear_power: str
    gear_type: str  # "Limited" or "Brand"
    price: int


# ── API 获取 ────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Splatoon3GearBot/1.0 (https://github.com/Cinamon99/gear)"
}


def fetch_json(url: str, label: str = "data") -> dict[str, Any] | None:
    """获取 JSON 数据,失败时返回 None."""
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
        logger.info("%s 获取成功 (%d bytes)", label, len(resp.content))
        return resp.json()
    except requests.RequestException as e:
        logger.error("获取 %s 失败: %s", label, e)
        return None
    except json.JSONDecodeError as e:
        logger.error("解析 %s JSON 失败: %s", label, e)
        return None


# ── 时间工具 ────────────────────────────────────────────────────────────
def parse_sale_end_time(raw: str | int | float) -> datetime | None:
    """
    解析 saleEndTime 为 UTC datetime.
    支持 ISO 8601 字符串和 Unix 时间戳(数字).
    """
    if isinstance(raw, str):
        try:
            # 移除末尾 'Z' 再解析,然后标记为 UTC
            dt = datetime.fromisoformat(raw.rstrip("Z"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            # 可能实际上是数字字符串
            try:
                return datetime.fromtimestamp(float(raw), tz=timezone.utc)
            except (ValueError, OSError):
                return None
    try:
        return datetime.fromtimestamp(float(raw), tz=timezone.utc)
    except (ValueError, OSError):
        return None


def to_local_time(utc_dt: datetime, tz_name: str = LOCAL_TIMEZONE) -> datetime:
    """将 UTC datetime 转换为本地时区."""
    return utc_dt.astimezone(pytz.timezone(tz_name))


# ── 装备筛选 ────────────────────────────────────────────────────────────
def should_keep(power_name: str, typename: str) -> bool:
    """判断装备是否满足筛选条件."""
    if power_name in KEY_PRIMARY_POWERS:
        return True
    if typename == "ClothingGear" and power_name in CLOTHING_ONLY_POWERS:
        return True
    return False


def lookup_chinese_name(
    splatoon3ink_id: str, fallback_name: str, locale_data: dict | None
) -> str:
    """从 locale 数据中查找中文名称."""
    if locale_data is None:
        return fallback_name
    entry = locale_data.get("gear", {}).get(splatoon3ink_id, fallback_name)
    if isinstance(entry, dict):
        return entry.get("name", fallback_name)
    return str(entry)


def process_gears(
    gears: list[dict],
    gear_type: str,
    locale_data: dict | None,
) -> list[GearItem]:
    """处理一批装备,返回筛选后的 GearItem 列表."""
    items: list[GearItem] = []
    for gear in gears:
        end_time = parse_sale_end_time(gear["saleEndTime"])
        if end_time is None:
            logger.warning("跳过无效时间的装备: %s", gear.get("gear", {}).get("name"))
            continue

        g = gear["gear"]
        power_name = g["primaryGearPower"]["name"]
        typename = g["__typename"]

        if not should_keep(power_name, typename):
            continue

        gear_name = lookup_chinese_name(
            g["__splatoon3ink_id"], g["name"], locale_data
        )
        price = gear.get("price", 0)

        items.append(
            GearItem(
                sale_end_time=end_time,
                gear_name=gear_name,
                primary_gear_power=power_name,
                gear_type=gear_type,
                price=price,
            )
        )
        logger.info(
            "✓ [%s] %s | %s | %d 鱿钞 | 截止 %s",
            gear_type,
            gear_name,
            power_name,
            price,
            end_time.strftime("%Y-%m-%d %H:%M UTC"),
        )
    return items


def parse_gear_data(
    data: dict, locale_data: dict | None, include_brand: bool = True
) -> list[GearItem]:
    """解析完整 gear.json,返回筛选后列表."""
    items: list[GearItem] = []

    # limitedGears (限时装备)
    limited = data["data"]["gesotown"]["limitedGears"]
    items.extend(process_gears(limited, "Limited", locale_data))

    # pickupBrand (品牌装备)
    if include_brand:
        brand = data["data"]["gesotown"]["pickupBrand"]["brandGears"]
        items.extend(process_gears(brand, "Brand", locale_data))

    logger.info("总计筛选到 %d 件装备", len(items))
    return items


# ── 日历生成 ────────────────────────────────────────────────────────────
def create_calendar_events(item: GearItem) -> list[icalendar.Event]:
    """
    为一件装备创建日历事件。
    返回 [截止事件, 开售事件], 开售事件可能 None.
    """
    local_end = to_local_time(item.sale_end_time)
    translated_power = POWER_TRANSLATION.get(
        item.primary_gear_power, item.primary_gear_power
    )

    events: list[icalendar.Event] = []

    # ── 事件1: 截止提醒(结束前2小时醒来到结束) ──
    event = icalendar.Event()
    event.add("summary", f"在售 {translated_power}: {item.gear_name} 即将截止")
    event.add(
        "description",
        f"价格: {item.price} 鱿钞\n"
        f"截止时间: {local_end.strftime('%Y-%m-%d %H:%M:%S %Z')}",
    )
    event.add("dtstart", item.sale_end_time - timedelta(hours=2))
    event.add("dtend", item.sale_end_time)
    event["uid"] = str(uuid.uuid4())

    # 30分钟前闹钟
    alarm = icalendar.Alarm()
    alarm.add("trigger", timedelta(minutes=-30))
    alarm.add("action", "DISPLAY")
    alarm.add("description", f"{item.gear_name} 还有30分钟截止!")
    event.add_component(alarm)
    events.append(event)

    # ── 事件2: 开售提醒(结束前24~22小时) ──
    event_before = icalendar.Event()
    event_before.add("summary", f"{translated_power}: {item.gear_name} 开始售卖!")
    event_before.add(
        "description",
        f"价格: {item.price} 鱿钞\n"
        f"截止时间: {local_end.strftime('%Y-%m-%d %H:%M:%S %Z')}",
    )
    event_before.add("dtstart", item.sale_end_time - timedelta(hours=24))
    event_before.add("dtend", item.sale_end_time - timedelta(hours=22))
    event_before["uid"] = str(uuid.uuid4())
    events.append(event_before)

    return events


def create_ics_file(items: list[GearItem], output_path: str) -> str:
    """生成 .ics 日历文件,返回写入路径."""
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Splatoon3 Gear Reminder//Nous//")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")

    for item in items:
        for ev in create_calendar_events(item):
            cal.add_component(ev)

    # 确保输出目录存在
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(cal.to_ical())

    logger.info("已生成日历文件: %s (%d 事件)", output_path, len(cal.subcomponents))
    return output_path


# ── 主流程 ──────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Splatoon 3 Gear Reminder — 生成装备售卖日历",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  %(prog)s                         # 默认输出到桌面\n"
            "  %(prog)s -o ./my_gear.ics        # 指定路径\n"
            "  %(prog)s --no-brand              # 只处理限时装备\n"
            "  %(prog)s -v                      # 详细日志\n"
        ),
    )
    parser.add_argument(
        "-o", "--output",
        default=DEFAULT_OUTPUT,
        help=f"输出 .ics 文件路径 (默认: ~/Desktop/splatoon3_gear_reminders.ics)",
    )
    parser.add_argument(
        "--no-brand",
        action="store_true",
        help="不处理品牌装备 (pickupBrand)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="输出更详细的日志",
    )
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # 1. 拉取数据
    gear_data = fetch_json(GEAR_API_URL, "装备数据")
    if gear_data is None:
        logger.error("无法获取装备数据,终止。")
        return

    locale_data = fetch_json(LOCALE_API_URL, "中文翻译")

    # 2. 筛选装备
    items = parse_gear_data(gear_data, locale_data, include_brand=not args.no_brand)

    # 3. 生成日历 (0 件时也生成空白日历,保证订阅 URL 始终可用)
    create_ics_file(items, args.output)
    count = len(items)

    # 4. 打印汇总
    print(f"\n{'🎯' if count else '📭'} 筛选到 {count} 件装备,已生成日历文件:")
    print(f"   {args.output}")
    print(f"   导入日历即可查看。\n")


if __name__ == "__main__":
    main()
