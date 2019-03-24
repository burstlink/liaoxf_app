#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:LeeYY
# datetime:2018/9/21 1:05
# software: PyCharm
'默认配置文件'


configs = {
    'db': {  # 定义数据库相关信息
        "host": "127.0.0.1",
        "port": 3306,
        "user": "root",
        "password": "liyy1234",
        "database": "awesome"
        },
    "session": {  # 定义会话信息
        "secret": "awesome"
        }
    }