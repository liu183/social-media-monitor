"""飞书推送模块 - 支持 Webhook、Bot API、多维表格三种方式"""

import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path


class FeishuWebhook:
    """飞书群机器人 Webhook"""

    def __init__(self, webhook_url):
        self.url = webhook_url

    def send_text(self, text):
        """发送文本消息"""
        payload = {
            "msg_type": "text",
            "content": {"text": text}
        }
        return self._post(payload)

    def send_image(self, image_key):
        """发送图片消息"""
        payload = {
            "msg_type": "image",
            "content": {"image_key": image_key}
        }
        return self._post(payload)

    def send_rich_text(self, title, content_lines):
        """
        发送富文本消息（图文混排）
        content_lines: 列表，每行是一个列表，包含元素
        元素格式: {"tag": "text", "text": "..."} 或 {"tag": "a", "text": "...", "href": "..."}
                 或 {"tag": "img", "image_key": "..."}
        """
        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": content_lines
                    }
                }
            }
        }
        return self._post(payload)

    def send_interactive(self, card):
        """发送卡片消息"""
        payload = {
            "msg_type": "interactive",
            "card": card
        }
        return self._post(payload)

    def _post(self, payload):
        try:
            resp = requests.post(
                self.url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            data = resp.json()
            if data.get("code") == 0 or data.get("StatusCode") == 0:
                return True
            print(f"  [WARN] Webhook 发送失败: {data}")
            return False
        except Exception as e:
            print(f"  [ERROR] Webhook 请求异常: {e}")
            return False


class FeishuBot:
    """飞书应用机器人（需要 App ID 和 App Secret）"""

    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token = None
        self._token_expire = 0

    def get_tenant_access_token(self):
        """获取 tenant_access_token"""
        if self._token and time.time() < self._token_expire:
            return self._token

        resp = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={
                "app_id": self.app_id,
                "app_secret": self.app_secret
            },
            timeout=10
        )
        data = resp.json()
        if data.get("code") == 0:
            self._token = data["tenant_access_token"]
            self._token_expire = time.time() + data.get("expire", 7200) - 300
            return self._token
        print(f"  [ERROR] 获取 token 失败: {data}")
        return None

    def send_to_chat(self, chat_id, msg_type, content):
        """发送消息到群聊"""
        token = self.get_tenant_access_token()
        if not token:
            return False

        resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "receive_id": chat_id,
                "msg_type": msg_type,
                "content": json.dumps(content)
            },
            timeout=10
        )
        data = resp.json()
        if data.get("code") == 0:
            return True
        print(f"  [WARN] Bot 发送失败: {data}")
        return False

    def upload_image(self, image_path):
        """上传图片到飞书，返回 image_key"""
        token = self.get_tenant_access_token()
        if not token:
            return None

        with open(image_path, "rb") as f:
            resp = requests.post(
                "https://open.feishu.cn/open-apis/im/v1/images",
                headers={"Authorization": f"Bearer {token}"},
                data={"image_type": "message"},
                files={"image": f},
                timeout=30
            )
        data = resp.json()
        if data.get("code") == 0:
            return data["data"]["image_key"]
        print(f"  [WARN] 图片上传失败: {data}")
        return None


class FeishuBitable:
    """飞书多维表格"""

    def __init__(self, app_id, app_secret, app_token, table_id):
        self.bot = FeishuBot(app_id, app_secret)
        self.app_token = app_token
        self.table_id = table_id

    def add_record(self, fields):
        """添加一条记录"""
        token = self.bot.get_tenant_access_token()
        if not token:
            return False

        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={"fields": fields},
            timeout=10
        )
        data = resp.json()
        if data.get("code") == 0:
            return True
        print(f"  [WARN] Bitable 写入失败: {data}")
        return False

    def add_records_batch(self, records):
        """批量添加记录（最多 500 条）"""
        token = self.bot.get_tenant_access_token()
        if not token:
            return False

        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/batch_create"
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={"records": [{"fields": r} for r in records]},
            timeout=30
        )
        data = resp.json()
        if data.get("code") == 0:
            return True
        print(f"  [WARN] Bitable 批量写入失败: {data}")
        return False


