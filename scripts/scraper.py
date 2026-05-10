"""直接抓取模块 - 使用 gallery-dl 从 X/Instagram 抓取媒体"""

import os
import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime


def get_cookies(platform):
    """从环境变量获取 cookies"""
    if platform == "x":
        auth_token = os.environ.get("X_AUTH_TOKEN", "")
        ct0 = os.environ.get("X_CT0", "")
        if auth_token and ct0:
            return {"auth_token": auth_token, "ct0": ct0}
    elif platform == "instagram":
        sessionid = os.environ.get("IG_SESSION_ID", "")
        if sessionid:
            return {
                "sessionid": sessionid,
                "ds_user_id": os.environ.get("IG_DS_USER_ID", ""),
                "csrftoken": os.environ.get("IG_CSRFTOKEN", ""),
            }
    return None


def build_gallery_dl_config(platform, cookies):
    """构建 gallery-dl 临时配置文件"""
    config = {
        "extractor": {
            "twitter": {
                "cards": True,
                "conversations": False,
                "expand": False,
                "fallback": True,
                "include": ["timeline"],
                "likes": False,
                "logout": False,
                "pinned": False,
                "quoted": True,
                "replies": True,
                "retweets": False,
                "text-tweets": False,
                "twitpic": False,
                "unique": True,
                "users": "user",
                "videos": True,
            } if platform == "x" else {},
            "instagram": {
                "archive": None,
                "include": "posts",
                "videos": True,
                "unique": True,
            } if platform == "instagram" else {},
        },
        "output": {
            "mode": "terminal",
            "progress": False,
            "log": {"level": "error"},
        },
    }

    if cookies:
        if platform == "x":
            config["extractor"]["twitter"]["cookies"] = cookies
        elif platform == "instagram":
            config["extractor"]["instagram"]["cookies"] = cookies

    return config


def scrape_user_media(username, platform, output_dir, max_items=30, cookies=None):
    """
    使用 gallery-dl 抓取用户媒体

    返回: list of dict，每个 dict 包含文件信息
    """
    url = f"https://x.com/{username}" if platform == "x" else f"https://www.instagram.com/{username}/"
    os.makedirs(output_dir, exist_ok=True)
    user_dir = os.path.join(output_dir, platform, username)
    os.makedirs(user_dir, exist_ok=True)

    print(f"  [抓取] {url}")

    # 构建配置
    config = build_gallery_dl_config(platform, cookies)

    # 写入临时配置文件
    conf_path = os.path.join(output_dir, f".gdl-{platform}-{username}.json")
    with open(conf_path, "w") as f:
        json.dump(config, f)

    # 构建命令
    cmd = [
        "gallery-dl",
        "--config", conf_path,
        "--range", f"1-{max_items}",
        "-d", user_dir,
        "--no-mtime",
        "--write-metadata",  # 写入元数据 JSON
        url
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,  # 3 分钟超时
            cwd=output_dir,
        )

        if result.returncode == 0:
            # 扫描下载的文件
            downloaded = scan_downloaded_files(user_dir)
            print(f"  [完成] 下载 {len(downloaded)} 个文件")
            return downloaded
        else:
            stderr = result.stderr[:500] if result.stderr else ""
            stdout = result.stdout[:500] if result.stdout else ""
            print(f"  [失败] gallery-dl 返回码 {result.returncode}")
            if stderr:
                print(f"  stderr: {stderr}")
            if stdout:
                print(f"  stdout: {stdout}")
            return []

    except subprocess.TimeoutExpired:
        print(f"  [超时] {username} 抓取超时")
        return []
    except FileNotFoundError:
        print(f"  [错误] gallery-dl 未安装")
        return []
    finally:
        # 清理临时配置
        if os.path.exists(conf_path):
            os.remove(conf_path)


def scan_downloaded_files(directory):
    """扫描目录，返回所有媒体文件和对应的元数据"""
    media_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm", ".mkv", ".mov"}
    results = []

    for root, dirs, files in os.walk(directory):
        for fname in files:
            fpath = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()

            if ext in media_exts:
                # 查找对应的元数据文件
                meta_path = fpath + ".json"
                metadata = {}
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                    except:
                        pass

                results.append({
                    "path": fpath,
                    "filename": fname,
                    "ext": ext,
                    "size": os.path.getsize(fpath),
                    "is_video": ext in {".mp4", ".webm", ".mkv", ".mov"},
                    "metadata": metadata,
                })

    return results


def scrape_all_accounts(accounts, base_dir, max_per_account=30):
    """抓取所有账号的媒体"""
    all_results = {}

    for account in accounts:
        platform = account["platform"]
        username = account["username"]
        name = account.get("name", username)

        print(f"\n[账号] {name} ({platform}: @{username})")

        cookies = get_cookies(platform)
        if not cookies:
            print(f"  [警告] 未配置 {platform} cookies，可能无法获取内容")

        files = scrape_user_media(
            username=username,
            platform=platform,
            output_dir=base_dir,
            max_items=max_per_account,
            cookies=cookies,
        )

        all_results[f"{platform}:{username}"] = {
            "account": account,
            "files": files,
            "count": len(files),
        }

    return all_results
