from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os
import traceback
import requests
from azure.core.credentials import AzureKeyCredential
from azure.ai.language.questionanswering import QuestionAnsweringClient

def process_message(data):
    # 假設你處理完畢後需要推送結果
    result = "Processed result here"
    user_id = data['events'][0]['source']['userId']
    
    # 推送結果到用戶
    push_message(user_id, result)

def push_message(user_id, message):
    headers = {
        'Authorization': 'Bearer YOUR_CHANNEL_ACCESS_TOKEN',
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
    client = QuestionAnsweringClient(new_endpoint, new_credential)
    with client:
        output = client.get_answers(
            question=text,
            project_name=new_knowledge_base_project,
            deployment_name=new_deployment
        )
    return output.answers[0].answer if output.answers else None

def old_QA_response(text):
    client = QuestionAnsweringClient(old_endpoint, old_credential)
    with client:
        output = client.get_answers(
            question=text,
            project_name=old_knowledge_base_project,
            deployment_name=old_deployment
        )
    return output.answers[0].answer if output.answers else None

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
    try:
            # 使用新的 Question Answering 系統
        QA_answer = new_QA_response(msg)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(QA_answer))
    except:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage('QA Error'))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    try:
            # 使用新的 Question Answering 系統
        QA_answer = old_QA_response(msg)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(QA_answer))
    except:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage('QA Error'))


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
