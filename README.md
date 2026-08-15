# Discord Bot

A self-hosted Python Discord bot for VPS deployment. It uses `discord.py`, local SQLite, FFmpeg, and `yt-dlp` for music playback.

No external database server is required. On first start, the bot creates `data/`, `data/bot.db`, and all required SQLite tables automatically.

## Features

- Welcome embed for new members.
- Music commands with queue support.
- YouTube links, YouTube search, and best-effort Spotify link handling.
- Local SQLite stats database.
- Temporary voice rooms.
- Starboard.
- XP, levels, profiles, and leaderboard.
- Achievements.
- Server stats.
- Fun commands.
- Moderation commands and moderation logging.
- systemd service sample for Ubuntu VPS.

## Commands

Music:

```text
!play <youtube_url | spotify_url | search text>
!pause
!resume
!skip
!stop
!queue
!nowplaying
!volume <0-150>
!shuffle
!remove <queue_number>
!clear
```

Server:

```text
!profile [member]
!serverstats
!leaderboard
!achievements [member]
!temproom [name]
```

Fun:

```text
!coinflip
!roll [sides]
!8ball <question>
!choose <options>
!rate <thing>
!ship <first> <second>
```

Moderation:

```text
!purge <1-100>
!warn <member> [reason]
!mute <member> [reason]
!unmute <member> [reason]
!kick <member> [reason]
!ban <member> [reason]
```

Moderation commands use Discord permissions. Normal members cannot run them unless they have the required Discord permission.

## Requirements

- Python 3.11 or newer.
- FFmpeg.
- A Discord bot token.
- Discord privileged intents enabled:
  - Server Members Intent
  - Message Content Intent
- For reliable YouTube playback on VPS:
  - latest `yt-dlp[default]`
  - Deno installed for YouTube JavaScript challenge solving
  - optional `cookies.txt` when YouTube blocks the VPS IP

## Discord Developer Portal Setup

1. Open the Discord Developer Portal.
2. Create an application.
3. Go to **Bot** and create a bot.
4. Copy the bot token. Keep it private.
5. Enable privileged gateway intents:
   - **Server Members Intent**
   - **Message Content Intent**
6. Go to **OAuth2 > URL Generator**.
7. Select scope:
   - `bot`
8. Select permissions:
   - Send Messages
   - Embed Links
   - Read Message History
   - Add Reactions
   - Connect
   - Speak
   - Move Members
   - Manage Channels
   - Manage Messages
   - Moderate Members
   - Kick Members
   - Ban Members
9. Open the generated invite URL and add the bot to your server.

## Local Setup

```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg
```

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python bot.py
```

In `.env`, set:

```env
DISCORD_TOKEN=your_real_token_here
```

## Configuration

 `DISCORD_TOKEN``WELCOME_CHANNEL_ID=` is required. Set `MUSIC_VOICE_CHANNEL_ID=` blank if the bot should join whichever voice channel the caller is currently using.


```env
WELCOME_CHANNEL_ID=
MUSIC_VOICE_CHANNEL_ID=
```



Common optional settings:

```env
COMMAND_PREFIX=!
DATABASE_PATH=data/bot.db
STARBOARD_CHANNEL_ID=
MOD_LOG_CHANNEL_ID=
TEMP_VOICE_LOBBY_ID=
TEMP_VOICE_CATEGORY_ID=
STARBOARD_THRESHOLD=5
YTDLP_COOKIES_FILE=
YTDLP_JS_RUNTIMES=deno
YTDLP_REMOTE_COMPONENTS=
```

If `STARBOARD_CHANNEL_ID` is blank, the bot looks for `#starboard` or `#stars`.

If `MOD_LOG_CHANNEL_ID` is blank, the bot looks for `#mod-log`, `#mod-logs`, or `#logs`.

If `TEMP_VOICE_LOBBY_ID` is blank, users can still create temporary rooms with `!temproom`.

## VPS Deployment

Recommended production path:

```text
/opt/discord-vps-bot
```

Install system packages:

```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg curl
```

Install Deno for YouTube challenge solving:

```bash
curl -fsSL https://deno.land/install.sh | sudo env DENO_INSTALL=/usr/local sh
/usr/local/bin/deno --version
```

Create a dedicated user:

```bash
sudo adduser --system --group --home /opt/discord-vps-bot discordbot
sudo mkdir -p /opt/discord-vps-bot
sudo chown -R discordbot:discordbot /opt/discord-vps-bot
```

Upload or clone the project into `/opt/discord-vps-bot`, then:

```bash
cd /opt/discord-vps-bot
sudo -u discordbot python3 -m venv venv
sudo -u discordbot venv/bin/pip install -r requirements.txt
sudo -u discordbot cp .env.example .env
sudo -u discordbot nano .env
sudo -u discordbot mkdir -p data
```

Install and start the service:

```bash
sudo cp systemd/discord-bot.service /etc/systemd/system/discord-bot.service
sudo systemctl daemon-reload
sudo systemctl enable discord-bot
sudo systemctl start discord-bot
```

Check status:

```bash
sudo systemctl status discord-bot
journalctl -u discord-bot -f
```

Restart after config or code changes:

```bash
sudo systemctl restart discord-bot
```

## YouTube Playback Notes

YouTube changes often, especially for VPS IP addresses. The bot includes several workarounds:

- uses `yt-dlp[default]`
- supports Deno/EJS JavaScript challenge solving
- supports optional browser cookies
- caches audio locally before playback to avoid unstable direct `googlevideo.com` streams
- tries multiple yt-dlp player profiles
- tries search fallback if a specific upload has no usable audio format

More detail: [docs/YOUTUBE_TROUBLESHOOTING.md](docs/YOUTUBE_TROUBLESHOOTING.md)

## License

MIT. See [LICENSE](LICENSE).
