import asyncio
import json
import os
import random
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Optional
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

import discord
import yt_dlp
from discord.ext import commands

from core.database import utc_now_iso


YTDL_OPTIONS = {
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": False,
    "noplaylist": True,
    "retries": 10,
    "fragment_retries": 10,
    "socket_timeout": 30,
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    },
}

YTDL_DOWNLOAD_PROFILES = [
    (
        "web_embedded",
        {"extractor_args": {"youtube": {"player_client": ["web_embedded"]}}},
    ),
    (
        "default_no_android_sdkless",
        {"extractor_args": {"youtube": {"player_client": ["default", "-android_sdkless"]}}},
    ),
    (
        "tv_embedded",
        {"extractor_args": {"youtube": {"player_client": ["tv_embedded"]}}},
    ),
    ("default", {}),
]

FFMPEG_RECONNECT_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"


@dataclass
class Track:
    title: str
    source_url: str
    webpage_url: str
    requester_id: int
    duration: Optional[int] = None
    stream_url: Optional[str] = None
    headers: Optional[dict[str, str]] = None
    local_path: Optional[str] = None
    fallback_query: Optional[str] = None


class MusicState:
    def __init__(self) -> None:
        self.queue: Deque[Track] = deque()
        self.now_playing: Optional[Track] = None
        self.volume = 0.5
        self.text_channel_id: Optional[int] = None


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.states: dict[int, MusicState] = {}

    def state_for(self, guild_id: int) -> MusicState:
        if guild_id not in self.states:
            self.states[guild_id] = MusicState()
        return self.states[guild_id]

    def ytdl_options(self, extra: Optional[dict] = None) -> dict:
        options = {**YTDL_OPTIONS}
        cookies_file = os.getenv("YTDLP_COOKIES_FILE", "").strip()
        if cookies_file:
            options["cookiefile"] = cookies_file
        js_runtimes = os.getenv("YTDLP_JS_RUNTIMES", "").strip()
        if js_runtimes:
            runtimes = {}
            for item in js_runtimes.split(","):
                item = item.strip()
                if not item:
                    continue
                name, _, path = item.partition(":")
                runtimes[name] = {"path": path or None}
            options["js_runtimes"] = runtimes
        remote_components = os.getenv("YTDLP_REMOTE_COMPONENTS", "").strip()
        if remote_components:
            options["remote_components"] = {name.strip() for name in remote_components.split(",") if name.strip()}
        if extra:
            options.update(extra)
        return options

    def ytdl_info_options(self, extra: Optional[dict] = None) -> dict:
        options = self.ytdl_options(
            {
                "extract_flat": True,
                "format": None,
            }
        )
        options.pop("format", None)
        if extra:
            options.update(extra)
        return options

    async def extract_tracks(self, query: str, requester_id: int) -> list[Track]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._extract_tracks_sync, query, requester_id)

    def _extract_tracks_sync(self, query: str, requester_id: int) -> list[Track]:
        query = query.strip()
        if "spotify.com/" in query:
            return self._extract_spotify_best_effort(query, requester_id)

        youtube_id = self.youtube_video_id(query)
        if youtube_id:
            webpage_url = f"https://www.youtube.com/watch?v={youtube_id}"
            title = self.youtube_oembed_title(webpage_url) or f"YouTube video {youtube_id}"
            return [
                Track(
                    title=title,
                    source_url=webpage_url,
                    webpage_url=webpage_url,
                    requester_id=requester_id,
                    fallback_query=title if not title.startswith("YouTube video ") else None,
                )
            ]

        search_query = query if query.startswith(("http://", "https://")) else f"ytsearch1:{query}"
        with yt_dlp.YoutubeDL(self.ytdl_info_options()) as ydl:
            info = ydl.extract_info(search_query, download=False)
            entries = info.get("entries") if isinstance(info, dict) else None
            if entries is not None:
                return [self._track_from_info(entry, requester_id) for entry in entries if entry and (entry.get("id") or entry.get("url"))][:25]
            return [self._track_from_info(info, requester_id)]

    def youtube_video_id(self, query: str) -> Optional[str]:
        if not query.startswith(("http://", "https://")):
            return None
        parsed = urlparse(query)
        host = parsed.netloc.lower().removeprefix("www.")
        if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
            if parsed.path == "/watch":
                return (parse_qs(parsed.query).get("v") or [None])[0]
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed"}:
                return parts[1]
        if host == "youtu.be":
            return parsed.path.strip("/") or None
        return None

    def youtube_oembed_title(self, webpage_url: str) -> Optional[str]:
        oembed_url = f"https://www.youtube.com/oembed?format=json&url={quote(webpage_url, safe='')}"
        request = Request(
            oembed_url,
            headers=YTDL_OPTIONS["http_headers"],
        )
        try:
            with urlopen(request, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            print(f"Could not load YouTube oEmbed metadata for {webpage_url}: {exc}")
            return None
        return data.get("title")

    def _extract_spotify_best_effort(self, query: str, requester_id: int) -> list[Track]:
        with yt_dlp.YoutubeDL(self.ytdl_info_options()) as ydl:
            info = ydl.extract_info(query, download=False)

        entries = info.get("entries") if isinstance(info, dict) else None
        candidates = entries or [info]
        tracks: list[Track] = []
        with yt_dlp.YoutubeDL(self.ytdl_info_options()) as ydl:
            for item in candidates[:25]:
                if not item:
                    continue
                title = item.get("title") or item.get("track") or item.get("url")
                uploader = item.get("uploader") or item.get("artist") or ""
                if not title:
                    continue
                search = f"ytsearch1:{title} {uploader}".strip()
                result = ydl.extract_info(search, download=False)
                result_entries = result.get("entries") or []
                if result_entries:
                    tracks.append(self._track_from_info(result_entries[0], requester_id))
        return tracks

    def _track_from_info(self, info: dict, requester_id: int) -> Track:
        video_id = info.get("id")
        extractor = (info.get("extractor_key") or info.get("extractor") or "").lower()
        if video_id and "youtube" in extractor:
            webpage_url = f"https://www.youtube.com/watch?v={video_id}"
        else:
            webpage_url = info.get("webpage_url") or info.get("original_url") or info.get("url")

        return Track(
            title=info.get("title") or "Unknown title",
            source_url=webpage_url,
            webpage_url=webpage_url,
            requester_id=requester_id,
            duration=info.get("duration"),
            stream_url=info.get("url"),
            headers=info.get("http_headers"),
            fallback_query=info.get("title"),
        )

    async def prepare_track(self, track: Track) -> Track:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._download_track_sync, track)

    def _download_track_sync(self, track: Track) -> Track:
        cache_dir = Path("data/music_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        errors = []
        for profile_name, profile_options in YTDL_DOWNLOAD_PROFILES:
            try:
                return self._download_track_with_profile(track, cache_dir, profile_name, profile_options)
            except Exception as exc:
                errors.append(f"{profile_name}: {exc}")
                print(f"yt-dlp profile {profile_name} failed for {track.source_url}: {exc}")

        fallback = self._download_fallback_search_result(track, cache_dir, errors)
        if fallback:
            return fallback

        raise RuntimeError("All yt-dlp download profiles failed: " + " | ".join(errors))

    def _download_fallback_search_result(self, track: Track, cache_dir: Path, errors: list[str]) -> Optional[Track]:
        if not track.fallback_query:
            return None

        original_id = self.youtube_video_id(track.source_url)
        print(f"Trying YouTube search fallback for {track.title}: {track.fallback_query}")

        try:
            with yt_dlp.YoutubeDL(self.ytdl_info_options()) as ydl:
                result = ydl.extract_info(f"ytsearch5:{track.fallback_query}", download=False)
        except Exception as exc:
            errors.append(f"search_fallback_lookup: {exc}")
            print(f"YouTube search fallback lookup failed for {track.fallback_query}: {exc}")
            return None

        entries = result.get("entries") or []
        for entry in entries:
            if not entry:
                continue
            candidate_id = entry.get("id")
            if not candidate_id or candidate_id == original_id:
                continue
            candidate_url = f"https://www.youtube.com/watch?v={candidate_id}"
            candidate = Track(
                title=entry.get("title") or track.title,
                source_url=candidate_url,
                webpage_url=candidate_url,
                requester_id=track.requester_id,
                fallback_query=None,
            )
            for profile_name, profile_options in YTDL_DOWNLOAD_PROFILES:
                try:
                    prepared = self._download_track_with_profile(candidate, cache_dir, profile_name, profile_options)
                    print(f"Used fallback YouTube result for {track.title}: {prepared.webpage_url}")
                    return prepared
                except Exception as exc:
                    errors.append(f"fallback {candidate_id} {profile_name}: {exc}")
                    print(f"Fallback candidate {candidate_id} profile {profile_name} failed: {exc}")
        return None

    def _download_track_with_profile(
        self,
        track: Track,
        cache_dir: Path,
        profile_name: str,
        profile_options: dict,
    ) -> Track:
        options = self.ytdl_options(
            {
                "outtmpl": str(cache_dir / "%(id)s.%(ext)s"),
                **profile_options,
            }
        )
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(track.source_url, download=False)
            entries = info.get("entries") if isinstance(info, dict) else None
            if entries:
                info = next(entry for entry in entries if entry and entry.get("url"))

            if info.get("is_live"):
                track.title = info.get("title") or track.title
                track.stream_url = info["url"]
                track.webpage_url = info.get("webpage_url") or track.webpage_url
                track.duration = info.get("duration") or track.duration
                track.headers = info.get("http_headers") or YTDL_OPTIONS.get("http_headers")
                return track

            downloaded = ydl.extract_info(track.source_url, download=True)
            downloaded_entries = downloaded.get("entries") if isinstance(downloaded, dict) else None
            if downloaded_entries:
                downloaded = next(entry for entry in downloaded_entries if entry)

        requested_downloads = downloaded.get("requested_downloads") or []
        filepath = None
        if requested_downloads:
            filepath = requested_downloads[0].get("filepath")
        if filepath is None:
            filepath = ydl.prepare_filename(downloaded)
        if not Path(filepath).exists():
            video_id = downloaded.get("id")
            matches = list(cache_dir.glob(f"{video_id}.*")) if video_id else []
            matches = [path for path in matches if not path.name.endswith(".part")]
            if matches:
                filepath = str(matches[0])

        track.title = downloaded.get("title") or track.title
        track.webpage_url = downloaded.get("webpage_url") or track.webpage_url
        track.duration = downloaded.get("duration") or track.duration
        track.local_path = str(filepath)
        print(f"Prepared audio with yt-dlp profile {profile_name}: {track.title}")
        return track

    def ffmpeg_options_for(self, track: Track) -> dict[str, str]:
        before_options = FFMPEG_RECONNECT_OPTIONS
        headers = track.headers or YTDL_OPTIONS.get("http_headers") or {}
        if headers:
            header_text = "".join(f"{name}: {value}\r\n" for name, value in headers.items())
            before_options += f' -headers "{header_text}"'
        return {
            "before_options": before_options,
            "options": "-vn",
        }

    async def ensure_voice(self, ctx: commands.Context) -> Optional[discord.VoiceClient]:
        voice = getattr(ctx.author, "voice", None)
        if voice is None or voice.channel is None:
            await ctx.reply("Join the music voice channel first.", mention_author=False)
            return None

        required_id = self.bot.config.music_voice_channel_id
        if required_id and voice.channel.id != required_id:
            await ctx.reply(f"Use music commands from <#{required_id}>.", mention_author=False)
            return None

        voice_client = ctx.guild.voice_client
        if voice_client and voice_client.channel != voice.channel:
            await voice_client.move_to(voice.channel)
        elif voice_client is None:
            voice_client = await voice.channel.connect(self_deaf=True)
        return voice_client

    async def play_next(self, guild: discord.Guild) -> None:
        state = self.state_for(guild.id)
        voice_client = guild.voice_client
        if voice_client is None or not voice_client.is_connected():
            state.now_playing = None
            return

        if not state.queue:
            state.now_playing = None
            asyncio.run_coroutine_threadsafe(self.disconnect_later(guild), self.bot.loop)
            return

        queued_track = state.queue.popleft()
        try:
            track = await self.prepare_track(queued_track)
        except Exception as exc:
            print(f"Could not prepare audio for {queued_track.title} ({queued_track.source_url}): {exc}")
            state.now_playing = None
            if state.text_channel_id is not None:
                channel = guild.get_channel(state.text_channel_id)
                if isinstance(channel, discord.TextChannel):
                    await channel.send(f"I could not prepare audio for **{queued_track.title}**. Skipping it.")
            await self.play_next(guild)
            return

        if not track.stream_url:
            if not track.local_path:
                await self.play_next(guild)
                return

        def after(error: Exception | None) -> None:
            if error:
                print(f"Audio playback error: {error}")
            self.delete_cached_file(track)
            asyncio.run_coroutine_threadsafe(self.play_next(guild), self.bot.loop)

        state.now_playing = track
        try:
            audio_source = track.local_path or track.stream_url
            ffmpeg_options = {} if track.local_path else self.ffmpeg_options_for(track)
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(audio_source, **ffmpeg_options),
                volume=state.volume,
            )
            voice_client.play(source, after=after)
        except Exception as exc:
            print(f"Could not start audio playback: {exc}")
            state.now_playing = None
            await self.play_next(guild)
            return

        await self.announce_now_playing(guild, track)

    def delete_cached_file(self, track: Track) -> None:
        if not track.local_path:
            return
        try:
            Path(track.local_path).unlink(missing_ok=True)
        except OSError as exc:
            print(f"Could not delete cached music file {track.local_path}: {exc}")

    async def announce_now_playing(self, guild: discord.Guild, track: Track) -> None:
        state = self.state_for(guild.id)
        if state.text_channel_id is None:
            return
        channel = guild.get_channel(state.text_channel_id)
        if isinstance(channel, discord.TextChannel):
            await channel.send(f"Now playing: **{track.title}**\n{track.webpage_url}")

    async def disconnect_later(self, guild: discord.Guild) -> None:
        await asyncio.sleep(180)
        voice_client = guild.voice_client
        state = self.state_for(guild.id)
        if voice_client and not voice_client.is_playing() and not state.queue:
            await voice_client.disconnect()

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        voice_client = await self.ensure_voice(ctx)
        if voice_client is None:
            return

        msg = await ctx.reply("Loading track...", mention_author=False)
        try:
            tracks = await self.extract_tracks(query, ctx.author.id)
        except Exception as exc:
            print(f"Could not load music query {query}: {exc}")
            await msg.edit(content="I could not load that link or search.")
            return

        if not tracks:
            await msg.edit(content="I could not find anything playable.")
            return

        state = self.state_for(ctx.guild.id)
        state.text_channel_id = ctx.channel.id
        state.queue.extend(tracks)
        await self.bot.db.executemany(
            """
            INSERT INTO music_history (guild_id, user_id, title, url, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(ctx.guild.id, ctx.author.id, track.title, track.webpage_url, utc_now_iso()) for track in tracks],
        )

        if voice_client.is_playing() or voice_client.is_paused():
            await msg.edit(content=f"Queued **{len(tracks)}** track(s).")
        else:
            await msg.edit(content=f"Queued **{len(tracks)}** track(s). Starting playback.")
            await self.play_next(ctx.guild)

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context) -> None:
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.reply("Paused.", mention_author=False)
        else:
            await ctx.reply("Nothing is playing.", mention_author=False)

    @commands.command(name="resume")
    async def resume(self, ctx: commands.Context) -> None:
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.reply("Resumed.", mention_author=False)
        else:
            await ctx.reply("Nothing is paused.", mention_author=False)

    @commands.command(name="skip")
    async def skip(self, ctx: commands.Context) -> None:
        vc = ctx.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await ctx.reply("Skipped.", mention_author=False)
        else:
            await ctx.reply("Nothing is playing.", mention_author=False)

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context) -> None:
        state = self.state_for(ctx.guild.id)
        state.queue.clear()
        state.now_playing = None
        vc = ctx.guild.voice_client
        if vc:
            await vc.disconnect()
        await ctx.reply("Stopped and cleared the queue.", mention_author=False)

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context) -> None:
        state = self.state_for(ctx.guild.id)
        lines = []
        if state.now_playing:
            lines.append(f"Now: **{state.now_playing.title}**")
        for index, track in enumerate(list(state.queue)[:10], start=1):
            lines.append(f"{index}. {track.title}")
        if len(state.queue) > 10:
            lines.append(f"...and {len(state.queue) - 10} more")
        await ctx.reply("\n".join(lines) if lines else "The queue is empty.", mention_author=False)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx: commands.Context) -> None:
        track = self.state_for(ctx.guild.id).now_playing
        if track is None:
            await ctx.reply("Nothing is playing.", mention_author=False)
            return
        await ctx.reply(f"Now playing: **{track.title}**\n{track.webpage_url}", mention_author=False)

    @commands.command(name="volume")
    async def volume(self, ctx: commands.Context, percent: int) -> None:
        if percent < 0 or percent > 150:
            await ctx.reply("Choose a volume between 0 and 150.", mention_author=False)
            return
        state = self.state_for(ctx.guild.id)
        state.volume = percent / 100
        vc = ctx.guild.voice_client
        if vc and vc.source and isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = state.volume
        await ctx.reply(f"Volume set to {percent}%.", mention_author=False)

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context) -> None:
        state = self.state_for(ctx.guild.id)
        queue = list(state.queue)
        random.shuffle(queue)
        state.queue = deque(queue)
        await ctx.reply("Queue shuffled.", mention_author=False)

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int) -> None:
        state = self.state_for(ctx.guild.id)
        if index < 1 or index > len(state.queue):
            await ctx.reply("That queue position does not exist.", mention_author=False)
            return
        track = list(state.queue)[index - 1]
        del state.queue[index - 1]
        await ctx.reply(f"Removed **{track.title}**.", mention_author=False)

    @commands.command(name="clear")
    async def clear(self, ctx: commands.Context) -> None:
        self.state_for(ctx.guild.id).queue.clear()
        await ctx.reply("Queue cleared.", mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
