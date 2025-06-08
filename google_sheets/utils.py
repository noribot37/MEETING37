import gspread
import pandas as pd
import os
import json

gc = None
SHEET = None

try:
    SERVICE_ACCOUNT_KEY_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

    if SERVICE_ACCOUNT_KEY_JSON:
        try:
            credentials_dict = json.loads(SERVICE_ACCOUNT_KEY_JSON)
            gc = gspread.service_account_from_dict(credentials_dict)
            print("DEBUG: Google Sheets service account authenticated successfully.")
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to decode GOOGLE_SHEETS_CREDENTIALS JSON: {e}")
            pass # エラーを捕捉して続行
        except Exception as e:
            print(f"ERROR: Error authenticating Google Sheet client: {e}")
            pass # エラーを捕捉して続行
    else:
        print("ERROR: GOOGLE_SHEETS_CREDENTIALS environment variable not set.")
        pass # エラーを捕捉して続行

    SPREADSHEET_NAME = os.getenv("GOOGLE_SHEETS_SPREADSHEET_NAME")
    if not SPREADSHEET_NAME:
        print("ERROR: GOOGLE_SHEETS_SPREADSHEET_NAME environment variable not set.")
        pass # エラーを捕捉して続行
    else:
        print(f"DEBUG: Using spreadsheet name: {SPREADSHEET_NAME}")

    if gc: # gcが正常に初期化されている場合のみシートを開く
        try:
            SHEET = gc.open(SPREADSHEET_NAME)
            print(f"DEBUG: Spreadsheet '{SPREADSHEET_NAME}' opened successfully.")
        except gspread.SpreadsheetNotFound:
            print(f"ERROR: Spreadsheet '{SPREADSHEET_NAME}' not found. Please check the name or permissions.")
            pass # エラーを捕捉して続行
        except Exception as e:
            print(f"ERROR: Error opening spreadsheet '{SPREADSHEET_NAME}': {e}")
            pass # エラーを捕捉して続行

except ValueError as ve:
    print(f"Configuration Error: {ve}")
except Exception as e:
    print(f"An unexpected error occurred during Google Sheet initialization: {e}")


def get_all_records(worksheet_name="シート1"):
    print(f"DEBUG: Attempting to get all records from worksheet: {worksheet_name}")
    if SHEET is None:
        print("ERROR: Google Sheet not initialized. Cannot get records.")
        return pd.DataFrame()
    try:
        worksheet = SHEET.worksheet(worksheet_name)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        if '日付' in df.columns:
            df['日付'] = pd.to_datetime(df['日付'], errors='coerce')
        print(f"DEBUG: Successfully got {len(df)} records from '{worksheet_name}'.")
        return df
    except gspread.WorksheetNotFound:
        print(f"ERROR: Worksheet '{worksheet_name}' not found. Returning empty DataFrame.")
        return pd.DataFrame()
    except Exception as e:
        print(f"ERROR: Error getting all records from '{worksheet_name}': {e}")
        return pd.DataFrame()

def add_schedule(schedule_data: dict):
    print(f"DEBUG: Attempting to add schedule: {schedule_data.get('タイトル')}")
    if SHEET is None:
        print("ERROR: Google Sheet not initialized. Cannot add schedule.")
        return False
    try:
        worksheet = SHEET.worksheet("シート1")
        headers = worksheet.row_values(1)
        row_values = []
        for header in headers:
            row_values.append(schedule_data.get(header, ''))
        worksheet.append_row(row_values)
        print(f"DEBUG: Added new schedule: {schedule_data.get('タイトル')}")
        return True
    except Exception as e:
        print(f"ERROR: Error adding schedule: {e}")
        return False

def delete_schedule(row_index: int):
    print(f"DEBUG: Attempting to delete schedule at row: {row_index}")
    if SHEET is None:
        print("ERROR: Google Sheet not initialized. Cannot delete schedule.")
        return False
    try:
        worksheet = SHEET.worksheet("シート1")
        worksheet.delete_rows(row_index)
        print(f"DEBUG: Deleted schedule at row {row_index}.")
        return True
    except Exception as e:
        print(f"ERROR: Error deleting schedule: {e}")
        return False

def edit_schedule(row_index: int, update_data: dict):
    print(f"DEBUG: Attempting to edit schedule at row {row_index} with data: {update_data}")
    if SHEET is None:
        print("ERROR: Google Sheet not initialized. Cannot edit schedule.")
        return False
    try:
        worksheet = SHEET.worksheet("シート1")
        headers = worksheet.row_values(1)
        for column_name, new_value in update_data.items():
            if column_name in headers:
                col_index = headers.index(column_name) + 1
                worksheet.update_cell(row_index, col_index, new_value)
                print(f"DEBUG: Updated cell R{row_index}C{col_index} ({column_name}) to '{new_value}'.")
            else:
                print(f"WARNING: Column '{column_name}' not found in worksheet headers. Skipping update.")
        return True
    except Exception as e:
        print(f"ERROR: Error editing schedule: {e}")
        return False

