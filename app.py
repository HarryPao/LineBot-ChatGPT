# Standard Library Imports
import os
import json
import threading
import time
from datetime import datetime, timedelta
import logging

# Third-Party Imports
from flask import Flask, request
from linebot import LineBotApi
from linebot.v3.webhook import WebhookHandler
from linebot.models import TextSendMessage
import schedule
import requests

# Local Imports
from db_module.db_operations import PostgreSQLHandler

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize LineBot API
line_bot_api= LineBotApi(os.environ['CHANNEL_ACCESS_TOKEN'])

# Initialize the PostgreSQLHandler
# db_handler = PostgreSQLHandler(
#     dbname='YOUR_DB_NAME',
#     user='YOUR_DB_USER',
#     password='YOUR_DB_PWD',
#     host='YOUR_DB_HOST',
#     port='YOUR_DB_SERVER_PORT' # Default PostgreSQL port
# )
DATABASE_URL = os.environ['DATABASE_URL']
db_handler = PostgreSQLHandler(DATABASE_URL)

@app.route("/", methods=['POST'])
def linebot():
    """This function would be ran upon there is POST request from webhook."""

    # Get the request body as text
    body = request.get_data(as_text=True)

    # Parse the body asJSON
    json_data = json.loads(body)

    try:
        # Inintialize Webhook Handler
        handler = WebhookHandler(os.environ['CHANNEL_SECRET'])
        
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
        if user_message[:5].lower() == 'hi ai' or checkUserModeStatus(user_id):

            # Check if the user have enough quota to ask question
            if checkUserMsgQuota(user_id, user_name):

                # Enter AI mode if the message starts with 'hi ai'.(Assuming that the user use 'hi ai' to enter AI mode)
                if user_message[:5].lower() == 'hi ai':
                    enterAImode(user_id)

                # Record last msg time
                updateLastAImsgTime(user_id)

                # Redirect the question to chatPDF
                reply_msg = askChatPDF(user_message)

            # The user does not have enough quota to ask question
            else:
                reply_msg = "很抱歉，由於您已達到每日詢問AI客服的次數上限:50次/日，AI客服將先行告退。您可以等待明日繼續詢問或是聯絡CRESTDiving客服專線，謝謝！"
                exitAImode(user_id)
                
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

    selected_data = db_handler.select_data('users', condition=f"userid = '{user_id}'")

    if selected_data != []:
        userName = selected_data[0][1]
        userQuota = selected_data[0][3]

        if userName != user_name:
            modifyUserName(user_id, user_name)

        if userQuota == 0:
            return False
        else:
            userMsgQuotaDecreaseOne(selected_data)
            return True
    
    else:
        # Cannot find this user_id, then it is a new user,
        # Add this user to the DB table
        addUser(user_id, user_name)
        return True

def modifyUserName(user_id, user_name):
    """Modify user's profile name (displayed name) in DB"""

    update_condition = f"userid = '{user_id}'"
    update_data = {'username': user_name}
    db_handler.update_data('users', update_data, update_condition)

def addUser(user_id, user_name):
    """Add the new user to DB, and set the quota to 49,
    because the user would use 1 quota upon asking question."""

    data_to_insert = {'userid': user_id, 'username': user_name, 'quota': 49}
    db_handler.insert_data('users', data_to_insert)

def userMsgQuotaDecreaseOne(select_data):
    """Decrease user's message quota by 1"""

    userId = select_data[0][2]
    userQuota = select_data[0][3]
    userQuota -= 1
    
    update_condition = f"userid ='{userId}'"
    update_data = {'quota': userQuota}
    db_handler.update_data('users', update_data, update_condition)

def checkUserModeStatus(user_id):
    """See if the user is in AI-mode"""

    selected_data = db_handler.select_data('users', condition=f"userid = '{user_id}'")
    userAImode = selected_data[0][4]
    return userAImode

def enterAImode(user_id):
    """Turn the user's AImode status into active(true)."""

    update_condition = f"userid = '{user_id}'"
    update_data = {'aimode': True}
    db_handler.update_data('users', update_data, update_condition)

