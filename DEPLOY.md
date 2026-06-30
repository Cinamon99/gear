# 部署指南

## 📅 日历订阅 — 免费方案 (无需服务器)

利用 **GitHub Actions + GitHub Pages** 实现永久免费的自动日历订阅。

### 原理

```
GitHub Actions (每2小时)
  ↓ 自动运行脚本 → gear.ics
  ↓ 部署到 Pages
GitHub Pages CDN
  ↓ https://你的用户名.github.io/项目名/gear.ics
手机日历 ← 订阅这个 URL
```

### 配置步骤

#### 1. 推送到 GitHub

```bash
# 创建 GitHub 仓库(不要勾选 README/LICENSE/.gitignore)
# 然后在本地:
cd /Users/rose/Downloads/gear

# 替换为你的仓库地址
git init
git add .
git commit -m "init: splatoon3 gear reminder"
git branch -M main
git remote add origin https://github.com/你的用户名/gear.git
git push -u origin main
```

#### 2. 启用 GitHub Pages

1. 打开你的仓库 → **Settings** → **Pages**
2. **Source** 选择 **GitHub Actions**
3. 等待几分钟,让第一次 Action 跑完
4. 右上角会出现 Pages 的 URL: `https://你的用户名.github.io/gear/`

#### 3. 手机上订阅

日历订阅地址:

```
https://你的用户名.github.io/gear/gear.ics
```

**iOS**: 设置 → 日历 → 账户 → 添加订阅日历 → 粘贴 URL
**Android**: Google 日历 App → 右下角+ → 来自 URL 的日历
**macOS**: 日历 App → 文件 → 新建日历订阅

之后每 2 小时自动更新,完全免费无限期。

> 💡 **为什么免费?**
> GitHub Actions 免费额度: 每月 2000 分钟,这个工作流每次跑约 30 秒,一个月成本 ≈ 180 分钟,完全在免费额度内。Pages 带宽也是免费的。

---

## 🤖 QQ Bot — 需要服务器的方案

QQ Bot 需要 **24 小时在线** 连接 QQ 协议。你有以下选择:

### 方案 A: Oracle 云免费层 (推荐)

[Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/) 提供**永久免费**的 ARM 实例(4核 24GB RAM),跑 Lagrange + Bot 绰绰有余。

### 方案 B: 轻量云服务器

| 服务商 | 最低价格 | 说明 |
|--------|----------|------|
| 阿里云轻量 | ~24元/月 | 国内延迟低 |
| 腾讯云轻量 | ~30元/月 | 国内延迟低 |
| RackNerd | ~$10/年 | 国外,便宜 |

### Ubuntu 部署步骤

以下在一台全新的 Ubuntu 22.04/24.04 服务器上执行。

#### 1. 基础环境

```bash
# 更新 & 安装
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip nginx git curl wget unzip

# 安装 .NET 8 (Lagrange 需要)
wget https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh
chmod +x /tmp/dotnet-install.sh
/tmp/dotnet-install.sh --channel 8.0 --install-dir /usr/share/dotnet
ln -sf /usr/share/dotnet/dotnet /usr/local/bin/dotnet
dotnet --version  # 应 >= 8.0
```

#### 2. 上传项目 & 装依赖

```bash
# 从 GitHub 克隆
cd /opt
git clone https://github.com/你的用户名/gear.git
cd gear
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 验证脚本
python splatoon3_gear_reminders.py -v
```

#### 3. 配置 Nginx (提供 .ics 文件)

```bash
cat > /etc/nginx/sites-available/gear << 'EOF'
server {
    listen 80;
    server_name _;

    root /var/www/gear;
    location / {
        add_header Access-Control-Allow-Origin "*";
    }
    location ~ \.ics$ {
        add_header Content-Type text/calendar;
        add_header Cache-Control "no-cache, must-revalidate";
    }
}
EOF

ln -sf /etc/nginx/sites-available/gear /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
```

