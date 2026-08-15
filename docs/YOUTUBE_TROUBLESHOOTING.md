# YouTube Troubleshooting

The music system uses `yt-dlp` and FFmpeg. YouTube changes often, especially on VPS IP addresses.

## First Checks

```bash
cd /opt/discord-vps-bot
source venv/bin/activate
pip install -U "yt-dlp[default]"
yt-dlp --version
ffmpeg -version
```

## Deno / EJS Challenge Solver

If logs mention signature solving, n-challenge solving, EJS, or only image formats, install Deno:

```bash
curl -fsSL https://deno.land/install.sh | sudo env DENO_INSTALL=/usr/local sh
/usr/local/bin/deno --version
```

Then test:

```bash
yt-dlp --cookies cookies.txt --js-runtimes deno -F "https://www.youtube.com/watch?v=VIDEO_ID"
```

If EJS components are still missing:

```bash
yt-dlp --cookies cookies.txt --js-runtimes deno --remote-components ejs:github -F "https://www.youtube.com/watch?v=VIDEO_ID"
```

To use this from the bot, set in `.env`:

```env
YTDLP_JS_RUNTIMES=deno
YTDLP_REMOTE_COMPONENTS=ejs:github
```

## Cookies

If YouTube blocks the VPS with `403 Forbidden`, export cookies from a browser session where YouTube works.

Upload them as:

```text
/opt/discord-vps-bot/cookies.txt
```

Then set:

```env
YTDLP_COOKIES_FILE=/opt/discord-vps-bot/cookies.txt
```

Treat `cookies.txt` like a password.

