#!/usr/bin/env python
# -*- coding:utf-8 -*-
# software: PyCharm
import logging
from aiohttp import web
logging.basicConfig(level=logging.INFO)


# 一个请求处理程序，必须是个协程(async)，接受Request实例作为唯一的参数
async def index(request):
    text = "My first python web application."
    return web.Response(text=text)


def init():
    # 创建一个Application实例，注册请求处理程序(依据特定的http方法和请求路径)
    app = web.Application()
    app.add_routes([web.get('/', index), ])
    # 调用run_app运行application实例
    web.run_app(app, host="127.0.0.1", port=9000)
    logging.info('Server started at http://127.0.0.1:9000...')


if __name__ == '__main__':
    init()
