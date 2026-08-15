from datetime import datetime, timezone

import discord
from discord.ext import commands

from core.database import utc_now_iso


class TempVoice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def create_room(self, member: discord.Member, base_channel: discord.VoiceChannel) -> discord.VoiceChannel:
        category = None
        if self.bot.config.temp_voice_category_id:
            category = member.guild.get_channel(self.bot.config.temp_voice_category_id)
        if category is None:
            category = base_channel.category

        overwrites = {
            member.guild.default_role: discord.PermissionOverwrite(connect=True),
            member: discord.PermissionOverwrite(manage_channels=True, move_members=True, connect=True),
        }
        channel = await member.guild.create_voice_channel(
            name=f"{member.display_name}'s room",
            category=category if isinstance(category, discord.CategoryChannel) else None,
            overwrites=overwrites,
            reason="Temporary voice room",
        )
        await self.bot.db.execute(
            "INSERT OR REPLACE INTO temp_rooms (guild_id, channel_id, owner_id, created_at) VALUES (?, ?, ?, ?)",
            (member.guild.id, channel.id, member.id, utc_now_iso()),
        )
        return channel

    @commands.command(name="temproom", aliases=["room"])
    async def temproom(self, ctx: commands.Context, *, name: str | None = None) -> None:
        voice = getattr(ctx.author, "voice", None)
        if voice is None or voice.channel is None:
            await ctx.reply("Join a voice channel first.", mention_author=False)
            return

        channel = await self.create_room(ctx.author, voice.channel)
        if name:
            await channel.edit(name=name[:90])
        await ctx.author.move_to(channel)
        await ctx.reply(f"Created {channel.mention}. It will be deleted when empty.", mention_author=False)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.bot:
            return

        if before.channel and before.channel != after.channel:
            await self.finish_voice_session(member)
        if after.channel and before.channel != after.channel:
            await self.start_voice_session(member, after.channel)

        if after.channel and self.bot.config.temp_voice_lobby_id and after.channel.id == self.bot.config.temp_voice_lobby_id:
            channel = await self.create_room(member, after.channel)
            await member.move_to(channel)

        if before.channel and before.channel != after.channel:
            await self.delete_empty_temp_room(before.channel)

    async def start_voice_session(self, member: discord.Member, channel: discord.VoiceChannel) -> None:
        await self.bot.db.execute(
            """
            INSERT OR REPLACE INTO voice_sessions (guild_id, user_id, channel_id, started_at)
            VALUES (?, ?, ?, ?)
            """,
            (member.guild.id, member.id, channel.id, utc_now_iso()),
        )

    async def finish_voice_session(self, member: discord.Member) -> None:
        row = await self.bot.db.fetchone(
            "SELECT started_at FROM voice_sessions WHERE guild_id = ? AND user_id = ?",
            (member.guild.id, member.id),
        )
        if not row:
            return
        started = datetime.fromisoformat(row["started_at"])
        seconds = max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
        await self.bot.db.ensure_user(member.guild.id, member.id)
        await self.bot.db.execute(
            "UPDATE user_stats SET voice_seconds = voice_seconds + ? WHERE guild_id = ? AND user_id = ?",
            (seconds, member.guild.id, member.id),
        )
        await self.bot.db.execute(
            "DELETE FROM voice_sessions WHERE guild_id = ? AND user_id = ?",
            (member.guild.id, member.id),
        )

        achievements = self.bot.get_cog("Achievements")
        if achievements:
            await achievements.check_stat_achievements(member)

    async def delete_empty_temp_room(self, channel: discord.VoiceChannel) -> None:
        row = await self.bot.db.fetchone(
            "SELECT 1 FROM temp_rooms WHERE guild_id = ? AND channel_id = ?",
            (channel.guild.id, channel.id),
        )
        if not row or len(channel.members) > 0:
            return
        await self.bot.db.execute("DELETE FROM temp_rooms WHERE channel_id = ?", (channel.id,))
        await channel.delete(reason="Temporary voice room empty")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TempVoice(bot))

