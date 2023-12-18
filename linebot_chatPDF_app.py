import os
from flask import Flask, request
from linebot import LineBotApi
from linebot.v3.webhook import WebhookHandler
from linebot.models import TextSendMessage
import json
import threading
import time
from datetime import datetime, timedelta
import schedule
import requests

app = Flask(__name__)

# Global lock to synchronize file access
file_lock = threading.Lock()

@app.route("/", methods=['POST'])
def linebot():
    """This function would be ran upon there is POST request from webhook."""

    # Get the request body as text
    body = request.get_data(as_text=True)

    # Parse the body asJSON
    json_data = json.loads(body)

    try:
        # Inintialize LineBot API and Webhook Handler
        line_bot_api = LineBotApi('YOUR_CHANNEL_ACCESS_TOKEN')
        handler = WebhookHandler('YOUR_CHANNEL_SECRET')
        
        # Get signature from request headers
        signature = request.headers['X-Line-Signature']

        # Handle the webhook events
        handler.handle(body, signature)

        # Extract reply token and user's message from the JSON data
        user_id = json_data['events'][0]['source']['userId']
        reply_token = json_data['events'][0]['replyToken']
        user_message = json_data['events'][0]['message']['text']
       # Use user_id to get the profile of the user
        profile = line_bot_api.get_profile(user_id)
        user_name = profile.display_name

        # Check if the message starts with 'hi ai:, if it does, enter AI mode.
        if user_message[:6].lower() == 'hi ai':

            # Check if the user have enough quota to ask question
            if checkUserMsgQuota(user_id, user_name):
                
                # Enter AI mode -> record status: idle_time

                # Redirect the question to chatPDF
                reply_msg = askChatPDF(user_message)

            # The user does not have enough quota to ask question
            else:
                reply_msg = "We're sorry, but you've reached the message limit of the day. Please ask again tomorrow."

        # If not a special command, echo the user's message
        # Use tradtional linebot mode
        else:
            reply_msg = user_message
        
        # Send the reply message back to the user
        text_message = TextSendMessage(text=reply_msg)
        line_bot_api.reply_message(reply_token,text_message)

    except Exception as e:
        # Print any exceptions for debugging purposes
        print(e)
    return 'OK'

def checkUserMsgQuota(user_id, user_name):
    """First check if user has change his/her profile name (display name), if he/she has, modify it in userInfo.json.
    Then, check if the userId exists and has enough quota of messages to ask question.
    If the user has enough quota, return true to enable asking chatPDF question.
    If the user has no quota, return false to reject the user from asking.
    If the user is a new user to this LineBot, add his/her  userId to the userInfo.json, and return ture to enable asking question."""
    
    # Acquire the lock before reading/modifying the file
    with file_lock:

        # Read the JSON file
        with open('./userInfo.json', 'r') as json_file:

            # Load JSON data
            data = json.load(json_file)
            
            # Check if this user_id exists and has enough quota of messages to ask
            for user in data:
                if user.get("userId") == user_id:

                    # Check if this user has modified his/her profile name(display name); if he/her had, modify in userInfo.json
                    if user['userName'] != user_name:
                        modifyUserName(data, user, user_name)

                    if user['quota'] == 0:
                        return False
                    else:
                        # User have enough quota, quota-=1
                        userMsgQuotaDecreaseOne(data, user, user['quota'])
                        return True
                    
            # Cannot find this user_id, then it is a new user.
            # Add this user to the JSON file
            addUser(data, user_id, user_name)
            return True
        
    # Automatically release the lock after this section been executed

def modifyUserName(json_data, user, user_name):
    """Modify user's profile name (display name) in userInfo.json."""

    # Update the old user name to new user name
    user.update({"userName": user_name})

    # Write the updated info to the ./userInfo.json
    with open('./userInfo.json', 'w') as json_file:
        json.dump(json_data, json_file, indent=4)

    return 'OK'

def addUser(json_data, user_id, user_name):
    """Add the userId of the new user to the userInfo.json, and set the quota to 49,
    because the user would use 1 quota upon asking question."""
    
    # Set the info of new_user
    new_user = {"userName": f"{user_name}", "userId": f"{user_id}", "quota": 49}

    # Append the new user info to the bottom of the userInfo.json
    json_data.append(new_user)
    with open('./userInfo.json', 'w') as json_file:
        json.dump(json_data, json_file, indent=4)

    return 'OK'

def userMsgQuotaDecreaseOne(json_data, user, quota):
    """Decrease the quota of message of a specific user."""

    # Update remain quota of the user
    quota -= 1
    user.update({"quota": quota})

    # Write the updated info to the ./userInfo.json
    with open('./userInfo.json', 'w') as json_file:
        json.dump(json_data, json_file, indent=4)

    return 'OK'

def askChatPDF(user_message):
    """Call chatPDF API to ask questions."""

    # Send the user_message to chatPDF for processing
    headers = {
        'x-api-key': 'sec_EIk82OYktur67w3RUJRjZTtcbKbaaZrV',
        "Content-Type": "application/json",
    }

    data = {
        'sourceId': "cha_f1jeDgt6Gmbdc9pFx6p9O",
        'messages': [
            {
                'role': "user",
                'content': f"{user_message[6:]}",
            }
        ]
    }

    response = requests.post(
        'https://api.chatpdf.com/v1/chats/message', headers=headers, json=data
    )
    if response.status_code == 200:
        response_msg = response.json()['content']
    else:
        response_msg = "Sorry, it seems that there is something wrong with the AI right now. Please ask AI later, thank you."
    
    return response_msg

def reset_status():
    """Load the userInfo.json, reset the "quota" to 50 of every user, and save it back."""
    
    # Acquire the lock
    with file_lock:
        
        with open("./userInfo.json", 'r') as json_file:
            data = json.load(json_file)

            # Reset every users' quota of messages to 50
            for user in data:
                user['quota'] = 50
    # Release the lock

    # Acquire the lock
    with file_lock:

        with open("./userInfo.json", 'w') as json_file:
            json.dump(data, json_file, indent=4)
    # Release the lock after writing to the file       

def scheduled_reset(exit_event):
    """Reset users' quota to 50 upon everyday midnight """
    schedule.every().day.at("00:00").do(reset_status)

    while not exit_event.is_set():
        # Check if there are any scheduled tasks that need to be executed
        schedule.run_pending()

        # Introduces a small delay of 1 sec between iterations of the loop, 
        # preventing the loop from consuming excessive CPU resources
        time.sleep(30)

def main():
    """Ran as a background task and continuously check the time
     to check if resetting users' quota of message is needed."""
    
    # Create an Event to  signal the thread to exit.(Upon Ctrl+c is pressed)
    exit_event = threading.Event()

    # Start a thread for the scheduled task
    schedule_thread = threading.Thread(target=scheduled_reset, args=(exit_event,))
    schedule_thread.start()

    try:
        # Run the Flask app
        app.run(debug=True)

    except KeyboardInterrupt:
        # Ctrl+c is pressed, set the exit event and wait for the thread to exit
        exit_event.set()
        schedule_thread.join()

if __name__ == "__main__":

    main()

