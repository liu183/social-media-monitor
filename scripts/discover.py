"""账号发现模块 - 从已配置账号的关注列表中自动发现新账号"""

import os
import time
import requests
from datetime import datetime


# X API 认证头
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

# 越南女性名字特征
FEMALE_NAME_KEYWORDS = {
    # 越南语女性标识
    "thị", "cô", "chị", "em", "gái", "nữ",
    # 英语/通用
    "girl", "woman", "female", "queen", "princess", "angel", "babe", "baby",
    "hotgirl", "hot girl", "cosgirl", "cos girl",
}

FEMALE_NAMES_VN = {
    "linh", "hoa", "mai", "lan", "hương", "trang", "ngọc", "hạnh", "oanh",
    "tuyết", "thảo", "ngân", "hằng", "dung", "yến", "nhung", "phương", "hà",
    "lệ", "thu", "xuân", "diệu", "hiền", "hồng", "kim", "thanh", "tâm",
    "anh", "chi", "giang", "khánh", "minh", "nga", "phượng", "quỳnh", "trâm",
    "vân", "bích", "cúc", "đào", "huệ", "lien", "như", "sương", "thúy",
    "tuyền", "uyên", "vy", "nhã", "khanh", "my", "ly", "na", "tâm",
    "tiên", "nguyệt", "mỹ", "hậu", "gấm", "đan", "kỳ", "bình", "ân",
    "hiếu", "nhi", "nhí", "bé", "xinh", "đẹp", "dễ thương",
}


def get_auth_headers():
    """构建 X API 认证头"""
    auth_token = os.environ.get("X_AUTH_TOKEN", "")
    ct0 = os.environ.get("X_CT0", "")

    return {
        "authorization": f"Bearer {BEARER_TOKEN}",
        "x-csrf-token": ct0,
        "cookie": f"auth_token={auth_token}; ct0={ct0}",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
    }


def get_following_list(screen_name, cursor=None, count=200):
    """获取指定用户的关注列表"""
    headers = get_auth_headers()
    params = {
        "screen_name": screen_name,
        "count": count,
        "skip_status": "true",
        "include_user_entities": "false",
    }
    if cursor:
        params["cursor"] = cursor

    try:
        resp = requests.get(
            "https://x.com/i/api/1.1/friends/list.json",
            headers=headers,
            params=params,
            timeout=30,
        )

        if resp.status_code == 429:
            # Rate limit
            reset_time = int(resp.headers.get("x-rate-limit-reset", 0))
            wait = max(reset_time - int(time.time()), 60)
            print(f"  [限流] 等待 {wait} 秒...")
            time.sleep(wait)
            return get_following_list(screen_name, cursor, count)

        if resp.status_code != 200:
            print(f"  [错误] API 返回 {resp.status_code}: {resp.text[:200]}")
            return [], None

        data = resp.json()
        users = data.get("users", [])
        next_cursor = data.get("next_cursor_str")

        return users, next_cursor

    except Exception as e:
        print(f"  [错误] 请求失败: {e}")
        return [], None


def is_likely_female(user):
    """猜测用户是否为女性"""
    name = (user.get("name") or "").lower()
    description = (user.get("description") or "").lower()
    screen_name = (user.get("screen_name") or "").lower()

    # 检查名字中的女性标识
    for keyword in FEMALE_NAME_KEYWORDS:
        if keyword in name or keyword in description:
            return True

    # 检查越南女性名字
    name_parts = name.split()
    for part in name_parts:
        if part in FEMALE_NAMES_VN:
            return True

    # 检查 bio 中的女性相关词
    female_bio_indicators = [
        "cosplay", "model", "hot", "sexy", "cute", "xinh", "đẹp",
        "gái", "nữ", "cô", "chị", "em gái", "hotgirl",
    ]
    for indicator in female_bio_indicators:
        if indicator in description:
            return True

    return False


