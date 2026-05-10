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
    """获取用户的最新推文（使用 GraphQL API）"""
    headers = get_auth_headers()

    # 先获取用户 rest_id
    query_id = "G3KGOASz96M-Qu0nwmGXNg"  # UserByScreenName
    variables = f'{{"screen_name":"{screen_name}","withSafetyModeUserFields":true}}'
    features = '{"hidden_profile_subscriptions_enabled":true,"rweb_tipjar_consumption_enabled":true,"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"subscriptions_verification_info_is_identity_verified_enabled":true,"subscriptions_verification_info_verified_since_enabled":true,"highlights_tweets_tab_ui_enabled":true,"responsive_web_twitter_article_notes_tab_enabled":true,"subscriptions_feature_can_gift_premium":true,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"responsive_web_graphql_timeline_navigation_enabled":true}'

    resp = requests.get(
        f"https://x.com/i/api/graphql/{query_id}/UserByScreenName",
        headers=headers,
        params={"variables": variables, "features": features},
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"  [错误] 获取用户信息失败: {resp.status_code}")
        return []

    user_data = resp.json().get("data", {}).get("user", {}).get("result", {})
    user_id = user_data.get("rest_id")
    if not user_id:
        print(f"  [错误] 无法获取用户 ID")
        return []

    # 获取推文（使用 UserTweets GraphQL）
    tweets_query_id = "E3opETHurmVJflFsUBVuUQ"  # UserTweets
    tweets_variables = f'{{"userId":"{user_id}","count":{count},"includePromotedContent":true,"withQuickPromoteEligibilityTweetFields":true,"withVoice":true,"withV2Timeline":true}}'
    tweets_features = '{"rweb_tipjar_consumption_enabled":true,"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":true,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"rweb_video_timestamps_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_enhance_cards_enabled":false}'

    resp = requests.get(
        f"https://x.com/i/api/graphql/{tweets_query_id}/UserTweets",
        headers=headers,
        params={"variables": tweets_variables, "features": tweets_features},
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"  [错误] 获取推文失败: {resp.status_code}")
        return []

    # 解析 GraphQL 响应
    tweets = []
    data = resp.json().get("data", {}).get("user", {}).get("result", {})
    timeline = data.get("timeline_v2", {}).get("timeline", {}).get("instructions", [])

    for instruction in timeline:
        entries = instruction.get("entries", [])
        for entry in entries:
            content = entry.get("content", {})
            tweet_result = content.get("itemContent", {}).get("tweet_results", {}).get("result", {})
            legacy = tweet_result.get("legacy", {})
            if legacy:
                tweets.append({
                    "full_text": legacy.get("full_text", ""),
                    "entities": legacy.get("entities", {}),
                })

    return tweets


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
