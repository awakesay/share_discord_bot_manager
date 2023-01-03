
import os
import json
import platform
import subprocess
from typing import Union
import discord
import tabulate as Tabulate         # 重複回避
from tabulate import tabulate       # テーブル化

DO_CMD_TIMEOUT = 60                 # mng_do_cmdのタイムアウト設定

RETURN_CODE_MSG = {                 # tabulateで表にするとズレるので、日本語から英語にしました。
    0: "Processed successfully.",   # 正常に処理しました。
    1: "Argument value not found.", # 引数の値が見つかりません。
    2: "Already processed.",        # 既に処理しています。
    3: "An error has occurred."     # エラーが発生しました。
}

bots: dict = {}         # ボット情報（subprocess.Popenオブジェクトも格納します。）
bot_names: list = []    # コマンド引数の入力候補
do_cmds: list = []      # コマンド引数の入力制限

def run_bot():

    global bots         # 関数内でグローバル変数の代入利用
    global bot_names

    # ボット情報取得（popen属性追加）
    bots = get_config_json('bots')
    del bots['{bot_name}']
    for value in bots.values():
        value['popen'] = None
    # 引数取得（ボット名）
    bot_names = list(get_config_json('bots').keys())
    bot_names.remove('{bot_name}')
    # 入力制限取得（コマンド）
    do_cmds = get_config_json('do_cmd_permission')['start_cmd']

    intents = discord.Intents.all()
    intents.message_content = True
    bot = discord.Bot(intents=intents)


    @bot.event
    async def on_ready():
        """起動メッセージ"""
        print(f'{"-"*30}\non_ready: discord_bot_manager')
        print(f'python_version: {platform.python_version()}')
        print(f'pycord_version: {discord.__version__}')


    @bot.slash_command(description='ボットのステータスを表示します。')
    async def mng_status_bots(ctx: discord.ApplicationContext):
        """"""
        await ctx.respond(f'```\ncmd: mng_status_bots\n```')
        table = []
        for bot_name, value in bots.items():
            table.append({
                'bot_name': bot_name,
                'status': 'active' if value['popen'] != None else 'dead'
            })
        await ctx.channel.send(f'```\n{tabulate(table, headers="keys")}\n```')


    @bot.slash_command(description='全ボットに対し起動コマンドを実行します。')
    async def mng_start_all_bot(ctx: discord.ApplicationContext):
        """"""
        await ctx.respond(f'```\ncmd: mng_start_all_bot\n```')
        table = []
        for bot_name in bots.keys():
            res = start(bots, bot_name)
            table.append({
                'cmd': 'mng_start_all_bot',
                'bot_name': bot_name,
                'ret_code': res[0],
                'ret_msg': RETURN_CODE_MSG.get(res[0], 'unknown'),
                'err_msg': 'none' if res[1] == '' else res[1]
            })
        await ctx.channel.send(f'```\n{tabulate(table, headers="keys",)}\n```')


    @bot.slash_command(description='指定したボットに対し起動コマンドを実行します。')
    async def mng_start_bot(
        ctx: discord.ApplicationContext,
        bot_name: discord.Option(
            input_type=str,
            description=f'ボット名を指定してください。（入力候補）',
            choices=bot_names,
            required=True
        )
    ):
        """"""
        await ctx.respond(f'```\ncmd: mng_start_bot, bot_name: {bot_name}\n```')
        res = start(bots, bot_name)
        table =[{
            'cmd': 'mng_start_bot',
            'bot_name': bot_name,
            'ret_code': res[0],
            'ret_msg': RETURN_CODE_MSG.get(res[0], 'unknown'),
            'err_msg': 'none' if res[1] == '' else res[1]
        }]
        await ctx.channel.send(f'```\n{tabulate(table, headers="keys")}\n```')


    @bot.slash_command(description='指定したボットに対し停止コマンドを実行します。')
    async def mng_stop_bot(
        ctx: discord.ApplicationContext,
        bot_name: discord.Option(
            input_type=str,
            description=f'ボット名を指定してください。（入力候補）',
            choices=bot_names,
            required=True
        )
    ):
        """"""
        await ctx.respond(f'```\ncmd: mng_stop_bot, bot_name: {bot_name}\n```')
        res = stop(bots, bot_name)
        table =[{
            'cmd': 'mng_stop_bot',
            'bot_name': bot_name,
            'ret_code': res[0],
            'ret_msg': RETURN_CODE_MSG.get(res[0], 'unknown'),
            'err_msg': 'none' if res[1] == '' else res[1]
        }]
        await ctx.channel.send(f'```\n{tabulate(table, headers="keys")}\n```')


    @bot.slash_command(description='指定したボットに対し停止コマンド・起動コマンドを順次実行します。')
    async def mng_restart_bot(
        ctx: discord.ApplicationContext,
        bot_name: discord.Option(
            input_type=str,
            description=f'ボット名を指定してください。（入力候補）',
            choices=bot_names,
            required=True
        )
    ):
        """"""
        await ctx.respond(f'```\ncmd: mng_restart_bot, bot_name: {bot_name}\n```')
        res_stop = list(stop(bots, bot_name)) + ['mng_stop_bot']
        res_start = list(start(bots, bot_name)) + ['mng_start_bot']
        table = []
        for res in [res_stop, res_start]:
            table.append({
                'cmd': res[2],
                'bot_name': bot_name,
                'ret_code': res[0],
                'ret_msg': RETURN_CODE_MSG.get(res[0], 'unknown'),
                'err_msg': 'none' if res[1] == '' else res[1]
            })
        await ctx.channel.send(f'```\n{tabulate(table, headers="keys")}\n```')


    @bot.slash_command(description='指定したボットに対しgit pullコマンド・停止コマンド・起動コマンドを順次実行します。')
    async def mng_git_pull(
        ctx: discord.ApplicationContext,
        bot_name: discord.Option(
            input_type=str,
            description=f'ボット名を指定してください。（入力候補）',
            choices=bot_names,
            required=True
        )
    ):
        """"""
        await ctx.respond(f'```\ncmd: mng_git_pull, bot_name: {bot_name}\n```')
        res_pull = list(pull(bots, bot_name)) + ['mng_git_pull']    
        res_stop = list(stop(bots, bot_name)) + ['mng_stop_bot']
        res_start = list(start(bots, bot_name)) + ['mng_start_bot']
        table = []
        for res in [res_pull, res_stop, res_start]:
            table.append({
                'cmd': res[2],
                'bot_name': bot_name,
                'ret_code': res[0],
                'ret_msg': RETURN_CODE_MSG.get(res[0], 'unknown'),
                'err_msg': 'none' if res[1] == '' else res[1]
            })
        await ctx.channel.send(f'```\n{tabulate(table, headers="keys")}\n```')


    @bot.slash_command(description=f'ボットが稼働しているローカルマシンにコマンドを送ります。（タイムアウト{DO_CMD_TIMEOUT}秒）')
    async def mng_do_cmd(
        ctx: discord.ApplicationContext,
        command: discord.Option(
            input_type=str,
            description=f'許可コマンド [{", ".join(do_cmds)}]',
            required=True
        )
    ):
        await ctx.respond(f'```\ncmd: mng_do_cmd, command: {command}\n```')
        res = do_cmd(ctx, command)
        table = [{
            'cmd': 'mng_do_cmd',
            'command': command,
            'ret_code': res[0],
            'ret_msg': RETURN_CODE_MSG.get(res[0], 'unknown'),
            'err_msg': 'none' if res[1] == '' else res[1]
        }]
        await ctx.channel.send(f'```\n{tabulate(table, headers="keys")}\n```')
        
        LENGTH_LIMIT = 1900
        for std_name, std_output in zip(['stdout', 'stderr'], [res[2], res[3]]):
            if len(std_output) != 0:
                msg = f'[{std_name}]\n{std_output}'
                if len(msg) > LENGTH_LIMIT:
                    msg = f'[{std_name}] 表示できない前半を省略しました。\n<省略>{msg[-LENGTH_LIMIT:]}'
                await ctx.channel.send(f'```\n{msg}\n```')
        
    bot.run(get_config_json('discord_bot')['token'])


