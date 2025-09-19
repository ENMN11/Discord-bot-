# stick_no_pin.py
import os
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN") or "PUT_YOUR_TOKEN_HERE"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Lưu trạng thái sticky theo kênh
# { channel_id: {"content": str, "last_msg_id": int|None, "enabled": bool} }
sticky: dict[int, dict] = {}

def need_manage_messages(member: discord.Member) -> bool:
    return member.guild_permissions.manage_messages

async def bot_perms_ok(channel: discord.abc.GuildChannel) -> bool:
    perms = channel.permissions_for(channel.guild.me)
    # cần gửi/xoá/đọc lịch sử
    return perms.send_messages and perms.read_message_history and perms.manage_messages

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        await bot.tree.sync()
        print("Slash synced.")
    except Exception as e:
        print("Sync error:", e)

# --- Sticky logic: không ghim, chỉ xoá & gửi lại ---
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    data = sticky.get(message.channel.id)
    if data and data.get("enabled") and data.get("content"):
        # Xoá bản stick cũ (nếu còn), rồi gửi lại
        old_id = data.get("last_msg_id")
        if old_id:
            try:
                old_msg = await message.channel.fetch_message(old_id)
                await old_msg.delete()
            except discord.NotFound:
                pass
            except discord.Forbidden:
                pass

        try:
            new_msg = await message.channel.send(data["content"])
            data["last_msg_id"] = new_msg.id
        except discord.Forbidden:
            pass

    await bot.process_commands(message)

# --- /stick set ---
@bot.tree.command(name="stick", description="Bật/tắt sticky (không ghim).")
@app_commands.describe(
    action="set/clear",
    content="Nội dung sticky (chỉ cần khi action=set)"
)
async def stick_cmd(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    content: str | None = None
):
    await interaction.response.defer(ephemeral=True)

    if not isinstance(interaction.user, discord.Member) or not need_manage_messages(interaction.user):
        return await interaction.followup.send("❌ Cần quyền **Manage Messages**.", ephemeral=True)

    if not await bot_perms_ok(interaction.channel):
        return await interaction.followup.send("❌ Bot thiếu quyền **Send / Read History / Manage Messages**.", ephemeral=True)

    ch_id = interaction.channel.id

    if action.value == "set":
        if not content or not content.strip():
            return await interaction.followup.send("❌ Vui lòng nhập `content` khi dùng `action=set`.", ephemeral=True)

        # Xoá bản stick cũ (nếu có)
        last_id = sticky.get(ch_id, {}).get("last_msg_id")
        if last_id:
            try:
                m = await interaction.channel.fetch_message(last_id)
                await m.delete()
            except discord.NotFound:
                pass
            except discord.Forbidden:
                pass

        msg = await interaction.channel.send(content)
        sticky[ch_id] = {"content": content, "last_msg_id": msg.id, "enabled": True}
        return await interaction.followup.send("✅ Đã bật sticky (không ghim) cho kênh này.", ephemeral=True)

    else:  # clear
        data = sticky.pop(ch_id, None)
        if data and data.get("last_msg_id"):
            try:
                m = await interaction.channel.fetch_message(data["last_msg_id"])
                await m.delete()
            except discord.NotFound:
                pass
            except discord.Forbidden:
                pass
        return await interaction.followup.send("✅ Đã tắt sticky cho kênh này.", ephemeral=True)

# Chọn giá trị cho tham số action
@stick_cmd.autocomplete("action")
async def action_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    choices = [
        app_commands.Choice(name="set", value="set"),
        app_commands.Choice(name="clear", value="clear"),
    ]
    return [c for c in choices if c.name.startswith(current.lower())]

if __name__ == "__main__":
    if TOKEN == "PUT_YOUR_TOKEN_HERE" or not TOKEN:
        raise SystemExit("⚠️ Hãy đặt token vào DISCORD_TOKEN hoặc sửa hằng TOKEN.")
    bot.run(TOKEN)
