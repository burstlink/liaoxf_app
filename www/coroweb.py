#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:LeeYY
# datetime:2019/3/18 22:31
# software: PyCharm
import asyncio, os,inspect, logging, functools
from urllib import parse
from aiohttp import web
from apis import APIError


def get(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator


def post(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator


def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # 参数类型为命名关键字参数且没有指定默认值
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)


def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # 所有命名关键字参数的参数名都提取出来
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)


# 判断fn有没有命名关键字参数，有的话就返回True
def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True


# 判断fn有没有关键字参数，有的话就返回True
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True


def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        # 找到参数名为request的参数后把found设置为True
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and
                      param.kind != inspect.Parameter.KEYWORD_ONLY and
                      param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named '
                             'parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found


class RequestHandler(object):
    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    async def __call__(self, request):
        kw = None
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Context-Type.')
                ct = request.content_type.lower()
                if ct.startswith('appliction/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                elif ct.startswith('appliction/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # 没有关键字参数但有命名关键字参数
                copy = dict()
                for name in self._named_kw_args:
                    # 把命名关键字都提取出来，存入copy这个dict
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            for k, v in request.match_info.items():  # 不懂
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            # 如果有request参数，就把这个参数存入kw
            kw['request'] = request
        if self._required_kw_args:
            # 如果有未指定默认值的命名关键字参数
            for name in self._required_kw_args:
                # 用for循环迭代
                if name not in kw:
                    # kw必须包含全部未指定默认值的命名关键字参数，如果发现遗漏则说明有参数没传入
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))


def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        # 如果函数即不是一个协程也不是生成器，那就把函数变成一个协程
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__,
                                                ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))


def add_routes(app, module_name):
    # 因为handlers模块在当前目录下，所以在app.py中传入的module_name是handlers
    # 假设handlers模块在handler目录下，那传入的module_name就是handler.handlers
    n = module_name.rfind('.')
    # 找出module_name中.的索引位置
    if n == (-1):
        # -1表示没有找到，说明模块在当前目录下，直接导入
        # 查了下官方文档，__import__的作用类似import，import是为当前模块导入另一个模块，而__import__则是返回一个对象
        mod = __import__(module_name, globals(), locals())
    else:
        # 当module_name为handler.handlers时，[n+1:]就是取.后面的部分，也就是handlers
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)#
    for attr in dir(mod):
        if attr.startswith('_'):
            # 下划线开头说明是私有属性，不是我们想要的，直接跳过进入下一个循环
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            # 查看提取出来的属性是不是函数
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                # 如果是函数，再判断是否有__method__和__route__属性
                add_route(app, fn)
