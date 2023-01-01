
import os
import json
import pathlib
import subprocess
from typing import Union, Literal
import discord
from functools import cache

ERROR_CODE_MSG = {
    0: "正常に処理しました。",
    1: "引数の値が見つかりません。",
    2: "既に処理しています。",
    3: "エラーが発生しました。"
}

bots: dict = {}     # ボット情報（subprocess.Popenオブジェクト格納）
args_bot: list = [] # 引数のボット名（コマンド利用時の利便性向上）

def run_bot():

    intents = discord.Intents.all()
    intents.message_content = True
    bot = discord.Bot(intents=intents)

    @bot.event
    async def on_ready():
        """起動処理＆メッセージ"""
        # ボット情報取得（popen属性追加）
        global bots
        bots = get_config_json('bots')
        del bots['{bot_name}']
        for value in bots.values():
            value['popen'] = None
        # 引数取得（ボット名）
        global args_bot
        args_bot = list(get_config_json('bots').keys())
        args_bot.remove('{bot_name}')
        # 起動メッセージ
        print('on_ready')
        print(f'version: {discord.__version__}')


    @bot.slash_command(description='ボットの一覧を表示します。（bot_name, status）')
    async def bot_list(ctx):
        """ボットの一覧を表示します。"""
        await ctx.respond(f'```\ncmd: bot_list\n```')
        embed = discord.Embed(title='bot_list', colour=discord.Colour.blurple())
        for key, value in bots.items():
            status = 'active' if value['popen'] != None else 'dead'
            embed.add_field(name=f'bot_name: {key}', value=f'status: {status}', inline=False)
        
        await ctx.channel.send(embed=embed)

    @bot.slash_command(description='指定したボットを起動します。')
    async def launch_bot(
        ctx: discord.ApplicationContext,
        bot_name: discord.Option(str, required=True, description=f" = [{', '.join(args_bot)}]")
    ):
        """ボットを起動します。"""
        await ctx.respond(f'```\ncmd: launch_bot, args: {bot_name}\n```')
        res = launch(bots, bot_name)
        msg = '\n'.join([
            'cmd: launch_bot',
            f'arg: {bot_name}',
            f'return_code: {res[0]}',
            f'return_msg: {ERROR_CODE_MSG[res[0]]}',
            f'error_msg: {res[1]}'
        ])
        await ctx.channel.send(f'```\n{msg}\n```')


    @bot.slash_command(description='指定したボットを停止します。')
    async def kill_bot(
        ctx: discord.ApplicationContext,
        bot_name: discord.Option(str, required=True, description=f" = [{', '.join(args_bot)}]")
    ):
        """起動しているボットを停止します。"""
        await ctx.respond(f'```\ncmd: kill_bot, args: {bot_name}\n```')
        res = kill(bots, bot_name)
        msg = '\n'.join([
            'cmd: kill_bot',
            f'arg: {bot_name}',
            f'return_code: {res[0]}',
            f'return_msg: {ERROR_CODE_MSG[res[0]]}',
            f'error_msg: {res[1]}'
        ])
        await ctx.channel.send(f'```\n{msg}\n```')


    @bot.slash_command(description='リモートリポジトリをプルします。')
    async def git_pull(
        ctx: discord.ApplicationContext,
        bot_name: discord.Option(str, required=True, description=f" = [{', '.join(args_bot)}]")
    ):
        """プルリクエスト実行"""
        await ctx.respond(f'```\ncmd: get_pull, args: {bot_name}\n```')
        # pull
        res = pull(bots, bot_name)
        msg = '\n'.join([
            'cmd: git_pull',
            f'arg: {bot_name}',
            f'return_code: {res[0]}',
            f'return_msg: {ERROR_CODE_MSG[res[0]]}',
            f'error_msg: {res[1]}'
        ])
        await ctx.channel.send(f'```\n{msg}\n```')

        # kill
        res_kill = kill(bots, bot_name)
        msg_restart = '\n'.join([
            'restart_bot: kill -> launch',
            '------------------------------',
            'cmd: kill_bot',
            f'arg: {bot_name}',
            f'return_code: {res_kill[0]}',
            f'return_msg: {ERROR_CODE_MSG[res_kill[0]]}',
            f'error_msg: {res_kill[1]}'
        ])

        # launch
        res_launch = launch(bots, bot_name)
        msg_restart += '\n'.join([
            '\n------------------------------',
            'cmd: launch_bot',
            f'arg: {bot_name}',
            f'return_code: {res_launch[0]}',
            f'return_msg: {ERROR_CODE_MSG[res_launch[0]]}',
            f'error_msg: {res_launch[1]}'
        ])
        await ctx.channel.send(f'```\n{msg_restart}\n```')

    bot.run(get_config_json('discord_bot')['token'])


def launch(bots: dict, bot_name: str) -> list[int, str]:
    """subprocess.Popenでボットを起動して['popen']に格納します。"""
    if bot_name not in bots.keys():
        return 1, ''    # 引数の値が見つかりません。
    elif (bot := bots[bot_name])['popen'] != None:
        return 2, ''    # 既に処理しています。
    else:
        try:
            popen = subprocess.Popen(f"exec {bot['launch_app']} {bot['app_arg']}", shell=True)
            bot['popen'] = popen
            return 0, ''        # 正常に処理しました。      
        except Exception as e:
            return 3, str(e)    # エラーが発生しました。
            

def kill(bots: dict, bot_name: str) -> list[int, str]:
    """subprocess.Popenで起動したボットを停止します。"""
    if bot_name not in bots.keys():
        return 1, ''    # 引数の値が見つかりません。
    elif (bot := bots[bot_name])['popen'] == None:
        return 2, ''    # 既に処理しています。
    else:
        # bot['popen'].terminate()
        bot['popen'].kill()
        bot['popen'] = None
        return 0, ''    # 正常に処理しました。


def pull(bots: dict, bot_name: str) -> list[int, str]:
    """Gitのpullコマンドを実行します。（予めGitリモートリポジトリの設定をする必要があります。）
    コンフリクトが起きたら、対処できないかも…"""
    if bot_name not in bots.keys():
        return 1, ''    # 引数の値が見つかりません。
    else:
        try:
            dir = bots[bot_name]['git_dir']
            cmd = f'cd {dir}; git pull'
            if (return_code := os.system(cmd)) == 0:
                return 0, ''    # 正常に処理しました。
            else:
                return 3, f'cmd: {cmd}\nreturn_code: {return_code}' # リターンコード出るか？
        except Exception as e:
            return 3, str(e)    # エラーが発生しました。


#@cache  # キャッシュによる高速化
def get_config_json(name: str) -> Union[list, dict]:
    """configフォルダ内の設定を取得して返します。"""
    path = f'{os.path.abspath(os.path.dirname(__file__))}/config/{name}.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


if __name__ == '__main__':
    run_bot()