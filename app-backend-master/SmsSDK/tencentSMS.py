import json
import logging
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.sms.v20190711 import sms_client, models

logger = logging.getLogger(__name__)


class TencentSMS(object):

    def message_send(self, mobile_set, code):
        try:
            # TODO 需要优化
            cred = credential.Credential("AKID4sQav2kXZLr76tM8YbsxlIwKSJwKs1XG", "nL4b1EE0vJRbeaAVakqlW8lBQOCmvfMp")
            httpProfile = HttpProfile()
            httpProfile.endpoint = "sms.tencentcloudapi.com"

            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            client = sms_client.SmsClient(cred, "ap-guangzhou", clientProfile)

            req = models.SendSmsRequest()
            params = {
                "PhoneNumberSet": [mobile_set],
                "Sign": "租莱租趣",
                "TemplateID": "832581",
                "SmsSdkAppid": "1400468254",
                "TemplateParamSet": [code]
            }
            req.from_json_string(json.dumps(params))

            resp = client.SendSms(req)
            logger.info(resp.to_json_string())
            return resp
        except TencentCloudSDKException as err:
            logger.info(err)
            return None

