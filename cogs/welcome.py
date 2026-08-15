from datetime import datetime, timezone

import discord
from discord.ext import commands


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return

        await self.bot.db.ensure_user(
            member.guild.id,
            member.id,
            member.joined_at.isoformat() if member.joined_at else None,
        )

        channel_id = self.bot.config.welcome_channel_id
        channel = member.guild.get_channel(channel_id) if channel_id else discord.utils.get(member.guild.text_channels, name="welcome")
        if not isinstance(channel, discord.TextChannel):
            return

        member_number = member.guild.member_count or len(member.guild.members)
        created = discord.utils.format_dt(member.created_at, style="R")
        joined = discord.utils.format_dt(datetime.now(timezone.utc), style="F")

        embed = discord.Embed(
            title=f"Welcome to {member.guild.name}",
            description=(
                f"{member.mention}, glad to have you here.\n\n"
                f"**Member number:** #{member_number}\n"
                f"**Account created:** {created}\n"
                f"**Joined:** {joined}"
            ),
            color=0x57F287,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Have a good time and check the rules.")
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))

