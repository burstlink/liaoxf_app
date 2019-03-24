#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:LeeYY
# datetime:2018/9/21 1:08
# software: PyCharm
'自定义的配置文件,用以覆盖一些默认配置,从而避免了对默认配置文件的直接修改'

__author__ = 'Engine'

configs = {
    "db": {  # 重载的数据库信息,将会覆盖默认的数据库相关配置信息
        "host": "127.0.0.1"
        }
    }