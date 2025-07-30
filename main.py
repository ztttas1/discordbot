import discord
from discord.ext import commands
from discord import ButtonStyle, Interaction
from discord.ui import Button, View
import flask
from flask import Flask, request, render_template_string
import requests
import os
from dotenv import load_dotenv
import asyncio

# 環境変数の読み込み
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HCAPTCHA_SITE_KEY = os.getenv("HCAPTCHA_SITE_KEY")
HCAPTCHA_SECRET_KEY = os.getenv("HCAPTCHA_SECRET_KEY")
FLASK_URL = "https://ztk.stars.ne.jp"  # Flaskサーバーの公開URL（ngrokなど）

# Discordボットの設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Flaskアプリの設定
app = Flask(__name__)

# グローバル変数でロールとチャンネルを管理
created_role = None
created_channel = None

# Discordボタンのクラス
class VerificationButton(View):
    def __init__(self, flask_url):
        super().__init__(timeout=None)
        self.flask_url = flask_url

    @discord.ui.button(label="認証する", style=ButtonStyle.primary, custom_id="verify_button")
    async def verify_button(self, interaction: Interaction, button: Button):
        user_id = interaction.user.id
        unique_link = f"{self.flask_url}/verify?user_id={user_id}"
        await interaction.user.send(f"以下のリンクから認証を完了してください:\n{unique_link}")
        await interaction.response.send_message("認証リンクをDMに送信しました！", ephemeral=True)

# Discordコマンド
@bot.command()
@commands.has_permissions(administrator=True)
async def create(ctx):
    global created_role, created_channel

    # ロールの作成
    created_role = await ctx.guild.create_role(name="Verified", colour=discord.Colour.green(), hoist=True)

    # チャンネルの作成
    created_channel = await ctx.guild.create_text_channel("verification")

    # サーバーの全チャンネルを取得
    for channel in ctx.guild.text_channels:
        if channel != created_channel:
            # 作成したロールがない場合、発言を制限
            await channel.set_permissions(created_role, send_messages=True)
            await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        else:
            # 作成したチャンネルでは全員が発言可能
            await channel.set_permissions(ctx.guild.default_role, send_messages=True)

    # ボタンを送信
    view = VerificationButton(FLASK_URL)
    await created_channel.send("以下のボタンを押して認証をしてください:", view=view)
    await ctx.send("ロールとチャンネルを作成し、権限を設定しました。")

# Flaskルート: 認証ページ
@app.route("/verify", methods=["GET"])
def verify_page():
    user_id = request.args.get("user_id")
    return render_template_string("""
        <html>
            <head>
                <script src="https://js.hcaptcha.com/1/api.js" async defer></script>
            </head>
            <body>
                <h1>認証ページ</h1>
                <form action="/submit" method="POST">
                    <input type="hidden" name="user_id" value="{{ user_id }}">
                    <div class="h-captcha" data-sitekey="{{ site_key }}"></div>
                    <button type="submit">認証を完了</button>
                </form>
            </body>
        </html>
    """, user_id=user_id, site_key=HCAPTCHA_SITE_KEY)

# Flaskルート: hCaptchaの検証とロール付与
@app.route("/submit", methods=["POST"])
def submit():
    user_id = request.form.get("user_id")
    hcaptcha_response = request.form.get("h-captcha-response")

    # hCaptchaの検証
    verify_url = "https://hcaptcha.com/siteverify"
    payload = {
        "response": hcaptcha_response,
        "secret": HCAPTCHA_SECRET_KEY
    }
    response = requests.post(verify_url, data=payload).json()

    if response["success"]:
        # Discord APIを使用してロールを付与
        guild = bot.get_guild(YOUR_GUILD_ID)  # ギルドIDを指定
        member = guild.get_member(int(user_id))
        if member and created_role:
            try:
                asyncio.run_coroutine_threadsafe(member.add_roles(created_role), bot.loop)
                return "認証が完了しました！ロールを付与しました。"
            except Exception as e:
                return f"エラー: {str(e)}"
        else:
            return "ユーザーが見つかりません。"
    else:
        return "hCaptchaの認証に失敗しました。"

# Flaskサーバーを別スレッドで実行
def run_flask():
    app.run(host="0.0.0.0", port=5000)

# ボットとFlaskを同時に起動
if __name__ == "__main__":
    import threading
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    bot.run(DISCORD_TOKEN)
