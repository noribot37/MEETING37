import gspread
import pandas as pd # pandasも必要なのでインポート
import os
from datetime import datetime # datetimeも元のコードにあったのでインポート

# --- 初期化 ---
# 認証情報は環境変数から読み込む
SERVICE_ACCOUNT_KEY_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
if SERVICE_ACCOUNT_KEY_JSON:
    try:
        # JSON文字列を直接読み込む (evalは危険だが、ユーザーが環境変数で設定しているため今回は使用)
        gc = gspread.service_account_from_dict(eval(SERVICE_ACCOUNT_KEY_JSON))
    except Exception as e:
        raise ValueError(f"Error initializing gspread from GOOGLE_SHEETS_CREDENTIALS: {e}")
else:
    raise ValueError("GOOGLE_SHEETS_CREDENTIALS environment variable not set.")

# スプレッドシート名を取得
SPREADSHEET_NAME = os.getenv("GOOGLE_SHEETS_SPREADSHEET_NAME")
if not SPREADSHEET_NAME:
    raise ValueError("GOOGLE_SHEETS_SPREADSHEET_NAME environment variable not set.")

# グローバルなSHEETオブジェクト
try:
    SHEET = gc.open(SPREADSHEET_NAME)
except gspread.SpreadsheetNotFound:
    raise ValueError(f"Spreadsheet '{SPREADSHEET_NAME}' not found. Please check the name or permissions.")


# --- ヘルパー関数 (元の300行コードから維持) ---
def get_worksheet(spreadsheet_name, worksheet_name): # gcはグローバルなSHEETを使用するので不要
    """指定されたスプレッドシートとワークシートを取得するヘルパー関数"""
    try:
        # spreadsheet = gc.open(spreadsheet_name) # グローバルなSHEETを使うので不要
        worksheet = SHEET.worksheet(worksheet_name)
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        print(f"Error: Worksheet '{worksheet_name}' not found in '{spreadsheet_name}'.")
        return None
    except Exception as e:
        print(f"An error occurred while getting worksheet: {e}")
        return None

def add_record(record_data, worksheet_name): # gcはグローバルなSHEETを使用するので不要
    """
    指定されたワークシートに新しいレコードを追加する。
    record_dataは辞書形式。 (元の300行コードから維持)
    """
    worksheet = get_worksheet(SPREADSHEET_NAME, worksheet_name)
    if worksheet is None:
        return False

    try:
        # ヘッダー行を取得
        headers = worksheet.row_values(1)

        # record_data のキーとヘッダーを比較し、適切な順序で値のリストを作成
        values_to_add = [record_data.get(header, '') for header in headers]

        worksheet.append_row(values_to_add)
        print(f"Record added successfully to '{worksheet_name}'.")
        return True
    except Exception as e:
        print(f"Error adding record to '{worksheet_name}': {e}")
        return False

def get_all_records(worksheet_name): # gcはグローバルなSHEETを使用するので不要
    """
    指定されたワークシートの全てのレコードを辞書のリストとして取得する。 (元の300行コードから維持)
    """
    worksheet = get_worksheet(SPREADSHEET_NAME, worksheet_name)
    if worksheet is None:
        return pd.DataFrame() # DataFrameを返すように変更

    try:
        records = worksheet.get_all_records()
        print(f"Retrieved {len(records)} records from '{worksheet_name}'.")
        return pd.DataFrame(records) # pandas DataFrameとして返す
    except Exception as e:
        print(f"Error retrieving records from '{worksheet_name}': {e}")
        return pd.DataFrame() # エラー時は空のDataFrameを返す

def delete_record(date_to_delete, title_to_delete, worksheet_name): # gcはグローバルなSHEETを使用するので不要
    """
    指定されたワークシートから日付とタイトルが一致するレコードを削除する。 (元の300行コードから維持)
    """
    worksheet = get_worksheet(SPREADSHEET_NAME, worksheet_name)
    if worksheet is None:
        return False, "ワークシートが見つかりません。"

    try:
        all_values = worksheet.get_all_values()
        if not all_values:
            return False, "ワークシートにデータがありません。"

        headers = all_values[0]
        rows_to_keep = [headers] # ヘッダーは常に保持
        deleted_count = 0

        for i, row in enumerate(all_values[1:], start=1): # ヘッダーの次の行から開始
            record_dict = dict(zip(headers, row))
            record_date = record_dict.get('日付', '').strip()
            record_title = record_dict.get('タイトル', '').strip()

            if record_date == date_to_delete.strip() and record_title == title_to_delete.strip():
                deleted_count += 1
                print(f"DEBUG: Deleting row {i+1} for Date: '{record_date}', Title: '{record_title}'")
            else:
                rows_to_keep.append(row)

        if deleted_count > 0:
            worksheet.clear()
            worksheet.append_rows(rows_to_keep)
            print(f"Deleted {deleted_count} record(s) from '{worksheet_name}'.")
            return True, f"{deleted_count}件のスケジュールを削除しました。"
        else:
            print(f"No matching record found for Date: '{date_to_delete}', Title: '{title_to_delete}' in '{worksheet_name}'.")
            return False, "指定された日付とタイトルのスケジュールは見つかりませんでした。"

    except Exception as e:
        print(f"Error deleting record from '{worksheet_name}': {e}")
        return False, f"スケジュールの削除中にエラーが発生しました: {e}"

