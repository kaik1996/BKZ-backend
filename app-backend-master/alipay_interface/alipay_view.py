#! Python3
# -*- coding: utf-8 -*-
import logging
import traceback
import os

from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.domain.AlipayTradeAppPayModel import AlipayTradeAppPayModel
from alipay.aop.api.domain.GoodsDetail import GoodsDetail
from alipay.aop.api.domain.ExtUserInfo import ExtUserInfo
from alipay.aop.api.request.AlipayTradeAppPayRequest import AlipayTradeAppPayRequest
from alipay.aop.api.response.AlipayTradePayResponse import AlipayTradePayResponse
from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest
from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel
from Crypto.PublicKey import RSA

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', filemode='a',)
logger = logging.getLogger('')

# Alipay 设置：
ALIPAY_PUBLIC_KEY = os.path.join(os.path.abspath('.'), 'alipay_interface', 'alipay_keys', 'alipay_public.txt')
APP_PUBLIC_KEY = os.path.join(os.path.abspath('.'), 'alipay_interface', 'alipay_keys', 'app_public.txt')
APP_PRIVATE_KEY = os.path.join(os.path.abspath('.'), 'alipay_interface', 'alipay_keys', 'app_private.txt')


def get_key(key_path):
    """取得密钥"""
    with open(key_path) as fp:
        return RSA.importKey(fp.read())


def client_init():
    # 实例化客户端
    alipay_client_config = AlipayClientConfig()
    alipay_client_config.server_url = 'https://openapi.alipay.com/gateway.do'
    alipay_client_config.app_id = ''
    alipay_client_config.app_private_key = get_key(APP_PRIVATE_KEY)
    alipay_client_config.alipay_public_key = get_key(ALIPAY_PUBLIC_KEY)
    client = DefaultAlipayClient(alipay_client_config, logger)
    return client


def order_submit(client, price, amount, out_trade_no, mobile):
    # 构造请求参数对象
    model = AlipayTradeAppPayModel()

    # TODO model.auth_code = ''
    model.body = '帮克租会员购买'
    goods_list = list()
    goods1 = GoodsDetail()
    goods1.alipay_goods_id = ''
    goods1.goods_name = '帮克租'
    goods1.price = price
    goods1.quantity = amount
    # TODO model.goods_id = ''
    goods_list.append(goods1)
    model.goods_detail = goods_list
    ext_user_info1 = list()
    extUserInfo = ExtUserInfo()
    extUserInfo.mobile = mobile
    ext_user_info1.append(extUserInfo)
    model.ext_user_info = ext_user_info1

    model.out_trade_no = out_trade_no
    model.product_code = ''
    #
    model.store_id = ''
    model.subject = '会员服务购买'
    model.timeout_express = '10m'
    model.total_amount = price * amount

    request = AlipayTradeAppPayRequest(biz_model=model)
    request.notify_url = ''     # TODO 支付宝回调链接
    request.return_url = ''     # TODO 支付后跳转页面

    # 如果有auth_token、app_auth_token等其他公共参数，放在udf_params中
    # udf_params = dict()
    # from alipay.aop.api.constant.ParamConstants import *
    # udf_params[P_APP_AUTH_TOKEN] = "xxxxxxx"
    # request.udf_params = udf_params
    # 执行请求，执行过程中如果发生异常，会抛出，请打印异常栈

    response_content = None
    # noinspection PyBroadException
    try:
        response_content = client.execute(request)
    except Exception as e:
        print(traceback.format_exc())
    if not response_content:
        print('failed execute')
        return False
    else:
        response = AlipayTradePayResponse()
        # 解析响应结果
        response.parse_response_content(response_content)
        print(response.body)
        if response.is_success():
            # 如果业务成功，则通过response属性获取需要的值
            print('get response trade_no:' + response.trade_no)
        else:
            # 如果业务失败，从从错误码中可以得知错误情况，具体错误码信息查看文档
            print(response.code + ',' + response.msg + ',' + response.sub_code + ',' + response.sub_msg)
        return response


def order_query(client, out_trade_no):
    """
    查询订单
    输入：商户订单号
    """
    # 初始化客户端
    # TODO 待完成

    model = AlipayTradeQueryModel()

    model.out_trade_no = out_trade_no
    request = AlipayTradeAppPayRequest(biz_model=model)

    """ 第三方调用（服务商模式），传值app_auth_token后，会收款至授权token对应商家账号，如何获传值app_auth_token请参考文档：
    https://opensupport.alipay.com/support/helpcenter/79/201602494631 """
    # request.add_other_text_param('app_auth_token', '传入获取到的app_auth_token值')

    response = client.execute(request)


# def bill_downloadurl(client, date):
#     """  构造请求参数对象，当前调用接口名称：alipay.data.dataservice.bill.downloadurl.query（查询对账单下载地址接口） """
#     model = AlipayDataDataserviceBillDownloadurlQueryModel()
#
#     """ 日账单格式为yyyy - MM - dd；月账单格式为yyyy - MM。不支持下载当日或者当月账单 """
#     model.bill_date = date
#
#     """可以获取以下账单类型：trade、signcustomer；trade指基于支付宝交易收单接口的业务账单；
#     signcustomer是指基于商户支付宝余额收入及支出等资金变动的帐务账单"""
#     model.bill_type="signcustomer";
#
#     request = AlipayDataDataserviceBillDownloadurlQueryRequest(biz_model=model)
#
#     """ 第三方调用（服务商模式），传值app_auth_token后，会收款至授权token对应商家账号，如何获传值app_auth_token请参考文档：
#     https://opensupport.alipay.com/support/helpcenter/79/201602494631 """
#     # request.add_other_text_param('app_auth_token','传入获取到的app_auth_token值')
#
#     """ 执行API调用 """
#     response = client.execute(request)
#
#     """ 获取接口调用结果，如果调用失败，可根据返回错误信息到该文档寻找排查方案：https://opensupport.alipay.com/support/helpcenter"""
