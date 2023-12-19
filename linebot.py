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

# Initialize LineBot API
line_bot_api= LineBotApi(os.environ['CHANNEL_ACCESS_TOKEN'])

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

        with file_lock:
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

def checkUserModeStatus(user_id):
    """Check userInfo.json to if user is in AI mode."""

    # Read the JSON file
    with open('./userInfo.json', 'r') as json_file:

        # Load JSON data
        data = json.load(json_file)

        # Check user's mode status
        for user in data:
            if user.get("userId") == user_id:
                return user['AImode']

def enterAImode(user_id):
    """Turn user's AImode status into active(true)."""

    # Read the JSON file
    with open('./userInfo.json', 'r') as json_file:

        # Load JSON data
        data = json.load(json_file)

        # Search the user info and update his/her AImode into active(true).
        for user in data:
            if user.get("userId") == user_id:
                user.update({"AImode": True})
                break
            
    # Write the file
    with open('./userInfo.json', 'w') as json_file:
        json.dump(data, json_file, indent=4)

def updateLastAImsgTime(user_id):
    """Update user's lastAImsgTime in userInfo.json to the current time."""

    # Read the JSON file
    with open('./userInfo.json', 'r') as json_file:

        #Load JSON data
        data = json.load(json_file)

        # Search the user info and update his/her AImode into active(true).
        for user in data:
            if user.get("userId") == user_id:
                user.update({"lastAImsgTime": time.time()})
                break

    # Write the file
    with open('./userInfo.json', 'w') as json_file:
        json.dump(data, json_file, indent=4)

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

def check_idle_users(exit_event):
    """Periodically check idle users and sends notifications if their idle time exceeds 5 mins"""

    # Periodically check idle users and send notifications
    while not exit_event.is_set():
        with file_lock:
            # Check if there are any scheduled tasks that need to be executed
            schedule.run_pending()

            with open('./userInfo.json', 'r') as json_file:

                # Load JSON data
                data = json.load(json_file)

                currunt_time = time.time()
                for user in data:

                    # Only deactivates AI mode and sends notification if the user is in AI mode
                    if checkUserModeStatus(user['userId']):

                        # Calculate user's idle time, and see if the user's idle time exceed 5 mins.
                        idle_time = currunt_time - user['lastAImsgTime']
                        if idle_time > 60:
                            exitAImodeNotification(user['userId'])
                            exitAImode(user['userId'])
        time.sleep(5)

def exitAImodeNotification(user_id):
    """Notify specific user to let him/her know the AI customer service is signing off."""

    # Create a TextSendMessage object with the message content
    notificationMsg = TextSendMessage(text = "Dear customer, hello! As you have been idle for more than 5 minutes, the AI customer service is now signing off. If you still need the services of our AI customer service, please use 'hi ai' to wake me up. Looking forward to continuing to serve you!")
    
    # Use the push_message method to send the message
    line_bot_api.push_message(user_id, messages=notificationMsg)

def exitAImode(user_id):
    """Turn user's AImode status into deactive(false)."""

    # Read the JSON file
    with open('./userInfo.json', 'r') as json_file:

        # Load JSON data
        data = json.load(json_file)

        # Search the user info and update his/her AImode into deactive(false).
        for user in data:
            if user.get("userId") == user_id:
                user.update({"AImode": False})
                break

    # Write the file
    with open('./userInfo.json', 'w') as json_file:
        json.dump(data, json_file, indent=4)

def reset_status():
    """Load the userInfo.json, reset the "quota" to 50 of every user, and save it back."""
    
    with open("./userInfo.json", 'r') as json_file:
        data = json.load(json_file)

        # Reset every users' quota of messages to 50
        for user in data:
            user['quota'] = 50

    with open("./userInfo.json", 'w') as json_file:
        json.dump(data, json_file, indent=4)

def scheduled_reset(exit_event):
    """Reset users' quota to 50 upon everyday midnight """


    while not exit_event.is_set():
        with file_lock:
            # Check if there are any scheduled tasks that need to be executed
            schedule.run_pending()
            schedule.every().day.at("00:00").do(reset_status)

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

    # Start a thread for consistently check users' idle time
    check_idle_thread = threading.Thread(target=check_idle_users, args=(exit_event,))
    check_idle_thread.start()

    try:
        # Run the Flask app
        app.run(debug=True)

    except KeyboardInterrupt:
        # Ctrl+c is pressed, set the exit event and wait for the thread to exit
        exit_event.set()
        schedule_thread.join()
        check_idle_thread.join()

if __name__ == "__main__":

    main()

