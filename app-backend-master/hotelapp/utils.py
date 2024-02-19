import logging
import re
from rest_framework import exceptions
from rest_framework.permissions import BasePermission
from rest_framework.authentication import BaseAuthentication
from django.utils import timezone
from django.middleware.csrf import CsrfViewMiddleware
# 分页测试
from rest_framework.pagination import PageNumberPagination
# SmsCode required
import django_redis
from random import choice
# 腾讯云短信服务 rows: 7-8
from SmsSDK.tencentSMS import TencentSMS
# 上传文件预签名地址生成器
import time
from datetime import timedelta, datetime
from minio import Minio
import uuid
from minio.datatypes import PostPolicy
import base64
import json
from Crypto.Cipher import AES
import requests
from hotelapp.models import AgencyUser
from my_exception.exceptions import SMSTypeError, SMSSendError, TokenExpiredError
from hotelapp.models import LandlordUser, AgencyUser, SuperUser, LandlordToken, AgencyToken, SuperUserToken

MINIO_URL = '106.52.14.160:9000'
ACCESS_KEY = 'pengsiji'
SECRET_KEY = 'pengsiji2019'
bucket_name = 'media'
object_name = 'sources.list'

APIKEY = '54039892c2c858dc2f2e3829d5226c1d'  # should fix

# 设置log
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format=' %(asctime)s - %(levelname)s - %(message)s')

# 验证手机号码是否符合规格的正则表达式
REGEX_MOBILE = r'^1[3568]\d{9}$|^147\d{8}$|^176\d{8}$'
# 短信发送类型：单发和群发
SINGLE = 0
MULTIPLE = 1

# DISTANCE_TYPE = (
#     ('0', '0.5km以内'), ('1', '1km以内'), ('2', '2km以内'), ('3', '大于2km')
# )

# def userAuthentication(my_request):
#     """"""
#     token = my_request.META.get("HTTP_TOKEN")
#     if not token:
#         return None
#     try:
#         token_manager = TokenManager()
#         token_manager.token = token
#         token_manager.varify_token()
#         user = token_manager.mobile
#     except:
#         logger.debug('账号认证异常抛出')
#         user = None
#     # Unauthenticated, CSRF validation not required
#
#     if not user:
#         return None
#     # CSRF passed with authenticated user
#     return user

def userAuthentication(my_request):
    """"""
    token = my_request.META.get("HTTP_TOKEN")
    if not token:
        return None
    token_manager = TokenManager()
    token_manager.token = token
    if re.search('agency', my_request.get_full_path()):
        token_manager.prefix = 'A_'
        token_manager.model_class = AgencyToken
    elif re.search('superuser', my_request.get_full_path()):
        token_manager.prefix = 'S_'
        token_manager.model_class = AgencyToken
    else:
        token_manager.model_class = LandlordToken
    token_manager.get_origin_data()
    if not token_manager.mobile:
        instance = token_manager.find_instance_in_table()
        if instance:
            raise TokenExpiredError
    return (token_manager.mobile, token_manager.token)


class MyPaginatioin(PageNumberPagination):
    """
    定制化page
    """
    page_size = 10   # 10项
    page_query_param = 'page'
    page_size_query_param = 'page_size'
    max_page_size = 20


# 中介账号权限验证 #
class AgencyPermission(BasePermission):
    def has_permission(self, request, view):
        """
        判断是否为房东
        :param request: 请求
        :param view: 视图默认true
        :return: True / False
        """
        if str(request.user) != 'AnonymousUser':
            return False
        else:
            return True

    def has_object_permission(self, request, view, obj):
        """
        :param request:
        :param view:
        :param obj:
        :return:
        """
        if obj.mobile == request.user:
            return True
        else:
            return False


class Agency2HousePermission(BasePermission):
    """
    中介账号权限
    """
    def has_permission(self, request, view):
        """
        匿名用户和非会员不能查看房源
        """
        if str(request.user) != 'AnonymousUser':
            try:
                instance = AgencyUser.objects.get(mobile=request.user)
            except:
                raise exceptions.PermissionDenied
            if instance.vip_type != '0':
                return True
        else:
            return False

    def has_object_permission(self, request, view, obj):
        return True


