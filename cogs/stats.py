import discord
from discord.ext import commands


def level_requirement(level: int) -> int:
    return 100 + (level * level * 40)


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="profile", aliases=["stats"])
    async def profile(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        member = member or ctx.author
        row = await self.bot.db.fetchone(
            "SELECT * FROM user_stats WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id),
        )
        if row is None:
            await self.bot.db.ensure_user(ctx.guild.id, member.id)
            row = await self.bot.db.fetchone(
                "SELECT * FROM user_stats WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, member.id),
            )

        level = row["level"]
        xp = row["xp"]
        next_xp = level_requirement(level)
        voice_hours = round(row["voice_seconds"] / 3600, 1)

        embed = discord.Embed(title=f"{member.display_name}'s profile", color=member.color.value or 0x5865F2)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level", value=str(level))
        embed.add_field(name="XP", value=f"{xp}/{next_xp}")
        embed.add_field(name="Messages", value=str(row["messages"]))
        embed.add_field(name="Voice time", value=f"{voice_hours}h")
        embed.add_field(name="Commands", value=str(row["commands_used"]))
        embed.add_field(name="Stars received", value=str(row["stars_received"]))
        if member.joined_at:
            embed.add_field(name="Joined server", value=discord.utils.format_dt(member.joined_at, style="R"))

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="serverstats")
    async def serverstats(self, ctx: commands.Context) -> None:
        rows = await self.bot.db.fetchall("SELECT * FROM user_stats WHERE guild_id = ?", (ctx.guild.id,))
        total_messages = sum(row["messages"] for row in rows)
        total_voice = sum(row["voice_seconds"] for row in rows)
        total_commands = sum(row["commands_used"] for row in rows)

        embed = discord.Embed(title=f"{ctx.guild.name} stats", color=0x3498DB)
        embed.add_field(name="Members", value=str(ctx.guild.member_count))
        embed.add_field(name="Tracked users", value=str(len(rows)))
        embed.add_field(name="Messages tracked", value=str(total_messages))
        embed.add_field(name="Voice time tracked", value=f"{round(total_voice / 3600, 1)}h")
        embed.add_field(name="Commands used", value=str(total_commands))
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="leaderboard", aliases=["lb"])
    async def leaderboard(self, ctx: commands.Context) -> None:
        rows = await self.bot.db.fetchall(
            """
            SELECT user_id, xp, level FROM user_stats
            WHERE guild_id = ?
            ORDER BY xp DESC
            LIMIT 10
            """,
            (ctx.guild.id,),
        )
        lines = []
        for index, row in enumerate(rows, start=1):
            member = ctx.guild.get_member(row["user_id"])
            name = member.display_name if member else f"User {row['user_id']}"
            lines.append(f"**{index}.** {name} - level {row['level']} ({row['xp']} XP)")

        await ctx.reply("\n".join(lines) if lines else "No XP data yet.", mention_author=False)

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context) -> None:
        prefix = self.bot.config.command_prefix
        embed = discord.Embed(title="Bot commands", color=0x5865F2)
        embed.add_field(
            name="Music",
            value=f"`{prefix}play`, `{prefix}pause`, `{prefix}resume`, `{prefix}skip`, `{prefix}stop`, `{prefix}queue`, `{prefix}nowplaying`, `{prefix}volume`",
            inline=False,
        )
        embed.add_field(
            name="Server",
            value=f"`{prefix}profile`, `{prefix}serverstats`, `{prefix}leaderboard`, `{prefix}achievements`, `{prefix}temproom`",
            inline=False,
        )
        embed.add_field(
            name="Fun",
            value=f"`{prefix}coinflip`, `{prefix}roll`, `{prefix}8ball`, `{prefix}choose`, `{prefix}rate`, `{prefix}ship`",
            inline=False,
        )
        embed.add_field(
            name="Moderation",
            value=f"`{prefix}purge`, `{prefix}warn`, `{prefix}mute`, `{prefix}unmute`, `{prefix}kick`, `{prefix}ban`",
            inline=False,
        )
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Stats(bot))

