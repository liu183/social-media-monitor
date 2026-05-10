# 社媒监控 - 自动抓取 X/Instagram 内容推送到飞书

每天自动抓取 X (Twitter) 和 Instagram 账号的最新照片、视频，汇总推送到飞书。

## 功能

- 🐦 支持 X (Twitter) 和 Instagram
- 📸 自动下载图片和视频
- 📊 飞书群消息推送（Webhook）
- 🤖 飞书机器人推送（Bot API）
- 📋 飞书多维表格归档（Bitable）
- 🔄 自动去重，只推送新内容

## 快速开始

### 1. Fork 仓库

将本仓库 Fork 到你的 GitHub 账号。

### 2. 配置飞书 Webhook（最简单，必填）

1. 打开飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人
2. 复制 Webhook 地址
3. 在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加：
   - `FEISHU_WEBHOOK_URL` = 你的 Webhook 地址

### 3. 配置监控账号

编辑 `config/accounts.yaml`，添加你要监控的账号：

```yaml
accounts:
  - platform: x
    username: "elonmusk"
    name: "Elon Musk"

  - platform: instagram
    username: "natgeo"
    name: "National Geographic"
```

### 4. 手动触发测试

进入 GitHub 仓库 → Actions → Daily Social Media Monitor → Run workflow

## 可选配置

### 飞书多维表格归档

1. 创建飞书多维表格
2. 创建飞书应用（需要 `bitable:app` 和 `im:message` 权限）
3. 添加 Secrets：
   - `FEISHU_APP_ID` = 应用 ID
   - `FEISHU_APP_SECRET` = 应用 Secret
   - `FEISHU_BITABLE_APP_TOKEN` = 多维表格 token（URL 中获取）
   - `FEISHU_BITABLE_TABLE_ID` = 数据表 ID
4. 运行 `python scripts/setup_feishu_bitable.py` 创建字段

### Instagram Cookie（提高抓取成功率）

1. 浏览器登录 Instagram
2. F12 → Application → Cookies，获取：
   - `sessionid`
   - `ds_user_id`
   - `csrftoken`
3. 添加到 GitHub Secrets

### X/Twitter Cookie（提高抓取成功率）

1. 浏览器登录 X
2. F12 → Application → Cookies，获取：
   - `auth_token`
   - `ct0`
3. 添加到 GitHub Secrets

### 自建 RSSHub（公共实例不稳定时）

```bash
# 方式1: Docker 本地运行
docker run -d -p 12000:12000 diygod/rsshub

# 方式2: 部署到 Railway（免费）
# 访问 https://railway.app 一键部署 RSSHub
```

添加 Secret: `RSSHUB_BASE_URL` = 你的实例地址

## 项目结构

```
social-media-monitor/
├── .github/workflows/daily.yml   # GitHub Actions 定时任务
├── config/
│   └── accounts.yaml             # 监控账号列表
├── scripts/
│   ├── main.py                   # 主程序入口
│   ├── config.py                 # 配置加载
│   ├── rss_fetcher.py            # RSS 源获取
│   ├── media_downloader.py       # 媒体下载
│   ├── feishu.py                 # 飞书推送
│   └── setup_feishu_bitable.py   # 多维表格初始化
├── data/                         # 运行时数据
│   ├── media/                    # 下载的媒体文件
│   └── state.json                # 运行状态（已处理的条目）
├── requirements.txt
└── README.md
```

## 飞书多维表格字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 平台 | 文本 | x 或 instagram |
| 账号 | 文本 | 用户名 |
| 账号名称 | 文本 | 显示名称 |
| 内容摘要 | 文本 | 帖子标题/描述 |
| 原文链接 | 超链接 | 原始帖子链接 |
| 发布时间 | 文本 | 帖子发布时间 |
| 图片数量 | 数字 | 包含的图片数 |
| 视频数量 | 数字 | 包含的视频数 |
| 下载文件数 | 数字 | 成功下载的文件数 |
| 抓取时间 | 文本 | 本次抓取时间 |
