import asyncio
import json
import re
from datetime import datetime, timedelta

from botpy import BotAPI
from botpy.message import GroupMessage
from croniter.croniter import croniter
from httpcore import ConnectTimeout

import maimai.api
from utils.command_util import Commands
from utils.database import Database
from utils.score_process import diving_fish_uploading, lxns_uploading


@Commands("bind", "绑定", "绑")
async def bind(api: BotAPI, message: GroupMessage, command: str, params: list[str] | None = None):
    if params is None:
        await message.reply(
            content=f"请在命令后附带有效登入二维码内容\r\n例：/{command} SGWCMAID000...")
        return True

    if len(params) != 1 or len(params[0]) != 84 or not params[0].startswith("SGWCMAID") or re.match(
            "^[0-9A-F]+$", params[0][20:]) is None:
        await message.reply(content="无效的登入二维码")
        return True

    try:
        if datetime.now() - datetime.strptime(params[0][8:20], "%y%m%d%H%M%S") > timedelta(
                minutes=10):
            await message.reply(content="过期的登入二维码")
            return True
    except ValueError:
        await message.reply(content="无效的登入二维码")
        return True

    try:
        result = await maimai.api.A(params[0])
    except ConnectTimeout:
        await message.reply(content="远端访问超时")
        return True
    except ValueError:
        await message.reply(content="远端访问异常")
        return True

    if result["errorID"] != 0 or result["userID"] == -1:
        await message.reply(content="API异常")
        return True

    if result["userID"] in maimai.api.queues and type(maimai.api.queues[result["userID"]]) is list:
        await message.reply(content="队列中有一个尚未完成的任务")
        return True

    with Database("uid") as db:
        db.set(message.author.member_openid, result["userID"])
    await message.reply(content="舞萌中二账号绑定成功")
    return True


@Commands("binddf", "绑定水鱼", "绑水鱼")
async def binddf(api: BotAPI, message: GroupMessage, command: str, params: list[str] | None = None):
    if params is None:
        await message.reply(content=f"请在命令后附带水鱼上传Token\r\n例：/{command} 000...")
        return True

    if len(params) != 1 or len(params[0]) != 128 or re.match("^[0-9A-Za-z]+$", params[0]) is None:
        await message.reply(content="无效的水鱼上传Token")
        return True

    with Database("dfid") as db:
        db.set(message.author.member_openid, params[0])
    await message.reply(content="水鱼上传Token绑定成功")
    return True


@Commands("bindlx", "绑定落雪", "绑落雪")
async def bindlx(api: BotAPI, message: GroupMessage, command: str, params: list[str] | None = None):
    if params is None:
        await message.reply(content=f"请在命令后附带好友码\r\n例：/{command} 000...")
        return True

    if len(params) != 1 or len(params[0]) != 15 or not params[0].isdigit():
        await message.reply(content="无效的好友码")
        return True

    with Database("lxid") as db:
        db.set(message.author.member_openid, params[0])
    await message.reply(content="好友码绑定成功")
    return True


@Commands("pull", "爬取", "拉取", "推送", "推")
async def pull(api: BotAPI, message: GroupMessage, command: str, params: None = None):
    with Database("uid") as db:
        uid = db.get(message.author.member_openid)
    if not uid:
        await message.reply(content="尚未绑定舞萌中二账号")
        return True

    with Database("dfid") as db:
        dfid = db.get(message.author.member_openid)
    with Database("lxid") as db:
        lxid = db.get(message.author.member_openid)
    if not dfid and not lxid:
        await message.reply(content="尚未绑定任一查分器")
        return True

    try:
        result = await maimai.api.B(uid)
    except ConnectTimeout:
        await message.reply(content="远端访问超时")
        return True
    except ValueError:
        await message.reply(content="远端访问异常")
        return True

    tasks = []
    if dfid:
        tasks.append(diving_fish_uploading(dfid, result))

    if lxid:
        tasks.append(lxns_uploading(lxid, result))

    results = await asyncio.gather(*tasks)
    msgs = []
    for _, result in enumerate(results):
        if result[0] or result[1] is None:
            continue

        msgs.append(result[1])

    if len(msgs) <= 0:
        await message.reply(content="成绩推送成功")
        return True

    await message.reply(content=f"成绩推送失败：\r\n{"\r\n".join(msgs)}")
    return True


