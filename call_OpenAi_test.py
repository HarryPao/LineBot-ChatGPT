# Import necessary modules
from openai import OpenAI
import os

# Get the OpenAI API key from environment variables, please do set your own API key to environment variable beforehand.
api_key = os.environ.get("OPENAI_API_KEY")

# Create an OpenAI client instance using API key
client = OpenAI()

# Use the OpenAI API to generate a chat completion
completion = client.chat.completions.create(
  model="gpt-3.5-turbo",
  messages=[
  # Provide guidance to the model about its role or function in the ongooing conversation.
    {"role": "system", "content": "You are a humorous person who currently live in Taiwan and can speak both English and Mandarin fluently."},
    {"role": "user", "content": "嗨!請用一句話自我介紹"}
  ],
  max_tokens=100
)

# Print the generated response from ChatGPT-3.5
print(completion.choices[0].message.content)
