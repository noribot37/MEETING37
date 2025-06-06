import gspread
import pandas as pd
import os
from datetime import datetime

# --- 初期化 ---
# 認証情報は環境変数から読み込む
SERVICE_ACCOUNT_KEY_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
if SERVICE_ACCOUNT_KEY_JSON:
    try:
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


# --- ヘルパー関数 (元の300行コードから維持 + 調整) ---
def get_worksheet(worksheet_name): # gcやspreadsheet_nameはグローバルから取得
    """指定されたワークシートを取得するヘルパー関数"""
    try:
        worksheet = SHEET.worksheet(worksheet_name)
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        print(f"Error: Worksheet '{worksheet_name}' not found in '{SPREADSHEET_NAME}'.")
        return None
    except Exception as e:
        print(f"An error occurred while getting worksheet: {e}")
        return None

def add_record(record_data, worksheet_name):
    """
    指定されたワークシートに新しいレコードを追加する。
    record_dataは辞書形式。 (元の300行コードから維持)
    """
    worksheet = get_worksheet(worksheet_name)
    if worksheet is None:
        return False

    try:
        headers = worksheet.row_values(1)
        values_to_add = [record_data.get(header, '') for header in headers]
        worksheet.append_row(values_to_add)
        print(f"Record added successfully to '{worksheet_name}'.")
        return True
    except Exception as e:
        print(f"Error adding record to '{worksheet_name}': {e}")
        return False

def get_all_records(worksheet_name):
    """
    指定されたワークシートの全てのレコードをDataFrameとして取得する。
    """
    worksheet = get_worksheet(worksheet_name)
    if worksheet is None:
        return pd.DataFrame()

    try:
        records = worksheet.get_all_records()
        print(f"Retrieved {len(records)} records from '{worksheet_name}'.")
        return pd.DataFrame(records)
    except Exception as e:
        print(f"Error retrieving records from '{worksheet_name}': {e}")
        return pd.DataFrame()

def delete_record(date_to_delete, title_to_delete, worksheet_name):
    """
    指定されたワークシートから日付とタイトルが一致するレコードを削除する。 (元の300行コードから維持)
    """
    worksheet = get_worksheet(worksheet_name)
    if worksheet is None:
        return False, "ワークシートが見つかりません。"

    try:
        all_values = worksheet.get_all_values()
        if not all_values:
            return False, "ワークシートにデータがありません。"

        headers = all_values[0]
        rows_to_keep = [headers]
        deleted_count = 0

        for i, row in enumerate(all_values[1:], start=1):
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

