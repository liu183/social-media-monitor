"""主程序 - 社媒监控工作流入口"""

import os
import sys
import json
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from scripts.config import (
    load_accounts,
    get_feishu_webhook,
    get_feishu_app_credentials,
    get_feishu_bitable_info,
    get_feishu_chat_id,
)
from scripts.scraper import scrape_all_accounts
from scripts.feishu import (
    FeishuWebhook,
    FeishuBot,
    FeishuBitable,
    build_daily_summary,
    build_card_message,
    push_to_bitable,
    send_post_to_feishu,
)

# 数据目录
DATA_DIR = Path("data")
MEDIA_DIR = DATA_DIR / "media"
STATE_FILE = DATA_DIR / "state.json"


def load_state():
    """加载上次运行状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_run": None, "seen_files": {}}


def save_state(state):
    """保存运行状态"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def file_hash(filepath):
    """计算文件路径的哈希（用于去重）"""
    # 用文件名+大小作为简单去重 key
    name = os.path.basename(filepath)
    size = os.path.getsize(filepath)
    return hashlib.md5(f"{name}:{size}".encode()).hexdigest()


def filter_new_files(scrape_results, state):
    """过滤出新文件（未见过的）"""
    seen = state.get("seen_files", {})
    new_results = {}

    for key, data in scrape_results.items():
        new_files = []
        for f in data["files"]:
            fhash = file_hash(f["path"])
            if fhash not in seen:
                new_files.append(f)
                seen[fhash] = datetime.now().isoformat()

        if new_files:
            new_results[key] = {
                **data,
                "files": new_files,
                "new_count": len(new_files),
            }

    # 清理 30 天前的记录
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    seen = {k: v for k, v in seen.items() if v > cutoff}
    state["seen_files"] = seen

    return new_results


def prepare_entries_for_feishu(new_results):
    """将抓取结果转换为飞书推送格式"""
    entries = []

    for key, data in new_results.items():
        account = data["account"]
        files = data["files"]

        # 按帖子分组（通过元数据中的 post_id 或 URL）
        posts = {}
        for f in files:
            meta = f.get("metadata", {})
            post_id = meta.get("post_id") or meta.get("shortcode") or f["filename"].split("_")[0]
            if post_id not in posts:
                posts[post_id] = {
                    "id": post_id,
                    "platform": account["platform"],
                    "username": account["username"],
                    "account_name": account.get("name", account["username"]),
                    "title": (meta.get("description") or meta.get("content") or "")[:100],
                    "link": meta.get("post_url", meta.get("url", "")),
                    "published": meta.get("date", ""),
                    "images": [],
                    "videos": [],
                    "local_files": [],
                    "download_count": 0,
                    "has_media": True,
                }

            post = posts[post_id]
            if f["is_video"]:
                post["videos"].append(f["path"])
            else:
                post["images"].append(f["path"])
            post["local_files"].append(f["path"])
            post["download_count"] += 1

        entries.extend(posts.values())

    return entries


