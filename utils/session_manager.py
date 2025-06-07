# utils/session_manager.py

from config import Config

_user_session_data = {}

def get_user_session_data(user_id: str, key: str = Config.SESSION_DATA_KEY):
    """
    ユーザーのセッションデータを取得します。
    """
    return _user_session_data.get(user_id, {}).get(key)

def set_user_session_data(user_id: str, key: str = Config.SESSION_DATA_KEY, data: dict = None):
    """
    ユーザーのセッションデータを設定または更新します。
    """
    if user_id not in _user_session_data:
        _user_session_data[user_id] = {}
    _user_session_data[user_id][key] = data

def delete_user_session_data(user_id: str, key: str = Config.SESSION_DATA_KEY):
    """
    ユーザーのセッションデータを削除します。
    """
    if user_id in _user_session_data and key in _user_session_data[user_id]:
        del _user_session_data[user_id][key]
    if user_id in _user_session_data and not _user_session_data[user_id]: # セッションデータが空になったらユーザーエントリも削除
        del _user_session_data[user_id]