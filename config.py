import os

class Config:
    # LINE Bot API設定
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

    # Google Sheets API設定
    GOOGLE_SHEETS_SPREADSHEET_NAME = os.getenv('GOOGLE_SHEETS_SPREADSHEET_NAME')
    GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME = os.getenv('GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME', 'スケジュール')
    GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME = os.getenv('GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME', '参加者')

    # Google Sheets 認証情報 (JSON文字列を環境変数から取得)
    # 本番環境ではKMSなどで暗号化することを推奨
    GOOGLE_SHEETS_CREDENTIALS = os.getenv('GOOGLE_SHEETS_CREDENTIALS')

    # デフォルト応答メッセージ
    DEFAULT_REPLY_MESSAGE = "認識できないコマンドです。メニューから選択するか、正しいコマンドを入力してください。"

    # 日時フォーマット
    DATETIME_FORMAT = '%Y/%m/%d %H:%M'
    DATE_FORMAT = '%Y/%m/%d'
    TIME_FORMAT = '%H:%M'

class SessionState:
    # 汎用状態
    NONE = "none" # 初期状態またはセッション終了状態

    # スケジュール登録関連の状態
    ASKING_SCHEDULE_DATE = "asking_schedule_date"
    ASKING_SCHEDULE_START_TIME = "asking_schedule_start_time"
    ASKING_SCHEDULE_TITLE = "asking_schedule_title"
    ASKING_SCHEDULE_LOCATION = "asking_schedule_location"
    ASKING_SCHEDULE_DETAIL = "asking_schedule_detail"
    ASKING_SCHEDULE_DEADLINE = "asking_schedule_deadline"
    ASKING_SCHEDULE_SCALE = "asking_schedule_scale"
    ASKING_FOR_ANOTHER_SCHEDULE_REGISTRATION = "asking_for_another_schedule_registration"
    ASKING_CONTINUE_ON_DUPLICATE_SCHEDULE = "asking_continue_on_duplicate_schedule"

    # スケジュール編集関連の状態
    ASKING_SCHEDULE_EDIT_DATE = "asking_schedule_edit_date"
    ASKING_SCHEDULE_EDIT_TITLE = "asking_schedule_edit_title"
    ASKING_SCHEDULE_EDIT_FIELD = "asking_schedule_edit_field"
    ASKING_SCHEDULE_EDIT_NEW_VALUE = "asking_schedule_edit_new_value"
    ASKING_FOR_ANOTHER_SCHEDULE_EDIT = "asking_for_another_schedule_edit"

    # スケジュール削除関連の状態
    ASKING_SCHEDULE_DELETE_DATE = "asking_schedule_delete_date"
    ASKING_SCHEDULE_DELETE_TITLE = "asking_schedule_delete_title"
    ASKING_CONFIRM_SCHEDULE_DELETE = "asking_confirm_schedule_delete"
    ASKING_FOR_NEXT_SCHEDULE_DELETION = "asking_for_next_schedule_deletion"


    # 参加予定登録Q&A関連の状態 (attendance_qna.py が使用)
    ASKING_ATTENDANCE_STATUS = "asking_attendance_status" # 出欠（〇△✕）を尋ねる
    ASKING_FOR_REMARKS_CONFIRMATION = "asking_for_remarks_confirmation" # 備考の有無を尋ねる
    ASKING_ATTENDANCE_REMARKS = "asking_attendance_remarks" # 備考内容を尋ねる


    # 参加予定登録関連の状態 (attendance_commands.py が使用)
    ASKING_ATTENDEE_REGISTRATION_DATE = "asking_attendee_registration_date"
    ASKING_ATTENDEE_REGISTRATION_TITLE = "asking_attendee_registration_title"
    ASKING_ATTENDEE_STATUS = "asking_attendee_status"
    ASKING_ATTENDEE_NOTES = "asking_attendee_notes"
    ASKING_CONFIRM_ATTENDEE_REGISTRATION = "asking_confirm_attendee_registration"
    ASKING_FOR_ANOTHER_ATTENDEE_REGISTRATION = "asking_for_another_attendee_registration"
    ASKING_ATTENDEE_REGISTRATION_CONFIRMATION = "asking_attendee_registration_confirmation" # message_processors.py のみで使用


    # 参加予定編集関連の状態 (attendance_commands.py が使用)
    ASKING_ATTENDEE_DATE = "asking_attendee_date"
    ASKING_ATTENDEE_TITLE = "asking_attendee_title"
    ASKING_ATTENDEE_CONFIRM_CANCEL = "asking_attendee_confirm_cancel" # キャンセル確認
    ASKING_ATTENDEE_EDIT_NOTES = "asking_attendee_edit_notes" # 備考編集
    ASKING_FOR_ANOTHER_ATTENDEE_EDIT = "asking_for_another_attendee_edit"


    _state_store = {} # {user_id: current_state_string}

    @classmethod
    def set_state(cls, user_id, state):
        cls._state_store[user_id] = state
        print(f"DEBUG: User {user_id} state changed to: {state}")

    @classmethod
    def get_state(cls, user_id):
        return cls._state_store.get(user_id, cls.NONE)

    @classmethod
    def clear_state(cls, user_id):
        if user_id in cls._state_store:
            del cls._state_store[user_id]
            print(f"DEBUG: User {user_id} state cleared.")