def filter_user(user, min_followers=1000, min_statuses=500):
    """筛选符合条件的用户"""
    # 基本条件
    followers = user.get("followers_count", 0)
    statuses = user.get("statuses_count", 0)
    following = user.get("friends_count", 0)

    # 粉丝数筛选
    if followers < min_followers:
        return False

    # 媒体数筛选（用推文数代理）
    if statuses < min_statuses:
        return False

    # 跳过已认证账号（通常是公众人物/品牌）
    if user.get("verified", False):
        return False

    # 跳过保护账号
    if user.get("protected", False):
        return False

    # 性别筛选
    if not is_likely_female(user):
        return False

    return True


def discover_from_account(account, existing_usernames, max_pages=5):
    """从单个账号的关注列表中发现新账号"""
    username = account["username"]
    name = account.get("name", username)

    print(f"\n[发现] 扫描 @{name} 的关注列表...")

    new_accounts = []
    cursor = None
    page = 0
    total_checked = 0

    while page < max_pages:
        users, next_cursor = get_following_list(username, cursor)

        if not users:
            break

        for user in users:
            total_checked += 1
            screen_name = user.get("screen_name", "")

            # 跳过已存在的账号
            if screen_name.lower() in existing_usernames:
                continue

            if filter_user(user):
                new_accounts.append({
                    "platform": "x",
                    "username": screen_name,
                    "name": user.get("name", screen_name),
                    "discovered_from": username,
                    "discovered_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "followers": user.get("followers_count", 0),
                    "statuses": user.get("statuses_count", 0),
                })
                print(f"  [新发现] @{screen_name} - 粉丝: {user.get('followers_count', 0)}, 推文: {user.get('statuses_count', 0)}")

        page += 1
        cursor = next_cursor

        if not cursor or cursor == "0":
            break

        time.sleep(2)  # 请求间隔

    print(f"  [完成] 检查了 {total_checked} 个账号，发现 {len(new_accounts)} 个新账号")
    return new_accounts


def discover_all(accounts, max_pages_per_account=5):
    """从所有已配置账号的关注列表中发现新账号"""
    # 收集已存在的用户名
    existing_usernames = {a["username"].lower() for a in accounts}

    all_new = []
    seen_in_this_run = set()

    for i, account in enumerate(accounts):
        if account.get("platform") != "x":
            continue

        new_accounts = discover_from_account(
            account, existing_usernames | seen_in_this_run, max_pages_per_account
        )

        for acc in new_accounts:
            if acc["username"].lower() not in seen_in_this_run:
                all_new.append(acc)
                seen_in_this_run.add(acc["username"].lower())

        # 每处理 5 个账号休息一下
        if (i + 1) % 5 == 0:
            print(f"\n[休息] 已处理 {i + 1} 个账号，暂停 30 秒...")
            time.sleep(30)
        else:
            time.sleep(3)

    return all_new


def format_discovery_report(new_accounts):
    """生成发现报告"""
    if not new_accounts:
        return "未发现新账号"

    lines = [
        f"🔍 账号发现报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"共发现 {len(new_accounts)} 个新账号",
        "",
    ]

    # 按粉丝数排序
    sorted_accounts = sorted(new_accounts, key=lambda x: x.get("followers", 0), reverse=True)

    for acc in sorted_accounts[:50]:  # 最多显示 50 个
        lines.append(
            f"@{acc['username']} ({acc['name']}) - "
            f"粉丝: {acc.get('followers', 0):,} - "
            f"来源: @{acc.get('discovered_from', '?')}"
        )

    if len(new_accounts) > 50:
        lines.append(f"... 还有 {len(new_accounts) - 50} 个")

    return "\n".join(lines)


if __name__ == "__main__":
    from scripts.config import load_accounts, save_accounts

    accounts = load_accounts()
    print(f"当前配置 {len(accounts)} 个账号")

    new_accounts = discover_all(accounts, max_pages_per_account=3)

    if new_accounts:
        print(f"\n发现 {len(new_accounts)} 个新账号")
        print(format_discovery_report(new_accounts))

        # 保存到配置
        save_accounts(new_accounts)
        print(f"\n已添加到 accounts.yaml")
    else:
        print("\n未发现新账号")
