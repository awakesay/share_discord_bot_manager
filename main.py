
import os
import json
import pathlib
import subprocess
from typing import Union, Literal
import discord
from functools import cache

RETURN_CODE_MSG = {
    0: "正常に処理しました。",
    1: "引数の値が見つかりません。",
    2: "既に処理しています。",
    3: "エラーが発生しました。"
}

bots: dict = {}     # ボット情報（subprocess.Popenオブジェクト格納）
args_bot: list = [] # 引数のボット名（コマンド利用時の利便性向上）

def run_bot():

    global bots
    global args_bot
    
    intents = discord.Intents.all()
    intents.message_content = True
    bot = discord.Bot(intents=intents)

    @bot.event
    async def on_ready():
        """起動処理＆メッセージ"""
        global bots
        global args_bot
        # ボット情報取得（popen属性追加）
        bots = get_config_json('bots')
        del bots['{bot_name}']
        for value in bots.values():
            value['popen'] = None
        # 引数取得（ボット名）
        args_bot = list(get_config_json('bots').keys())
        args_bot.remove('{bot_name}')
        # 起動メッセージ
        print('on_ready')
        print(f'version: {discord.__version__}')


    @bot.slash_command(description='ボットの一覧を表示します。（bot_name, status）')
    async def bot_list(ctx):
        """ボットの一覧を表示します。"""
        await ctx.respond(f'```\ncmd: bot_list\n```')
        msg = 'bot_name\t->\tstatus\n------------------------------'
        for bot_name, value in bots.items():
            status = 'active' if value['popen'] != None else 'dead'
            msg += f'\n{bot_name}\t->\t{status}'
        await ctx.channel.send(f'```\n{msg}\n```')


    @bot.slash_command(description='管理下のボットを全て起動します。')
    async def start_bots(ctx):
        """全てのボットを起動します。"""
        await ctx.respond(f'```\ncmd: start_bots\n```')
        msg = ''
        for bot_name in bots.keys():
            res = start(bots, bot_name)
            sep = '\n------------------------------' if msg != '' else ''
            msg += '\n'.join([
                sep,
                'cmd: start_bot',
                f'arg: {bot_name}',
                f'return_code: {res[0]}',
                f'return_msg: {RETURN_CODE_MSG[res[0]]}',
                f'error_msg: {res[1]}'
            ])
        await ctx.channel.send(f'```\n{msg}\n```')

    @bot.slash_command(description='指定したボットを起動します。引数のボット名は /bot_list コマンドで確認できます。')
    async def start_bot(
        ctx: discord.ApplicationContext,
        bot_name: discord.Option(str, required=True, description=f'ボット名を指定してください。 /bot_list コマンドでボット名を確認できます。')
    ):
        """ボットを起動します。"""
        await ctx.respond(f'```\ncmd: start_bot, bot_name: {bot_name}\n```')
        res = start(bots, bot_name)
        msg = '\n'.join([
            'cmd: start_bot',
            f'arg: {bot_name}',
            f'return_code: {res[0]}',
            f'return_msg: {RETURN_CODE_MSG[res[0]]}',
            f'error_msg: {res[1]}'
        ])
        await ctx.channel.send(f'```\n{msg}\n```')


    @bot.slash_command(description='指定したボットを再起動します。引数のボット名は /bot_list コマンドで確認できます。')
    async def restart_bot(
        ctx: discord.ApplicationContext,
        bot_name: discord.Option(str, required=True, description=f'ボット名を指定してください。 /bot_list コマンドでボット名を確認できます。')
    ):
        """ボットを再起動します。"""
        await ctx.respond(f'```\ncmd: restart_bot, bot_name: {bot_name}\n```')
        # kill
        res_kill = kill(bots, bot_name)
        msg_restart = '\n'.join([
            'restart_bot: kill -> start',
            '------------------------------',
            'cmd: kill_bot',
            f'arg: {bot_name}',
            f'return_code: {res_kill[0]}',
            f'return_msg: {RETURN_CODE_MSG[res_kill[0]]}',
            f'error_msg: {res_kill[1]}'
        ])

        # start
        res_start = start(bots, bot_name)
        msg_restart += '\n'.join([
            '\n------------------------------',
            'cmd: start_bot',
            f'arg: {bot_name}',
            f'return_code: {res_start[0]}',
            f'return_msg: {RETURN_CODE_MSG[res_start[0]]}',
            f'error_msg: {res_start[1]}'
        ])
        await ctx.channel.send(f'```\n{msg_restart}\n```')

    @bot.slash_command(description='指定したボットを停止します。引数のボット名は /bot_list コマンドで確認できます。')
    async def kill_bot(
        ctx: discord.ApplicationContext,
        bot_name: discord.Option(str, required=True, description='ボット名を指定してください。 /bot_list コマンドでボット名を確認できます。')
    ):
        """起動しているボットを停止します。"""
        await ctx.respond(f'```\ncmd: kill_bot, bot_name: {bot_name}\n```')
        res = kill(bots, bot_name)
        msg = '\n'.join([
            'cmd: kill_bot',
            f'arg: {bot_name}',
            f'return_code: {res[0]}',
            f'return_msg: {RETURN_CODE_MSG[res[0]]}',
            f'error_msg: {res[1]}'
        ])
        await ctx.channel.send(f'```\n{msg}\n```')


    @bot.slash_command(description='リモートリポジトリをプルして、ボットの再起動コマンドを実行します。')
    async def git_pull(
        ctx: discord.ApplicationContext,
        bot_name: discord.Option(str, required=True, description='ボット名を指定してください。 /bot_list コマンドでボット名を確認できます。')
    ):
        """プルリクエスト実行"""
        await ctx.respond(f'```\ncmd: get_pull, bot_name: {bot_name}\n```')
        # pull
        res = pull(bots, bot_name)
        msg = '\n'.join([
            'cmd: git_pull',
            f'arg: {bot_name}',
            f'return_code: {res[0]}',
            f'return_msg: {RETURN_CODE_MSG[res[0]]}',
            f'error_msg: {res[1]}'
        ])
        await ctx.channel.send(f'```\n{msg}\n```')

        # kill
        res_kill = kill(bots, bot_name)
        msg_restart = '\n'.join([
            'auto restart: kill -> start',
            '------------------------------',
            'cmd: kill_bot',
            f'arg: {bot_name}',
            f'return_code: {res_kill[0]}',
            f'return_msg: {RETURN_CODE_MSG[res_kill[0]]}',
            f'error_msg: {res_kill[1]}'
        ])

        # start
        res_start = start(bots, bot_name)
        msg_restart += '\n'.join([
            '\n------------------------------',
            'cmd: start_bot',
            f'arg: {bot_name}',
            f'return_code: {res_start[0]}',
            f'return_msg: {RETURN_CODE_MSG[res_start[0]]}',
            f'error_msg: {res_start[1]}'
        ])
        await ctx.channel.send(f'```\n{msg_restart}\n```')

    bot.run(get_config_json('discord_bot')['token'])


def start(bots: dict, bot_name: str) -> list[int, str]:
    """subprocess.Popenでボットを起動して['popen']に格納します。"""
    if bot_name not in bots.keys():
        return 1, ''    # 引数の値が見つかりません。
    elif (bot := bots[bot_name])['popen'] != None:
        return 2, ''    # 既に処理しています。
    else:
        try:
            popen = subprocess.Popen(f"exec {bot['start_app']} {bot['app_arg']}", shell=True)
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
                return 3, f'cmd: {cmd}\nreturn_code: {return_code}' # リターンコード出るかわからんけど念の為
        except Exception as e:
            return 3, str(e)    # エラーが発生しました。


def get_config_json(name: str) -> Union[list, dict]:
    """configフォルダ内の設定を取得して返します。"""
    path = f'{os.path.abspath(os.path.dirname(__file__))}/config/{name}.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


if __name__ == '__main__':
    run_bot()