def update_record(search_criteria, update_data, worksheet_name):
    """
    指定されたワークシートで検索条件に一致するレコードを更新する。 (元の300行コードから維持)
    search_criteria: 例 {'日付': '2023-04-01', 'タイトル': '会議'}
    update_data: 例 {'場所': 'オンライン', '備考': '議題：新製品開発'}
    """
    worksheet = get_worksheet(worksheet_name)
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
    """
    worksheet = get_worksheet(worksheet_name)
    if worksheet is None:
        return False, "ワークシートが見つかりません。"

    try:
        headers = worksheet.row_values(1)
        if date_column_name not in headers:
            print(f"Error: Date column '{date_column_name}' not found in worksheet '{worksheet_name}'.")
            return False, f"指定された日付カラム名 '{date_column_name}' が見つかりません。"

        date_col_index = headers.index(date_column_name) + 1

        worksheet.sort((date_col_index, sort_order))
        print(f"Worksheet '{worksheet_name}' sorted by '{date_column_name}' in {sort_order} order.")
        return True, "シートを日付で並べ替えました。"

    except Exception as e:
        print(f"Error sorting worksheet '{worksheet_name}': {e}")
        return False, f"シートの並べ替え中にエラーが発生しました: {e}"


def delete_row_by_criteria(criteria_dict, worksheet_name):
    """
    指定されたワークシートから、複数の条件に一致する行を削除する。 (元の300行コードから維持)
    """
    worksheet = get_worksheet(worksheet_name)
    if worksheet is None:
        return False, "ワークシートが見つかりません。"

    try:
        all_values = worksheet.get_all_values()
        if not all_values:
            return False, "ワークシートにデータがありません。"

        headers = all_values[0]
        data_rows = all_values[1:]

        rows_to_keep = [headers]
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


# --- BOTの機能に必要な追加関数 ---

# get_attendees_for_user は以前のエラー解決のために導入し、attendance_qna.pyで必要
def get_attendees_for_user(user_id: str):
    """
    特定のユーザーの参加予定を取得する。
    スプレッドシートの 'シート2' からユーザーIDに一致する参加情報を抽出し、リストで返す。
    """
    try:
        worksheet = get_worksheet("シート2")
        if worksheet is None:
            return []
        df = pd.DataFrame(worksheet.get_all_records())

        user_attendances = df[df['参加者ID'] == user_id]

        if not user_attendances.empty:
            return user_attendances[['タイトル', '日付', '参加者名', '出欠', '備考']].values.tolist()
        else:
            return []
    except Exception as e:
        print(f"Error getting attendees for user: {e}")
        return []

# add_schedule_record は schedule_commands.pyでスケジュール登録のために必要
def add_schedule_record(date: str, time: str, place: str, title: str,
                        detail: str, deadline: str, duration: str, worksheet_name: str = "シート1"):
    """
    新しいスケジュールレコードを指定されたワークシートに追加する。
    """
    worksheet = get_worksheet(worksheet_name)
    if worksheet is None:
        return False

    try:
        # シート1のヘッダー列に合わせてデータを準備
        # ヘッダー: 日付, 時間, 場所, タイトル, 詳細, 申込締切日, 尺
        new_row = [date, time, place, title, detail, deadline, duration]
        worksheet.append_row(new_row)
        print(f"Schedule record added successfully to '{worksheet_name}'.")
        return True
    except Exception as e:
        print(f"Error adding schedule record to '{worksheet_name}': {e}")
        return False

# 元の300行のutils.pyにあったupdate_or_add_attendeeを、BOTの挙動に合わせ修正して統合
def update_or_add_attendee(date: str, title: str, user_id: str, username: str, attendance_status: str, notes: str = ""):
    """
    指定された日付とタイトルのイベントに対し、出席者を更新または追加する。
    対象シートは 'シート2' （参加者情報シート）
    """
    try:
        worksheet = get_worksheet("シート2")
        if worksheet is None:
            return False, "ワークシート 'シート2' が見つかりません。"

        df = pd.DataFrame(worksheet.get_all_records())

        mask = (df['日付'] == date) & \
               (df['タイトル'] == title) & \
               (df['参加者ID'] == user_id) # あなたのシート2の列名に合わせる

        if not df[mask].empty:
            row_index = df[mask].index[0] + 2
            # 列名 '出欠', '備考' を使用 (あなたのシート2の列名に合わせる)
            worksheet.update_cell(row_index, df.columns.get_loc('出欠') + 1, attendance_status)
            worksheet.update_cell(row_index, df.columns.get_loc('備考') + 1, notes)
            print(f"Updated attendee for {username} in {title} on {date}.")
            return True, "参加予定を更新しました。"
        else:
            # 列の順番に合わせてデータを準備: タイトル, 日付, 参加者名, 参加者ID, 出欠, 備考 (あなたのシート2の列名に合わせる)
            new_row = [title, date, username, user_id, attendance_status, notes]
            worksheet.append_row(new_row)
            print(f"Added new attendee {username} to {title} on {date}.")
            return True, "参加予定を登録しました。"
    except Exception as e:
        print(f"Error updating or adding attendee: {e}")
        return False, f"参加予定の更新/登録中にエラーが発生しました: {e}"

