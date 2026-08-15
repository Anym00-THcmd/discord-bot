import random

from discord.ext import commands


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="coinflip", aliases=["flip"])
    async def coinflip(self, ctx: commands.Context) -> None:
        await ctx.reply(random.choice(["Heads", "Tails"]), mention_author=False)

    @commands.command(name="roll")
    async def roll(self, ctx: commands.Context, sides: int = 6) -> None:
        if sides < 2 or sides > 100000:
            await ctx.reply("Choose a number of sides between 2 and 100000.", mention_author=False)
            return
        await ctx.reply(f"You rolled **{random.randint(1, sides)}** on a d{sides}.", mention_author=False)

    @commands.command(name="8ball")
    async def eight_ball(self, ctx: commands.Context, *, question: str = "") -> None:
        answers = [
            "Yes.",
            "No.",
            "Probably.",
            "Probably not.",
            "Ask again later.",
            "Definitely.",
            "I would not count on it.",
        ]
        await ctx.reply(random.choice(answers), mention_author=False)

    @commands.command(name="choose")
    async def choose(self, ctx: commands.Context, *, options: str) -> None:
        choices = [item.strip() for item in options.replace(",", " ").split() if item.strip()]
        if len(choices) < 2:
            await ctx.reply("Give me at least two options.", mention_author=False)
            return
        await ctx.reply(f"I choose **{random.choice(choices)}**.", mention_author=False)

    @commands.command(name="rate")
    async def rate(self, ctx: commands.Context, *, thing: str) -> None:
        await ctx.reply(f"{thing} is **{random.randint(0, 100)}/100**.", mention_author=False)

    @commands.command(name="ship")
    async def ship(self, ctx: commands.Context, first: str, second: str) -> None:
        score = random.randint(0, 100)
        bar = "#" * (score // 10) + "-" * (10 - score // 10)
        await ctx.reply(f"**{first} + {second}**: {score}%\n`{bar}`", mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