def start(bots: dict, bot_name: str) -> list[int, str]:
    """subprocess.Popenでボットを起動してbots['popen']に格納します。"""
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
            

def stop(bots: dict, bot_name: str) -> list[int, str]:
    """bots['popen']に格納されたsubprocess.Popenを停止します。"""
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


def do_cmd(ctx: discord.ApplicationContext, command: str) -> list[int, str, str, str]:
    """ローカルマシンでコマンドを実行します。"""
    do_cmd_permission = get_config_json('do_cmd_permission')
    if ctx.author.id not in do_cmd_permission['user_id']:
        return 3, 'User without permission.', '', ''

    pass_cmd = [cmd for cmd in do_cmd_permission['start_cmd'] if command.startswith(cmd)]
    if len(pass_cmd) == 0:
        return 3, f'Not permitted command.', '', ''

    try:
        ret = subprocess.run(
            [command],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            encoding='utf-8',
            timeout=DO_CMD_TIMEOUT  # タイムアウト設定
        )
        return 0, '', ret.stdout, ret.stderr
    except subprocess.TimeoutExpired as e:
        return 3, f'Timeout.({DO_CMD_TIMEOUT} sec)', '', ''


def get_config_json(name: str) -> Union[list, dict]:
    """configフォルダ内の設定を取得して返します。"""
    path = f'{os.path.abspath(os.path.dirname(__file__))}/config/{name}.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


if __name__ == '__main__':
    run_bot()