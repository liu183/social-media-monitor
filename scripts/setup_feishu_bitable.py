"""创建飞书多维表格的字段结构 - 首次运行时使用"""

import os
import requests
import json


def get_token(app_id, app_secret):
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret}
    )
    return resp.json().get("tenant_access_token")


def create_table_fields(token, app_token, table_id):
    """为多维表格创建所需的字段"""
    fields = [
        {"field_name": "平台", "type": 1},  # 1=文本
        {"field_name": "账号", "type": 1},
        {"field_name": "账号名称", "type": 1},
        {"field_name": "内容摘要", "type": 1},
        {"field_name": "原文链接", "type": 15},  # 15=超链接
        {"field_name": "发布时间", "type": 1},
        {"field_name": "图片数量", "type": 2},  # 2=数字
        {"field_name": "视频数量", "type": 2},
        {"field_name": "下载文件数", "type": 2},
        {"field_name": "抓取时间", "type": 1},
    ]

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"

    for field in fields:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=field
        )
        data = resp.json()
        if data.get("code") == 0:
            print(f"  [OK] 创建字段: {field['field_name']}")
        else:
            print(f"  [WARN] 字段 {field['field_name']}: {data.get('msg', '未知错误')}")


def main():
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN")
    table_id = os.environ.get("FEISHU_BITABLE_TABLE_ID")

    if not all([app_id, app_secret, app_token, table_id]):
        print("请设置环境变量: FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BITABLE_APP_TOKEN, FEISHU_BITABLE_TABLE_ID")
        return

    token = get_token(app_id, app_secret)
    if not token:
        print("获取 token 失败")
        return

    print("创建多维表格字段...")
    create_table_fields(token, app_token, table_id)
    print("完成!")


if __name__ == "__main__":
    main()