class AgencyAuthentication(BaseAuthentication):
    """中介账号认证"""
    def authenticate(self, request):
        """认证方法
        Returns a `User` if the request session currently has a logged in user.
        Otherwise returns `None`.
        """
        return userAuthentication(request)


class SuperUserAuthentication(BaseAuthentication):
    """管理员账号认证"""
    def authenticate(self, request):
        token = request.META.get("HTTP_TOKEN")
        if not token:
            return None
        token_manager = TokenManager()
        token_manager.token = token
        token_manager.prefix = 'S_'
        token_manager.model_class = SuperUserToken
        token_manager.get_origin_data()
        if not token_manager.mobile:
            instance = token_manager.find_instance_in_table()
            if instance:
                raise TokenExpiredError
        return (token_manager.mobile, token_manager.token)


class Agency2FavoritesPermission(BaseAuthentication):
    """中介对"""
    def has_permission(self, request, view):
        """判断是否为匿名用户
        :param request: 请求
        :param view: 视图默认true
        :return: True / False
        """
        if str(request.user) == 'AnonymousUser':
            return False
        else:
            return True

    def has_object_permission(self, request, view, obj):
        """
        :param request:
        :param view:
        :param obj:
        :return:
        """
        if obj.mobile == request.user:
            return True
        else:
            return False


class SuperUser2HousePermission(BasePermission):
    """
    中介账号权限
    """
    def has_permission(self, request, view):
        if str(request.user) != 'AnonymousUser':
            try:
                instance = SuperUser.objects.filter(mobile=request.user).first()
            except:
                raise exceptions.PermissionDenied
            if instance is not None:
                return True
        else:
            return False

    def has_object_permission(self, request, view, obj):
        return True


class BulletinBoardAuthentication(BaseAuthentication):
    def authenticate(self, request):
        return userAuthentication(request)


class BulletinBoardPermission(BasePermission):
    def has_permission(self, request, view):
        """
        当用户是超级用户可以crud，非超级用户只能查看
        """
        if request.method in ['GET'] or SuperUser.objects.filter(mobile=request.user).count == 1:
            return True
        return False

    def has_object_permission(self, request, view, obj):
        """
        :param request:
        :param view:
        :param obj:
        :return:
        """
        if obj.mobile == request.user:
            return True
        else:
            return False


# 房东账号的权限验证
class LandlordPermission(BasePermission):
    """
    房东账号权限
    """
    def has_permission(self, request, view):
        """
        判断是否为房东
        :param request: 请求
        :param view: 视图默认true
        :return: True / False
        """
        if str(request.user) != 'AnonymousUser':
            return True
        else:
            return False

    def has_object_permission(self, request, view, obj):
        """
        :param request:
        :param view:
        :param obj:
        :return:
        """
        if obj.mobile == request.user:
            return True
        else:
            return False


# 房东对房源CURD时对账号的权限验证
class Landlord2HousePermission(BasePermission):
    """
    房东账号权限
    """
    def has_permission(self, request, view):
        """
        判断是否为房东
        :param request: 请求
        :param view: 视图默认true
        :return: True / False
        """
        if str(request.user) == 'AnonymousUser':
            raise exceptions.PermissionDenied
        return True
        # if self.queryset.objects.exclude(mobile=request.user).count():
        #     return True
        # else:
        #     return False

    def has_object_permission(self, request, view, obj):
        """
        :param request:
        :param view:
        :param obj:
        :return:
        """
        if obj.uploader.mobile == request.user:
            return True
        else:
            return False


# 房东对房源CURD时对账号的权限验证
class Landlord2QRCodePermission(BasePermission):
    """
    房东账号权限
    """
    def has_permission(self, request, view):
        """
        判断是否为房东
        :param request: 请求
        :param view: 视图默认true
        :return: True / False
        """
        if str(request.user) == 'AnonymousUser':
            raise exceptions.PermissionDenied
        return True
        # if self.queryset.objects.exclude(mobile=request.user).count():
        #     return True
        # else:
        #     return False

    def has_object_permission(self, request, view, obj):
        """
        :param request:
        :param view:
        :param obj:
        :return:
        """
        if obj.uploader.mobile == request.user:
            return True
        else:
            return False


