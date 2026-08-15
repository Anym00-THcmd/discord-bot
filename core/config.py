import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _optional_int(name: str) -> Optional[int]:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    return int(value)


@dataclass(frozen=True)
class Config:
    discord_token: str
    command_prefix: str
    database_path: Path
    welcome_channel_id: Optional[int]
    music_voice_channel_id: Optional[int]
    starboard_channel_id: Optional[int]
    mod_log_channel_id: Optional[int]
    starboard_threshold: int
    xp_per_message_min: int
    xp_per_message_max: int
    xp_cooldown_seconds: int
    temp_voice_lobby_id: Optional[int]
    temp_voice_category_id: Optional[int]
    muted_role_name: str

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token or token == "put_your_bot_token_here":
            raise RuntimeError("DISCORD_TOKEN is missing. Copy .env.example to .env and add your bot token.")

        return cls(
            discord_token=token,
            command_prefix=os.getenv("COMMAND_PREFIX", "!").strip() or "!",
            database_path=Path(os.getenv("DATABASE_PATH", "data/bot.db")),
            welcome_channel_id=_optional_int("WELCOME_CHANNEL_ID"),
            music_voice_channel_id=_optional_int("MUSIC_VOICE_CHANNEL_ID"),
            starboard_channel_id=_optional_int("STARBOARD_CHANNEL_ID"),
            mod_log_channel_id=_optional_int("MOD_LOG_CHANNEL_ID"),
            starboard_threshold=int(os.getenv("STARBOARD_THRESHOLD", "5")),
            xp_per_message_min=int(os.getenv("XP_PER_MESSAGE_MIN", "8")),
            xp_per_message_max=int(os.getenv("XP_PER_MESSAGE_MAX", "14")),
            xp_cooldown_seconds=int(os.getenv("XP_COOLDOWN_SECONDS", "60")),
            temp_voice_lobby_id=_optional_int("TEMP_VOICE_LOBBY_ID"),
            temp_voice_category_id=_optional_int("TEMP_VOICE_CATEGORY_ID"),
            muted_role_name=os.getenv("MUTED_ROLE_NAME", "Muted").strip() or "Muted",
        )

