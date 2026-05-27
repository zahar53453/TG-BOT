# TG BOT

Telegram weather bot for airport chats.

## Local run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set environment variables from `.env.example`.
3. Start the bot:

```bash
python run_all.py
```

## Railway

This repo is prepared for Railway deploy from GitHub.

- Start command is defined in `railway.json`
- Required variables:
  - `BOT_TOKEN`
  - `METEOFRANCE_APPLICATION_ID`
  - `WUNDERGROUND_PWS_API_KEY`

The bot runs as a worker process and does not need a public domain.
