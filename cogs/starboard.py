import discord
from discord.ext import commands

from core.database import utc_now_iso


STAR_EMOJIS = {"⭐", "🌟", "star"}


class Starboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def starboard_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        configured = self.bot.config.starboard_channel_id
        channel = guild.get_channel(configured) if configured else None
        if isinstance(channel, discord.TextChannel):
            return channel
        for name in ("starboard", "stars"):
            channel = discord.utils.get(guild.text_channels, name=name)
            if isinstance(channel, discord.TextChannel):
                return channel
        return None

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        await self.update_starboard(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        await self.update_starboard(payload)

    async def update_starboard(self, payload: discord.RawReactionActionEvent) -> None:
        if str(payload.emoji) not in STAR_EMOJIS:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        starboard = self.starboard_channel(guild)
        if starboard is None or payload.channel_id == starboard.id:
            return

        channel = guild.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return
        if message.author.bot:
            return

        star_count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) in STAR_EMOJIS:
                star_count = reaction.count
                break

        existing = await self.bot.db.fetchone(
            "SELECT starboard_message_id FROM starboard_messages WHERE guild_id = ? AND source_message_id = ?",
            (guild.id, message.id),
        )
        if star_count < self.bot.config.starboard_threshold and not existing:
            return

        embed = discord.Embed(
            description=message.content or "[attachment]",
            color=0xF1C40F,
            timestamp=message.created_at,
        )
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        embed.add_field(name="Original", value=f"[Jump to message]({message.jump_url})", inline=False)
        embed.set_footer(text=f"{star_count} star(s)")
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)

        content = f"⭐ **{star_count}** in {channel.mention}"
        if existing:
            try:
                star_message = await starboard.fetch_message(existing["starboard_message_id"])
                await star_message.edit(content=content, embed=embed)
            except discord.NotFound:
                await self.create_starboard_post(starboard, message, content, embed, star_count)
            return

        await self.create_starboard_post(starboard, message, content, embed, star_count)
        await self.bot.db.ensure_user(guild.id, message.author.id)
        await self.bot.db.execute(
            "UPDATE user_stats SET stars_received = stars_received + ? WHERE guild_id = ? AND user_id = ?",
            (star_count, guild.id, message.author.id),
        )

        member = guild.get_member(message.author.id)
        achievements = self.bot.get_cog("Achievements")
        if member and achievements:
            await achievements.check_stat_achievements(member)

    async def create_starboard_post(
        self,
        starboard: discord.TextChannel,
        message: discord.Message,
        content: str,
        embed: discord.Embed,
        star_count: int,
    ) -> None:
        star_message = await starboard.send(content=content, embed=embed)
        await self.bot.db.execute(
            """
            INSERT OR REPLACE INTO starboard_messages
            (guild_id, source_message_id, starboard_message_id, channel_id, stars, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message.guild.id, message.id, star_message.id, starboard.id, star_count, utc_now_iso()),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Starboard(bot))

