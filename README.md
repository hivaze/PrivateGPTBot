## Приватный телеграм бот на основе ChatGPT

Бот с несколькими персонажами для доступа по вашему OpenAI ключу к API gpt-3.5-turbo (chatgpt). 
Умеет воспринимать картинки с помощью BLIP (но не документы, по крайней мере не все).

### Возможности
- Имеет вайтлист пользователей для ограниченного доступа, но может работать в глобальном режиме
- Имеет несколько настраиваемых персонажей (system prompt в ChatGPT)
- Умеет работать с длинной историей сообщений и большими сообщениями,
за счет адаптивного урезания истории, чтобы влезли новые сообщения
- Умеет работать с картинками. "Шутник" умеет создавать мемы по ним (примеры ниже)
- Все сообщения можно изменить, чтобы было удобнее запускать из коробки
- Можно запустить в Docker

Используемые фреймворки: `aiogram`, `openai`, `transformers` и `torch`. \
Полный список зависимостей (7 штук) в `requirements.txt`.

Все конфиги находятся в `resources/`.

Запуск после установки зависимостей и настройки просто: `python main.py`.

### TODO Roadmap
- ✔️ Адаптивное урезание истории
- ✔️ Добавление возможности воспринимать картинки (BLIP)
- ✔️ Возможность полной кастомизации всех сообщений
- ⏳ Реляционная БД пользователей
- ⏳ Возможность генерировать картинки
- ⏳ Возможность понимать голосовые сообщения
- ⏳ Возможность создавать своего персонажа в рамках сессии

### После /start и изначальные персонажи

Персонажи настраиваются в `resources/personalities.json` \
Некоторые сообщения можно поменять в `resources/messages.json`

![after_start.png](docs%2Fafter_start.png)

### Основная конфигурация

Выполнена в виде json файла, находится в `resources/config.json` 

```
{
  "OPENAI_KEY": "OPENAI_KEY",
  "TG_BOT_TOKEN": "TG_BOT_TOKEN",
  "last_messages_count": 8, <- use only 8 last message to save tokens
  "global_mode": false, <- will disable allowed_users section
  "allowed_users": [
    "hivaze"
  ],
  "append_tokens_count": false,
  "openai_api_retries": 3,
  "blip": {
    "use_large": true, <- use "Salesforce/blip-image-captioning-large" model or base
    "device": "cpu"
  },
  "blip_gpt_prompts": { <- prompts for GPT and BLIP connection
    "joker": "Create a joke like a meme about the image, it shows: {image_caption}. Try to be brief and post-ironic. Try to avoid starting with 'when you'. Используй русский язык.",
    "basic": "Imagine that I sent you a picture, it shows: {image_caption}. Используй русский язык.",
    "caption_message": "{prompt} В дополнение к картинке: {message}"
  },
  "generation_params": { <- params from OpenAI API
    "model": "gpt-3.5-turbo",
    "temperature": 0.8,
    "presence_penalty": 0.0,
    "max_tokens": 896,
    "n": 1,
    "top_p": 0.9
  }
}
```

### Пример работы шутника

Шутник старается шутить про все что угодно. Кроме того он умеет воспринимать картинки за счет BLIP и последующего перефраза описания картинки ChatGPT

![joker_example.png](docs%2Fjoker_example.png)

![image_joker_example_2.png](docs%2Fimage_joker_example_2.png)

![image_joker_example_1.png](docs%2Fimage_joker_example_1.png)

### Вид из терминала

Сообщения не логируются!

![terminal_view.png](docs%2Fterminal_view.png)