def updateLastAImsgTime(user_id):
    """Update the user's lastAImsgTime to the current time."""

    update_condition = f"userid = '{user_id}'"
    update_data = {'lastaimsgtime': time.time()}
    db_handler.update_data('users', update_data, update_condition)

def askChatPDF(user_message):
    """Call chatPDF API to ask questions."""

    CHATPDF_API_KEY = os.environ['CHATPDF_API_KEY']
    CHATPDF_FILE_SOURCE = os.environ['CHATPDF_FILE_SOURCE']
    # Send the user_message to chatPDF for processing
    headers = {
        'x-api-key': f"{CHATPDF_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        'sourceId': f"{CHATPDF_FILE_SOURCE}",
        'messages': [
            {
                'role': "user",
                'content': f"{user_message}",
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

def check_idle_user(exit_event):
    """Periodically check idle users and sends notifications if their idle time exceeds 5 mins"""
    # Don't know why this while loop was executed twice every 5 sec,

    # Periodically check idle users and send notifications
    while not exit_event.is_set():

        # Check if there are any scheduled tasks that need to be executed
        schedule.run_pending()
        current_time = time.time()

        users = db_handler.select_data('users', columns=['username', 'userid', 'aimode', 'lastaimsgtime'])
        
        for user in users:
            userId = user[1]
            userLastAImsgTime = user[3]

            # Only deactivate AI-mode and sends notification if the user is in AI-mode.
            if checkUserModeStatus(userId):

                # Calculate user's idle time, and see if the user's idle time exceed 5 mins.
                idle_time = current_time - userLastAImsgTime
                if idle_time > 300:
                    exitAImodeNotification(userId)
                    exitAImode(userId)

        time.sleep(5)

def exitAImodeNotification(user_id):
    """Notify specific user to let him/her know the AI customer service is signing off."""

    # Create a TextSendMessage object with the message content
    notificationMsg = TextSendMessage(text = "親愛的客戶您好，由於您已超過5分鐘未互動，AI客服將先行告退~若需要AI客服的服務，請再次以'Hi ai'喚醒AI哦")
    
    # Use the push_message method to send the message
    line_bot_api.push_message(user_id, messages=notificationMsg)

def exitAImode(user_id):
    """Turn user's AImode status into passive(false)."""

    update_condition = f"userid = '{user_id}'"
    update_data = {'aimode': False}
    db_handler.update_data('users', update_data, update_condition)

def reset_status():
    """Load the userInfo.json, reset the "quota" to 50 of every user, and save it back."""

    update_condition = "True"
    update_data = {"quota": 50}
    db_handler.update_data('users', update_data, update_condition)

def scheduled_reset(exit_event):
    """Reset users' quota to 50 upon everyday midnight """

    while not exit_event.is_set():
        # Check if there are any scheduled tasks that need to be executed
        schedule.run_pending()
        schedule.every().day.at("00:00").do(reset_status)

        # Introduces a small delay of 1 sec between iterations of the loop, 
        # preventing the loop from consuming excessive CPU resources
        time.sleep(30)

def main():
    """Ran as a background task and continuously check the time
     to check if resetting users' quota of message is needed.
     Also continuously checking users' idle time and deactivate AImode when meeded"""

    # Create an Event to  signal the thread to exit.(Upon Ctrl+c is pressed)
    exit_event = threading.Event()
    try:
        # Start a thread for the scheduled task
        schedule_thread = threading.Thread(target=scheduled_reset, args=(exit_event,))
        schedule_thread.start()

        # Start a thread for consistently check users' idle time
        check_idle_thread = threading.Thread(target=check_idle_user, args=(exit_event,))
        check_idle_thread.start()

    except KeyboardInterrupt:
        # Ctrl+c is pressed, set the exit event for threads to exit gracefully
        exit_event.set()

        # Wait for the threads to exit
        schedule_thread.join()
        check_idle_thread.join()

        # Close the database connection
        db_handler.close_connection()

if __name__ == "__main__":
    # When running this Flask app in development environment, this block would be ran

    # Run the Flask app
    app.run(debug=True)
    main()

else:
    # When running this Flask app on Heroku with Gunicorn, this block would be ran
    # Gunicorn would start the Flask app automatically, no need to explicitly run app here.
    main()