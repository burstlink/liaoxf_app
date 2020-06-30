#!/usr/bin/env python
# -*- coding:utf-8 -*-
# software: PyCharm
import logging
import aiomysql


# 打印sql执行的log
def log(sql):
    logging.info('SQL:%s ' % sql)


# 创建数据库连接池
# async/await
# async修饰function-->"异步函数"
# 耗时的io操作(具有__await__属性或者一个异步的函数)--> await
async def create_pool(loop, **kw):
    logging.info("create the database connection pool...")
    # 双下划线开头的成员是私有的，全局变量
    global __pool
    # kw.get方法后面是默认值
    __pool = await aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )


# 数据库操作-查找
async def select(sql, args, size=None):
    log(sql)
    # 从线程池获取数据库连接
    async with __pool.acquire() as conn:
        # 使用connection创建游标协程
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # 执行指定的sql语句操作(args是元组或者列表)
            await cur.execute(sql.replace('?', '%s'), args or ())
            if size:
                rs = await cur.fetchmany(size)
            else:
                rs = await cur.fetchall()
            await cur.close()
        logging.info('rows returned: %s' % len(rs))
        return rs


# 数据库操作-增删改
async def execute(sql, args, autocommit=True):
    log(sql)
    async with __pool.acquire() as conn:
        if not autocommit:
            # 开始数据库操作(事务)的协程
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                # 返回受影响的行数
                affected = cur.rowcount
            await cur.close()
            if not autocommit:
                # 提交数据库操作的协程
                await conn.commit()
        except BaseException as e:
            # 数据库事务失败回滚
            if not autocommit:
                # 回滚数据库操作的协程
                await conn.rollback()
            raise e
        return affected


# 常用数据库数据类型封装，方便对象定义时候使用
class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    # __str__函数，方便日志调用对象打印相关信息，不然只能打印对象内存地址
    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)


# mysql数据类型-	变长字符串
class StringField(Field):
    # 默认100长度(够用)
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)


# mysql数据类型-布尔型
class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


# mysql数据类型-极大整数值
class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)


# mysql数据类型-浮点类型
class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


# mysql数据类型-长文本数据
class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


# num=3，那L就是['?','?','?']，返回一个字符串'?,?,?'
def create_args_string(num):
    tmp = []
    for n in range(num):
        tmp.append('?')
    return ', '.join(tmp)


class ModelMetaclass(type):
    # __new__是创建实例的方法，__init__是实例创建之后初始化的方法，new方法的调用是发生在init之前
    def __new__(mcs, name, bases, attrs):
        """
        元类创建类对象方法
        :param name: 类对象的类名
        :param bases: 类对象的父类
        :param attrs: 类对象的命名空间，是个dict
        :return:
        """
        # 排除掉对Model类的修改，Model类是用户自定义对象直接继承的父类，主要继承了数据事务封装的方法
        # 不需要metaclass添加的这些属性方法
        if name == 'Model':
            return type.__new__(mcs, name, bases, attrs)
        table_name = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, table_name))
        mappings = dict()
        fields = []
        primary_key = None
        # attrs是一个dict，遍历k,v
        for k, v in attrs.items():
            # 从attar中过滤是Field类型的对象的value
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                # 主键True
                if v.primary_key:
                    # 如果前面的循环已经赋值的主键，则说明一个model出现两个主键数据，
                    if primary_key:
                        raise BaseException('Duplicate primary key for field: %s' % k)
                    primary_key = k
                else:
                    # 非主键field
                    fields.append(k)
        # 这就表示没有找到主键也要报错，主键一定要有
        if not primary_key:
            raise BaseException('Primary key not found.')
        # 从attrs中删除field属性的数据
        for k in mappings.keys():
            attrs.pop(k)
        #  ['a', 'b'] -->  ['`a`', '`b`']
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        # 整理后重新赋值属性
        attrs['__mappings__'] = mappings
        attrs['__table__'] = table_name
        attrs['__primary_key__'] = primary_key
        attrs['__fields__'] = fields
        # 生成select、insert、update、delete四个sql语句，存入attrs
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primary_key, ', '.join(escaped_fields), table_name)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (table_name, ', '.join(escaped_fields),
                                                                           primary_key,
                                                                           create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (table_name, ', '.join(map(lambda f: '`%s`=?' % (
                mappings.get(f).name or f), fields)), primary_key)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (table_name, primary_key)
        return type.__new__(mcs, name, bases, attrs)


class Model(dict, metaclass=ModelMetaclass):
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    # instance可以通过instance.key形式获取返回值
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    # instance可以通过instance.key=XX形式赋值
    def __setattr__(self, key, value):
        self[key] = value

    # getattr() 函数用于返回一个对象属性值
    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            # 当前实例找不到想要的属性值时，就要到__mappings__属性中查找
            field = self.__mappings__[key]
            # 如果查询出来的字段具有default属性，那就检查default属性值是方法还是具体的值
            if field.default is not None:
                # 如果是方法就直接返回调用后的值，如果是具体的值那就返回这个值
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                # 没属性的加进去
                setattr(self, key, value)
        return value

    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        # 通过条件来查询对象，一个对象对应数据库表中的一行
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            # 如果limit为一个整数n，那就将查询结果的前n个结果返回
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            # 如果limit为一个tuple，则前一个值代表索引，后一个值代表从这个索引开始要取的结果数
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = await select(' '.join(sql), args)
        # 返回一个cls类实例的数据list(查到的数据)
        return [cls(**r) for r in rs]

    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        sql = ['select count(`%s`) _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    async def find(cls, pk):
        # 主键查找
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    # save、update、remove实例方法
    async def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        # 执行sql语句后返回影响的行数
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warning('failed to insert record: affected rows: %s' % rows)

    async def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warning('failed to update by primary key: affected rows: %s' % rows)

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warning('failed to remove by primary key: affected rows: %s' % rows)
