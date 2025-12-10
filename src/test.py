import os

import requests
from dotenv import load_dotenv


def main():
    _ = load_dotenv()
    API_CHAT = f'Bearer {os.getenv("API_CHAT_GPT")}'
    URL = 'https://api.openai.com/v1/chat/completions'

    header = {'Authorization': API_CHAT}
    payload = {
        'model': 'gpt-5-nano',
        'messages': [
            {'role': 'user', 'content': 'qual o seu modelo?'},
        ],
    }

    response = requests.post(URL, json=payload, headers=header)

    print(response.text)
    pass


if __name__ == '__main__':
    main()
