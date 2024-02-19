# -*- coding: utf-8 -*-
import os
import json
import base64
import secrets
import time

import requests
from datetime import datetime, timedelta
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from hotel.settings import BASE_DIR

Wx_Order_Url_JSAPI = 'https://api.mch.weixin.qq.com/v3/pay/transactions/jsapi'

Wx_Order_Url_Native = 'https://api.mch.weixin.qq.com/v3/pay/transactions/native'

Wx_Order_Url_GET_CERT = 'https://api.mch.weixin.qq.com/v3/certificates'

Wx_Order_Url_Turnover_Notify = 'https://test.zulaizuqu.cool/hotelapp/turnover_wx_notify'

Wx_Order_Url_Query = 'https://api.mch.weixin.qq.com/v3/pay/transactions/out-trade-no/'

PRIVATE_KEY_PATH = os.path.join(BASE_DIR, 'WechatPay/apiclient_key.pem')

PUBLIC_KEY_PATH = os.path.join(BASE_DIR, 'WechatPay/apiclient_pub_key.pem')

API_V3_KEY_PATH = os.path.join(BASE_DIR, 'WechatPay/APIV3_key.txt')

PAY_STATUS = {'SUCCESS': '0', 'REFUND': '1', 'NOTPAY': '2', 'CLOSED': '3', 'REVOKED': '4', 'USERPAYING': '5', 'PAYERROR': '6'}

PAY_MESSAGE = {'SUCCESS': '支付成功', 'REFUND': '转入退款', 'NOTPAY': '未支付', 'CLOSED': '已关闭', 'REVOKED': '已撤销',
               'USERPAYING': '支付中', 'PAYERROR': '支付失败'}

PAY_KEY = list(PAY_STATUS)


def getWxPayOrderID():
    return 'bangkezu' + datetime.now().strftime("%Y%m%d%H%M%S%f")


def getExpireTime():
    # TODO
    return (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def orderSubmit(price, out_trade_no, notify_url):
    appid = 'wx1e9705c9750ee114'
    mchid = '1608112493'
    description = '帮克租二维码收款'
    time_expire = getExpireTime()
    total = price

    jjson = {}
    jjson.update({'appid': appid})
    jjson.update({'mchid': mchid})
    jjson.update({'description': description})
    jjson.update({'out_trade_no': out_trade_no})
    jjson.update({'time_expire': time_expire})
    jjson.update({'notify_url': notify_url})
    jjson.update({'amount': {'total': int(total), 'currency': 'CNY'}})

    return json.dumps(jjson)


def closeOrder(out_trade_no):
    mchid = '1608112493'

    jjson = {}
    jjson.update({'mchid': mchid})
    body = json.dumps(jjson)

    Wx_Close_Url = 'http://api.mch.weixin.qq.com/v3/pay/transactions/out-trade-no/' + out_trade_no + '/close'

    return requests.post(Wx_Close_Url, body.encode('utf-8'), headers={'Content-Type': 'application/json'})


def WxPayOrder(price, out_trade_no, url, notify_url):
    # 获取封装好的json订单信息
    body = orderSubmit(price, out_trade_no, notify_url)

    timestamp = int(time.time())
    nonce = secrets.token_hex(16)
    sign_str = generatorSign('POST', '/v3/pay/transactions/native', timestamp, nonce, body)
    private_key_path = PRIVATE_KEY_PATH
    wx_sign = calculateSign(sign_str, private_key_path)

    auth_value = f'WECHATPAY2-SHA256-RSA2048 mchid="1608112493",nonce_str="{nonce}",timestamp="{str(timestamp)}",signature="{wx_sign}",serial_no="7AEF84537B07D54563EF0D793489124EF6260378"'

    return requests.post(url, body.encode('utf-8'), headers={'Content-Type': 'application/json', 'Authorization': auth_value})


def decrypt(nonce, ciphertext, associated_data):
    key = "BangKeZuYuanGongZhiFu20217777777"
    key_bytes = str.encode(key)
    nonce_bytes = str.encode(nonce)
    ad_bytes = str.encode(associated_data)
    data = base64.b64decode(ciphertext)
    aesgcm = AESGCM(key_bytes)
    return aesgcm.decrypt(nonce_bytes, data, ad_bytes)


def sign(sign_str, key):
    rsa_key = RSA.importKey(key)
    signer = pkcs1_15.new(rsa_key)
    digest = SHA256.new(sign_str.encode('utf-8'))
    sign = base64.b64decode(signer.sign(digest)).decode('utf-8')
    return sign


def vetifySign(request):
    with open(PUBLIC_KEY_PATH, 'r') as f:
        public_key = RSA.importKey(f.read())
        request_header = request.META
        wx_signature = request_header['HTTP_WECHATPAY_SIGNATURE']
        signature = base64.b64decode(wx_signature)
        timestamp = request_header['HTTP_WECHATPAY_TIMESTAMP']
        nonce = request_header['HTTP_WECHATPAY_NONCE']
        body = request.body.decode()

        sign_str = generatorSign(timestamp, nonce, body)

        h = SHA256.new(sign_str.encode('utf-8'))
        verifier = pkcs1_15.new(public_key)
        return verifier.verify(h, signature)


# 生成签名串
def generatorSign(*args):
    sign = ''
    for arg in args:
        sign += f'{arg}\n'
    return sign


# 计算签名串的值
def calculateSign(sign_str, private_key_path):
    with open(private_key_path, 'r') as f:
        rsa_key = RSA.importKey(f.read())
        signer = pkcs1_15.new(rsa_key)
        digest = SHA256.new(sign_str.encode('utf-8'))
        sign = base64.b64encode(signer.sign(digest)).decode(('utf-8'))
        return sign