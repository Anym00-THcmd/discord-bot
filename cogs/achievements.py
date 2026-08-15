import discord
from discord.ext import commands

from core.database import utc_now_iso


ACHIEVEMENTS = {
    "first_message": ("First Words", "Send your first tracked message."),
    "chatty_100": ("Chatty", "Send 100 tracked messages."),
    "level_5": ("Rising Regular", "Reach level 5."),
    "level_10": ("Server Veteran", "Reach level 10."),
    "voice_hour": ("Voice Regular", "Spend 1 hour in voice."),
    "star_collector": ("Star Collector", "Receive 10 star reactions."),
    "command_runner": ("Bot Explorer", "Use 25 commands."),
}


class Achievements(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def award(self, member: discord.Member, key: str) -> bool:
        if key not in ACHIEVEMENTS:
            return False
        row = await self.bot.db.fetchone(
            """
            SELECT 1 FROM achievements
            WHERE guild_id = ? AND user_id = ? AND achievement_key = ?
            """,
            (member.guild.id, member.id, key),
        )
        if row:
            return False

        await self.bot.db.execute(
            """
            INSERT INTO achievements (guild_id, user_id, achievement_key, earned_at)
            VALUES (?, ?, ?, ?)
            """,
            (member.guild.id, member.id, key, utc_now_iso()),
        )
        return True

    async def check_activity(self, member: discord.Member, messages: int, level: int) -> None:
        newly_awarded = []
        checks = [
            ("first_message", messages >= 1),
            ("chatty_100", messages >= 100),
            ("level_5", level >= 5),
            ("level_10", level >= 10),
        ]
        for key, passed in checks:
            if passed and await self.award(member, key):
                newly_awarded.append(ACHIEVEMENTS[key][0])

        if newly_awarded:
            try:
                await member.send(f"New achievement unlocked: **{', '.join(newly_awarded)}**")
            except discord.Forbidden:
                pass

    async def check_stat_achievements(self, member: discord.Member) -> None:
        row = await self.bot.db.fetchone(
            "SELECT voice_seconds, stars_received, commands_used FROM user_stats WHERE guild_id = ? AND user_id = ?",
            (member.guild.id, member.id),
        )
        if not row:
            return
        checks = [
            ("voice_hour", row["voice_seconds"] >= 3600),
            ("star_collector", row["stars_received"] >= 10),
            ("command_runner", row["commands_used"] >= 25),
        ]
        for key, passed in checks:
            if passed:
                await self.award(member, key)

    @commands.command(name="achievements", aliases=["badges"])
    async def achievements(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        member = member or ctx.author
        rows = await self.bot.db.fetchall(
            """
            SELECT achievement_key, earned_at FROM achievements
            WHERE guild_id = ? AND user_id = ?
            ORDER BY earned_at ASC
            """,
            (ctx.guild.id, member.id),
        )
        unlocked = {row["achievement_key"]: row["earned_at"] for row in rows}
        lines = []
        for key, (name, description) in ACHIEVEMENTS.items():
            mark = "[x]" if key in unlocked else "[ ]"
            lines.append(f"{mark} **{name}** - {description}")

        embed = discord.Embed(title=f"{member.display_name}'s achievements", description="\n".join(lines), color=0xF1C40F)
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Achievements(bot))

