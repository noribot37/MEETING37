import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import Config # config.py から設定をインポート

# グローバル変数としてgspreadクライアントとスプレッドシートインスタンスを保持
# モジュールが読み込まれた際に一度だけ初期化を試みる
_client = None
_spreadsheet = None

def _initialize_google_sheets_connection():
    """
    Google Sheets APIクライアントを初期化し、指定されたスプレッドシートを開く内部関数。
    初回呼び出し時に一度だけ実行される。
    """
    global _client, _spreadsheet

    if _client is not None and _spreadsheet is not None:
        return # 既に初期化済みであれば何もしない

    try:
        credentials_json = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
        if not credentials_json:
            raise ValueError("GOOGLE_SHEETS_CREDENTIALS environment variable not set.")

        credentials_info = json.loads(credentials_json)
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
        _client = gspread.authorize(creds)
        print("DEBUG: Google Sheets service account authenticated successfully.")

        # config.py からスプレッドシート名を取得
        spreadsheet_name = Config.GOOGLE_SHEETS_SPREADSHEET_NAME
        if not spreadsheet_name:
            raise ValueError("GOOGLE_SHEETS_SPREADSHEET_NAME is not set in config.py or environment variable.")

        _spreadsheet = _client.open(spreadsheet_name)
        print(f"DEBUG: Spreadsheet '{spreadsheet_name}' opened successfully.")

    except gspread.SpreadsheetNotFound:
        print(f"ERROR: Spreadsheet '{Config.GOOGLE_SHEETS_SPREADSHEET_NAME}' not found. Please check the name or permissions.")
        # 致命的なエラーなので、raiseしてアプリケーションの起動を止める
        raise FileNotFoundError(f"Spreadsheet '{Config.GOOGLE_SHEETS_SPREADSHEET_NAME}' not found.")
    except Exception as e:
        print(f"ERROR: Error initializing Google Sheets client or opening spreadsheet: {e}")
        # 致命的なエラーなので、raiseしてアプリケーションの起動を止める
        raise

# モジュールがインポートされたときに一度だけ初期化を試みる
try:
    _initialize_google_sheets_connection()
except (ValueError, FileNotFoundError, Exception) as e:
    print(f"CRITICAL ERROR: Failed to initialize Google Sheets API client: {e}")
    # 初期化失敗時は、後続のget_google_sheets_client()などがエラーを返すようにする
    _client = None
    _spreadsheet = None


def get_google_sheets_client_and_spreadsheet():
    """
    初期化されたgspreadクライアントとスプレッドシートインスタンスを返します。
    """
    if _client is None or _spreadsheet is None:
        # 初期化が失敗している場合、またはまだ実行されていない場合（通常はモジュールロード時に実行されるはず）
        # ここで再度初期化を試みるか、エラーを返すか選択。ここではエラーを返す。
        raise RuntimeError("Google Sheets client or spreadsheet not initialized.")
    return _client, _spreadsheet

