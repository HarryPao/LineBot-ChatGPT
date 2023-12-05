from openai import OpenAI
import os
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import json

app = Flask(__name__)

@app.route("/", methods=['POST'])
def linebot():
    # Get the request body as text
    body = request.get_data(as_text=True)

    # Parse the body asJSON
    json_data = json.loads(body)
    #print(json_data)

    try:
        # Inintialize LineBot API and Webhook Handler
        line_bot_api = LineBotApi('Your Own Channel Access Token')
        handler = WebhookHandler('Your Own Channel Secret')

        # Get signature from request headers
        signature = request.headers['X-Line-Signature']

        # Handle the webhook events
        handler.handle(body, signature)

        # Extract reply token and user's message from the JSON data
        reply_token = json_data['events'][0]['replyToken']
        user_message = json_data['events'][0]['message']['text']

        # Extract the first six characters of the message in lowercase
        ai_msg = user_message[:6].lower()
        reply_msg = ''

        # Get OpenAI API key from environment variables
        api_key = os.environ.get("OPENAI_API_KEY")
        client = OpenAI()

        # Check if the message starts with 'hi ai:
        if ai_msg == 'hi ai:':
            
            # Send the rest of the message to OpenAI for processing
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You're a humorous services assistant who can speak both English and Chinese(TW) fluently."},
                    {"role": "user", "content": user_message[6:]}
                ],
                max_tokens=100
            )
            print(f"User asked: {user_message}")
            reply_msg = completion.choices[0].message.content
        else:
            # If not a special command, echo the user's message
            reply_msg = user_message

        # Send the reply message back to the user
        text_message = TextSendMessage(text=reply_msg)
        line_bot_api.reply_message(reply_token,text_message)

    except Exception as e:
        # Print any exceptions for debugging purposes
        print(e)
    return 'OK'

if __name__ == "__main__":
    # Run the Flask app
    app.run()