#### 4. 部署日历文件 (crontab)

```bash
mkdir -p /var/www/gear

# 每30分钟更新
crontab -l 2>/dev/null; echo "*/30 * * * * cd /opt/gear && /opt/gear/venv/bin/python splatoon3_gear_reminders.py -o /var/www/gear/gear.ics > /dev/null 2>&1" | crontab -
```

#### 5. 部署 QQ Bot

##### 5.1 下载 & 启动 Lagrange

```bash
cd /opt
# 去 GitHub Releases 找最新版:
# https://github.com/LagrangeDev/Lagrange.Core/releases
wget https://github.com/LagrangeDev/Lagrange.Core/releases/download/v0.8.2/Lagrange.OneBot_linux-x64.zip
unzip Lagrange.OneBot_linux-x64.zip -d lagrange
cd lagrange
chmod +x Lagrange.OneBot

# 首次启动 → 生成配置 → 扫码登录
./Lagrange.OneBot
# Ctrl+C 停止后,编辑 lagrange-config.json...
# 确认 ReverseWebSocket 端口 = 8080
```

##### 5.2 配置 Bot

```bash
cd /opt/gear
cp .env.prod .env
nano .env
```

填入:

```ini
ONEBOT_WS_URLS=["ws://127.0.0.1:8080/onebot"]
SUPERUSERS=["你的QQ号"]
GEAR_TARGET_GROUPS=["要推送的群号"]
GEAR_TARGET_USERS=[""]
GEAR_CHECK_INTERVAL=30
```

##### 5.3 systemd 服务

```bash
# Lagrange 服务
cat > /etc/systemd/system/lagrange.service << 'SERVICE'
[Unit]
Description=Lagrange OneBot
After=network.target
[Service]
Type=simple
WorkingDirectory=/opt/lagrange
ExecStart=/opt/lagrange/Lagrange.OneBot
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
SERVICE

# Bot 服务
cat > /etc/systemd/system/gear-bot.service << 'SERVICE'
[Unit]
Description=Splatoon3 Gear Bot
After=network.target lagrange.service
Wants=lagrange.service
[Service]
Type=simple
WorkingDirectory=/opt/gear
ExecStart=/opt/gear/venv/bin/python /opt/gear/bot/bot.py
Restart=always
RestartSec=10
Environment=NB_ENV=prod
[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable lagrange gear-bot
systemctl start lagrange gear-bot
```

##### 5.4 验证

```bash
# 查看日志
journalctl -u gear-bot -n 30 --no-pager

# 群里 @机器人 发「查装备」
```

---

## 🍎 macOS 本地自动更新 (无需 GitHub)

用 launchd 替代 crontab:

```bash
# 复制 plist (注意修改其中路径为你的实际路径)
cp .github/macos/com.splatoon3.gear.plist ~/Library/LaunchAgents/

# 加载
launchctl load ~/Library/LaunchAgents/com.splatoon3.gear.plist

# 查看日志
cat /tmp/splatoon3_gear.log

# 卸载
# launchctl unload ~/Library/LaunchAgents/com.splatoon3.gear.plist
```

---

## 常见问题

**Q: GitHub Actions 报错?**
- 检查 `https://github.com/你的用户名/gear/actions` 看运行日志
- 确认仓库 Settings → Pages 选了 "GitHub Actions"

**Q: 日历文件生成了但手机上不更新?**
- 手机日历订阅有缓存(通常 24h),手动删掉重新添加即可触发刷新
- 或去 GitHub Actions 手动运行一次 workflow 立即更新

**Q: 当前没有目标装备会怎样?**
- 脚本仍然生成有效的空日历文件,订阅不会断。等商店轮换到目标技能就会自动出现事件。

**Q: Lagrange 扫码登录不上?**
- 尝试设置签名服务器: `"SignServerUrl": "https://sign.lagrange.one"`
- 或使用最新版 Lagrange.Core
