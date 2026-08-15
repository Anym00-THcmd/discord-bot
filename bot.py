import asyncio
import logging

import discord
from discord.ext import commands

from core.config import Config
from core.database import Database


COGS = [
    "cogs.welcome",
    "cogs.music",
    "cogs.temp_voice",
    "cogs.starboard",
    "cogs.xp",
    "cogs.achievements",
    "cogs.stats",
    "cogs.fun",
    "cogs.moderation",
]


class ServerBot(commands.Bot):
    def __init__(self, config: Config, db: Database):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.reactions = True
        intents.voice_states = True
        intents.guilds = True
        intents.messages = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(config.command_prefix),
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(
                everyone=False,
                roles=False,
                users=True,
                replied_user=False,
            ),
        )
        self.config = config
        self.db = db

    async def setup_hook(self) -> None:
        await self.db.connect()
        await self.db.setup()

        for cog in COGS:
            await self.load_extension(cog)

    async def on_ready(self) -> None:
        logging.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "unknown")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"{self.config.command_prefix}help",
            )
        )

    async def on_command(self, ctx: commands.Context) -> None:
        if ctx.guild and ctx.author and not ctx.author.bot:
            await self.db.increment_command(ctx.guild.id, ctx.author.id)
            achievements = self.get_cog("Achievements")
            if achievements:
                await achievements.check_stat_achievements(ctx.author)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("You do not have permission to use that command.", mention_author=False)
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"Missing argument: `{error.param.name}`.", mention_author=False)
            return
        if isinstance(error, commands.BadArgument):
            await ctx.reply("I could not understand one of the arguments.", mention_author=False)
            return

        logging.exception("Command error in %s", getattr(ctx.command, "qualified_name", "unknown"), exc_info=error)
        await ctx.reply("Something went wrong while running that command.", mention_author=False)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.from_env()
    db = Database(config.database_path)
    bot = ServerBot(config, db)
    async with bot:
        await bot.start(config.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
