import gspread
import pandas as pd
import os
import json # jsonモジュールをインポート

# グローバル変数として初期化
gc = None
SHEET = None

try:
    # サービスアカウントキーをJSON形式で取得
    SERVICE_ACCOUNT_KEY_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

    if SERVICE_ACCOUNT_KEY_JSON:
        try:
            # JSON文字列を安全にPython辞書に変換
            credentials_dict = json.loads(SERVICE_ACCOUNT_KEY_JSON)
            gc = gspread.service_account_from_dict(credentials_dict)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode GOOGLE_SHEETS_CREDENTIALS JSON: {e}")
        except Exception as e:
            # その他の認証エラーを捕捉
            raise ValueError(f"Error authenticating Google Sheet client: {e}")
    else:
        raise ValueError("GOOGLE_SHEETS_CREDENTIALS environment variable not set.")

    # スプレッドシート名を取得（あなたの既存の環境変数名を使用）
    SPREADSHEET_NAME = os.getenv("GOOGLE_SHEETS_SPREADSHEET_NAME")
    if not SPREADSHEET_NAME:
        raise ValueError("GOOGLE_SHEETS_SPREADSHEET_NAME environment variable not set.")

    # スプレッドシートを開く
    try:
        SHEET = gc.open(SPREADSHEET_NAME)
    except gspread.SpreadsheetNotFound:
        raise ValueError(f"Spreadsheet '{SPREADSHEET_NAME}' not found. Please check the name or permissions.")
    except Exception as e:
        raise ValueError(f"Error opening spreadsheet '{SPREADSHEET_NAME}': {e}")

except ValueError as ve:
    # 環境変数またはスプレッドシート関連のエラーを捕捉
    print(f"Configuration Error: {ve}")
    # ここでエラーメッセージをより具体的に表示することも可能
    # 例えば、LINEにメッセージを返すようにすることもできますが、起動時エラーなのでReplitのログに出力
except Exception as e:
    # 予期せぬエラーを捕捉
    print(f"An unexpected error occurred during Google Sheet initialization: {e}")

# 以下、関数定義は変更なし

def get_all_records(worksheet_name="シート1"):
    """
    指定されたワークシートの全てのレコードをDataFrameとして取得する。
    デフォルトは「シート1」。
    """
    if SHEET is None:
        print("Google Sheet not initialized. Cannot get records.")
        return pd.DataFrame()
    try:
        worksheet = SHEET.worksheet(worksheet_name)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        # 日付カラムをdatetime型に変換（エラーを無視して変換できないものはNaTにする）
        if '日付' in df.columns:
            df['日付'] = pd.to_datetime(df['日付'], errors='coerce')
        return df
    except gspread.WorksheetNotFound:
        print(f"Worksheet '{worksheet_name}' not found. Returning empty DataFrame.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error getting all records from '{worksheet_name}': {e}")
        return pd.DataFrame()

def add_schedule(schedule_data: dict):
    """
    新しいスケジュールをスプレッドシートに追加する。
    Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME を使用。
    """
    if SHEET is None:
        print("Google Sheet not initialized. Cannot add schedule.")
        return False
    try:
        worksheet = SHEET.worksheet("シート1") # スケジュールシート
        # ヘッダー行を取得して列の順序を確認
        headers = worksheet.row_values(1)

        # データの順序をヘッダーに合わせて調整
        row_values = []
        for header in headers:
            # 辞書にキーが存在しない場合は空文字列をセット
            row_values.append(schedule_data.get(header, ''))

        worksheet.append_row(row_values)
        print(f"Added new schedule: {schedule_data.get('タイトル')}")
        return True
    except Exception as e:
        print(f"Error adding schedule: {e}")
        return False

def delete_schedule(row_index: int):
    """
    指定された行番号のスケジュールをスプレッドシートから削除する。
    Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME を使用。
    """
    if SHEET is None:
        print("Google Sheet not initialized. Cannot delete schedule.")
        return False
    try:
        worksheet = SHEET.worksheet("シート1") # スケジュールシート
        worksheet.delete_rows(row_index)
        print(f"Deleted schedule at row {row_index}.")
        return True
    except Exception as e:
        print(f"Error deleting schedule: {e}")
        return False

def edit_schedule(row_index: int, update_data: dict):
    """
    指定された行番号のスケジュールを更新する。
    update_data は {'列名': '新しい値'} の辞書。
    Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME を使用。
    """
    if SHEET is None:
        print("Google Sheet not initialized. Cannot edit schedule.")
        return False
    try:
        worksheet = SHEET.worksheet("シート1") # スケジュールシート
        headers = worksheet.row_values(1) # ヘッダー行を取得

        for column_name, new_value in update_data.items():
            if column_name in headers:
                col_index = headers.index(column_name) + 1 # 1-based index
                worksheet.update_cell(row_index, col_index, new_value)
                print(f"Updated cell R{row_index}C{col_index} ({column_name}) to '{new_value}'.")
            else:
                print(f"Warning: Column '{column_name}' not found in worksheet headers. Skipping update.")
        return True
    except Exception as e:
        print(f"Error editing schedule: {e}")
        return False

