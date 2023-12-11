from openai import OpenAI
import os
from flask import Flask, request
from linebot import LineBotApi
from linebot.v3.webhook import WebhookHandler
from linebot.models import TextSendMessage
import json

app = Flask(__name__)

@app.route("/", methods=['POST'])
def linebot():
    # Get the request body as text
    body = request.get_data(as_text=True)

    # Parse the body asJSON
    json_data = json.loads(body)

    try:
        # Inintialize LineBot API and Webhook Handler
        line_bot_api = LineBotApi('YOUR_CHANNEL_ACCESS_TOKEN')
        handler = WebhookHandler('YOUR_CHANNEL_SECRET')

        # Get OpenAI API key from environment variables
        api_key = os.environ.get("OPENAI_API_KEY")
        client = OpenAI()
        
        # Get signature from request headers
        signature = request.headers['X-Line-Signature']

        # Handle the webhook events
        handler.handle(body, signature)

        # Extract reply token and user's message from the JSON data
        user_id = json_data['events'][0]['source']['userId']
        reply_token = json_data['events'][0]['replyToken']
        user_message = json_data['events'][0]['message']['text']

        # Check if the user have enough quota to ask question
        if checkUserMsgQuota(user_id):

            # Extract the first six characters of the message in lowercase
            ai_msg = user_message[:6].lower()
            reply_msg = ''

        # Check if the message starts with 'hi ai:
        if ai_msg == 'hi ai:':
            
            # Send the rest of the message to OpenAI for processing
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You're a humorous services assistant who can speak both English and Chinese(TW) fluently."},
                    {"role": "user", "content": f"{user_message[6:]}"}
                ],
                max_tokens=100
            )
            print(f"User asked: {user_message}")
            reply_msg = completion.choices[0].message.content
        else:
            # If not a special command, echo the user's message
            reply_msg = user_message

        # The user does not have enough quota to ask question
        else:
            reply_msg = "We're sorry, but you've reached the message limit of the day. Please ask again tomorrow."
        
        # Send the reply message back to the user
        text_message = TextSendMessage(text=reply_msg)
        line_bot_api.reply_message(reply_token,text_message)

    except Exception as e:
        # Print any exceptions for debugging purposes
        print(e)
    return 'OK'

def checkUserMsgQuota(user_id):

    # Read the JSON file
    with open('./userInfo.json', 'r') as json_file:

        # Load JSON data
        data = json.load(json_file)
        
        # Check if this user_id exist and have enough quota of msg to ask
        for user in data:
            if user.get("userId") == user_id:
                if user['quota'] == 0:
                    return False
                else:
                    # User have enough quota, quota-=1
                    userMsgQuotaDecreaseOne(data, user, user['quota'])
                    return True
                
        # Cannot find this user_id, then it is a new user.
        # Add this user to the JSON file
        addUser(data, user_id)
        return True

def addUser(json_data, user_id):
    # Add new user's userId to the JSON file, and set the quota to 49, because the user used 1 quota upon asking question.
    new_user = {"userId": f"{user_id}", "quota": 49}

    # Append the new user info to the bottom of the userInfo.json
    json_data.append(new_user)
    with open('./userInfo.json', 'w') as json_file:
        json.dump(json_data, json_file, indent=4)

    return 'OK'

def userMsgQuotaDecreaseOne(json_data, user, quota):
    
    # Update remain quota of the user
    quota -= 1
    user.update({"quota": quota})

    # Write the updated info to the ./userInfo.json
    with open('./userInfo.json', 'w') as json_file:
        json.dump(json_data, json_file, indent=4)

    return 'OK'


if __name__ == "__main__":
    # Run the Flask app
    app.run(debug=True)