def run(dry_run=False, max_per_account=30):
    """主运行函数"""
    print(f"{'='*50}")
    print(f"社媒监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    # 加载配置
    accounts = load_accounts()
    if not accounts:
        print("[ERROR] 没有配置任何账号")
        return

    print(f"监控账号: {len(accounts)} 个")

    state = load_state()

    # ---- 第一步: 抓取媒体 ----
    print(f"\n{'='*50}")
    print("第一步: 抓取媒体内容")
    print(f"{'='*50}")

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print("[DRY RUN] 跳过实际抓取")
        scrape_results = {}
    else:
        scrape_results = scrape_all_accounts(
            accounts, str(MEDIA_DIR), max_per_account
        )

    # 统计
    total_files = sum(d["count"] for d in scrape_results.values())
    print(f"\n共抓取 {total_files} 个文件")

    # 过滤新文件
    new_results = filter_new_files(scrape_results, state)
    new_total = sum(d["new_count"] for d in new_results.values())
    print(f"新增文件: {new_total} 个")

    if not new_total:
        print("\n没有新内容，跳过推送")
        save_state(state)
        return

    # 转换为飞书格式
    entries = prepare_entries_for_feishu(new_results)

    # ---- 第二步: 推送到飞书 ----
    print(f"\n{'='*50}")
    print("第二步: 推送到飞书")
    print(f"{'='*50}")

    # 2.1 Webhook 群消息 - 每日摘要
    webhook_url = get_feishu_webhook()
    webhook = FeishuWebhook(webhook_url) if webhook_url else None

    if webhook:
        print("[Webhook] 发送每日摘要...")
        summary = build_daily_summary(entries)
        webhook.send_text(summary)
        time.sleep(1)
        card = build_card_message(entries)
        webhook.send_interactive(card)
        print("[Webhook] 摘要已发送")
    else:
        print("[Webhook] 未配置 FEISHU_WEBHOOK_URL，跳过")

    # 2.2 逐条发送帖子（图片+视频+说明+链接）
    creds = get_feishu_app_credentials()
    chat_id = get_feishu_chat_id()
    bot = None
    if creds["app_id"] and creds["app_secret"]:
        bot = FeishuBot(creds["app_id"], creds["app_secret"])
        print(f"[帖子] 逐条发送 {len(entries)} 个帖子到飞书群...")
        send_post_to_feishu(webhook, bot, chat_id, entries)
        print("[帖子] 发送完成")
    elif webhook:
        print("[帖子] 未配置飞书应用凭证，无法上传图片，仅发送文字")
        for entry in entries:
            text = f"@{entry.get('account_name', '')}: {entry.get('title', '')[:80]}"
            if entry.get("link"):
                text += f"\n{entry['link']}"
            webhook.send_text(text)
            time.sleep(0.5)
    else:
        print("[帖子] 未配置飞书凭证，跳过")

    # 2.3 多维表格归档
    bitable_info = get_feishu_bitable_info()
    if creds.get("app_id") and bitable_info.get("app_token") and bitable_info.get("table_id"):
        print("[Bitable] 写入多维表格...")
        bitable = FeishuBitable(
            creds["app_id"], creds["app_secret"],
            bitable_info["app_token"], bitable_info["table_id"]
        )
        push_to_bitable(bitable, entries)
        print("[Bitable] 完成")
    else:
        print("[Bitable] 未配置，跳过")

    # ---- 保存状态 ----
    state["last_run"] = datetime.now().isoformat()
    save_state(state)

    # ---- 统计 ----
    if MEDIA_DIR.exists():
        size = sum(f.stat().st_size for f in MEDIA_DIR.rglob("*") if f.is_file())
        print(f"\n媒体目录大小: {size / 1024 / 1024:.1f} MB")

    print(f"\n{'='*50}")
    print(f"完成! 新增 {new_total} 个文件，来自 {len(new_results)} 个账号")
    print(f"{'='*50}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    discover_mode = "--discover" in sys.argv
    max_items = 30
    max_pages = 3
    for arg in sys.argv:
        if arg.startswith("--max="):
            max_items = int(arg.split("=")[1])
        if arg.startswith("--pages="):
            max_pages = int(arg.split("=")[1])

    if discover_mode:
        from scripts.discover import discover_all, format_discovery_report
        from scripts.config import save_accounts

        accounts = load_accounts()
        print(f"当前配置 {len(accounts)} 个账号")
        print(f"{'='*50}")
        print("账号发现模式")
        print(f"{'='*50}")

        new_accounts = discover_all(accounts, max_pages_per_account=max_pages)

        if new_accounts:
            print(f"\n发现 {len(new_accounts)} 个新账号")
            print(format_discovery_report(new_accounts))

            added = save_accounts(new_accounts)
            print(f"\n已添加 {len(added)} 个新账号到 accounts.yaml")
        else:
            print("\n未发现新账号")
    else:
        run(dry_run=dry_run, max_per_account=max_items)
