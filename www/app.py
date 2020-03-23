#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:LeeYY
# datetime:2018/9/10 22:58
# software: PyCharm
import logging
import asyncio
import os
import json
import time
from datetime import datetime
from aiohttp import web
logging.basicConfig(level=logging.INFO)


def index(request):
    return web.Response(body=b'<h1>Awesome</h1>', content_type='html/plain')


async def init(loop):
    app = web.Application()
    app.add_routes([web.get('/', index)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 9000)
    await site.start()
    logging.info('Server started at http://127.0.0.1:9000...')


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init(loop))
    loop.run_forever()
