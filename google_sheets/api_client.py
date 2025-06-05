# google_sheets/api_client.py

import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_google_sheets_client():
    """
    Google Sheets APIクライアントを初期化して返します。
    """
    try:
        # ReplitのSecretsからサービスアカウントの認証情報を取得
        credentials_json = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
        if not credentials_json:
            raise ValueError("GOOGLE_SHEETS_CREDENTIALS environment variable not set.")

        # JSON文字列をPython辞書にパース
        credentials_info = json.loads(credentials_json)

        # スコープを設定 (読み書き権限)
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
        ]

        # サービスアカウントの認証情報でクライアントを初期化
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print(f"Error initializing Google Sheets client: {e}")
        raise # エラーを再スローして、呼び出し元で処理できるようにする