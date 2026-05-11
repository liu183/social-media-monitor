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


def build_gallery_dl_config(platform, cookies, archive_path=None):
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

    # 使用 archive 模式记录已下载的 URL，避免重复下载
    if archive_path:
        if platform == "x":
            config["extractor"]["twitter"]["archive"] = archive_path
        elif platform == "instagram":
            config["extractor"]["instagram"]["archive"] = archive_path

    if cookies:
        if platform == "x":
            config["extractor"]["twitter"]["cookies"] = cookies
        elif platform == "instagram":
            config["extractor"]["instagram"]["cookies"] = cookies

    return config


def scrape_videos_with_ytdlp(username, platform, output_dir, cookies=None, max_items=15):
    """使用 yt-dlp 下载视频"""
    if platform != "x":
        return []  # 目前只支持 X

    url = f"https://x.com/{username}"
    video_dir = os.path.join(output_dir, "videos", username)
    os.makedirs(video_dir, exist_ok=True)

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-overwrites",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", os.path.join(video_dir, "%(id)s.%(ext)s"),
        "--max-downloads", str(max_items),
        "--match-filter", "duration>0",  # 只下载有视频的
        url
    ]

    # 添加 cookies
    if cookies:
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        cmd.extend(["--cookies-from-browser", "chrome"])  # 备用
        # 写入 cookie 文件
        cookie_file = os.path.join(output_dir, f".cookies-{username}.txt")
        with open(cookie_file, "w") as f:
            f.write(f".x.com\tTRUE\t/\tFALSE\t0\tauth_token\t{cookies.get('auth_token', '')}\n")
            f.write(f".x.com\tTRUE\t/\tFALSE\t0\tct0\t{cookies.get('ct0', '')}\n")
        cmd.extend(["--cookies", cookie_file])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        # 扫描下载的视频文件
        videos = []
        if os.path.exists(video_dir):
            for f in os.listdir(video_dir):
                if f.lower().endswith((".mp4", ".webm", ".mkv", ".mov")):
                    fpath = os.path.join(video_dir, f)
                    videos.append({
                        "path": fpath,
                        "filename": f,
                        "ext": os.path.splitext(f)[1].lower(),
                        "size": os.path.getsize(fpath),
                        "is_video": True,
                        "metadata": {"source": "yt-dlp"},
                    })
        return videos
    except subprocess.TimeoutExpired:
        print(f"  [WARN] yt-dlp 视频下载超时")
        return []
    except FileNotFoundError:
        print(f"  [WARN] yt-dlp 未安装")
        return []
    finally:
        cookie_file = os.path.join(output_dir, f".cookies-{username}.txt")
        if os.path.exists(cookie_file):
            os.remove(cookie_file)


def scrape_user_media(username, platform, output_dir, max_items=30, cookies=None, archive_dir=None):
    """
    使用 gallery-dl 抓取用户媒体

    返回: list of dict，每个 dict 包含文件信息
    """
    url = f"https://x.com/{username}" if platform == "x" else f"https://www.instagram.com/{username}/"
    os.makedirs(output_dir, exist_ok=True)
    user_dir = os.path.join(output_dir, platform, username)
    os.makedirs(user_dir, exist_ok=True)

    print(f"  [抓取] {url}")

    # archive 文件记录已下载的 URL hash，避免重复下载
    archive_path = None
    if archive_dir:
        os.makedirs(archive_dir, exist_ok=True)
        archive_path = os.path.join(archive_dir, f"{platform}_{username}.db")

    # 构建配置，写入临时文件
    config = build_gallery_dl_config(platform, cookies, archive_path)
    conf_fd, conf_path = tempfile.mkstemp(suffix=".json", prefix=f"gdl-{platform}-")
    try:
        with os.fdopen(conf_fd, "w") as f:
            json.dump(config, f)
    except:
        os.close(conf_fd)
        raise

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
            timeout=90,
        )

        if result.returncode == 0:
            # 扫描下载的文件
            downloaded = scan_downloaded_files(user_dir)
            print(f"  [完成] 下载 {len(downloaded)} 个文件")

            # 对 X 账号额外用 yt-dlp 下载视频
            if platform == "x" and cookies:
                print(f"  [视频] 用 yt-dlp 下载视频...")
                videos = scrape_videos_with_ytdlp(username, platform, output_dir, cookies)
                if videos:
                    downloaded.extend(videos)
                    print(f"  [视频] 额外下载 {len(videos)} 个视频")

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


def scrape_all_accounts(accounts, base_dir, max_per_account=30, state=None):
    """抓取所有账号的媒体"""
    all_results = {}
    archive_dir = os.path.join(os.path.dirname(base_dir), "archive")

    # 增量模式：跳过今天已成功抓取的账号
    last_scraped = {}
    if state:
        last_scraped = state.get("last_scraped", {})
        today = datetime.now().strftime("%Y-%m-%d")
        skipped = 0
        for account in accounts:
            key = f"{account['platform']}:{account['username']}"
            if last_scraped.get(key, {}).get("date") == today:
                skipped += 1
        if skipped:
            print(f"[增量] 跳过今天已抓取的 {skipped} 个账号")

    for account in accounts:
        platform = account["platform"]
        username = account["username"]
        name = account.get("name", username)
        key = f"{platform}:{username}"

        # 增量模式：跳过今天已抓取的账号
        if last_scraped.get(key, {}).get("date") == datetime.now().strftime("%Y-%m-%d"):
            continue

        print(f"\n[账号] {name} ({platform}: @{username})")

        cookies = get_cookies(platform)
        if not cookies:
            if platform == "instagram":
                print(f"  [跳过] Instagram 需要 cookies，未配置")
                continue
            print(f"  [警告] 未配置 {platform} cookies，可能无法获取内容")

        files = scrape_user_media(
            username=username,
            platform=platform,
            output_dir=base_dir,
            max_items=max_per_account,
            cookies=cookies,
            archive_dir=archive_dir,
        )

        all_results[f"{platform}:{username}"] = {
            "account": account,
            "files": files,
            "count": len(files),
        }

        # 记录抓取时间
        if state is not None:
            if "last_scraped" not in state:
                state["last_scraped"] = {}
            state["last_scraped"][key] = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "count": len(files),
            }

    return all_results
