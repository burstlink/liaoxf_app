#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:LeeYY
# datetime:2018/9/11 0:10
# software: PyCharm
import asyncio
import logging
import aiomysql


# 所谓ORM就是对象关系映射：对象模型表示的对象映射到基于SQL的关系模型数据库结构中去
# 打印sql执行的log
def log(sql, args=()):
    logging.info('SQL:%s ' % sql)


# ----------------创建数据库线程池--------------------
async def create_pool(loop, **kw):
    logging.info("To create database connection pool...")
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


# ----------------sql语句封装成函数begin---------------------
async def select(sql, args, size=None):
    log(sql, args)
    global __pool
    async with __pool.get() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql.replace('?', '%s'), args or ())
            if size:
                rs = await cur.fetchmany(size)
            else:
                rs = await cur.fetchall()
        logging.info('rows returned: %s' % len(rs))
        return rs


async def execute(sql, args, autocommit=True):
    log(sql)
    async with __pool.get() as conn:
        if not autocommit:
            # 如果不是自动提交，也就是autocommit=False的话，就conn.begin()，不知道啥意思
            await conn.begin()  # 我猜可能是，不是自动连接数据库就连接数据库的意思
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount  # affected是受影响的行数，比如说插入一行数据，那受影响行数就是一行
            if not autocommit:
                # 这边同样不知道是啥意思，如果不是自动提交那就手动提交？提交什么，提交到哪儿？猜都没法猜
                await conn.commit()
        # 捕获数据库错误，但我不清楚具体是什么错误，为什么select函数不需要捕获？
        except BaseException as e:
            if not autocommit:
                # rollback是回滚的意思，那滚的是个什么玩意儿？不造啊
                await conn.rollback()
            raise
        return affected


# ----------------sql语句封装成函数end---------------------


# 这个函数在元类中被引用，作用是创建一定数量的占位符
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    # 比如说num=3，那L就是['?','?','?']，通过下面这句代码返回一个字符串'?,?,?'
    return ', '.join(L)


# -----------数据基类以及派生数据类begin---------------
class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)


class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)


class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)


class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


# -----------数据基类以及派生数据类over---------------

