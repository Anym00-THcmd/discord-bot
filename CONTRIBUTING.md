# Contributing

## Local Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

## Checks

Before opening a pull request:

```bash
python -m compileall .
```

Do not commit `.env`, cookies, local databases, logs, or generated cache files.
