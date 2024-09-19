from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os
import traceback
import requests
from azure.core.credentials import AzureKeyCredential
from azure.ai.language.questionanswering import QuestionAnsweringClient
import time

def process_message(data):
    result = "Processed result here"
    user_id = data['events'][0]['source']['userId']
    
    push_message(user_id, result)

def push_message(user_id, message):
    headers = {
        'Authorization': f'Bearer {os.getenv("CHANNEL_ACCESS_TOKEN")}',
        'Content-Type': 'application/json'
    }
    payload = {
        'to': user_id,
        'messages': [{'type': 'text', 'text': message}]
    }
    requests.post('https://api.line.me/v2/bot/message/push', headers=headers, json=payload)

app = Flask(__name__)
static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

# Channel Access Token
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
# Channel Secret
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# New Question Answering system configuration
new_endpoint = os.getenv('NEW_END_POINT')
new_credential = AzureKeyCredential(os.getenv('NEW_AZURE_KEY'))
new_knowledge_base_project = os.getenv('NEW_PROJECT')
new_deployment = 'production'

# Old Question Answering system configuration
old_endpoint = os.getenv('OLD_END_POINT')
old_credential = AzureKeyCredential(os.getenv('OLD_AZURE_KEY'))
old_knowledge_base_project = os.getenv('OLD_PROJECT')
old_deployment = 'production'

def new_QA_response(text):
    try:
        client = QuestionAnsweringClient(new_endpoint, new_credential)
        with client:
            output = client.get_answers(
                question=text,
                project_name=new_knowledge_base_project,
                deployment_name=new_deployment
            )
        return output.answers[0].answer if output.answers else None
    except Exception as e:
        print(f"Error in new QA system: {e}")
        return None

def old_QA_response(text):
    try:
        client = QuestionAnsweringClient(old_endpoint, old_credential)
        with client:
            output = client.get_answers(
                question=text,
                project_name=old_knowledge_base_project,
                deployment_name=old_deployment
            )
        return output.answers[0].answer if output.answers else None
    except Exception as e:
        print(f"Error in old QA system: {e}")
        return None

# 監聽所有來自 /callback 的 Post Request
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 處理訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    user_id = event.source.user_id  # 取得使用者的 user_id

    try:
        # 第一次回覆
        line_bot_api.reply_message(event.reply_token, TextSendMessage(f"關於此訊息，找到的消息為:"))
    except Exception as e:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage("執行錯誤"))

    # 第二次回覆（使用 push_message）
    time.sleep(2)  # 模擬一些處理時間
    try:
        QA_answer_new = new_QA_response(msg)
        if QA_answer_new:
            push_message(user_id, f"行事曆: {QA_answer_new}")
        else:
            push_message(user_id, "行事曆: 目前查無此資料")
    except Exception as e:
        print(traceback.format_exc())
        push_message(user_id, "行事曆: 執行錯誤")

    # 第三次回覆（使用 push_message）
    time.sleep(2)  # 模擬一些處理時間
    try:
        QA_answer_old = old_QA_response(msg)
        if QA_answer_old:
            push_message(user_id, f"校園公告: {QA_answer_old}")
        else:
            push_message(user_id, "校園公告: 目前查無此資料")
    except Exception as e:
        print(traceback.format_exc())
        push_message(user_id, "校園公告: 執行錯誤")

@handler.add(PostbackEvent)
def handle_postback(event):
    print(event.postback.data)

@handler.add(MemberJoinedEvent)
def welcome(event):
    uid = event.joined.members[0].user_id
    gid = event.source.group_id
    profile = line_bot_api.get_group_member_profile(gid, uid)
    name = profile.display_name
    message = TextSendMessage(text=f'{name} 歡迎加入')
    line_bot_api.reply_message(event.reply_token, message)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
