#!/usr/bin/env python
# -*- coding:utf-8 -*-
# software: PyCharm
from models import User
import asyncio
import orm
import pdb
import time


# 测试插入
async def test_save(loop):
    await orm.create_pool(loop, user='root', password='xxx', db='awesome')
    u = User(name='test01', email='test01@example.com',
             passwd='test01', image='about:blank')
    # pdb.set_trace()
    await u.save()


# 测试查询
async def test_findAll(loop):
    await orm.create_pool(loop, user='root', password='xxx', db='awesome')
    # 这里给的关键字参数按照xxx='xxx'的形式给出，会自动分装成dict
    rs = await User.findAll()
    # pdb.set_trace()
    for i in range(len(rs)):
        print(rs[i])


# 查询条数
async def test_findNumber(loop):
    await orm.create_pool(loop, user='root', password='xxx', db='awesome')
    count = await User.findNumber('email')
    print(count)


# 根据主键查找，这里试ID
async def test_find_by_key(loop):
    await orm.create_pool(loop, user='root', password='xxx', db='awesome')
    # rs是一个dict
    # ID请自己通过数据库查询
    rs = await User.find('001593513753659fb3cb929716340b389a79be4ad27288c000')
    print(rs)


# 根据主键更新
async def test_update(loop):
    await orm.create_pool(loop, user='root', password='xxx', db='awesome')
    # 必须按照列的顺序来初始化：'update `users` set `created_at`=?, `passwd`=?, `image`=?,
    # `admin`=?, `name`=?, `email`=? where `id`=?' 注意这里要使用time()方法，否则会直接返回个时间戳对象，而不是float值
    u = User(id='001593513753659fb3cb929716340b389a79be4ad27288c000', created_at=time.time(), passwd='test',
             image='about:blank', admin=True, name='test', email='hello1@example.com')
    # id必须和数据库一直，其他属性可以设置成新的值,属性要全
    # pdb.set_trace()
    await u.update()


# 根据主键删除
async def test_remove(loop):
    await orm.create_pool(loop, user='root', password='xxx', db='awesome')
    # 用id初始化一个实例对象
    u = User(id='001593513753659fb3cb929716340b389a79be4ad27288c000')
    await u.remove()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_remove(loop))
    __pool = orm.__pool
    # 需要先关闭连接池
    __pool.close()
    loop.run_until_complete(__pool.wait_closed())
    loop.close()
