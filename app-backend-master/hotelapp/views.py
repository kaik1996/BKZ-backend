# -*- coding: utf8 -*-
# Authentic
import base64
import re
import logging
import json

import requests
from django.utils import timezone
from django_filters import rest_framework
from rest_framework.views import APIView
from datetime import timedelta, datetime
from .utils import *
from .serializers import *
from .models import *
from rest_framework.response import Response
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseServerError, QueryDict
from rest_framework import viewsets, status, filters, mixins
from hotelapp.filters import HousesFilter, TurnOverFilter
from rest_framework.decorators import api_view
from django.contrib.gis.geos import Point
from django.db.models import Q
from django.contrib.gis.db.models.functions import Distance
from hotelapp.aes import AEScoder
from purchase_vip.tools import price_and_amount, err_para_lack, err_purchase, success_purchase, paying_msg
from my_exception.exceptions import SubwayNotExistError
from WechatPay.wechatpay_view import *
from openunipay.paygateway import unipay
from openunipay.models import PAY_WAY_WEIXIN, PAY_WAY_ALI
# PAY_WAY_WEIXIN: 微信支付 PAY_WAY_ALI: 支付宝支付

# 设置log
# logger = logging.getLogger(__name__)


class SuperUserCRUDView(viewsets.ModelViewSet):
    """超级管理员调用"""
    serializer_class = HousesSerializer
    authentication_classes = [SuperUserAuthentication]
    permission_classes = [SuperUser2HousePermission]
    pagination_class = MyPaginatioin
    filter_backends = (rest_framework.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_class = HousesFilter
    search_fields = ['name', 'detail_address']
    ordering_fields = ('id', 'price', 'updated_time')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        record_obj = HistoryRecord()
        record_obj.account = request.user
        record_obj.house_id = instance.id
        record_obj.save()
        return Response(serializer.data)

    def get_queryset(self):
        return Houses.objects.filter(is_delete=False)

    def create(self, request, *args, **kwargs):
        data1 = request.data.copy()
        data1['account'] = request.user
        data1['operator_name'] = 'CREATE'
        serializer1 = OperatorRecordSerializer(data=data1)
        serializer1.is_valid(raise_exception=True)
        serializer1.save()

        user = request.user
        data = request.data

        if str(type(data)) == "<class 'django.http.request.QueryDict'>":
            data = QueryDict(request.data.urlencode(), mutable=True)
            data.update({
                'operator': user,
            })
        else:
            data['operator'] = user
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        data1 = request.data.copy()
        data1['account'] = request.user
        data1['operator_name'] = 'UPDATE'

        # ====
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        # ----
        data1['house_id'] = instance.id
        serializer1 = OperatorRecordSerializer(data=data1)
        serializer1.is_valid(raise_exception=True)
        serializer1.save()
        # ----
        instance.operator = request.user
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        # 实现逻辑删除
        op_record = OperatorRecord()
        op_record.account = request.user
        op_record.operator_name = 'DELETE'

        instance = self.get_object()
        op_record.house_id = instance.id
        op_record.save()
        instance.is_delete = True
        instance.save(update_fields=['is_delete'])
        return Response({'detail': '删除成功'}, status=status.HTTP_200_OK)


# class SuperUserView(viewsets.ModelViewSet):
#     queryset = SuperUser.objects.all()
#     serializer_class = SuperUserSerializer


class LandlordUserView(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.RetrieveModelMixin,
                       mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = LandlordRegSerializer
    authentication_classes = [LandlordAuthentication]
    permission_classes = [LandlordPermission]
    pagination_class = MyPaginatioin

    def get_queryset(self):
        return LandlordUser.objects.filter(mobile=self.request.user)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        if LandlordUser.objects.filter(mobile=request.user).count() > 0:
            # logger.error(f'{request.user} 已经存在')
            error_msg = {
                'detail': "账号已存在"
            }
            return Response(error_msg, status=status.HTTP_400_BAD_REQUEST)
        if data['name'] and data['wechat'] and data['password']:
            data['is_valid'] = True
        else:
            data['is_valid'] = False
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        headers = self.get_success_headers(serializer.data)
        newuser = LandlordUser()
        newuser.mobile = serializer.validated_data['mobile']
        newuser.name = serializer.validated_data['name']
        newuser.wechat = serializer.validated_data['wechat']
        newuser.password = serializer.validated_data['password']
        newuser.is_valid = serializer.validated_data['is_valid']
        newuser.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class AgencyUserView(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.RetrieveModelMixin,
                     mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    1.创建新用户
    2.修改本人信息
    3.查看本人信息
    """
    serializer_class = AgencyRegSerializer
    authentication_classes = [AgencyAuthentication]
    permission_classes = [AgencyPermission]
    pagination_class = MyPaginatioin

    def get_queryset(self):
        return AgencyUser.objects.filter(mobile=self.request.user)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        if LandlordUser.objects.filter(mobile=request.user).count() > 0:
            # logger.error(f'{request.user} 已经存在')
            error_msg = {
                'detail': "账号已存在"
            }
            return Response(error_msg, status=status.HTTP_400_BAD_REQUEST)
        if data['name'] and data['wechat'] and data['password']:
            data['is_valid'] = True
        else:
            data['is_valid'] = False
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        headers = self.get_success_headers(serializer.data)
        newuser = LandlordUser()
        newuser.mobile = request.user
        newuser.name = serializer.validated_data['name']
        newuser.wechat = serializer.validated_data['wechat']
        newuser.password = serializer.validated_data['password']
        newuser.is_valid = serializer.validated_data['is_valid']
        newuser.vip_deadline = timezone.now()+timedelta(days=3)
        newuser.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# class ContractView(viewsets.ModelViewSet):
#     queryset = Contract.objects.all()
#     serializer_class = ContractSerializer


class LandlordCodeSendView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """短信验证码"""
    serializer_class = CodeSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile = serializer.validated_data['mobile']
        sms = SmsCode(mobile)
        sms.generate_code()
        sms.send_code()
        if not sms.is_sent:
            return Response({
                'detail': '验证码发送失败！',
            }, status=status.HTTP_400_BAD_REQUEST)
        sms.save_to_cache()
        return Response({
            "mobile": mobile,
        }, status=status.HTTP_201_CREATED)


class LandlordCodeCheckView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    验证短信验证码
    """
    serializer_class = CodeCheckSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile = serializer.validated_data['mobile']
        code = serializer.validated_data['code']
        sms = SmsCode(mobile)
        # sms.get_origin_code()
        result = sms.varify_code(code)

        if result == 0:
            token_manager = TokenManager()
            token_manager.mobile = mobile
            token_manager.generate_token()
            token_manager.save_to_cache()
            # logger.info('create_Token')
            token_manager.model_class = LandlordToken
            token_manager.create_token_in_table()

            # 用户信息
            users = LandlordUser.objects.filter(mobile=token_manager.mobile)
            if users.count() == 0:
                return Response({
                   'detail': '验证失败！',
                }, status=status.HTTP_401_UNAUTHORIZED)

                # 创建用户信息
                name = '用户_' + token_manager.mobile
                user = LandlordUser(mobile=token_manager.mobile, password="password", name=name,
                                    last_login=timezone.now(), is_valid=True)
                user.save()
                userinfo = user
            else:
                user = LandlordUser.objects.filter(mobile=token_manager.mobile)
                user.update(last_login=timezone.now())
                userinfo = user.get(mobile=token_manager.mobile)
            return Response({
                'user_name': userinfo.name,
                'token': token_manager.token,
                'mobile': userinfo.mobile,
            })
        elif result == 1:
            return Response({
                'detail': '验证失败！',
            }, status=status.HTTP_401_UNAUTHORIZED)
        else:
            return Response({
                'detail': '验证码已过期！',
            }, status=status.HTTP_401_UNAUTHORIZED)


class AgencyCodeSendView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """短信验证码"""
    serializer_class = CodeSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile = serializer.validated_data['mobile']
        sms = SmsCode(mobile)
        sms.prefix = 'AA_'
        sms.generate_code()
        sms.send_code()
        if not sms.is_sent:
            return Response({
                'detail': '验证码发送失败！',
            }, status=status.HTTP_400_BAD_REQUEST)
        sms.save_to_cache()
        return Response({
            "mobile": mobile,
        }, status=status.HTTP_201_CREATED)


class AgencyCodeCheckView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    验证短信验证码
    """
    serializer_class = CodeCheckSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile = serializer.validated_data['mobile']
        code = serializer.validated_data['code']
        sms = SmsCode(mobile)
        sms.prefix = 'AA_'
        # sms.get_origin_code()
        result = sms.varify_code(code)

        if result == 0:
            token_manager = TokenManager()
            token_manager.prefix = 'A_'
            token_manager.mobile = mobile
            token_manager.generate_token()
            token_manager.save_to_cache()
            # logger.info('create_Token')
            token_manager.model_class = AgencyToken
            token_manager.create_token_in_table()

            # 用户信息
            users = AgencyUser.objects.filter(mobile=token_manager.mobile)
            if users.count() == 0:
                # 创建用户信息
                name = '用户_' + token_manager.mobile
                user = AgencyUser(mobile=token_manager.mobile, password="password", name=name,
                                    last_login=timezone.now(), is_valid=True)
                user.save()
                userinfo = user
            else:
                user = AgencyUser.objects.filter(mobile=token_manager.mobile)
                user.update(last_login=timezone.now())
                userinfo = user.get(mobile=token_manager.mobile)
            return Response({
                'user_name': userinfo.name,
                'token': token_manager.token,
                'mobile': userinfo.mobile,
                'vip_deadline': userinfo.vip_deadline
            })
        elif result == 1:
            return Response({
                'detail': '验证失败！',
            }, status=status.HTTP_401_UNAUTHORIZED)
        else:
            return Response({
                'detail': '验证码已过期！',
            }, status=status.HTTP_401_UNAUTHORIZED)


class SuperUserCodeSendView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """短信验证码"""
    serializer_class = CodeSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile = serializer.validated_data['mobile']
        sms = SmsCode(mobile)
        sms.prefix = 'SS_'
        sms.generate_code()
        sms.send_code()
        if not sms.is_sent:
            return Response({
                'detail': '验证码发送失败！',
            }, status=status.HTTP_400_BAD_REQUEST)
        sms.save_to_cache()
        return Response({
            "mobile": mobile,
        }, status=status.HTTP_201_CREATED)


class SuperUserCodeCheckView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    验证短信验证码
    """
    serializer_class = CodeCheckSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile = serializer.validated_data['mobile']
        code = serializer.validated_data['code']
        sms = SmsCode(mobile)
        sms.prefix = 'SS_'
        # sms.get_origin_code()
        result = sms.varify_code(code)

        if result == 0:
            token_manager = TokenManager()
            token_manager.prefix = 'S_'
            token_manager.mobile = mobile
            token_manager.generate_token()
            token_manager.save_to_cache()
            # logger.info('create_Token')
            token_manager.model_class = SuperUserToken
            token_manager.clear_token_in_table_and_cache()
            token_manager.create_token_in_table()
            # 用户信息
            users = SuperUser.objects.filter(mobile=token_manager.mobile)
            if users.count() == 0:
                return Response({
                    'detail': '该用户不存在',
                }, status=status.HTTP_404_NOT_FOUND)
            else:
                user = SuperUser.objects.filter(mobile=token_manager.mobile)
                user.update(last_login=timezone.now())
                userinfo = user.get(mobile=token_manager.mobile)
            return Response({
                'user_name': userinfo.name,
                'token': token_manager.token,
                'mobile': userinfo.mobile,
            })
        elif result == 1:
            return Response({
                'detail': '验证失败！',
            }, status=status.HTTP_401_UNAUTHORIZED)
        else:
            return Response({
                'detail': '验证码已过期！',
            }, status=status.HTTP_401_UNAUTHORIZED)


def getPutPresignedUrl(request):
    """
    /upload_url?type=png
    本视图功能为文件上传提供预签名地址：
    成功时返回URL
    错误时返回None
    """
    # data = {
    #     'detail': '该用户未经授权！',
    # }
    # if 'user' not in request.session.keys():
    #     return HttpResponseForbidden(json.dumps(data,  ensure_ascii=False))
    file_type = request.GET.get('type')
    data = {
        'detail': '存储服务器暂不可用！',
    }
    uploader = Uploader()
    uploader.setBucketName('icons')
    if file_type:
        uploader.generateObjectName(file_type)
    else:
        uploader.generateObjectName()
    url = uploader.getPutUrl()
    if url:
        data = {
            'address': '/' + uploader.bucket_name + '/' + uploader.object_name,
            'url': url
        }
        return HttpResponse(json.dumps(data,  ensure_ascii=False))
    return HttpResponseServerError(json.dumps(data,  ensure_ascii=False))


def getPostPresignedUrl(request):
    """
    本视图功能为文件上传提供预签名地址：
    成功时返回formdata签名数据
    """
    data = {
        'detail': '存储服务器暂不可用!',
    }
    uploader = Uploader()
    uploader.setBucketName('media')
    uploader.updateExpiresDate()
    form_data = uploader.getPostUrl()
    data = {
        'x-amz-algorithm': form_data['x-amz-algorithm'],
        'x-amz-credential': form_data['x-amz-credential'],
        'x-amz-date': form_data['x-amz-date'],
        'policy': form_data['policy'].decode(encoding="utf-8"),
        'x-amz-signature': form_data['x-amz-signature'],
    }
    if form_data:
        return HttpResponse(json.dumps(data, ensure_ascii=False))
    return HttpResponseServerError(json.dumps(data, ensure_ascii=False))


class LandlordCRUDView(viewsets.ModelViewSet):
    """
    房东对房源的操作：
    1.查看本人上传的房源信息
    2.修改本人上传的房源信息
    3.删除本人上传的房源信息
    4.创建一个房源
    """
    serializer_class = HousesSerializer
    authentication_classes = [LandlordAuthentication]
    permission_classes = [Landlord2HousePermission]
    pagination_class = MyPaginatioin
    filter_backends = (rest_framework.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_class = HousesFilter
    search_fields = ['detail_address', 'name']
    ordering_fields = ('id', 'price', 'updated_time')

    def get_queryset(self):
        return Houses.objects.filter(uploader__mobile=self.request.user, is_delete=False)

    def create(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        if str(type(data)) == "<class 'django.http.request.QueryDict'>":
            data = QueryDict(request.data.urlencode(), mutable=True)
            data.update({
                'uploader': user,
            })
        else:
            data['uploader'] = user
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        # 防止通过修改request内容非法修改数据
        if request.data['uploader'] != request.user:
            error_msg = {
                'detail': "不能更改上传人信息"
            }
            return Response(error_msg, status=status.HTTP_400_BAD_REQUEST)
        return super(LandlordCRUDView, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        # 实现逻辑删除
        instance = self.get_object()
        instance.is_delete = True
        instance.save(update_fields=['is_delete'])
        return Response({'detail': '删除成功'}, status=status.HTTP_200_OK)


class AgencyCRUDView(mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """
    中介对房源的操作：
    1.查看房源信息
    """
    serializer_class = HousesSerializer
    # authentication_classes = [AgencyAuthentication]
    # permission_classes = [Agency2HousePermission]
    filter_backends = (rest_framework.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_class = HousesFilter
    pagination_class = MyPaginatioin
    search_fields = ['detail_address', 'name']

    def get_queryset(self):
        """只显示逻辑存在的房源"""
        nothing = self.request.query_params.get("nothing", 0)
        if nothing:
            return Houses.objects.none()
        lat = float(self.request.query_params.get("lat", 0))
        lon = float(self.request.query_params.get("lon", 0))
        distance = int(self.request.query_params.get("distance", 0))
        subway = self.request.query_params.get("subway", 0)
        nextregions = self.request.query_params.get("nextregions", 0)

        try:
            if nextregions != 0:
                nextregion_arr = json.loads(nextregions)
                queryset = Houses.objects.none()
                for i in nextregion_arr:
                    queryset = queryset | Houses.objects.filter(is_delete=False, is_rented=False, nextregion=i)
                return queryset
            subway_arr = json.loads(subway)
            queryset = Houses.objects.none()
            for i in subway_arr:
                subway_name = i + '(地铁站)'
                # subway_set = SubwayModel.objects.filter(name=subway_name)
                # if (subway_set.count() == 0):
                #     queryset = queryset | Houses.objects.none()
                # subway_obj = subway_set.first()
                queryset = queryset | Houses.objects.filter(is_delete=False, is_rented=False, subways__icontains=subway_name)
                # queryset = queryset | Houses.objects.filter(is_delete=False, geo__distance_lte=(subway_obj.geo, 1000))
            return queryset
        except:
            subway = self.request.query_params.get("subway", 0)
        if subway:
            subway_name = subway + '(地铁站)'
            # subway_set = SubwayModel.objects.filter(name=subway_name)
            # if (subway_set.count() == 0):
            #     return Houses.objects.none()
                # raise SubwayNotExistError
            # subway_obj = subway_set.first()
            # return Houses.objects.filter(is_delete=False, geo__distance_lte=(subway_obj.geo, 1000))
            return Houses.objects.filter(is_delete=False, is_rented=False, subways__icontains=subway_name)
        if lat and lon:
            point = Point(lon, lat, srid=4490)
            houses = Houses.objects.filter(is_delete=False, is_rented=False, geo__distance_lte=(point, distance)).annotate(distance=Distance('geo', point)).order_by('distance')
            if houses.count() >200:
                return houses[0:200]
            return houses
        return Houses.objects.filter(is_delete=False, is_rented=False)

    def list(self, request, *args, **kwargs):
        top_floor = self.request.query_params.get("top_floor", 0)
        around_subway = self.request.query_params.get("around_subway", 0)
        tag = self.request.query_params.get("tag", 0)
        with_photo = self.request.query_params.get("with_photo", 0)
        if top_floor:
            queryset = self.filter_queryset(self.get_queryset()).extra(where=["floor = house_total_floor"])
        else:
            queryset = self.filter_queryset(self.get_queryset())
        if around_subway:
            queryset = queryset.filter(~Q(subways= list()))
        if tag:
            queryset = queryset.filter(tag__icontains=tag)
        if with_photo:
            queryset = queryset.filter(~Q(photo_url=list()))
        all = self.request.query_params.get("all", 0)
        page = self.paginate_queryset(queryset)
        if page is not None and not all:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class LandlordWeChatSessionView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    微信小程序code获取session信息
    """
    serializer_class = WeChatCodeSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']
        wechat = WeChatTools()
        wechat.setCode(code)
        response = wechat.getSessionInfo()
        if response.status_code == 200 and 'session_key' in response.text:
            result = json.loads(response.text)
            return Response(result)
        else:
            return Response({
                'detail': '无法获取信息，请重试！',
            }, status=status.HTTP_400_BAD_REQUEST)


class AgencyWeChatSessionView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    微信小程序code获取session信息
    """
    serializer_class = WeChatCodeSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']
        wechat = WeChatTools()
        wechat.setToAgency()
        wechat.setCode(code)
        response = wechat.getSessionInfo()
        if response.status_code == 200 and 'session_key' in response.text:
            result = json.loads(response.text)
            return Response(result)
        else:
            return Response({
                'detail': '无法获取信息，请重试！',
            }, status=status.HTTP_400_BAD_REQUEST)


class SuperUserWeChatSessionView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    微信小程序code获取session信息
    """
    serializer_class = WeChatCodeSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']
        wechat = WeChatTools()
        wechat.setToSuperUser()
        wechat.setCode(code)
        response = wechat.getSessionInfo()
        if response.status_code == 200 and 'session_key' in response.text:
            result = json.loads(response.text)
            return Response(result)
        else:
            return Response({
                'detail': '无法获取信息，请重试！',
            }, status=status.HTTP_400_BAD_REQUEST)


class LandlordWeChatLoginView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    微信小程序获取加密手机号
    """
    serializer_class = WeChatLoginSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session_key = serializer.validated_data['session_key']
        encrypted_data = serializer.validated_data['encrypted_data']
        iv = serializer.validated_data['iv']
        wechat = WeChatTools()
        wechat.setDecryptParam(session_key=session_key, encrypted_data=encrypted_data, iv=iv)
        data = wechat.getDecryptData()
        if data:
            if data['countryCode'] != '86':
                return Response({
                    'detail': '当前只支持中国区域的手机号登录！',
                }, status=status.HTTP_400_BAD_REQUEST)

            token_manager = TokenManager()
            token_manager.mobile = data['purePhoneNumber']
            token_manager.generate_token()
            token_manager.save_to_cache()
            token_manager.model_class = LandlordToken
            token_manager.create_token_in_table()

            # 用户信息
            users = LandlordUser.objects.filter(mobile=token_manager.mobile)
            if users.count() == 0:
                return Response({
                    'detail': '验证失败！',
                }, status=status.HTTP_401_UNAUTHORIZED)
                # 创建用户信息
                name = '用户_'+ token_manager.mobile
                user = LandlordUser(mobile=token_manager.mobile, password="password", name=name, last_login=timezone.now(), is_valid=True)
                user.save()
                userinfo = user
            else:
                user = LandlordUser.objects.filter(mobile=token_manager.mobile)
                user.update(last_login=timezone.now())
                userinfo = user.get(mobile=token_manager.mobile)
            return Response({
                'user_name': userinfo.name,
                'token': token_manager.token,
                'mobile': userinfo.mobile,
            })

        return Response({
            'detail': '无法获取信息，请重试！',
        }, status=status.HTTP_400_BAD_REQUEST)


class AgencyWeChatLoginView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    微信小程序获取加密手机号
    """
    serializer_class = WeChatLoginSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session_key = serializer.validated_data['session_key']
        encrypted_data = serializer.validated_data['encrypted_data']
        iv = serializer.validated_data['iv']
        wechat = WeChatTools()
        wechat.setToAgency()
        wechat.setDecryptParam(session_key=session_key, encrypted_data=encrypted_data, iv=iv)
        data = wechat.getDecryptData()
        if data:
            if data['countryCode'] != '86':
                return Response({
                    'detail': '当前只支持中国区域的手机号登录！',
                }, status=status.HTTP_400_BAD_REQUEST)

            token_manager = TokenManager()
            token_manager.prefix = 'A_'
            token_manager.mobile = data['purePhoneNumber']
            token_manager.generate_token()
            token_manager.save_to_cache()
            token_manager.model_class = AgencyToken
            token_manager.create_token_in_table()

            # 用户信息
            users = AgencyUser.objects.filter(mobile=token_manager.mobile)
            if users.count() == 0:
                # 创建用户信息
                name = '用户_'+ token_manager.mobile
                user = AgencyUser(mobile=token_manager.mobile, password="password", name=name, last_login=timezone.now(), is_valid=True)
                user.save()
                userinfo = user
            else:
                user = AgencyUser.objects.filter(mobile=token_manager.mobile)
                user.update(last_login=timezone.now())
                userinfo = user.get(mobile=token_manager.mobile)
            return Response({
                'user_name': userinfo.name,
                'token': token_manager.token,
                'mobile': userinfo.mobile,
                'vip_deadline': userinfo.vip_deadline
            })

        return Response({
            'detail': '无法获取信息，请重试！',
        }, status=status.HTTP_400_BAD_REQUEST)


class SuperUserWeChatLoginView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    微信小程序获取加密手机号
    """
    serializer_class = WeChatLoginSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session_key = serializer.validated_data['session_key']
        encrypted_data = serializer.validated_data['encrypted_data']
        iv = serializer.validated_data['iv']
        wechat = WeChatTools()
        wechat.setToSuperUser()
        wechat.setDecryptParam(session_key=session_key, encrypted_data=encrypted_data, iv=iv)
        data = wechat.getDecryptData()
        if data:
            if data['countryCode'] != '86':
                return Response({
                    'detail': '当前只支持中国区域的手机号登录！',
                }, status=status.HTTP_400_BAD_REQUEST)

            token_manager = TokenManager()
            token_manager.prefix = 'S_'
            token_manager.mobile = data['purePhoneNumber']
            token_manager.generate_token()
            token_manager.save_to_cache()
            token_manager.model_class = SuperUserToken
            token_manager.clear_token_in_table_and_cache()
            token_manager.create_token_in_table()

            # 用户信息
            users = SuperUser.objects.filter(mobile=token_manager.mobile)
            if users.count() == 0:
                return Response({
                    'detail': '该用户不存在',
                }, status=status.HTTP_404_NOT_FOUND)
            else:
                user = SuperUser.objects.filter(mobile=token_manager.mobile)
                user.update(last_login=timezone.now())
                userinfo = user.get(mobile=token_manager.mobile)
            return Response({
                'user_name': userinfo.name,
                'token': token_manager.token,
                'mobile': userinfo.mobile,
            })

        return Response({
            'detail': '无法获取信息，请重试！',
        }, status=status.HTTP_400_BAD_REQUEST)


class LandlordRefreshTokenView(viewsets.GenericViewSet):
    """
    更新token接口
    """
    def list(self, request, *args, **kwargs):
        old_token = request.META.get("HTTP_TOKEN")
        if not old_token:
            return Response({
                'detail': 'token不存在，请重试！',
            }, status=status.HTTP_400_BAD_REQUEST)
        model_class = LandlordToken
        old_token_manager = TokenManager()
        new_token_manager = TokenManager()
        old_token_manager.model_class = model_class
        new_token_manager.model_class = model_class
        old_token_manager.token = old_token
        instance = old_token_manager.find_instance_in_table()
        if not instance:
            return Response({
                'detail': '无效的token！',
            }, status=status.HTTP_400_BAD_REQUEST)

        new_token_manager.mobile = instance.mobile
        # 删除旧token信息
        old_token_manager.del_cache_data()
        instance.delete()
        # 生成新token
        new_token_manager.generate_token()
        new_token_manager.save_to_cache()
        new_token_manager.create_token_in_table()

        model_class = LandlordUser
        # 用户信息
        users = model_class.objects.filter(mobile=new_token_manager.mobile)
        if users.count() == 0:
            return Response({
                'detail': '该用户不存在！',
            }, status=status.HTTP_400_BAD_REQUEST)
        else:
            user = model_class.objects.filter(mobile=new_token_manager.mobile)
            user.update(last_login=timezone.now())
            userinfo = user.get(mobile=new_token_manager.mobile)
        return Response({
            'user_name': userinfo.name,
            'token': new_token_manager.token,
            'mobile': userinfo.mobile,
        })


class AgencyRefreshTokenView(viewsets.GenericViewSet):
    """
    更新token接口
    """
    def list(self, request, *args, **kwargs):
        old_token = request.META.get("HTTP_TOKEN")
        if not old_token:
            return Response({
                'detail': 'token不存在，请重试！',
            }, status=status.HTTP_400_BAD_REQUEST)
        model_class = AgencyToken
        old_token_manager = TokenManager()
        new_token_manager = TokenManager()
        old_token_manager.model_class = model_class
        old_token_manager.prefix = 'A_'
        new_token_manager.model_class = model_class
        new_token_manager.prefix = 'A_'
        old_token_manager.token = old_token
        instance = old_token_manager.find_instance_in_table()
        if not instance:
            return Response({
                'detail': '无效的token！',
            }, status=status.HTTP_400_BAD_REQUEST)

        new_token_manager.mobile = instance.mobile
        # 删除旧token信息
        old_token_manager.del_cache_data()
        instance.delete()
        # 生成新token
        new_token_manager.generate_token()
        new_token_manager.save_to_cache()
        new_token_manager.create_token_in_table()

        model_class = AgencyUser
        # 用户信息
        users = model_class.objects.filter(mobile=new_token_manager.mobile)
        if users.count() == 0:
            return Response({
                'detail': '该用户不存在！',
            }, status=status.HTTP_400_BAD_REQUEST)
        else:
            user = model_class.objects.filter(mobile=new_token_manager.mobile)
            user.update(last_login=timezone.now())
            userinfo = user.get(mobile=new_token_manager.mobile)
        return Response({
            'user_name': userinfo.name,
            'token': new_token_manager.token,
            'mobile': userinfo.mobile,
            'vip_deadline': userinfo.vip_deadline
        })


class SuperUserRefreshTokenView(viewsets.GenericViewSet):
    """
    更新token接口
    """
    def list(self, request, *args, **kwargs):
        old_token = request.META.get("HTTP_TOKEN")
        if not old_token:
            return Response({
                'detail': 'token不存在，请重试！',
            }, status=status.HTTP_400_BAD_REQUEST)
        model_class = SuperUserToken
        old_token_manager = TokenManager()
        new_token_manager = TokenManager()
        old_token_manager.model_class = model_class
        old_token_manager.prefix = 'S_'
        new_token_manager.model_class = model_class
        new_token_manager.prefix = 'S_'
        old_token_manager.token = old_token
        instance = old_token_manager.find_instance_in_table()
        if not instance:
            return Response({
                'detail': '无效的token！',
            }, status=status.HTTP_400_BAD_REQUEST)

        new_token_manager.mobile = instance.mobile
        # 删除旧token信息
        old_token_manager.del_cache_data()
        instance.delete()
        # 生成新token
        new_token_manager.generate_token()
        new_token_manager.save_to_cache()
        new_token_manager.create_token_in_table()

        model_class = SuperUser
        # 用户信息
        users = model_class.objects.filter(mobile=new_token_manager.mobile)
        if users.count() == 0:
            return Response({
                'detail': '该用户不存在！',
            }, status=status.HTTP_400_BAD_REQUEST)
        else:
            user = model_class.objects.filter(mobile=new_token_manager.mobile)
            user.update(last_login=timezone.now())
            userinfo = user.get(mobile=new_token_manager.mobile)
        return Response({
            'user_name': userinfo.name,
            'token': new_token_manager.token,
            'mobile': userinfo.mobile,
        })


# TODO 待完成
@api_view(http_method_names=['GET'], )
def find_closest_subway(request):
    # 通过浏览器传来的longitude和latitude，找到最近地铁站名
    input_value = request.data
    print(input_value['longitude'])  # should remove
    print(input_value['latitude'])  # should remove
    if not input_value['longitude'] or not input_value['latitude']:
        err_msg = {
            'detail': "请上传必要信息：纬度和经度"
        }
        return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)
    # call a function to declare
    # TODO
    return 1


# TODO 暂不放开，需测试（调用支付宝付款接口）
# class AlipayView(mixins.CreateModelMixin, viewsets.GenericViewSet):
#     # 需要浏览器传来的购买会员类型('2': 月度会员 600, '3': 季度会员 580, '4': 半年会员 550, '5': 年度会员 500)
#     serializer_class = OrderSerializer
#
#     def create(self, request, *args, **kwargs):
#         if request.data['commodity_type'] not in ['2', '3', '4', '5']:
#             return Response(err_para_lack, status=status.HTTP_400_BAD_REQUEST)
#
#         vip_type = int(request.data['commodity_type'])
#         print(vip_type)  # should remove
#         # 生成最多64?位的商户订单号
#         out_trade_no = (str(timezone.now()) + 'bangkezumember' + self.request.user)[:64]
#
#         price = price_and_amount[vip_type - 2][1]
#         amount = price_and_amount[vip_type - 2][2]
#
#         alipay_response = order_submit(Alipay_Client, price, amount, out_trade_no, request.user)
#
#         if alipay_response.is_success():
#             # 接口调用成功
#             data = request.data.copy()
#             data['status'] = '1'
#             data['out_trade_no'] = out_trade_no
#             data['purchase_user'] = request.user
#             serializer = self.get_serializer(data=data)
#             serializer.is_valid(raise_exception=True)
#             self.perform_create(serializer)
#             headers = self.get_success_headers(serializer.data)
#             return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
#         else:
#             return Response(err_purchase, status=status.HTTP_408_REQUEST_TIMEOUT)


# TODO 暂不放开，需要测试（支付宝付款接口）
# class AlipayNotifyURLView(APIView):
#     """ 支付宝回调视图 """
#     def cal_day(self, month_amount):
#         if timezone.now().month % 2 == 0:
#             even_month = int(month_amount/2)
#             odd_month = month_amount - even_month
#         else:
#             odd_month = int(month_amount/2)
#             even_month = month_amount - odd_month
#         return odd_month * 31 + even_month * 30
#
#     def check_pay(self, params):
#         from alipay.aop.api.util.SignatureUtils import verify_with_rsa
#         sign = params.pop('sign', None)
#         params.pop('sign_type')  # 取出签名类型
#         params = sorted(params.items(), key=lambda e: e[0], reverse=False)  # 取出字典元素按key的字母升序排序形成列表
#         message = "&".join(u"{}={}".format(k, v) for k, v in params).encode()  # 将列表转为二进制参数字符串
#         # with open(settings.ALIPAY_PUBLIC_KEY_PATH, 'rb') as public_key: # 打开公钥文件
#         try:
#             #     status =verify_with_rsa(public_key.read().decode(),message,sign) # 验证签名并获取结果
#             # 验证签名并获取结果
#             ali_status = verify_with_rsa(get_key(ALIPAY_PUBLIC_KEY).encode('utf-8').decode('utf-8'), message, sign)
#             return ali_status  # 返回验证结果
#         except:  # 如果验证失败，返回假值。
#             return False
#
#     def post(self, request):
#         params = request.POST.dict()
#         if self.check_pay(params) and params.trade_status != 'TRADE_CLOSED':
#             try:
#                 order_instance = Order.objects.get(out_trade_no=self.request.data['out_trade_no'])
#                 agency_instance = AgencyUser.objects.get(mobile=order_instance.purchase_user)
#             except:
#                 return Response({'detail': '发生了一些小故障，请重试或者咨询客服'}, status=status.HTTP_400_BAD_REQUEST)
#
#             purchase_type = order_instance.commodity_type
#             for i in price_and_amount:
#                 if i[0] == purchase_type:
#                     month = i[2]
#             if month:
#                 order_instance.status = '2'
#                 order_instance.save(update_fields=['status'])
#                 agency_instance.vip_deadline += timedelta(days=self.cal_day(month))
#                 agency_instance.vip_type = purchase_type
#                 agency_instance.save(update_fields=['vip_deadline', 'vip_type'])
#                 return HttpResponse('success')  # 成功后必须返回success
#         return Response({'detail': '发生了一些小故障，请重试或者咨询客服'}, status=status.HTTP_400_BAD_REQUEST)


class FavoritesView(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.DestroyModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    """收藏夹操作视图"""
    serializer_class = FavoritesSerializer
    authentication_classes = [AgencyAuthentication]
    permission_classes = [Agency2FavoritesPermission]

    def get_queryset(self):
        return Favorites.objects.filter(mobile=self.request.user)

    def create(self, request, *args, **kwargs):
        self.serializer_class = FavoritesSerializer
        data = request.data.copy()
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        # instance_set = Favorites.objects.filter(mobile=request.user, house_id_id=data['house_id'])
        # if instance_set.count() == 1:
        #     err_msg = {
        #         'detail': '该房源已收藏'
        #     }
        #     return Response(err_msg, status=status.HTTP_208_ALREADY_REPORTED)
        instance_set = Favorites.objects.filter(mobile=request.user)
        if instance_set.count() >= 20:
            err_msg = {
                'detail': '每人最多只能收藏20个房源'
            }
            return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)

        mobile = serializer.validated_data['mobile']

        house = serializer.validated_data['house_id']
        instance = Favorites(mobile=mobile, house_id_id=house.id)
        instance.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        self.serializer_class = FavoriteHousesSerializer
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        self.serializer_class = FavoriteHousesSerializer
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class LandlordBulletinBoardView(mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = BulletinBoardSerializer
    authentication_classes = []
    permission_classes = []

    def get_queryset(self):
        return BulletinBoard.objects.filter(type='1')


class AgencyBulletinBoardView(mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = BulletinBoardSerializer
    authentication_classes = []
    permission_classes = []

    def get_queryset(self):
        return BulletinBoard.objects.filter(type='0')


class SuperUserBulletinBoardView(mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = BulletinBoardSerializer
    authentication_classes = []
    permission_classes = []

    def get_queryset(self):
        return BulletinBoard.objects.filter(type='2')


class HouseTemplateView(viewsets.ModelViewSet):
    serializer_class = HouseTemplateSerializer
    authentication_classes = [PublicAuthentication]
    # permission_classes = [LandlordPermission]
    # pagination_class = MyPaginatioin

    def get_queryset(self):
        return HouseTemplate.objects.filter(uploader=self.request.user)


class FeedbackView(viewsets.ModelViewSet):
    serializer_class = FeedbackSerializer
    # authentication_classes = [LandlordAuthentication]
    # permission_classes = [LandlordPermission]
    # pagination_class = MyPaginatioin
    def get_queryset(self):
        return Feedback.objects.all()


class BatchHousesView(mixins.CreateModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = BatchHousesSerializer
    authentication_classes = [PublicAuthentication]
    # permission_classes = [LandlordPermission]
    # pagination_class = MyPaginatioin

    def create(self, request):
        data = request.data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        houses = serializer.validated_data['houses']
        serializers = []
        try:
            for room in houses['rooms']:
                room['uploader'] = request.user
                room['house_type'] = houses['basicInfo']['house_type']
                room['name'] = houses['basicInfo']['name']
                room['contact_phone'] = houses['basicInfo']['contact_phone']
                room['mgmtCost'] = houses['basicInfo']['mgmtCost']
                room['region'] = houses['basicInfo']['region']
                room['detail_address'] = houses['basicInfo']['detail_address']
                room['probably_address'] = houses['basicInfo']['probably_address']
                room['latitude'] = houses['basicInfo']['latitude']
                room['longitude'] = houses['basicInfo']['longitude']
                room['deposit'] = houses['basicInfo']['deposit']
                room['tariff_type'] = houses['basicInfo']['tariff_type']
                room['has_elevator'] = houses['basicInfo']['has_elevator']
                room['can_feed_dog'] = houses['basicInfo']['can_feed_dog']
                room['mgmtCost'] = houses['basicInfo']['mgmtCost']
                house = HousesSerializer(data=room)
                serializers.append(house)
        except :
            return Response({
                'detail': 'JSON数据访问错误'
            }, status=status.HTTP_400_BAD_REQUEST)
        for instance in serializers:
            instance.is_valid(raise_exception=True)
            instance.save()
        return Response({
            'count': len(serializers),
            'detail': '上传成功'
        })


class SuperUserBatchHousesView(mixins.CreateModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = BatchHousesSerializer
    authentication_classes = [PublicAuthentication]
    # permission_classes = [LandlordPermission]
    # pagination_class = MyPaginatioin

    def create(self, request):
        data = request.data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        houses = serializer.validated_data['houses']
        serializers = []
        try:
            for room in houses['rooms']:
                room['operator'] = request.user
                room['uploader'] = houses['basicInfo']['uploader']
                room['house_type'] = houses['basicInfo']['house_type']
                room['name'] = houses['basicInfo']['name']
                room['contact_phone'] = houses['basicInfo']['contact_phone']
                room['mgmtCost'] = houses['basicInfo']['mgmtCost']
                room['region'] = houses['basicInfo']['region']
                room['detail_address'] = houses['basicInfo']['detail_address']
                room['probably_address'] = houses['basicInfo']['probably_address']
                room['latitude'] = houses['basicInfo']['latitude']
                room['longitude'] = houses['basicInfo']['longitude']
                room['deposit'] = houses['basicInfo']['deposit']
                room['tariff_type'] = houses['basicInfo']['tariff_type']
                room['has_elevator'] = houses['basicInfo']['has_elevator']
                room['can_feed_dog'] = houses['basicInfo']['can_feed_dog']
                room['mgmtCost'] = houses['basicInfo']['mgmtCost']
                house = HousesSerializer(data=room)
                serializers.append(house)
        except :
            return Response({
                'detail': 'JSON数据访问错误'
            }, status=status.HTTP_400_BAD_REQUEST)
        for instance in serializers:
            instance.is_valid(raise_exception=True)
            instance.save()
        return Response({
            'count': len(serializers),
            'detail': '上传成功'
        })


class LandlordStat(mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = HouseTemplateSerializer
    authentication_classes = [LandlordAuthentication]
    # permission_classes = [LandlordPermission]
    # pagination_class = MyPaginatioin

    def list(self, request, *args, **kwargs):
        # no_rent = Houses.objects.filter(is_rented=False, uploader=request.user).count()
        is_rent = Houses.objects.filter(is_rented=True, uploader=request.user, is_delete=False).count()
        total_house_num = Houses.objects.filter(uploader=request.user, is_delete=False).count()
        community_num = Houses.objects.filter(house_type__in=['0', '1'], uploader=request.user, is_delete=False).count()
        countryside_num = Houses.objects.filter(house_type='2', uploader=request.user, is_delete=False).count()
        flats_num = Houses.objects.filter(house_type='3', uploader=request.user, is_delete=False).count()
        time = timezone.now() + timedelta(days=14)
        will_overdue_num = Houses.objects.filter(rent_deadline__lt=time, uploader=request.user, is_delete=False).count()
        no_rent = total_house_num-is_rent
        data = {
            'no_rent': no_rent,
            'is_rent': is_rent,
            'total_house_num': total_house_num,
            'community_num': community_num,
            'countryside_num': countryside_num,
            'flats_num': flats_num,
            'will_overdue_num': will_overdue_num,
        }
        return Response(data, status=status.HTTP_200_OK)


class SuperUserStat(mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = HouseTemplateSerializer
    authentication_classes = [SuperUserAuthentication]
    # permission_classes = []

    def list(self, request, *args, **kwargs):
        is_rent = Houses.objects.filter(is_rented=True, is_delete=False).count()
        total_house_num = Houses.objects.filter(is_delete=False).count()
        community_num = Houses.objects.filter(house_type__in=['0', '1'], is_delete=False).count()
        countryside_num = Houses.objects.filter(house_type='2', is_delete=False).count()
        flats_num = Houses.objects.filter(house_type='3', is_delete=False).count()
        time = timezone.now() + timedelta(days=14)
        will_overdue_num = Houses.objects.filter(rent_deadline__lt=time, is_delete=False).count()
        no_rent = total_house_num - is_rent
        data = {
            'no_rent': no_rent,
            'is_rent': is_rent,
            'total_house_num': total_house_num,
            'community_num': community_num,
            'countryside_num': countryside_num,
            'flats_num': flats_num,
            'will_overdue_num': will_overdue_num,
        }
        return Response(data, status=status.HTTP_200_OK)


class HouseAddress(mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = HouseTemplateSerializer
    authentication_classes = [LandlordAuthentication]
    # permission_classes = [LandlordPermission]
    # pagination_class = MyPaginatioin
    def list(self, request, *args, **kwargs):
        houses = Houses.objects.filter(uploader_id=request.user, is_delete=False).distinct('detail_address').order_by('detail_address').values('detail_address')
        addresses = []
        for house in houses:
            addresses.append(house['detail_address'])
        data = {
            'addresses': addresses
        }
        return Response(data)


class SearchTipsView(mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = HouseTemplateSerializer
    authentication_classes = [PublicAuthentication]
    # permission_classes = [AgencyPermission]
    def list(self, request, *args, **kwargs):
        content = (self.request.query_params.get("content", 0))
        data = {
            'tips': []
        }
        if content:
            names = Houses.objects.filter(is_delete=False, name__contains=content).distinct('name').order_by(
                'name').values('name', 'latitude', 'longitude')[:3]
            addresses = Houses.objects.filter(is_delete=False, detail_address__contains=content).distinct('detail_address').order_by(
                'detail_address').values('detail_address', 'latitude', 'longitude')[:3]
            for name in names:
                data['tips'].append({
                    'tip': name['name'],
                    'latitude': name['latitude'],
                    'longitude': name['longitude'],
                    'type': 'name'
                })
            for address in addresses:
                data['tips'].append({
                    'tip': address['detail_address'],
                    'latitude': address['latitude'],
                    'longitude': address['longitude'],
                    'type': 'address'
                })
        return Response(data)


class SearchSubwayView(mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = HouseTemplateSerializer
    authentication_classes = [PublicAuthentication]
    # permission_classes = [AgencyPermission]
    def list(self, request, *args, **kwargs):
        lat = float(self.request.query_params.get("lat", 0))
        lon = float(self.request.query_params.get("lon", 0))
        data = {
            'subways': []
        }
        if lat and lon:
            point = Point(lon, lat, srid=4490)
            subways = SubwayModel.objects.filter(geo__distance_lte=(point, 500))
            for subway in subways:
                data['subways'].append(subway.name)
        return Response(data)


class CheckLandlord(mixins.CreateModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = CheckLandlordSerializer
    authentication_classes = [SuperUserAuthentication]
    permission_classes = [LandlordPermission]
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # 用户信息
        users = LandlordUser.objects.filter(mobile=serializer.validated_data['mobile'])
        if users.count() == 0:
            return Response({
                'detail': '该用户不存在！',
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data)


class HistoryRecordView(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = HistoryRecordSerializer
    authentication_classes = [PublicAuthentication]

    def get_queryset(self):
        return HistoryRecord.objects.all() # should modify


class StaffLocationView(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = StaffLocationSerializer
    authentication_classes = [PublicAuthentication]

    def get_queryset(self):
        return StaffLocation.objects.all() # should modify

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        if 'longitude' not in data.keys() or 'latitude' not in data.keys() or 'address_name' not in data.keys():
            err_msg = {
                'detail': "请上传必要信息：纬度和经度 and address_name"
            }
            return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)
        if not data['longitude'] or not data['latitude'] or not data['address_name']:
            err_msg = {
                'detail': "请上传必要信息：纬度和经度 and address_name"
            }
            return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)
        data['account'] = request.user
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class OperatorRecordView(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = OperatorRecordSerializer
    authentication_classes = [PublicAuthentication]

    def get_queryset(self):
        return OperatorRecord.objects.all()  # should modify


class TurnoverRecordView(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, mixins.UpdateModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = TurnoverRecordSerializer
    authentication_classes = [PublicAuthentication]
    filter_backends = (rest_framework.DjangoFilterBackend, filters.OrderingFilter)
    filter_class = TurnOverFilter
    ordering_fields = ('id', 'rent_fee', 'rent_time')

    def get_queryset(self):
        return TurnoverRecord.objects.filter(account=self.request.user)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        # if 'organization' not in data.keys() or 'address' not in data.keys() or 'rent_fee' not in data.keys() or 'house_no' not in data.keys():
        #     err_msg = {
        #         'detail': "请上传必要信息：organization,address,rent_fee,house_no"
        #     }
        #     return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)
        # if not data['organization'] or not data['address'] or not data['rent_fee'] or not data['house_no']:
        #     err_msg = {
        #         'detail': "请上传必要信息：organization,address,rent_fee,house_no"
        #     }
        #     return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)
        data['account'] = request.user
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        data = request.data.copy()
        data['account'] = request.user
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if instance.status!='0' and instance.status!='1':
            data['rent_fee'] = instance.rent_fee
            data['rent_time'] = instance.rent_time
        if instance.status == '1':
            data['rent_fee'] = instance.rent_fee
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

class TurnoverStatView(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = TurnoverRecordSerializer
    authentication_classes = [PublicAuthentication]
    filter_backends = (rest_framework.DjangoFilterBackend, filters.OrderingFilter)
    filter_class = TurnOverFilter

    def get_queryset(self):
        return TurnoverRecord.objects.filter(account=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        data = {
            'sum': 0,
            'count': 0,
        }
        for item in queryset:
            data['sum'] += int(item.rent_fee)
        data['count'] = queryset.count()
        return Response(data)


# QR Code Model CRUD
class QRCodeURLView(viewsets.ModelViewSet):
    serializer_class = QRCodeURLSerializer
    authentication_classes = [LandlordAuthentication]

    def get_queryset(self):
        return QRCodeURLModel.objects.filter(mobile=self.request.user)

    def create(self, request, *args, **kwargs):
        data = data=request.data.copy()
        data['mobile'] = request.user
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = data = request.data.copy()
        data['mobile'] = request.user
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


class GetQRCodeURL(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = QRCodeURLSerializer
    authentication_classes = [LandlordAuthentication]
    # permission_classes = [Landlord2HousePermission]
    pagination_class = MyPaginatioin

    def get_queryset(self):
        return QRCodeURLModel.objects.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        aes = AEScoder()
        id = aes.encrypt(str(instance.id))
        data = {
            'id': id
        }
        return Response(data)


class QRCodeQueryView(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = QRCodeURLViewSerializer
    def get_queryset(self):
        return QRCodeView.objects.all()

    def list(self, request, *args, **kwargs):
        code = self.request.query_params.get("code", 0)
        if not code:
            data = {
                'detail': "code not exists"
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        aes = AEScoder()
        origin = aes.decrypt(code)
        if not origin:
            data = {
                'detail': "code not exists"
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        id = int(origin)
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(id=id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class QRCodeQueryOthersView(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = QRCodeURLOthersViewSerializer
    def get_queryset(self):
        return QRCodeOthersView.objects.all()

    def list(self, request, *args, **kwargs):
        code = self.request.query_params.get("code", 0)
        if not code:
            data = {
                'detail': "code not exists"
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        aes = AEScoder()
        origin = aes.decrypt(code)
        if not origin:
            data = {
                'detail': "code not exists"
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        id = int(origin)
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(id=id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class PublicGetHouseView(mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    """
    查看房源信息
    """
    serializer_class = HousesSerializer

    def get_queryset(self):
        return Houses.objects.all()

    def list(self, request, *args, **kwargs):
        code = self.request.query_params.get("code", 0)
        if not code:
            data = {
                'detail': "code not exists"
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        aes = AEScoder()
        origin = aes.decrypt(code)
        if not origin:
            data = {
                'detail': "code not exists"
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        id = int(origin)
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(id=id).order_by('floor')
        if not queryset.count() :
            data = {
                'detail': "house not exists"
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(queryset.first())
        return Response(serializer.data)


class LandlordHouseOptions(mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    serializer_class = HousesSerializer
    authentication_classes = [LandlordAuthentication]
    # permission_classes = [LandlordPermission]
    # pagination_class = MyPaginatioin
    def list(self, request, *args, **kwargs):
        queryset = Houses.objects.filter(uploader_id=request.user, is_delete=False).order_by('detail_address')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# TODO 待完成
@api_view(http_method_names=['GET'], )
def list_one_qrcode(request):
    # 通过浏览器传来的longitude和latitude，找到最近地铁站名
    input_value = request.data

    if not input_value['QRCodeId']:
        err_msg = {
            'detail': "请上传必要信息：The QRCode ID"
        }
        return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)
    # call a function to declare
    qrCode = QRCodeURLModel.objects.filter(id=input_value['QRCodeId'])
    if not qrCode:
        err_msg = {
            'detail': "请上传必要信息：The QRCodeId is not exists, Please input a valid QRCodeId"
        }
        return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)

    # TODO
    return 1


# @api_view(http_method_names=['POST'],)
# def HouseInherit(request):
#     # should provide landlord's mobile
#     input_value = request.data
#
#     if not input_value['mobile']:
#         err_msg = {
#             'detail': 'please input mobile'
#         }
#         return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)
#
#     mobile = input_value['mobile']
#     houseList = Houses.objects.filter(contact_phone=mobile, uploader_id='18125953690')
#     for i in houseList:
#         print(i)
#     return Response({'success': '1'}, status=status.HTTP_400_BAD_REQUEST)


class TurnoverPayView(viewsets.ModelViewSet):
    # 需要浏览器传来流水金额
    serializer_class = TurnoverOrderSerializer
    authentication_classes = [PublicAuthentication]

    def get_queryset(self):
        return TurnoverOrderModel.objects.filter(salesman_mobile=self.request.user)

    def create(self, request, *args, **kwargs):
        if not request.data['money']:
            return Response(err_para_lack, status=status.HTTP_400_BAD_REQUEST)

        order = TurnoverOrderModel.objects.filter(salesman_mobile=request.user, status__in=['2', '5', '7'])

        current_time = datetime.now() - timedelta(minutes=10)

        if order.count():
            for i in order:
                if current_time < i.created_date:
                    return Response('存在处理中的订单，请先支付或取消该订单', status=status.HTTP_400_BAD_REQUEST)
                else:
                    i.status = '3'
                    i.save(update_fields=["status"])

        # 生成最多32?位的商户订单号
        out_trade_no = getWxPayOrderID()

        price = request.data['money']
        amount = 1

        total_price = (price * amount * 100)
        notify_url = Wx_Order_Url_Turnover_Notify

        wx_response = WxPayOrder(total_price, out_trade_no, Wx_Order_Url_Native, notify_url)

        wx_content = json.loads(wx_response.content.decode())

        if wx_response.status_code == 200:
            data = request.data.copy()
            data['out_trade_no'] = out_trade_no
            data['status'] = '7'
            data['created_date'] = datetime.now()
            data['salesman_mobile'] = request.user
            data['money'] = price
            data['turnover_id'] = 46
            data['pay_url'] = wx_content['code_url']
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        else:
            message = wx_response.content
            message = message.decode()
            return HttpResponse(f'创建订单失败,错误码：{wx_response.status_code}, 错误信息：{message}, 请重新创建或联系客服。')

    def update(self, request, *args, **kwargs):
        data = request.data.copy()
        wx_response = closeOrder(data["out_trade_no"])
        data["status"] = '3'
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

class TurnoverPayNotifyView(APIView, ):
    """ 微信员工流水付款回调视图 """
    def post(self, request):
        try:
            vetifySign(request)
        except:
            return Response({'detail': '验签不通过'}, status=status.HTTP_400_BAD_REQUEST)

        msg = request.body.decode('utf-8')
        info = json.loads(msg)

        resource = info['resource']
        ciphertext = resource['ciphertext']
        nonce = resource['nonce']
        associated_data = resource['associated_data']
        result = decrypt(nonce, ciphertext, associated_data).decode()
        result = json.loads(result)

        try:
            order_instance = TurnoverOrderModel.objects.get(out_trade_no=result['out_trade_no'])
        except:
            return Response({'detail': '发生了一些小故障，请重试或者咨询客服'}, status=status.HTTP_400_BAD_REQUEST)

        wx_status = result['trade_state']

        if wx_status not in PAY_KEY:
            return Response({'code': 'UNDEFINE', 'message': '返回值异常'}, status=status.HTTP_400_BAD_REQUEST)

        order_instance.status = PAY_STATUS[wx_status]
        order_instance.save(update_fields=['status'])
        return Response({'code': wx_status, 'message': PAY_MESSAGE[wx_status]}, status=status.HTTP_200_OK)


class TurnoverPayUrl(APIView):
    """ wechat pay query order view """
    def get(self, request):
        price = float(self.request.query_params.get("price", None))
        id = self.request.query_params.get("id", None)
        fresh = self.request.query_params.get("fresh", None)
        paid_orders = TurnoverOrderModel.objects.filter(turnover_id=id, money=price, status='0')
        if paid_orders:
            order = TurnoverOrderSerializer(paid_orders.first())
            return Response(order.data, status=status.HTTP_200_OK)

        if not fresh:
            pay_orders = TurnoverOrderModel.objects.filter(turnover_id=id, money=price, status__in=['2', '5', '7'])
            if pay_orders:
                pay_order = pay_orders.first()
                order = TurnoverOrderSerializer(pay_order)
                return Response(order.data, status=status.HTTP_200_OK)
        if fresh:
            current_time = datetime.now() - timedelta(minutes=1)
            pay_orders = TurnoverOrderModel.objects.filter(turnover_id=id, money=price, created_date__gt=current_time)
            if pay_orders:
                err_msg = {
                    'detail': '请求太过频繁，请一分钟后尝试刷新'
                }
                return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)
        phone = TurnoverRecord.objects.get(id=id).account
        # 生成最多32?位的商户订单号
        out_trade_no = getWxPayOrderID()

        amount = 1

        total_price = (price * amount * 100)
        notify_url = Wx_Order_Url_Turnover_Notify

        wx_response = WxPayOrder(total_price, out_trade_no, Wx_Order_Url_Native, notify_url)

        wx_content = json.loads(wx_response.content.decode())

        if wx_response.status_code == 200:
            data = request.data.copy()
            data['out_trade_no'] = out_trade_no
            data['status'] = '7'
            data['created_date'] = datetime.now()
            data['salesman_mobile'] = phone
            data['money'] = price
            data['pay_url'] = wx_content['code_url']
            data['turnover_id'] = id

            serializer = TurnoverOrderSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            message = wx_response.content
            message = message.decode()
            return HttpResponse(f'创建订单失败,错误码：{wx_response.status_code}, 错误信息：{message}, 请重新创建或联系客服。')


class TurnoverPayMini(APIView):
    """ wechat mini pay"""
    def get(self, request):
        id = self.request.query_params.get("id", None)
        openid = self.request.query_params.get("openid", None)

        if id == None and openid == None:
            msg = {
                'detail': 'id or openid not exist'
            }
            return Response(msg)
        # get turnover
        turnovers = TurnoverRecord.objects.filter(id=id)
        if not turnovers:
            msg = {
                'detail': 'turnover not exist'
            }
            return Response(msg)

        turnover = turnovers.first()

        # check status
        ('0', '订单已创建'), ('1', '未支付'), ('2', '已支付'), ('3', '退款中'), ('4', '已退款'), ('5', '已关闭')
        status = turnover.status
        fee = turnover.rent_fee/2
        if status == '0':
            # create order
            out_trade_no = getWxPayOrderID()
            payway = PAY_WAY_WEIXIN
            amount = 1
            client_ip = '61.140.220.32'
            product_desc = '帮克租收款'
            product_detail = '内部单号:' + str(turnover.id)
            total_price = int(fee * amount * 100)

            result = unipay.create_order(out_trade_no, payway, client_ip, product_desc, product_detail, total_price,
                                     user=None, attach=None,
                                     expire=120, fee_type='CNY', openid=openid, trade_type='JSAPI')
            result['status'] = '1'
            turnover.orderno = out_trade_no
            turnover.status = '1'
            turnover.save()
            unipay.set_pay_info(out_trade_no, result)
            return Response(result)

        if status == '2' or status == '3' or status=='4' or status == '5':
            # paid
            result = {
                'status': status
            }
            return Response(result)

        if status == '1':
            pay_status = unipay.query_order(orderno=turnover.orderno)
            if pay_status.succ:
                turnover.status ='2'
                result = {
                    'status': turnover.status
                }
                return Response(result)

            # is paying
            payway = unipay.get_order_payway(turnover.orderno)
            if payway == (PAY_WAY_WEIXIN, 'JSAPI'):
                # same payway
                result = unipay.get_pay_info(turnover.orderno)
                if result:
                    return Response(result)
                # else expire payinfo need to refresh

            # diffrent payway. close order and create new order
            # close order
            unipay.close_order(turnover.orderno)
            #create new order
            out_trade_no = getWxPayOrderID()
            payway = PAY_WAY_WEIXIN
            amount = 1
            client_ip = '61.140.220.32'
            product_desc = '帮克租收款'
            product_detail = '内部单号:' + str(turnover.id)
            total_price = int(fee * amount * 100)

            result = unipay.create_order(out_trade_no, payway, client_ip, product_desc, product_detail, total_price,
                                         user=None, attach=None,
                                         expire=120, fee_type='CNY', openid=openid, trade_type='JSAPI')
            result['status'] = '1'
            turnover.orderno = out_trade_no
            turnover.status = '1'
            turnover.save()
            unipay.set_pay_info(out_trade_no, result)
            return Response(result)


class TurnoverPayQrcode(APIView):
    """ wechat qrcode pay"""
    def get(self, request):
        id = self.request.query_params.get("id", None)
        # openid = self.request.query_params.get("openid", None)

        if id == None:
            msg = {
                'detail': 'id not exist'
            }
            return Response(msg)
        # get turnover
        turnovers = TurnoverRecord.objects.filter(id=id)
        if not turnovers:
            msg = {
                'detail': 'turnover not exist'
            }
            return Response(msg)

        turnover = turnovers.first()

        # check status
        ('0', '订单已创建'), ('1', '未支付'), ('2', '已支付'), ('3', '退款中'), ('4', '已退款'), ('5', '已关闭')
        status = turnover.status
        fee = turnover.rent_fee/2
        if status == '0':
            # create order
            out_trade_no = getWxPayOrderID()
            payway = PAY_WAY_WEIXIN
            amount = 1
            client_ip = '61.140.220.32'
            product_desc = '帮克租收款'
            product_detail = '内部单号:' + str(turnover.id)
            total_price = int(fee * amount * 100)

            result = unipay.create_order(out_trade_no, payway, client_ip, product_desc, product_detail, total_price,
                                     user=None, attach=None,
                                     expire=120, fee_type='CNY', trade_type='NATIVE')
            print(result)
            result['status'] = '1'
            turnover.orderno = out_trade_no
            turnover.status = '1'
            turnover.save()
            unipay.set_pay_info(out_trade_no, result)
            return Response(result)

        if status == '2' or status == '3' or status=='4' or status == '5':
            # paid
            result = {
                'status': status
            }
            return Response(result)

        if status == '1':
            pay_status = unipay.query_order(orderno=turnover.orderno)
            if pay_status.succ:
                turnover.status ='2'
                result = {
                    'status': turnover.status
                }
                return Response(result)

            # is paying
            payway = unipay.get_order_payway(turnover.orderno)
            if payway == (PAY_WAY_WEIXIN, 'NATIVE'):
                # same payway
                result = unipay.get_pay_info(turnover.orderno)
                if result:
                    return Response(result)
                # else expire payinfo need to refresh

            # diffrent payway. close order and create new order
            # close order
            unipay.close_order(turnover.orderno)
            #create new order
            out_trade_no = getWxPayOrderID()
            payway = PAY_WAY_WEIXIN
            amount = 1
            client_ip = '61.140.220.32'
            product_desc = '帮克租收款'
            product_detail = '内部单号:' + str(turnover.id)
            total_price = int(fee * amount * 100)

            result = unipay.create_order(out_trade_no, payway, client_ip, product_desc, product_detail, total_price,
                                         user=None, attach=None,
                                         expire=120, fee_type='CNY', trade_type='NATIVE')
            result['status'] = '1'
            turnover.orderno = out_trade_no
            turnover.status = '1'
            turnover.save()
            unipay.set_pay_info(out_trade_no, result)
            return Response(result)


class TurnoverPayQuery(APIView):
    """ wechat pay query order view """

    def post(self, request):
        if not request.data['out_trade_no']:
            return Response(err_para_lack, status=status.HTTP_400_BAD_REQUEST)

        query_url = Wx_Order_Url_Query + request.data['out_trade_no']

        timestamp = int(time.time())
        nonce = secrets.token_hex(16)
        sign_str = generatorSign('GET', query_url[29:]+'?mchid=1608112493', timestamp, nonce, '')
        private_key_path = PRIVATE_KEY_PATH
        wx_sign = calculateSign(sign_str, private_key_path)

        auth_value = f'WECHATPAY2-SHA256-RSA2048 mchid="1608112493",nonce_str="{nonce}",timestamp="{str(timestamp)}",signature="{wx_sign}",serial_no="7AEF84537B07D54563EF0D793489124EF6260378"'

        wx_response = requests.get(query_url, params={'mchid': '1608112493'}, headers={'Content-Type': 'application/json', 'Authorization': auth_value})


        result = wx_response.json()
        # out_trade_no = result['out_trade_no']
        # trade_state = result['trade_state']
        # respon = {
        #     # "attach": "",
        #     "out_trade_no": result['out_trade_no'],
        #     # "payer": result['payer'],
        #     "promotion_detail": result['promotion_detail'],
        #     "trade_state": result['trade_state'],
        #     "trade_state_desc": result['trade_state_desc']
        # }
        # order = TurnoverOrderModel.objects.get(out_trade_no=out_trade_no)
        # order.status = PAY_STATUS[trade_state]
        # order.save()

        return Response(result)

class OtherAppGetHouseView(mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    """
    查看房源信息
    """
    serializer_class = HousesSerializer
    pagination_class = MyPaginatioin
    filter_backends = (rest_framework.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_class = HousesFilter
    search_fields = ['detail_address', 'name']
    ordering_fields = ('id', 'price', 'updated_time')

    def get_queryset(self):
        return Houses.objects.all()

    def list(self, request, *args, **kwargs):
        mobile = self.request.query_params.get("mobile", 0)
        if not mobile:
            data = {
                'detail': "mobile not exists"
            }
            return Response(data, status.HTTP_400_BAD_REQUEST)
        result = PublicWhiteListModel.objects.filter(mobile=mobile).count()
        if result == 0:
            data = {
                'detail': "no permission"
            }
            return Response(data, status.HTTP_403_FORBIDDEN)
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(uploader=mobile, is_delete=False).order_by('id')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class OtherAppGetHouseAddress(mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    def list(self, request, *args, **kwargs):
        mobile = self.request.query_params.get("mobile", 0)
        if not mobile:
            data = {
                'detail': "mobile not exists"
            }
            return Response(data, status.HTTP_400_BAD_REQUEST)
        result = PublicWhiteListModel.objects.filter(mobile=mobile).count()
        if result == 0:
            data = {
                'detail': "no permission"
            }
            return Response(data, status.HTTP_403_FORBIDDEN)

        houses = Houses.objects.filter(uploader=mobile, is_delete=False).distinct('detail_address').order_by('detail_address').values('detail_address')
        addresses = []
        print(houses)
        for house in houses:
            addresses.append(house['detail_address'])
        data = {
            'addresses': addresses
        }
        return Response(data)

# TODO
# class WxPayView(mixins.CreateModelMixin, viewsets.GenericViewSet):
#     # 需要浏览器传来的购买会员类型('2': 月度会员 600, '3': 季度会员 580, '4': 半年会员 550, '5': 年度会员 500)
#     serializer_class = OrderSerializer
#
#     def create(self, request, *args, **kwargs):
#         if request.data['commodity_type'] not in ['2', '3', '4', '5']:
#             return Response(err_para_lack, status=status.HTTP_400_BAD_REQUEST)
#
#         vip_type = int(request.data['commodity_type'])
#
#         # 生成最多32?位的商户订单号
#         out_trade_no = getWxPayOrderID()
#
#         price = price_and_amount[vip_type - 2][1]
#         amount = price_and_amount[vip_type - 2][2]
#
#         total_price = (price * amount * 100)
#
#         notify_url = 'https://127.0.0.1/hotelapp/agency/WxPayresult'
#
#         Wx_response = WxPayOrder(total_price, out_trade_no, Wx_Order_Url_JSAPI, notify_url)
#
#         if Wx_response.status_code == 200:
#             prepay_id = Wx_response.content['prepay_id']
#             data = request.data.copy()
#             data['out_trade_no'] = out_trade_no
#             data['status'] = '1'
#             data['created_date'] = datetime.now()
#             serializer = self.get_serializer(data=data)
#             serializer.is_valid(raise_exception=True)
#             self.perform_create(serializer)
#             headers = self.get_success_headers(serializer.data)
#             data['prepay_id'] = prepay_id       # prepay_id  给小程序调用
#             return Response(data, status=status.HTTP_201_CREATED, headers=headers)
#         else:
#             return HttpResponse(f'创建订单失败,错误码：{Wx_response.status_code}, 请重新创建或联系客服。')
#
#
# class WxNotifyURLView(APIView):
#     """ 微信回调视图 """
#     def cal_day(self, month_amount):
#         if timezone.now().month % 2 == 0:
#             even_month = int(month_amount/2)
#             odd_month = month_amount - even_month
#         else:
#             odd_month = int(month_amount/2)
#             even_month = month_amount - odd_month
#         return odd_month * 31 + even_month * 30
#
#     def check_pay(self, params):
#         from alipay.aop.api.util.SignatureUtils import verify_with_rsa
#         sign = params.pop('sign', None)
#         params.pop('sign_type')  # 取出签名类型
#         params = sorted(params.items(), key=lambda e: e[0], reverse=False)  # 取出字典元素按key的字母升序排序形成列表
#         message = "&".join(u"{}={}".format(k, v) for k, v in params).encode()  # 将列表转为二进制参数字符串
#         # with open(settings.ALIPAY_PUBLIC_KEY_PATH, 'rb') as public_key: # 打开公钥文件
#         try:
#             #     status =verify_with_rsa(public_key.read().decode(),message,sign) # 验证签名并获取结果
#             # 验证签名并获取结果
#             ali_status = verify_with_rsa(get_key(ALIPAY_PUBLIC_KEY).encode('utf-8').decode('utf-8'), message, sign)
#             return ali_status  # 返回验证结果
#         except:  # 如果验证失败，返回假值。
#             return False
#
#     def post(self, request):
#         key_path = ''
#         if not notify_sign(request, key_path):
#             return Response({'detail': '验签不通过'}, status=status.HTTP_400_BAD_REQUEST)
#
#         msg = request.body.decode('utf-8')
#         info = json.loads(msg)
#         resource = info['resource']
#         ciphertext = resource['ciphertext']
#         nonce = resource['nonce']
#         associated_data = resource['associated_data']
#         result = decrypt(key, nonce,ciphertext,associated_data)
#
#         try:
#             order_instance = Order.objects.get(out_trade_no=result['out_trade_no'])
#             agency_instance = AgencyUser.objects.get(mobile=order_instance.purchase_user)
#         except:
#             return Response({'detail': '发生了一些小故障，请重试或者咨询客服'}, status=status.HTTP_400_BAD_REQUEST)
#
#         if result['trade_state'] == 'SUCCESS':
#             purchase_type = order_instance.commodity_type
#             for i in price_and_amount:
#                 if i[0] == purchase_type:
#                     month = i[2]
#             if month:
#                 order_instance.status = '2'
#                 order_instance.save(update_fields=['status'])
#                 agency_instance.vip_deadline += timedelta(days=self.cal_day(month))
#                 agency_instance.vip_type = purchase_type
#                 agency_instance.save(update_fields=['vip_deadline', 'vip_type'])
#                 return Response({'code': 'SUCCESS', 'message': '成功'}, status=status.HTTP_200_OK)  # 成功后必须返回success
#         elif result['trade_state'] == 'PAYERROR' or result['trade_state'] == '':
#             order_instance.status = '0'
#             order_instance.save(update_fields=['status'])
#             close_order(result['out_trade_no'])
#             return Response({'code': 'PAYERROR', 'message': '支付失败/超时'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#
#
# @api_view(http_method_names=['GET'], )
# def wx_order_search(request):
#     # 通过浏览器传来的out_trade_no和mch_id，找到订单
#     input_value = request.data
#     print(input_value['out_trade_no'])  # should remove
#     print(input_value['mch_id'])  # should remove
#     if not input_value['out_trade_no'] or not input_value['mch_id']:
#         err_msg = {
#             'detail': "请上传必要信息:out_trade_no 和 mch_id"
#         }
#         return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)
#     url = 'https://api.mch.weixin.qq.com/v3/pay/transactions/out_trade_no/{' + input_value['out_trade_no'] + '?mchid=' + input_value['mch_id']
#     return requests.get(url)
