import discord
from discord.ext import commands

from core.database import utc_now_iso


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        configured = self.bot.config.mod_log_channel_id
        channel = guild.get_channel(configured) if configured else None
        if isinstance(channel, discord.TextChannel):
            return channel
        for name in ("mod-log", "mod-logs", "logs"):
            channel = discord.utils.get(guild.text_channels, name=name)
            if isinstance(channel, discord.TextChannel):
                return channel
        return None

    async def log_action(
        self,
        guild: discord.Guild,
        moderator: discord.Member | None,
        target: discord.Member | discord.User | None,
        action: str,
        reason: str | None,
    ) -> None:
        await self.bot.db.execute(
            """
            INSERT INTO mod_logs (guild_id, moderator_id, target_id, action, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                guild.id,
                moderator.id if moderator else None,
                target.id if target else None,
                action,
                reason,
                utc_now_iso(),
            ),
        )
        channel = self.log_channel(guild)
        if not channel:
            return

        embed = discord.Embed(title=f"Moderation: {action}", color=0xE67E22)
        if moderator:
            embed.add_field(name="Moderator", value=moderator.mention)
        if target:
            embed.add_field(name="Target", value=f"{target} (`{target.id}`)")
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        await channel.send(embed=embed)

    @commands.command(name="purge")
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int) -> None:
        if amount < 1 or amount > 100:
            await ctx.reply("Choose an amount between 1 and 100.", mention_author=False)
            return
        deleted = await ctx.channel.purge(limit=amount + 1)
        await self.log_action(ctx.guild, ctx.author, None, "purge", f"Deleted {len(deleted) - 1} messages in #{ctx.channel}.")
        confirmation = await ctx.send(f"Deleted {len(deleted) - 1} messages.")
        await confirmation.delete(delay=5)

    @commands.command(name="warn")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        await self.log_action(ctx.guild, ctx.author, member, "warn", reason)
        try:
            await member.send(f"You were warned in **{ctx.guild.name}**: {reason}")
        except discord.Forbidden:
            pass
        await ctx.reply(f"Warned {member.mention}.", mention_author=False)

    @commands.command(name="mute")
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        role = discord.utils.get(ctx.guild.roles, name=self.bot.config.muted_role_name)
        if role is None:
            role = await ctx.guild.create_role(name=self.bot.config.muted_role_name, reason="Mute role required by bot")
            for channel in ctx.guild.channels:
                try:
                    await channel.set_permissions(role, send_messages=False, speak=False, add_reactions=False)
                except discord.Forbidden:
                    continue
        await member.add_roles(role, reason=reason)
        await self.log_action(ctx.guild, ctx.author, member, "mute", reason)
        await ctx.reply(f"Muted {member.mention}.", mention_author=False)

    @commands.command(name="unmute")
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        role = discord.utils.get(ctx.guild.roles, name=self.bot.config.muted_role_name)
        if role:
            await member.remove_roles(role, reason=reason)
        await self.log_action(ctx.guild, ctx.author, member, "unmute", reason)
        await ctx.reply(f"Unmuted {member.mention}.", mention_author=False)

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        await member.kick(reason=reason)
        await self.log_action(ctx.guild, ctx.author, member, "kick", reason)
        await ctx.reply(f"Kicked {member}.", mention_author=False)

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        await member.ban(reason=reason, delete_message_days=0)
        await self.log_action(ctx.guild, ctx.author, member, "ban", reason)
        await ctx.reply(f"Banned {member}.", mention_author=False)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await self.log_action(member.guild, None, member, "member left", None)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))

