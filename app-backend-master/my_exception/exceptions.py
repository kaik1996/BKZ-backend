#! Python3
from rest_framework.exceptions import APIException
from rest_framework import status
from django.utils.translation import gettext_lazy as _


class SMSTypeError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('短信发送格式设置错误, 仅支持单发与群发')
    default_code = 'TypeError'


class SMSSendError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('短信发送途中出现异常')
    default_code = 'SendError'


class GetInstanceError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('查找实例时出现了意外')
    default_code = 'GetInstanceError'

class TokenExpiredError(APIException):
    status_code = status.HTTP_203_NON_AUTHORITATIVE_INFORMATION
    default_detail = _('token已过期')
    default_code = 'TokenExpiredError'


class SubwayNotExistError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('subway not exist')
    default_code = 'SubwayNotExistError'


