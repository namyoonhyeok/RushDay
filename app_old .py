import json
import time
import traceback
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from requests.auth import HTTPBasicAuth
import requests

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
specific_channel_id = data.get('specific_channel_id')

# Slack 클라이언트 설정
slack_client = WebClient(token=slack_bot_token)
socket_client = SocketModeClient(app_token=slack_app_token, web_client=slack_client)

# Jira 이슈 생성 함수
def create_jira_issue(summary):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    issue_data = {
        "fields": {
            "project": {
                "key": jira_project_key
            },
            "summary": summary,
            "description": f"Slack 메시지로 생성된 이슈입니다: {summary}",
            "issuetype": {
                "name": "Task"
            }
        }
    }

    response = requests.post(
        f"{jira_url}/rest/api/3/issue",
        json=issue_data,
        headers=headers,
        auth=HTTPBasicAuth(jira_email, jira_api_token)
    )

    if response.status_code == 201:
        print("Jira 이슈 생성 완료!")
    else:
        print("Jira 이슈 생성 실패:", response.status_code, response.text)

# 메시지 및 reaction_added 이벤트 테스트 핸들러
def process_socket_mode_request(client: SocketModeClient, req: SocketModeRequest):
    print("Received request type:", req.type)
    
    # message 이벤트인지 확인
    if req.type == "events_api" and req.payload["event"]["type"] == "message":
        message_text = req.payload["event"].get("text", "")
        print("Message event detected")
        print("Message Text:", message_text)
        
        # Slack에 이벤트 수신 완료 응답 전송
        client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))

    # reaction_added 이벤트인지 확인
    elif req.type == "events_api" and req.payload["event"]["type"] == "reaction_added":
        reaction = req.payload["event"].get("reaction", "")
        channel_id = req.payload["event"]["item"].get("channel", "")
        message_ts = req.payload["event"]["item"].get("ts", "")
        
        print(f"Reaction added: {reaction} in channel {channel_id} on message {message_ts}")
        
        # 특정 채널과 이모티콘에 반응
        if channel_id == specific_channel_id and (reaction == "ticket" or reaction == "티켓"):
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

            # Jira에 이슈 생성
            create_jira_issue(message_text)
        
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