def update_or_add_attendee(attendee_data: dict):
    """
    指定された日付とタイトルのイベントに対し、出席者を更新または追加する。
    対象シートは 'シート2' （参加者情報シート）
    attendee_data は {'日付': 'YYYY/MM/DD', 'タイトル': 'xxx', 'ユーザーID': 'Uxxx', '出欠': '〇', '備考': 'yyy'}
    """
    if SHEET is None:
        print("Google Sheet not initialized. Cannot update/add attendee.")
        return False
    try:
        worksheet = SHEET.worksheet("シート2") # 参加者情報シート
        df = pd.DataFrame(worksheet.get_all_records())

        user_id = attendee_data.get('ユーザーID')
        date = attendee_data.get('日付')
        title = attendee_data.get('タイトル')
        attendance_status = attendee_data.get('出欠', '')
        notes = attendee_data.get('備考', '')
        # 参加者名は今回はユーザーIDを代用、必要に応じてLINEのプロフィール名を取得
        username = user_id # 仮にユーザーIDを参加者名として使用

        # 既存のレコードを探す
        # 日付は文字列として比較（スプレッドシートから取得した時点では文字列）
        mask = (df['ユーザーID'] == user_id) & \
               (df['日付'] == date) & \
               (df['タイトル'] == title)

        if not df[mask].empty:
            # レコードを更新
            row_index = df[mask].index[0] + 2 # gspreadは1-based indexとヘッダー行を考慮
            headers = worksheet.row_values(1) # ヘッダー行を取得

            if '出欠' in headers:
                worksheet.update_cell(row_index, headers.index('出欠') + 1, attendance_status)
            if '備考' in headers:
                worksheet.update_cell(row_index, headers.index('備考') + 1, notes)
            print(f"Updated attendee for {user_id} in {title} on {date}.")
        else:
            # 新しいレコードを追加
            # 列の順番はスプレッドシートのヘッダーに合わせる
            headers = worksheet.row_values(1)
            new_row_values = []
            for col_name in headers:
                if col_name == 'タイトル':
                    new_row_values.append(title)
                elif col_name == '日付':
                    new_row_values.append(date)
                elif col_name == '参加者名': # ここは適宜修正が必要
                    new_row_values.append(username) 
                elif col_name == 'ユーザーID':
                    new_row_values.append(user_id)
                elif col_name == '出欠':
                    new_row_values.append(attendance_status)
                elif col_name == '備考':
                    new_row_values.append(notes)
                else:
                    new_row_values.append('') # その他の列は空で追加

            worksheet.append_row(new_row_values)
            print(f"Added new attendee {user_id} to {title} on {date}.")
        return True
    except Exception as e:
        print(f"Error updating or adding attendee: {e}")
        return False

def delete_row_by_criteria(worksheet_name: str, criteria: dict):
    """
    指定されたワークシートから、基準に合致する行を削除する。
    criteria は {'列名': '値'} の辞書。
    """
    if SHEET is None:
        print("Google Sheet not initialized. Cannot delete row.")
        return False
    try:
        worksheet = SHEET.worksheet(worksheet_name)
        df = pd.DataFrame(worksheet.get_all_records())

        # フィルタリング条件を作成
        mask = pd.Series([True] * len(df))
        for col, val in criteria.items():
            if col in df.columns:
                mask &= (df[col] == val)
            else:
                print(f"Warning: Criteria column '{col}' not found in worksheet '{worksheet_name}'.")
                return False # 存在しない列での削除は行わない

        rows_to_delete = df[mask]

        if not rows_to_delete.empty:
            # gspreadの行インデックスは1から始まるため +2 (ヘッダー行と0-based index)
            # 複数の行が一致する場合、全て削除するために逆順で処理
            sorted_indices = sorted(rows_to_delete.index.tolist(), reverse=True)
            for idx in sorted_indices:
                worksheet.delete_rows(idx + 2)
            print(f"Deleted {len(rows_to_delete)} rows from '{worksheet_name}' matching criteria: {criteria}")
            return True
        else:
            print(f"No rows found in '{worksheet_name}' matching criteria: {criteria}")
            return False
    except Exception as e:
        print(f"Error deleting row by criteria from '{worksheet_name}': {e}")
        return False

def get_attendees_for_user(user_id: str):
    """
    特定のユーザーの参加予定を取得する。
    スプレッドシートの 'シート2' からユーザーIDに一致する参加情報を抽出し、リストで返す。
    """
    if SHEET is None:
        print("Google Sheet not initialized. Cannot get attendees for user.")
        return []
    try:
        df = pd.DataFrame(SHEET.worksheet("シート2").get_all_records())

        # 'ユーザーID' 列でフィルタリング
        user_attendances = df[df['ユーザーID'] == user_id]

        if not user_attendances.empty:
            # あなたのシート2の列名に合わせて情報を抽出
            # 'タイトル', '日付', '参加者名', '出欠', '備考'
            # 抽出する順番は、表示したい順番に合わせてください
            return user_attendances[['タイトル', '日付', '参加者名', '出欠', '備考']].values.tolist()
        else:
            return [] # 参加予定が見つからない場合は空のリストを返す
    except Exception as e:
        print(f"Error getting attendees for user: {e}")
        return []