class LandlordAuthentication(BaseAuthentication):
    """
    房东账号认证
    """
    def authenticate(self, request):
        """
        认证方法
        Returns a `User` if the request session currently has a logged in user.
        Otherwise returns `None`.
        """
        return userAuthentication(request)


class PublicAuthentication(BaseAuthentication):
    """
    房东账号认证
    """
    def authenticate(self, request):
        """
        认证方法
        Returns a `User` if the request session currently has a logged in user.
        Otherwise returns `None`.
        """
        return userAuthentication(request)


class SmsCode:
    """
    短信验证码管理类，包含：
    读取缓存中的验证码，
    生成随机验证码，
    发送验证码，
    保存验证码至redis，
    返回短信验证结果
    """
    prefix = 'LL_'
    phone = ''
    cache = django_redis.get_redis_connection()
    code = ''
    is_sent = False

    def __init__(self, phone):
        self.phone = '+86'+phone

    def get_origin_code(self):

        self.code = self.cache.get(self.prefix + self.phone).decode()
        return self.code

    def generate_code(self):
        """生成6位数字验证码"""
        seeds = '1234567890'
        random_str = ''
        for i in range(6):
            random_str += (choice(seeds))
        self.code = random_str
        return self.code

    def send_code(self):
        tx_mes = TencentSMS()
        try:
            mes_state = tx_mes.message_send(self.phone, self.code)
        except Exception as err:
            logger.info(err)
            self.is_sent = False
        if mes_state is not None:
            self.is_sent = True

    def save_to_cache(self):
        self.cache.set(self.prefix + self.phone, self.code, 60*2)
        return True

    def varify_code(self, input_code):
        if not self.cache.__contains__(self.prefix + self.phone):
            return 2  # 验证码已过期！
        self.get_origin_code()
        if input_code != self.code:
            return 1  # 验证码错误，请重试！
        return 0  # 验证成功


class TokenManager:
    """
    token管理类，包含：
    读取缓存中的token信息，
    生成随机token，
    保存token至redis，
    返回token验证结果
    """
    prefix = 'L_'
    mobile = None
    cache = django_redis.get_redis_connection()
    token = ''
    model_class = None

    def get_origin_data(self):
        if self.cache.get(self.prefix+self.token):
            self.mobile = self.cache.get(self.prefix+self.token).decode()
            return self.mobile
        else:
            pass

    def del_cache_data(self):
        self.cache.delete(self.prefix + self.token)

    def del_cache_data_by_mobile(self):
        keys = self.cache.keys()
        for key in keys:
            value = self.cache.get(key)
            if value.decode() == self.mobile:
                self.cache.delete(key)
        return True

    def generate_token(self):
        self.token = str(uuid.uuid1())
        return self.token

    def save_to_cache(self):
        self.cache.set((self.prefix+self.token), self.mobile, 60*60*2)
        return True

    def create_token_in_table(self):
        instance = self.model_class()
        instance.mobile = self.mobile
        instance.token = self.token
        instance.update_time = timezone.now()
        instance.save()
        return True

    def clear_token_in_table_and_cache(self):
        instances = self.model_class.objects.filter(mobile=self.mobile)
        for instance in instances:
            token = 'S_'+instance.token
            self.cache.delete(token)
        instances.delete()
        return True

    def find_instance_in_table(self):
        instance = self.model_class.objects.filter(token=self.token).first()
        if not instance:
            return False
        return instance

    def is_token_in_table(self):
        """验证token是否在表中存在"""
        instance = self.model_class.objects.filter(token=self.token).first()
        if not instance:
            return False
        return True


class CSRFCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        # Return the failure reason instead of an HttpResponse
        return reason


