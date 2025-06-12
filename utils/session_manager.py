# utils/session_manager.py

import json

# ユーザーごとのセッションデータを保持する辞書
# {user_id: {data_key: data_value, ...}}
_session_data_store = {}

def get_user_session_data(user_id):
    """
    指定されたユーザーIDのセッションデータを取得します。
    データが見つからない場合はNoneを返します。
    """
    return _session_data_store.get(user_id)

def set_user_session_data(user_id, data):
    """
    指定されたユーザーIDのセッションデータを設定します。
    """
    _session_data_store[user_id] = data

def delete_user_session_data(user_id):
    """
    指定されたユーザーIDのセッションデータを削除します。
    """
    if user_id in _session_data_store:
        del _session_data_store[user_id]

def clear_all_session_data():
    """
    全てのセッションデータをクリアします。（テストやデバッグ用）
    """
    _session_data_store.clear()