@Commands("mai", "埋", "下埋")
async def mai(api: BotAPI, message: GroupMessage, command: str, params: list[str] | None = None):
    with Database("uid") as db:
        uid = db.get(message.author.member_openid)
    if not uid:
        await message.reply(content="尚未绑定舞萌中二账号")
        return True

    if params is None:
        await message.reply(content=f"请在命令后附带需要下埋的牌子\r\n例：/{command} 真极")
        return True

    if len(params) != 1 or len(params[0]) > 3 or len(params[0]) < 2:
        await message.reply(content="无效的牌子")
        return True

    with open("./data/map/mai_ver.json", "r", encoding="utf-8") as f:
        mai_ver: dict[str, list[str]] = json.load(f)

    ver_name = params[0][0]
    act_type = params[0][1:]
    if params[0] == "霸者":
        ver_name = "舞"
        act_type = "清"
    elif ver_name not in mai_ver or act_type not in ["极", "将", "神", "舞舞"] or params[
        0] == "真将":
        await message.reply(content="无效的牌子")
        return True

    try:
        succeed, msg = await maimai.api.C(uid, mai_ver[ver_name], act_type)
    except ConnectTimeout:
        await message.reply(content="远端访问超时")
        return True
    except ValueError:
        await message.reply(content="远端访问异常")
        return True

    if not succeed:
        await message.reply(content=f"任务提交失败：{msg}")
        return True

    queues = [k for (k, v) in maimai.api.queues.items() if type(v) is list]
    await message.reply(
        content=f"已提交至任务队列，{f"您位于第{len(queues)}位" if len(queues) > 1 else "下埋中"}")
    return True


@Commands("query", "查询进度", "查进度")
async def query(api: BotAPI, message: GroupMessage, command: str, params: None = None):
    with Database("uid") as db:
        uid = db.get(message.author.member_openid)
    if not uid:
        await message.reply(content="尚未绑定舞萌中二账号")
        return True

    if uid not in maimai.api.queues:
        await message.reply(content="队列中尚无任务")
        return True

    if type(maimai.api.queues[uid]) is str:
        await message.reply(content=f"任务被中断：{maimai.api.queues[uid]}")
        del maimai.api.queues[uid]
        return True

    queues = [k for (k, v) in maimai.api.queues.items() if type(v) is list]
    await message.reply(
        content=f"任务剩余{len(maimai.api.queues[uid])}，{"进行中" if queues[0] == uid else f"等待中，位于第{queues.index(uid) + 1}位"}")
    return True


@Commands("break", "中断", "打断", "停埋")
async def brea(api: BotAPI, message: GroupMessage, command: str, params: None = None):
    with Database("uid") as db:
        uid = db.get(message.author.member_openid)
    if not uid:
        await message.reply(content="尚未绑定舞萌中二账号")
        return True

    if uid not in maimai.api.queues or type(maimai.api.queues[uid]) is not list:
        await message.reply(content="队列中尚无任务")
        return True

    maimai.api.queues[uid].clear()
    await message.reply(content="任务已中断")
    return True


@Commands("sche", "定时", "定时拉取", "定时推送", "定时拉", "定时推")
async def sche(api: BotAPI, message: GroupMessage, command: str, params: list[str] | None = None):
    if params is None:
        await message.reply(content=f"请在命令后附带合法表达式\r\n例：/{command} 0 0/8")
        return True

    if len(params) != 2 or not croniter.is_valid(f"0 {params[0]} {params[1]} * * ?"):
        await message.reply(content="无效的表达式")
        return True

    raise NotImplementedError