class Uploader():
    client = Minio(MINIO_URL,
                   access_key=ACCESS_KEY,
                   secret_key=SECRET_KEY,
                   secure=False)
    bucket_name = 'bucket_name'
    object_name = 'object_name'
    expires = timedelta(minutes=5)
    expires_date = datetime.utcnow() + timedelta(minutes=60)
    content_max_length = 11*1024*1024

    def setConnection(self, minio_url, access_key, secret_key, secure=False):
        """
        重新设置有效连接
        """
        self.client = Minio(minio_url,
                   access_key=access_key,
                   secret_key=secret_key,
                   secure=secure)

    def getPutUrl(self):
        """
        生成有效文件上传链接
        """
        try:
            url = self.client.presigned_put_object(self.bucket_name, self.object_name, expires=self.expires)
        except:
            # TODO: add to logger
            return None
        return url

    def setExpiresDate(self, new_expires_date):
        self.expires_date = new_expires_date

    def updateExpiresDate(self):
         self.expires_date = datetime.utcnow() + timedelta(minutes=120)

    def setContentMaxLength(self, length):
        self.content_max_length = length

    def getPostUrl(self):
        """
        使用POST上传文件时，申请对象存储的预签名URL
        """
        try:
            post_policy = PostPolicy(self.bucket_name, self.expires_date)
            post_policy.add_starts_with_condition('key', 'prefix/')
            post_policy.add_content_length_range_condition(
                0, self.content_max_length
            )
            signed_form_data = self.client.presigned_post_policy(post_policy)
        except:
            return None
        return signed_form_data

    def generateObjectName(self, file_type='png'):
        """
        根据MAC地址和时间戳生成uuid，uuid作为唯一的文件名，file_type为文件类型后缀
        """
        self.object_name = str(uuid.uuid1()) + '.' + file_type

    def setBucketName(self, bucket_name):
        """
        设置bucket_name
        """
        self.bucket_name = bucket_name

    def setExpires(self, expires):
        """
        设置链接有效时长
        """
        self.expires = expires


class WXBizDataCrypt:
    def __init__(self, appId, sessionKey):
        self.appId = appId
        self.sessionKey = sessionKey

    def decrypt(self, encryptedData, iv):
        # base64 decode
        try:
            sessionKey = base64.b64decode(self.sessionKey)
            encryptedData = base64.b64decode(encryptedData)
            iv = base64.b64decode(iv)

            cipher = AES.new(sessionKey, AES.MODE_CBC, iv)

            decrypted = json.loads(self._unpad(cipher.decrypt(encryptedData)))

            if decrypted['watermark']['appid'] != self.appId:
                """raise Exception('Invalid Buffer')"""
                return None
        except:
            return None
        return decrypted

    def _unpad(self, s):
        return s[:-ord(s[len(s)-1:])]


class WeChatTools:
    """
    微信小程序工具类
    """
    app_id = 'wxaa0c004665958b50'
    app_secret ='c7cfd9257ee64ecdde07e1c136789136'
    code = ''
    session_key = ''
    encrypted_data = ''
    iv = ''

    def setCode(self, code):
        self.code = code

    def setToAgency(self):
        self.app_id = 'wx0cae891b2b2e49f4'
        self.app_secret = 'e29eec82901cfd5cb1679e7beab84bf5'

    def setToSuperUser(self):
        self.app_id = "wx1e9705c9750ee114"
        self.app_secret = "7fdcd4516c22825d8e748a6a411ffe59"

    def setDecryptParam(self, session_key, encrypted_data, iv):
        self.session_key = session_key
        self.encrypted_data = encrypted_data
        self.iv = iv

    def getSessionInfo(self):
        params = {
            'appid': self.app_id,
            'secret': self.app_secret,
            'js_code': self.code,
            'grant_type': 'authorization_code'
        }
        response = requests.get(url='https://api.weixin.qq.com/sns/jscode2session?', params=params)
        return response

    def getDecryptData(self):
        tool = WXBizDataCrypt(self.app_id, self.session_key)
        data = tool.decrypt(self.encrypted_data, self.iv)
        if 'watermark' not in data.keys():
            return None
        if 'appid' not in data['watermark'].keys():
            return None
        if 'timestamp' not in data['watermark'].keys():
            return None
        if data['watermark']['appid'] != self.app_id:
            return None
        if data['watermark']['timestamp'] < time.time()-3600:
            return  None
        return data


