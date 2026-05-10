"""从 X 帖子中提取 Instagram 账号"""

import os
import re
import time
import requests
from datetime import datetime


# X API 认证
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"


def get_auth_headers():
    """构建 X API 认证头"""
    auth_token = os.environ.get("X_AUTH_TOKEN", "")
    ct0 = os.environ.get("X_CT0", "")

    return {
        "authorization": f"Bearer {BEARER_TOKEN}",
        "x-csrf-token": ct0,
        "cookie": f"auth_token={auth_token}; ct0={ct0}",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }


def get_user_tweets(screen_name, count=50):
    """获取用户的最新推文"""
    headers = get_auth_headers()

    # 先获取用户 ID
    resp = requests.get(
        "https://x.com/i/api/1.1/users/show.json",
        headers=headers,
        params={"screen_name": screen_name},
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"  [错误] 获取用户信息失败: {resp.status_code}")
        return []

    user_id = resp.json().get("id_str")
    if not user_id:
        return []

    # 获取推文
    resp = requests.get(
        "https://x.com/i/api/1.1/statuses/user_timeline.json",
        headers=headers,
        params={
            "user_id": user_id,
            "count": count,
            "tweet_mode": "extended",
            "include_rts": "false",
        },
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"  [错误] 获取推文失败: {resp.status_code}")
        return []

    return resp.json()


def extract_ig_usernames(text):
    """从文本中提取 Instagram 用户名"""
    if not text:
        return []

    usernames = set()

    # 匹配 instagram.com/username 链接
    patterns = [
        r'instagram\.com/([a-zA-Z0-9_.]+)',
        r'instagr\.am/([a-zA-Z0-9_.]+)',
        r'ig\.me/([a-zA-Z0-9_.]+)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            # 过滤掉常见非用户名路径
            if m.lower() not in ('p', 'reel', 'stories', 'explore', 'accounts', 'direct', 'tv'):
                usernames.add(m)

    # 匹配 @username 格式（在 IG 相关上下文中）
    at_matches = re.findall(r'@([a-zA-Z0-9_.]+)', text)
    for m in at_matches:
        # 只在有 IG 相关关键词时才认为是 IG 用户名
        ig_keywords = ['instagram', 'ig', 'insta', 'ins', 'follow', '关注']
        text_lower = text.lower()
        if any(kw in text_lower for kw in ig_keywords):
            usernames.add(m)

    return list(usernames)


def extract_ig_from_source(source_account="my_ig_select", count=50):
    """从指定 X 账号的帖子中提取 IG 用户名"""
    print(f"[提取] 从 @{source_account} 的帖子中提取 IG 账号...")

    tweets = get_user_tweets(source_account, count)
    if not tweets:
        print("  [警告] 未获取到推文")
        return []

    all_usernames = set()
    for tweet in tweets:
        text = tweet.get("full_text") or tweet.get("text") or ""
        # 也检查展开的 URL
        entities = tweet.get("entities", {})
        for url in entities.get("urls", []):
            expanded = url.get("expanded_url", "")
            if "instagram.com" in expanded:
                text += " " + expanded

        usernames = extract_ig_usernames(text)
        all_usernames.update(usernames)

    print(f"  [完成] 从 {len(tweets)} 条推文中提取到 {len(all_usernames)} 个 IG 用户名")
    return list(all_usernames)


def get_ig_user_info(username):
    """获取 IG 用户信息（通过 web API）"""
    try:
        resp = requests.get(
            f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}",
            headers={
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "x-ig-app-id": "936619743392459",
                "cookie": f"sessionid={os.environ.get('IG_SESSION_ID', '')}",
            },
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json().get("data", {}).get("user", {})
            return {
                "username": username,
                "full_name": data.get("full_name", ""),
                "follower_count": data.get("edge_followed_by", {}).get("count", 0),
                "media_count": data.get("edge_owner_to_timeline_media", {}).get("count", 0),
                "is_private": data.get("is_private", False),
            }
    except Exception:
        pass

    return None


if __name__ == "__main__":
    from scripts.config import load_accounts, save_accounts

    # 提取 IG 用户名
    ig_usernames = extract_ig_from_source("my_ig_select", count=100)

    if not ig_usernames:
        print("未找到 IG 账号")
        exit(0)

    # 获取现有账号
    accounts = load_accounts()
    existing_usernames = {a["username"].lower() for a in accounts}

    # 过滤已存在的
    new_usernames = [u for u in ig_usernames if u.lower() not in existing_usernames]

    print(f"\n找到 {len(new_usernames)} 个新的 IG 账号")

    # 创建新账号条目
    new_accounts = []
    for username in new_usernames:
        new_accounts.append({
            "platform": "instagram",
            "username": username,
            "name": username,
        })

    if new_accounts:
        added = save_accounts(new_accounts)
        print(f"已添加 {len(added)} 个 IG 账号到 accounts.yaml")
    else:
        print("没有新账号需要添加")
