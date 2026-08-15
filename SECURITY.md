# Security Policy

## Secrets

Never commit these files:

- `.env`
- `cookies.txt`
- `data/bot.db`
- files inside `data/`

The Discord token and YouTube cookies should be treated like passwords. If either is leaked, rotate it immediately.

## Supported Version

This project is intended as a small self-hosted bot. Keep `discord.py`, `yt-dlp`, and your VPS packages updated before reporting playback issues.

## Reporting

For a private server bot, report issues through your private repository or server admin channel. Do not paste bot tokens, cookies, or full `.env` contents into public issue trackers.

