#!/usr/bin/env python
# -*- coding:utf-8 -*-
# software: PyCharm


class APIError(Exception):
    def __init__(self, error, data='', message=''):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message


class APIValueError(APIError):
    def __init__(self, filed, message=''):
        super(APIValueError, self).__init__('value:invalid', filed, message)


class APIResourceNotFoundError(APIError):
    def __init__(self, filed, message=''):
        super(APIResourceNotFoundError, self).__init__('value:notfound', filed, message)


class APIPressionError(APIError):
    def __init__(self, message=''):
        super(APIPressionError, self).__init__('permission:forbidden', 'permission', message)
