"""配置加载模块"""

import os
import yaml

def load_accounts(path="config/accounts.yaml"):
    """加载账号列表"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("accounts", [])

def get_rsshub_base():
    """获取 RSSHub 实例地址，支持自建或公共实例"""
    custom = os.environ.get("RSSHUB_BASE_URL")
    if custom:
        return custom.rstrip("/")
    # 公共实例列表，按优先级排列
    return "https://rsshub.app"

def get_feishu_webhook():
    """获取飞书 Webhook 地址"""
    return os.environ.get("FEISHU_WEBHOOK_URL", "")

def get_feishu_app_credentials():
    """获取飞书应用凭证（用于 Bot API 和 Bitable）"""
    return {
        "app_id": os.environ.get("FEISHU_APP_ID", ""),
        "app_secret": os.environ.get("FEISHU_APP_SECRET", ""),
    }

def get_feishu_bitable_info():
    """获取飞书多维表格信息"""
    return {
        "app_token": os.environ.get("FEISHU_BITABLE_APP_TOKEN", ""),
        "table_id": os.environ.get("FEISHU_BITABLE_TABLE_ID", ""),
    }

def get_feishu_chat_id():
    """获取飞书群聊 ID（用于 Bot 发消息）"""
    return os.environ.get("FEISHU_CHAT_ID", "")

def get_gallery_dl_config():
    """生成 gallery-dl 配置，使用环境变量中的 cookies"""
    config = {
        "extractor": {
            "twitter": {
                "cookies": {
                    "auth_token": os.environ.get("X_AUTH_TOKEN", ""),
                    "ct0": os.environ.get("X_CT0", ""),
                }
            },
            "instagram": {
                "cookies": {
                    "sessionid": os.environ.get("IG_SESSION_ID", ""),
                    "ds_user_id": os.environ.get("IG_DS_USER_ID", ""),
                    "csrftoken": os.environ.get("IG_CSRFTOKEN", ""),
                }
            }
        }
    }
    return config
