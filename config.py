# config.py
import os
from enum import Enum

# LINE Bot の設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

# Google Sheets の設定
# スプレッドシートの名前。Google Drive上で表示される名前と一致させてください。
# 例: "MeetingSchedulerBot"
class Config:
    # 修正箇所: スプレッドシート名を "meeting_schedule_data" に変更
    SPREADSHEET_NAME = os.getenv("GOOGLE_SHEETS_SPREADSHEET_NAME", "meeting_schedule_data") 
    # 修正箇所: スケジュールシート名を "シート1" に変更
    SCHEDULE_WORKSHEET_NAME = os.getenv("GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME", "シート1")
    # 修正箇所: 参加者リストシート名を "シート2" に変更
    ATTENDEES_WORKSHEET_NAME = os.getenv("GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME", "シート2")

# セッション管理のための状態定義
class SessionState(Enum):
    NONE = 0 # 初期状態またはセッション終了状態

    # スケジュール登録フロー
    ASKING_TITLE = 1
    ASKING_DATE = 2
    ASKING_TIME = 3
    ASKING_LOCATION = 4
    ASKING_DETAIL = 5
    ASKING_DEADLINE = 6
    ASKING_DURATION = 7 # 所要時間の状態を追加

    # スケジュール削除フロー
    DELETING_SCHEDULE_DATE = 10
    DELETING_SCHEDULE_TITLE = 11
    AWAITING_DELETE_CONFIRMATION = 12

    # スケジュール編集フロー
    EDITING_SCHEDULE_DATE = 20
    EDITING_SCHEDULE_TITLE = 21
    SELECTING_EDIT_ITEM = 22
    ASKING_NEW_VALUE = 23

    # 出欠登録Q&Aフロー (新規追加または修正)
    ASKING_ATTENDANCE_INTENTION = 29 # 出欠登録の意向確認待ち状態 # ← 追加済みであることを確認
    ASKING_ATTENDANCE_TARGET_EVENT = 30 # どのイベントの出欠を登録するか尋ねる状態
    ASKING_ATTENDANCE_STATUS = 31 # 出欠（〇△×）を尋ねる状態
    # ASKING_REASON_IF_NO = 32 # ← この行を削除します
    AWAITING_ATTENDANCE_CONFIRMATION = 33 # 出欠登録の最終確認状態

    # 参加予定編集フロー (新規追加または修正)
    EDITING_ATTENDANCE_DATE = 40 # 編集したい参加予定の日付を尋ねる状態
    EDITING_ATTENDANCE_TITLE = 41 # 編集したい参加予定のタイトルを尋ねる状態
    CONFIRM_ATTENDANCE_ACTION = 42 # キャンセルするか備考編集するか尋ねる状態
    EDITING_ATTENDANCE_NOTE = 43 # 備考を尋ねる状態
    ASK_ANOTHER_ATTENDANCE_EDIT = 44 # 他に編集したい予定があるか尋ねる状態

