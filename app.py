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

line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

new_endpoint = os.getenv('NEW_END_POINT')
new_credential = AzureKeyCredential(os.getenv('NEW_AZURE_KEY'))
new_knowledge_base_project = os.getenv('NEW_PROJECT')
new_deployment = 'production'

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

    # 先回應第一則訊息
    first_message = TextSendMessage(text=f"關於這個嘛，有個消息是:")

    # 先回應新 QA 系統的回答
    try:
        QA_answer_new = new_QA_response(msg)
        if QA_answer_new:
            second_message = TextSendMessage(text=f"☀️行事曆:\n\n{QA_answer_new}")
        else:
            second_message = TextSendMessage(text="☀️行事曆:\n\n目前查無此資料")
    except Exception as e:
        print(traceback.format_exc())
        second_message = TextSendMessage(text="☀️行事曆: 執行錯誤")

    # 隨後回應舊 QA 系統的回答
    try:
        QA_answer_old = old_QA_response(msg)
        if QA_answer_old:
            third_message = TextSendMessage(text=f"🌕校園公告:\n\n{QA_answer_old}")
        else:
            third_message = TextSendMessage(text="🌕校園公告:\n\n目前查無此資料")
    except Exception as e:
        print(traceback.format_exc())
        third_message = TextSendMessage(text="🌕校園公告: 執行錯誤")

    # 將三個訊息組合，使用reply_message一次性回應
    line_bot_api.reply_message(event.reply_token, [first_message, second_message, third_message])

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


