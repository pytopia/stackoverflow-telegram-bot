# Template for Telegram Bot

Template to create a telegram bot in python.

## How to Run
1. Set your telegram bot token as environment variable `TELEGRAM_BOT_TOKEN`:
```
export TELEGRAM_BOT_TOKEN=<your_telegram_bot_token>
```

2. Add `src` to `PYTHONPATH`:
```
export PYTHONPATH=${PWD}
```

3. Run:
```
python src/run.py
```

**Note:** You need to set up your mongodb database first in `src/db.py`.

## UML Diagram
<img src="./uml.png" alt="UML Diagram" width="50%">

## User Journey
<img src="./user_journey.png" alt="User Journey" width="50%">