def update_record(search_criteria, update_data, worksheet_name): # gcはグローバルなSHEETを使用するので不要
    """
    指定されたワークシートで検索条件に一致するレコードを更新する。 (元の300行コードから維持)
    search_criteria: 例 {'日付': '2023-04-01', 'タイトル': '会議'}
    update_data: 例 {'場所': 'オンライン', '備考': '議題：新製品開発'}
    """
    worksheet = get_worksheet(SPREADSHEET_NAME, worksheet_name)
    if worksheet is None:
        return False, "ワークシートが見つかりません。"

    try:
        all_values = worksheet.get_all_values()
        if not all_values:
            return False, "ワークシートにデータがありません。"

        headers = all_values[0]
        data_rows = all_values[1:]

        updated_count = 0
        new_all_values = [headers]

        for i, row_values in enumerate(data_rows):
            record_dict = dict(zip(headers, row_values))

            match = True
            for key, value in search_criteria.items():
                if record_dict.get(key) != value:
                    match = False
                    break

            if match:
                for update_key, update_value in update_data.items():
                    if update_key in headers:
                        col_index = headers.index(update_key)
                        row_values[col_index] = update_value
                updated_count += 1
                print(f"DEBUG: Updated row {i+2} (original index {i+1}) with {update_data}")
            new_all_values.append(row_values)

        if updated_count > 0:
            worksheet.clear()
            worksheet.append_rows(new_all_values)
            print(f"Updated {updated_count} record(s) in '{worksheet_name}'.")
            return True, f"{updated_count}件のスケジュールを更新しました。"
        else:
            print(f"No matching record found for search criteria {search_criteria} in '{worksheet_name}'.")
            return False, "指定された条件に一致するスケジュールは見つかりませんでした。"

    except Exception as e:
        print(f"Error updating record in '{worksheet_name}': {e}")
        return False, f"スケジュールの更新中にエラーが発生しました: {e}"

def sort_sheet_by_date(date_column_name='日付', worksheet_name='シート1', sort_order='ASCENDING'):
    """
    指定されたワークシートを日付カラムでソートする。 (元の300行コードから維持)
    date_column_name: 日付が格納されているカラムの名前（例: '日付'）
    sort_order: 'ASCENDING' (昇順) または 'DESCENDING' (降順)
    """
    worksheet = get_worksheet(SPREADSHEET_NAME, worksheet_name)
    if worksheet is None:
        return False, "ワークシートが見つかりません。"

    try:
        headers = worksheet.row_values(1)
        if date_column_name not in headers:
            return False, f"指定された日付カラム名 '{date_column_name}' が見つかりません。"

        date_col_index = headers.index(date_column_name) + 1

        worksheet.sort((date_col_index, sort_order))
        print(f"Worksheet '{worksheet_name}' sorted by '{date_column_name}' in {sort_order} order.")
        return True, "シートを日付で並べ替えました。"

    except Exception as e:
        print(f"Error sorting worksheet '{worksheet_name}': {e}")
        return False, f"シートの並べ替え中にエラーが発生しました: {e}"

# --- 新規追加・修正が必要な関数 (既存の関数を統合し、必要なものを追加) ---

# update_or_add_attendee は元の300行コードにもありましたが、参加者情報シートの構造に合わせるため、
# 以前の私の提案の形に修正して統合します。
def update_or_add_attendee(date: str, title: str, user_id: str, username: str, attendance_status: str, notes: str = ""):
    """
    指定された日付とタイトルのイベントに対し、出席者を更新または追加する。
    対象シートは 'シート2' （参加者情報シート）
    """
    try:
        # 'シート2' を使用
        worksheet = get_worksheet(SPREADSHEET_NAME, "シート2")
        if worksheet is None:
            return False, "ワークシート 'シート2' が見つかりません。"

        df = pd.DataFrame(worksheet.get_all_records())

        # 既存のレコードを探す
        # 列名 '日付', 'タイトル', '参加者ID' を使用 (あなたのシート2の列名に合わせる)
        mask = (df['日付'] == date) & \
               (df['タイトル'] == title) & \
               (df['参加者ID'] == user_id)

        if not df[mask].empty:
            # レコードを更新
            row_index = df[mask].index[0] + 2 # gspreadは1-based indexとヘッダー行を考慮
            # 列名 '出欠', '備考' を使用 (あなたのシート2の列名に合わせる)
            worksheet.update_cell(row_index, df.columns.get_loc('出欠') + 1, attendance_status)
            worksheet.update_cell(row_index, df.columns.get_loc('備考') + 1, notes)
            print(f"Updated attendee for {username} in {title} on {date}.")
        else:
            # 新しいレコードを追加
            # 列の順番に合わせてデータを準備: タイトル, 日付, 参加者名, 参加者ID, 出欠, 備考 (あなたのシート2の列名に合わせる)
            next_row = [title, date, username, user_id, attendance_status, notes]
            worksheet.append_row(next_row)
            print(f"Added new attendee {username} to {title} on {date}.")
        return True, "参加予定を更新しました。" if not df[mask].empty else "参加予定を登録しました。"
    except Exception as e:
        print(f"Error updating or adding attendee: {e}")
        return False, f"参加予定の更新/登録中にエラーが発生しました: {e}"


