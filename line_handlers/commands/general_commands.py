# line_handlers/commands/general_commands.py

from linebot.models import TextSendMessage


def show_qna(reply_token, line_bot_api_messaging):
    """
    「スケジュール入力Q&A」コマンドの処理。
    """
    messages = [TextSendMessage(text='スケジュール入力に関するよくある質問と回答です。\n\n'
                                   'Q1: スケジュールはどのように登録しますか？\n'
                                   'A1: 「スケジュール登録」と入力後、BOTの指示に従って情報を入力してください。\n\n'
                                   'Q2: 登録したスケジュールはどこで確認できますか？\n'
                                   'A2: 「スケジュール一覧」と入力すると、登録済みのスケジュールが一覧で表示されます。\n\n'
                                   'Q3: 参加予定の変更や備考の追加はできますか？\n'
                                   'A3: 「参加予定編集」と入力後、BOTの指示に従って操作してください。')]
    line_bot_api_messaging.reply_message(reply_token, messages)
    print("DEBUG: Displayed general Q&A.")


def handle_unknown_command(user_message, reply_token, line_bot_api_messaging):
    """
    認識できないコマンドに対するデフォルト応答。
    """
    print(f"DEBUG: Unknown command received: '{user_message}'")
    messages = [TextSendMessage(text='認識できないコマンドです。メニューから選択するか、正しいコマンドを入力してください。')]
    line_bot_api_messaging.reply_message(reply_token, messages)

