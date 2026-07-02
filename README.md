# Splatoon 3 Gear Reminder 🦑🎮

[![CI](https://github.com/Cinamon99/gear/actions/workflows/gear-update.yml/badge.svg)](https://github.com/你的用户名/gear/actions/workflows/gear-update.yml)

> Splatoon 3 装备售卖日历生成器 + QQ Bot 推送

自动从 [splatoon3.ink](https://splatoon3.ink) 拉取装备商店数据,筛选出**回归头/隐跳鞋/终场冲刺/走速衣/游速衣**这些有用的技能装备,生成日历文件供手机导入,或通过 QQ Bot 实时推送。

---

## ✨ 功能

- **日历订阅** — 自动生成 `.ics` 文件,手机日历导入即可查看截止时间
- **双重提醒** — 每件装备生成 2 个日历事件:开售提醒(提前 24h) + 截止提醒(提前 2h,带 30min 闹钟)
- **中文支持** — 装备名自动翻译为中文
- **QQ Bot** — 定时检查装备店,发现目标装备自动推送通知到 QQ 群
- **手动查询** — 在群里 `@bot 查装备` 即刻查看当前在售列表

## 🎯 关注的技能

| 技能 | 部位限制 | 游戏内简称 |
|------|----------|-----------|
| Comeback | 全品类 | 回归头 |
| Stealth Jump | 全品类 | 隐跳鞋 |
| Last-Ditch Effort | 全品类 | 终场冲刺 |
| Run Speed Up | 🧥 仅衣服 | 走速 |
| Swim Speed Up | 🧥 仅衣服 | 游速 |

## 🚀 快速开始

### 本地生成日历

```bash
# 1. 安装
git clone https://github.com/Cinamon99/gear.git
cd gear
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. 生成
python splatoon3_gear_reminders.py
# → 输出 gear.ics,导入手机日历即可
```

### macOS 定时自动更新

想自动更新?用 launchd:

```bash
# 拷贝 plist 并修改路径
cp .github/macos/com.splatoon3.gear.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.splatoon3.gear.plist
```

### 手机上订阅日历(永久免费,无需服务器)

这个项目自带 **GitHub Actions 工作流**,每 2 小时自动运行脚本并把 `.ics` 文件部署到 **GitHub Pages**(免费 CDN)。

**配置方法:**

1. **Fork/推送** 这个仓库到你的 GitHub
2. 去仓库 Settings → **Pages**,Source 选 **GitHub Actions**
3. 等几分钟让第一次 Action 跑完
4. 手机日历添加订阅:
   ```
   https://<你的GitHub用户名>.github.io/gear/gear.ics
   ```
   - **iOS**: 设置 → 日历 → 账户 → 添加订阅日历
   - **Android**: Google 日历 → 添加 → 来自 URL 的日历
   - **macOS**: 日历 → 文件 → 新建日历订阅

之后每 2 小时自动更新,完全免费。

### QQ Bot 部署 （尚未测试）

需要一台 24h 在线的服务器(或 Oracle 免费云等)。详见 [DEPLOY.md](DEPLOY.md)。

## 📁 项目结构

```
gear/
├── splatoon3_gear_reminders.py  # 🧠 核心模块
├── bot/                         # 🤖 QQ Bot
│   ├── bot.py                   #    启动入口
│   └── plugins/
│       ├── gear_check.py        #    定时检查 + 推送
│       └── commands.py          #    手动查询指令
├── .github/workflows/
│   └── gear-update.yml          # ⏰ 自动生成日历 (GitHub Actions)
├── DEPLOY.md                    # 📖 部署指南
├── requirements.txt
└── LICENSE                      # MIT
```

## 🛠 技术栈

- **Python 3.9+** — 核心逻辑
- **NoneBot2** — QQ Bot 框架
- **GitHub Actions + Pages** — 免费日历托管
- **Lagrange.Core** — QQ 协议实现

## 🙏 鸣谢 & 数据来源

本项目所有装备数据均来自 **[Splatoon3.ink](https://splatoon3.ink)**，感谢 [Matt Isenhower](https://github.com/misenhower) 提供高质量、稳定更新的 API。

使用此数据请遵守 [Data Access 政策](https://github.com/misenhower/splatoon3.ink/wiki/Data-Access)：

- 请求间隔不少于每小时 1 次，鼓励缓存
- 公众项目需注明数据来源
- 基于此数据的产品须免费提供

本项目 Actions 每 2 小时请求一次，请求头已设置 User-Agent 以便联系。

## 📜 许可

MIT