class ModelMetaclass(type):
    def __new__(cls, name, bases, attrs):
        # 这就是前面说的，写在最前面防止Model类操作元类，大家可以试着在这儿print(name)
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        # 从这儿开始当前类只可能是User类、Blog类、Comment类，下面我们以User类为例来解释
        # tableName就是需要在数据库中对应的表名，如果User类中没有定义__table__属性，那默认表名就是类名，也就是User
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        mappings = dict()  # 创建一个空的dict是为了后面储存User类的属性
        fields = []  # fields用来储存User类中除主键外的属性名
        primaryKey = None  # 主键默认为None，后面找到主键之后再赋值
        # attrs是User类的属性集合，是一个dict，需要通过items函数转换为[(k1,v1),(k2,v2)]这种形式，才能用for k, v in来循环
        for k, v in attrs.items():
            if isinstance(v, Field):  # 检测v的类型是不是Field
                logging.info('  found mapping: %s ==> %s' % (k, v))
                # 看到这儿大家一定很奇怪，attrs本来就是一个dict，把这个dict拆开来存入另一个dict是为什么？后面会解释的
                mappings[k] = v
                if v.primary_key:  # 如果该字段的主键值为True，那就找到主键了
                    if primaryKey:  # 在主键不为空的情况下又找到一个主键就会报错，因为主键有且仅有一个
                        raise BaseException('Duplicate primary key for field: %s' % k)
                    primaryKey = k  # 为主键赋值
                else:
                    fields.append(k)  # 不是主键的属性名储存到非主键字段名的list中
        if not primaryKey:  # 这就表示没有找到主键，也要报错，因为主键一定要有
            raise BaseException('Primary key not found.')
        for k in mappings.keys():  # 把User类中原有的属性全部删除
            attrs.pop(k)
        # fields中的值都是字符串，下面这个匿名函数的作用是在字符串两边加上``生成一个新的字符串，为了后面生成sql语句做准备
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__mappings__'] = mappings  # 把mappings这个dict存入attrs这个dict中
        attrs['__table__'] = tableName  # 其实attrs本来可能就有__table__属性的，但前面attrs.pop(k)把attrs里面的东西全给删了，所以这里需要重新赋值
        attrs['__primary_key__'] = primaryKey  # 存入主键属性名
        attrs['__fields__'] = fields  # 存入除主键外的属性名
        # 下面四句就是生成select、insert、update、delete四个sql语句，然后分别存入attrs
        # 要理解下面四句代码，需要对sql语句格式有一定的了解，其实并不是很难
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (
        tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (
        tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)  # 一个全新的User类新鲜出炉了，慢慢享用吧


# 到这儿可以总结一下元类到底干了些什么，还是以User类为例
# 首先、元类找出User类在数据库中对应的表名，对User类的自有属性逐条进行分析，找出主键和非主键，同时把这些属性全部存入mappings这个dict
# 然后、删除User类的全部属性，因为实际操作数据库的时候用不到这些属性
# 最后、把操作数据库需要用到的属性添加进去，这包括所有字段和字段类型的对应关系，类对应的表名、主键名、非主键名，还有四句sql语句
# 这些属性才是操作数据库正真需要用到的属性，但仅仅只有这些属性还是不够，因为没有方法
# 而Model类就提供了操作数据库要用到的方法

class Model(dict, metaclass=ModelMetaclass):
    # 定义Model类的初始化方法
    def __init__(self, **kw):
        # 这里直接调用了Model的父类dict的初始化方法，把传入的关键字参数存入自身的dict中
        super(Model, self).__init__(**kw)

    # 没有这个方法，获取dict的值需要通过d[k]的方式，有这个方法就可以通过属性来获取值，也就是d.k
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    # 和上面一样，不过这个是用来设置dict的值，通过d.k=v的方式
    def __setattr__(self, key, value):
        self[key] = value

    # 上面两个方法是用来获取和设置**kw转换而来的dict的值，而下面的getattr是用来获取当前实例的属性值，不要搞混了
    def getValue(self, key):
        # 如果没有与key相对应的属性值则返回None
        return getattr(self, key, None)

    # 如果当前实例没有与key对应的属性值时，就需要调用下面的方法了
    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            # 当前实例找不到想要的属性值时，就要到__mappings__属性中去找了，__mappings__属性对应的是一个dict，这个前面提过了
            field = self.__mappings__[key]
            if field.default is not None:  # 如果查询出来的字段具有default属性，那就检查default属性值是方法还是具体的值
                # 如果是方法就直接返回调用后的值，如果是具体的值那就返回这个值
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)  # 查到key对应的value后就设置为当前实例的属性，是为了方便下次查询？不是很确定
        return value

    @classmethod  # 这个装饰器是类方法的意思，这样就可以不创建实例直接调用类的方法
    # select操作的情况比较复杂，所以定义了三种方法
    async def findAll(cls, where=None, args=None, **kw):
        ' find objects by where clause. '  # 通过条件来查询对象，一个对象对应数据库表中的一行
        sql = [cls.__select__]  # 有同学说cls就相当与是self，我感觉对象用self代表自己，类用cls代表自己，个人看法仅供参考
        if where:  # 如果有where条件就在sql语句中加入字符串'where'和变量where
            sql.append('where')
            sql.append(where)
        if args is None:  # 这个参数是在执行sql语句前嵌入到sql语句中的，如果为None则定义一个空的list
            args = []
        orderBy = kw.get('orderBy', None)  # 从**kw中取得orderBy的值，没有就默认为None
        if orderBy:  # 解释同where
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')  # sql中limit有两种用法
            if isinstance(limit, int):  # 如果limit为一个整数n，那就将查询结果的前n个结果返回
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                # 如果limit为一个两个值的tuple，则前一个值代表索引，后一个值代表从这个索引开始要取的结果数
                sql.append('?, ?')
                args.extend(limit)  # 用extend是为了把tuple的小括号去掉，因为args传参的时候不能包含tuple
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))  # 如果不是上面两种情况，那就一定出问题了
        rs = await select(' '.join(sql), args)  # sql语句和args都准备好了就交给select函数去执行
        return [cls(**r) for r in rs]  # 将查询到的结果一一返回，看不懂cls(**r)的用法，虽然能猜出这是个什么

    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        ' find number by select and where. '  # 根据where条件查询结果数，注意，这里查询的是数量
        sql = ['select count(`%s`) _num_ from `%s`' % (selectField, cls.__table__)]  # 这sql语句是直接重构的，不是调用属性，看不懂_num_是什么意思
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:  # 如果查询结果数为0则返回None
            return None
        return rs[0]['_num_']  # rs应该是个list，而这个list的第一项对应的应该是个dict，这个dict中的_num_属性值就是结果数，我猜应该是这样吧

    @classmethod
    async def find(cls, pk):
        ' find object by primary key. '  # 根据主键查找是最简单的，而且结果只有一行，因为主键是独一无二的
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    # save、update、remove这三个方法需要管理员权限才能操作，所以不定义为类方法，需要创建实例之后才能调用
    async def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))  # 把实例的非关键字属性值全都查出来然后存入args这个list
        args.append(self.getValueOrDefault(self.__primary_key__))  # 把主键找出来加到args这个list的最后
        rows = await execute(self.__insert__, args)  # 执行sql语句后返回影响的结果行数
        if rows != 1:  # 一个实例只能插入一行数据，所以返回的影响行数一定为1,如果不为1那就肯定错了
            logging.warning('failed to insert record: affected rows: %s' % rows)

    # 下面两个的解释同上
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