def update_or_add_attendee(date, title, user_id, username, attendance_status, notes=""):
    print(f"DEBUG: Attempting to update or add attendee for {user_id} ({username}) for {title} on {date}.")
    if SHEET is None:
        print("ERROR: Google Sheet not initialized. Cannot update/add attendee.")
        return False, "Google Sheet not initialized."
    try:
        worksheet = SHEET.worksheet("シート2")
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        print(f"DEBUG: Fetched {len(df)} records from 'シート2' for attendee check.")

        # DataFrameが空の場合に早期リターンし、新規行を追加する
        if df.empty:
            print("DEBUG: 'シート2' is empty. Adding new attendee record directly.")
            headers = worksheet.row_values(1) # ヘッダーは必ず取得
            new_row_values = []
            for col_name in headers:
                if col_name == 'タイトル':
                    new_row_values.append(title)
                elif col_name == '日付':
                    new_row_values.append(date)
                elif col_name == '参加者名':
                    new_row_values.append(username)
                elif col_name == '参加者ID':
                    new_row_values.append(user_id)
                elif col_name == '出欠':
                    new_row_values.append(attendance_status)
                elif col_name == '備考':
                    new_row_values.append(notes)
                else:
                    new_row_values.append('') # 未知の列には空文字列

            worksheet.append_row(new_row_values)
            print(f"DEBUG: Added new attendee {user_id} to {title} on {date} (sheet was empty).")
            return True, "参加予定を登録しました。"

        # DataFrameが空でない場合のみ、列の存在をチェックして続行
        required_columns = ['参加者ID', '日付', 'タイトル']
        for col in required_columns:
            if col not in df.columns:
                print(f"ERROR: Required column '{col}' not found in 'シート2' DataFrame. Columns: {df.columns.tolist()}")
                return False, f"スプレッドシートに必須の列 '{col}' が見つかりません。"

        mask = (df['参加者ID'] == user_id) & \
               (df['日付'] == date) & \
               (df['タイトル'] == title)

        if not df[mask].empty:
            row_index = df[mask].index[0] + 2
            headers = worksheet.row_values(1)
            print(f"DEBUG: Existing attendee record found at row {row_index}. Updating.")

            if '出欠' in headers:
                worksheet.update_cell(row_index, headers.index('出欠') + 1, attendance_status)
                print(f"DEBUG: Updated attendance status to {attendance_status}.")
            if '備考' in headers:
                worksheet.update_cell(row_index, headers.index('備考') + 1, notes)
                print(f"DEBUG: Updated notes to '{notes}'.")
            print(f"DEBUG: Updated attendee for {user_id} in {title} on {date}.")
            return True, "参加予定を更新しました。"
        else:
            print("DEBUG: No existing attendee record found. Adding new row.")
            headers = worksheet.row_values(1)
            new_row_values = []
            for col_name in headers:
                if col_name == 'タイトル':
                    new_row_values.append(title)
                elif col_name == '日付':
                    new_row_values.append(date)
                elif col_name == '参加者名':
                    new_row_values.append(username)
                elif col_name == '参加者ID':
                    new_row_values.append(user_id)
                elif col_name == '出欠':
                    new_row_values.append(attendance_status)
                elif col_name == '備考':
                    new_row_values.append(notes)
                else:
                    new_row_values.append('')

            worksheet.append_row(new_row_values)
            print(f"DEBUG: Added new attendee {user_id} to {title} on {date}.")
            return True, "参加予定を登録しました。"
    except Exception as e:
        print(f"ERROR: Error updating or adding attendee: {e}")
        return False, f"エラーが発生しました: {e}"

def delete_row_by_criteria(worksheet_name: str, criteria: dict):
    print(f"DEBUG: Attempting to delete row from '{worksheet_name}' with criteria: {criteria}")
    if SHEET is None:
        print("ERROR: Google Sheet not initialized. Cannot delete row.")
        return False
    try:
        worksheet = SHEET.worksheet(worksheet_name)
        df = pd.DataFrame(worksheet.get_all_records())
        print(f"DEBUG: Fetched {len(df)} records from '{worksheet_name}' for deletion check.")

        mask = pd.Series([True] * len(df))
        for col, val in criteria.items():
            if col in df.columns:
                mask &= (df[col] == val)
            else:
                print(f"WARNING: Criteria column '{col}' not found in worksheet '{worksheet_name}'. Skipping deletion.")
                return False

        rows_to_delete = df[mask]

        if not rows_to_delete.empty:
            sorted_indices = sorted(rows_to_delete.index.tolist(), reverse=True)
            for idx in sorted_indices:
                worksheet.delete_rows(idx + 2)
            print(f"DEBUG: Deleted {len(rows_to_delete)} rows from '{worksheet_name}' matching criteria: {criteria}")
            return True
        else:
            print(f"DEBUG: No rows found in '{worksheet_name}' matching criteria: {criteria}")
            return False
    except Exception as e:
        print(f"ERROR: Error deleting row by criteria from '{worksheet_name}': {e}")
        return False

def get_attendees_for_user(user_id: str):
    print(f"DEBUG: Attempting to get attendees for user: {user_id}")
    if SHEET is None:
        print("ERROR: Google Sheet not initialized. Cannot get attendees for user.")
        return []
    try:
        df = pd.DataFrame(SHEET.worksheet("シート2").get_all_records())
        print(f"DEBUG: Fetched {len(df)} records from 'シート2' for user {user_id} attendees.")

        if df.empty:
            print("DEBUG: 'シート2' is empty. No attendees to retrieve.")
            return []

        # 取得したDataFrameの列名をログに出力
        print(f"DEBUG: Columns in 'シート2' DataFrame: {df.columns.tolist()}")

        if '参加者ID' not in df.columns:
            print(f"ERROR: '参加者ID' column not found in 'シート2'. Found columns: {df.columns.tolist()}")
            return [] # 列がない場合は空リストを返して処理を継続可能にする

        user_attendances = df[df['参加者ID'] == user_id]

        if not user_attendances.empty:
            print(f"DEBUG: Found {len(user_attendances)} attendee records for user {user_id}.")
            return user_attendances[['タイトル', '日付', '参加者名', '出欠', '備考']].values.tolist()
        else:
            print(f"DEBUG: No attendee records found for user {user_id}.")
            return []
    except Exception as e:
        print(f"ERROR: Error getting attendees for user: {e}")
        return []
