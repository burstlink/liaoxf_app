#!/usr/bin/env python
# -*- coding:utf-8 -*-
# software: PyCharm

import os
from datetime import datetime
from fabric import task


_TAR_FILE = 'dist-awesome.tar.gz'
_REMOTE_TMP_TAR = '/tmp/%s' % _TAR_FILE
_REMOTE_BASE_DIR = '/srv/awesome'

# 本地部署任务
@task
def deploy(c):
    newdir = 'www-%s' % datetime.now().strftime('%y-%m-%d_%H.%M.%S')
    # 删除已有的tar文件:
    c.run('rm -f %s' % _REMOTE_TMP_TAR)
    # 上传新的tar文件:
    c.run('cp dist/%s %s' % (_TAR_FILE, _REMOTE_TMP_TAR))
    # 创建新目录:
    c.sudo('bash -c "cd %s && mkdir %s"' % (_REMOTE_BASE_DIR, newdir))
    # 解压到新目录, vi添加浏览权限:
    c.sudo('bash -c "cd %s/%s && tar -xzvf %s && chmod -R 775 static/ && chmod 775 favicon.ico"' % (_REMOTE_BASE_DIR, newdir, _REMOTE_TMP_TAR))
    # 重置软链接
    c.sudo('bash -c "cd %s && rm -rf www && ln -s %s www && chown root:root www && chown -R root:root %s"' % (_REMOTE_BASE_DIR, newdir, newdir))
    # 重启Python服务和nginx服务器:
    c.sudo('supervisorctl restart vi', warn=True)
    c.sudo('nginx -s reload', warn=True)

# 本地打包文件
@task
def build(c):
    includes = ['static', 'templates', 'favicon.ico', '*.py', 'manifest.json', 'sw.js']
    excludes = ['test', '.*', '*.pyc', '*.pyo']
    c.run('rm -f dist/%s' % _TAR_FILE)
    run_path = os.path.join(os.path.abspath('.'), 'www')
    with c.cd(run_path):
        cmd = ['tar', '--dereference', '-czvf', '../dist/%s' % _TAR_FILE]
        cmd.extend(['--exclude=\'%s\'' % ex for ex in excludes])
        cmd.extend(includes)
        c.run(' '.join(cmd))