# get_attendees_for_user は以前のエラー解決のために導入し、attendance_qna.pyで必要
def get_attendees_for_user(user_id: str):
    """
    特定のユーザーの参加予定を取得する。
    スプレッドシートの 'シート2' からユーザーIDに一致する参加情報を抽出し、リストで返す。
    """
    try:
        df = pd.DataFrame(SHEET.worksheet("シート2").get_all_records())
        # '参加者ID' 列でフィルタリング
        user_attendances = df[df['参加者ID'] == user_id]

        if not user_attendances.empty:
            # 表示に必要な列を選択（例: 'タイトル', '日付', '参加者名', '出欠', '備考'）
            # ここはあなたのシート2の実際の列名に合わせてください
            return user_attendances[['タイトル', '日付', '参加者名', '出欠', '備考']].values.tolist()
        else:
            return []
    except Exception as e:
        print(f"Error getting attendees for user: {e}")
        return []

# add_schedule_record は add_record の代わりとして、schedule_commands.pyで必要
def add_schedule_record(date: str, time: str, place: str, title: str,
                        detail: str, deadline: str, duration: str, worksheet_name: str = "シート1"):
    """
    新しいスケジュールレコードを指定されたワークシートに追加する。
    """
    try:
        worksheet = get_worksheet(SPREADSHEET_NAME, worksheet_name)
        if worksheet is None:
            return False
        # あなたのシート1の列名に合わせてデータを準備
        # ヘッダー: 日付, 時間, 場所, タイトル, 詳細, 申込締切日, 尺
        new_row = [date, time, place, title, detail, deadline, duration]
        worksheet.append_row(new_row)
        print(f"Schedule record added successfully to '{worksheet_name}'.")
        return True
    except Exception as e:
        print(f"Error adding schedule record to '{worksheet_name}': {e}")
        return False

# delete_row_by_criteria は元の300行コードにあったが、現在どこからも呼び出されていない場合があるため、一旦統合する
# 必要があればline_handlers/commands/schedule_commands.pyなどで呼び出しを修正する
def delete_row_by_criteria(criteria_dict, worksheet_name): # gcはグローバルなSHEETを使用するので不要
    """
    指定されたワークシートから、複数の条件に一致する行を削除する。 (元の300行コードから維持)
    criteria_dict: 辞書形式で、{'カラム名': '値'} の形で削除条件を指定。
    """
    worksheet = get_worksheet(SPREADSHEET_NAME, worksheet_name)
    if worksheet is None:
        return False, "ワークシートが見つかりません。"

    try:
        all_values = worksheet.get_all_values()
        if not all_values:
            return False, "ワークシートにデータがありません。"

        headers = all_values[0]
        data_rows = all_values[1:]

        rows_to_keep = [headers] # ヘッダーは常に保持
        deleted_count = 0

        for i, row_values in enumerate(data_rows):
            row_dict = dict(zip(headers, row_values))

            match = True
            for key, value in criteria_dict.items():
                if key not in row_dict or row_dict[key] != value:
                    match = False
                    break

            if match:
                deleted_count += 1
                print(f"DEBUG: Deleting row matching criteria: {criteria_dict}")
            else:
                rows_to_keep.append(row_values)

        if deleted_count > 0:
            worksheet.clear()
            worksheet.append_rows(rows_to_keep)
            print(f"Deleted {deleted_count} row(s) matching criteria from '{worksheet_name}'.")
            return True, f"{deleted_count}件のレコードを削除しました。"
        else:
            print(f"No record found matching criteria: {criteria_dict} in '{worksheet_name}'.")
            return False, "指定された条件に一致するレコードは見つかりませんでした。"

    except Exception as e:
        print(f"Error in delete_row_by_criteria: {e}")
        return False, f"レコードの削除中にエラーが発生しました: {e}"

