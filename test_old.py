import json
import time
import traceback
import requests
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from requests.auth import HTTPBasicAuth

# JSON 파일에서 설정 불러오기
json_path = '/Users/yujuyoung/Desktop/BRANCHIFY_BOT/Fy_bot/applications_info.json'
with open(json_path, 'r') as file:
    data = json.load(file)

slack_bot_token = data.get('slack_bot_token')
slack_app_token = data.get('slack_app_token')
jira_email = data.get('jira_email')
jira_api_token = data.get('jira_api_token')
jira_url = data.get('jira_url')
jira_project_key = data.get('jira_project_key')
slack_channel_id = data.get('slack_channel_id') 

# Slack 클라이언트 설정
slack_client = WebClient(token=slack_bot_token)
socket_client = SocketModeClient(app_token=slack_app_token, web_client=slack_client)

### 1. Jira 티켓 생성 함수
def _create_ticket(issue_title, channel_id, thread_ts, ticket_type):
    slack_thread_link = f"{data.get('slack_server')}/archives/{channel_id}/p{thread_ts.replace('.', '')}"
    parent_message = "No thread message"  # 추가적인 설명이 필요하면 여기에 할당
    stripped_command = ticket_type.lower()

    if ticket_type in ["Story", "Task", "Epic"]:
        description = (
            f"{{panel:borderStyle=dashed|borderColor=#00b|titleBGColor=#d2e0fc|bgColor=#f0f4ff}}"
            f"This ticket is created as a result of the following Slack thread and its content is automatically copied here: {slack_thread_link}{{panel}}\n\n"
            f"*The automatically populated description from the original Slack thread:*\n\n{parent_message}"
        )
    else:
        description = (
            f"{{panel:borderStyle=dashed|borderColor=#00b|titleBGColor=#d2e0fc|bgColor=#f0f4ff}}"
            f"This ticket is created as a result of the following Slack thread and its content is automatically copied here: {slack_thread_link}{{panel}}\n\n"
            f"{{panel:title=Quick Reminder|borderStyle=dashed|borderColor=#ccc|titleBGColor=#F7D6C1|bgColor=#FFFFCE}}"
            f"Please ensure that the bug description adheres to the guidelines.{{panel}}\n\n"
            f"*The automatically populated description from the original Slack thread:*\n\n{parent_message}"
        )

    # Jira 티켓 생성 요청
    response = requests.post(
        f"{data.get('jira_url')}/rest/api/2/issue",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "fields": {
                "project": {
                    "key": data.get('jira_project_key')
                },
                "summary": issue_title,
                "description": description,
                "issuetype": {
                    "name": ticket_type
                },
                "labels": ["SlackBot"]
            }
        }),
        auth=HTTPBasicAuth(data.get('jira_email'), data.get('jira_api_token'))
    )

    if response.status_code == 201:
        issue_key = response.json().get("key")
        return f"{data.get('jira_url')}/browse/{issue_key}"
    else:
        print(f"Failed to create issue: {response.status_code}, {response.text}")
        return None
    

### 2. reaction_added 이벤트를 처리하여 메시지를 가져오는 함수
def handle_reaction_added(event):
    reaction = event.get("reaction")
    channel_id = event.get("item", {}).get("channel")
    message_ts = event.get("item", {}).get("ts")

    print(f"Reaction added: {reaction} in channel {channel_id} on message {message_ts}")
    
    # 특정 채널과 이모티콘 반응 확인
    if channel_id == slack_channel_id and (reaction == "ticket" or reaction == "티켓"):
        print("Matched specific channel and reaction.")

        # 메시지 가져오기
        result = slack_client.conversations_history(
            channel=channel_id,
            latest=message_ts,
            inclusive=True,
            limit=1
        )
        message_text = result["messages"][0]["text"]
        print(f"Message Text for Jira Issue: {message_text}")
        
        return message_text  # 메시지 텍스트 반환
    return None

#### 3. reaction_added 이벤트가 발생하면 자동으로 Jira 티켓을 생성하는 함수
def process_socket_mode_request(client: SocketModeClient, req: SocketModeRequest):
    print("Received request type:", req.type)
    
    # reaction_added 이벤트인지 확인
    if req.type == "events_api" and req.payload["event"]["type"] == "reaction_added":
        # 이벤트 데이터에서 필요한 정보 가져오기
        event_data = req.payload["event"]
        channel_id = event_data["item"]["channel"]
        thread_ts = event_data["item"]["ts"]

        # reaction 추가된 메시지의 텍스트 가져오기
        response = slack_client.conversations_history(channel=channel_id, latest=thread_ts, limit=1, inclusive=True)
        if response["ok"] and response["messages"]:
            message_text = response["messages"][0]["text"]
            
            # 메시지가 있을 경우 Jira 이슈 생성
            if message_text:
                issue_url = _create_ticket(message_text, channel_id, thread_ts, "Task")
                
                # 생성된 티켓 URL을 Slack에 회신
                if issue_url:
                    slack_client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts,
                        text=f"Jira 티켓이 생성되었습니다: {issue_url}"
                    )
        
        # Slack에 이벤트 수신 완료 응답 전송
        client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
        
# 이벤트 리스너에 핸들러 추가
socket_client.socket_mode_request_listeners.append(process_socket_mode_request)

# SocketMode 시작
if __name__ == "__main__":
    try:
        print("Connecting to Slack...")
        socket_client.connect()
        print("Connected to Slack")

        # 연결을 유지하기 위해 무한 루프 실행
        while True:
            time.sleep(1)

    except Exception as e:
        print("An error occurred:", e)
        traceback.print_exc()  # 예외의 전체 스택 추적 출력