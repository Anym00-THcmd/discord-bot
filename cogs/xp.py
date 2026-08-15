import random
from datetime import datetime, timezone

from discord.ext import commands

from cogs.stats import level_requirement


class XP(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return

        await self.bot.db.increment_message(message.guild.id, message.author.id)
        row = await self.bot.db.fetchone(
            "SELECT xp, level, last_xp_at, messages FROM user_stats WHERE guild_id = ? AND user_id = ?",
            (message.guild.id, message.author.id),
        )
        if row is None:
            return

        now = datetime.now(timezone.utc)
        if row["last_xp_at"]:
            last = datetime.fromisoformat(row["last_xp_at"])
            cooldown = self.bot.config.xp_cooldown_seconds
            if (now - last).total_seconds() < cooldown:
                return

        amount = random.randint(self.bot.config.xp_per_message_min, self.bot.config.xp_per_message_max)
        new_xp = row["xp"] + amount
        old_level = row["level"]
        new_level = old_level
        while new_xp >= level_requirement(new_level):
            new_level += 1

        await self.bot.db.add_xp(message.guild.id, message.author.id, amount, new_level)

        achievements = self.bot.get_cog("Achievements")
        if achievements:
            await achievements.check_activity(message.author, row["messages"] + 1, new_level)

        if new_level > old_level:
            await message.channel.send(f"{message.author.mention} reached **level {new_level}**.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(XP(bot))