def build_daily_summary(entries):
    """构建每日摘要文本（用于 Webhook）"""
    if not entries:
        return "今日暂无新内容更新"

    # 按平台和账号分组
    by_account = {}
    for e in entries:
        key = f"{e.get('account_name', e.get('username'))} ({e.get('platform')})"
        if key not in by_account:
            by_account[key] = []
        by_account[key].append(e)

    lines = [
        f"📸 社媒更新日报 - {datetime.now().strftime('%Y-%m-%d')}",
        f"共 {len(entries)} 条更新，来自 {len(by_account)} 个账号",
        ""
    ]

    for account, items in by_account.items():
        media_items = [i for i in items if i.get("has_media")]
        lines.append(f"▎{account}: {len(items)} 条 (含媒体 {len(media_items)} 条)")
        for item in items[:3]:  # 每个账号最多显示 3 条
            title = item.get("title", "")[:50]
            link = item.get("link", "")
            media_info = ""
            if item.get("download_count"):
                media_info = f" [{item['download_count']}个文件]"
            lines.append(f"  • {title}{media_info}")
            if link:
                lines.append(f"    {link}")
        if len(items) > 3:
            lines.append(f"  ... 还有 {len(items) - 3} 条")
        lines.append("")

    return "\n".join(lines)


def build_card_message(entries, title="社媒更新"):
    """构建飞书卡片消息"""
    elements = []

    # 统计信息
    total = len(entries)
    accounts = len(set(e.get("username") for e in entries))
    media_count = sum(e.get("download_count", 0) for e in entries)

    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"📊 **{total}** 条更新 | **{accounts}** 个账号 | **{media_count}** 个媒体文件"
        }
    })
    elements.append({"tag": "hr"})

    # 按账号分组展示
    by_account = {}
    for e in entries:
        key = e.get("account_name", e.get("username"))
        if key not in by_account:
            by_account[key] = []
        by_account[key].append(e)

    for account, items in list(by_account.items())[:10]:  # 最多显示 10 个账号
        platform_icon = "🐦" if items[0].get("platform") == "x" else "📷"
        content = f"{platform_icon} **{account}** ({len(items)} 条)\n"
        for item in items[:2]:
            title_text = item.get("title", "")[:40]
            link = item.get("link", "")
            if link:
                content += f"• [{title_text}]({link})\n"
            else:
                content += f"• {title_text}\n"

        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": content.strip()
            }
        })

    card = {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": title
            },
            "template": "blue"
        },
        "elements": elements
    }

    return card


def push_to_bitable(bitable, entries):
    """将更新推送到多维表格"""
    if not entries:
        return

    records = []
    for entry in entries:
        fields = {
            "平台": entry.get("platform", ""),
            "账号": entry.get("username", ""),
            "账号名称": entry.get("account_name", ""),
            "内容摘要": entry.get("title", "")[:200],
            "原文链接": {"link": entry.get("link", ""), "text": "查看"},
            "发布时间": entry.get("published", ""),
            "图片数量": len(entry.get("images", [])),
            "视频数量": len(entry.get("videos", [])),
            "下载文件数": entry.get("download_count", 0),
            "抓取时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        records.append(fields)

    # 分批写入，每批最多 500 条
    for i in range(0, len(records), 500):
        batch = records[i:i+500]
        bitable.add_records_batch(batch)
        time.sleep(1)  # 避免频率限制


def send_post_to_feishu(webhook, bot, entries, max_images_per_post=9):
    """
    将每个帖子作为富文本消息发送到飞书群
    包含：帖子说明 + 图片 + 原文链接 + 视频链接
    """
    if not entries:
        return

    for entry in entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        account_name = entry.get("account_name", entry.get("username", ""))
        platform = entry.get("platform", "")
        images = entry.get("local_files", [])
        videos = entry.get("videos", [])
        image_files = [f for f in images if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))]
        video_files = [f for f in images if f.lower().endswith((".mp4", ".webm", ".mkv", ".mov"))]

        # 构建富文本内容
        content_lines = []

        # 第一行：账号信息和说明
        header_parts = []
        if platform == "x":
            header_parts.append(f"🐦 @{account_name}")
        else:
            header_parts.append(f"📷 @{account_name}")

        if title:
            header_parts.append(title)

        content_lines.append([{"tag": "text", "text": " | ".join(header_parts)}])

        # 上传图片并添加到富文本
        if bot and image_files:
            img_keys = []
            for img_path in image_files[:max_images_per_post]:
                image_key = bot.upload_image(img_path)
                if image_key:
                    img_keys.append(image_key)
                time.sleep(0.3)

            if img_keys:
                img_line = []
                for key in img_keys:
                    img_line.append({"tag": "img", "image_key": key})
                content_lines.append(img_line)

        # 原文链接
        if link:
            content_lines.append([
                {"tag": "text", "text": "🔗 "},
                {"tag": "a", "text": "查看原文", "href": link}
            ])

        # 视频链接
        if video_files:
            content_lines.append([{"tag": "text", "text": f"🎬 包含 {len(video_files)} 个视频"}])
            for vf in video_files[:3]:
                fname = os.path.basename(vf)
                content_lines.append([{"tag": "text", "text": f"  📹 {fname}"}])

        # 发送富文本
        post_title = f"@{account_name}"
        webhook.send_rich_text(post_title, content_lines)
        time.sleep(1)  # 避免频率限制
