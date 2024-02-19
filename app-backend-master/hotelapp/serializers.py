from rest_framework import serializers, exceptions
# from .models import Houses, LandlordUser, VerifyCode, AgencyUser, WeChatCode, WeChatLogin, Order, Favorites, BulletinBoard,\
#     HouseTemplate, Feedback, BatchHouses, MobileModel, HistoryRecord, StaffLocation, OperatorRecord, TurnoverRecord
from .models import *
from rest_framework import serializers
from hotelapp.aes import AEScoder
from .utils import REGEX_MOBILE
import re


class HousesSerializer(serializers.ModelSerializer):
    """
    查看房屋信息序列化类
    """
    class Meta:
        model = Houses
        fields = '__all__'
        read_only_fields = ['created_time', 'update_time']

    def validate_contact_phone(self, data):
        if not re.match(REGEX_MOBILE, data):
            raise serializers.ValidationError("手机号码格式错误！")
        else:
            return data


# 测试用
# class SuperUserSerializer(serializers.HyperlinkedModelSerializer):
#     class Meta:
#         model = SuperUser
#         fields = '__all__'
#
#     def create(self, validated_data):
#         instance = AgencyUser.objects.create(**validated_data)
#         return instance
#
#     def update(self, instance, validated_data):
#         for k, v in validated_data.items():
#             setattr(instance, k, v)
#         instance.save()
#         return instance


# 测试用
# class ContractSerializer(serializers.HyperlinkedModelSerializer):
#     class Meta:
#         model = Contract
#         fields = '__all__'
#
#     def validate_owner(self, data):
#         owner_obj = LandlordUser.objects.get(mobile=data)
#         if not owner_obj:
#             raise exceptions.ValidationError('无该房东！')
#         return data
#
#     def validate_agency(self, data):
#         agency_obj = AgencyUser.objects.get(mobile=data)
#         if not agency_obj:
#             raise exceptions.ValidationError('无该中介！')
#         return data
#
#     def create(self, validated_data):
#         instance = Contract.objects.create(**validated_data)
#         return instance
#
#     def update(self, instance, validated_data):
#         for k, v in validated_data.items():
#             setattr(instance, k, v)
#         instance.save()
#         return instance


# class SmsSerializer(serializers.ModelSerializer):
#     """
#     验证码序列化类
#     """
#     @staticmethod
#     def validate_mobile(data):
#         """
#         手机注册验证功能
#         :param data: 手机号码
#         :return: 手机号码 / 抛出异常
#         """
#         if not re.match(REGEX_MOBILE, data):
#             raise serializers.ValidationError('手机号码格式错误')
#
#         interval_time = timezone.now() - timedelta(minutes=1)
#         if LandlordUser.objects.filter(code_updated_time__gt=interval_time, mobile=data).count():
#             raise serializers.ValidationError('两次发送验证码间隔小于一分钟')
#
#         return data
#
#     class Meta:
#         model = LandlordUser
#         fields = ['mobile']


class LandlordRegSerializer(serializers.ModelSerializer):
    """
    房东账号序列化类
    """
    def validate_password(self, data):
        if re.match(r'[A-Z]', data):   # 后期待完善
            if re.search(r'[a-z]', data) and re.search(r'[0-9]', data) and len(data) > 7:
                return data
            else:
                raise serializers.ValidationError('密码格式错误')
        else:
            raise serializers.ValidationError('密码首字母必须大写')

    # def validate_code(self, code):
    #     pass
    #     """
    #     verify_records = VerifyCode.objects.filter(mobile=self.initial_data['mobile']).order_by('-add_time')
    #     if verify_records:
    #         last_records = verify_records[0]
    #         three_min_ago = timezone.now() - timedelta(minutes=3)
    #         if three_min_ago > last_records.add_time:
    #             raise serializers.ValidationError('验证码过期')
    #
    #         if last_records.code != code:
    #             raise serializers.ValidationError('验证码1错误')
    #
    #     else:
    #         raise serializers.ValidationError('验证码2错误')
    #     """

    # def validate(self, validated_data):
    #     # 验证成功，删除验证码

    def create(self, validated_data):
        account = super(LandlordRegSerializer, self).create(validated_data=validated_data)
        account.set_password(validated_data['password'])
        account.save()
        return account

    class Meta:
        model = LandlordUser
        fields = '__all__'
        read_only_fields = ['created_time', 'updated_time', 'account_type']


class AgencyRegSerializer(serializers.ModelSerializer):
    # """
    # 中介账号序列化类
    # """

    # @staticmethod
    # def validate_password(value):
    #     if re.match(r'[A-Z]', value):   # 后期待完善
    #         if re.search(r'[a-z]', value) and re.search(r'[0-9]', value) and len(value) > 7:
    #             return value
    #         else:
    #             raise serializers.ValidationError('密码格式错误')
    #     else:
    #         raise serializers.ValidationError('密码首字母必须大写')

    def create(self, validated_data):
        account = super(AgencyRegSerializer, self).create(validated_data=validated_data)
        account.set_password(validated_data['password'])
        account.save()
        return account

    class Meta:
        model = AgencyUser
        fields = '__all__'
        read_only_fields = ['created_time', 'updated_time', 'is_valid', 'vip_type', 'vip_deadline', 'account_type']


class CodeSerializer(serializers.ModelSerializer):

    @staticmethod
    def validate_mobile(data):
        if not re.match(REGEX_MOBILE, data):
            raise serializers.ValidationError("手机号码格式错误！")

        # 验证码发送频率
        # one_minutes_ago = datetime.now() - timedelta(hours=0, minutes=1, seconds=0)
        # if VerifyCode.objects.filter(add_time__gt=one_minutes_ago, mobile=data).count():
        #     raise serializers.ValidationError("距离上一次发送未超过60s！")

        return data

    class Meta:
        model = VerifyCode
        fields = ['mobile']


class CodeCheckSerializer(serializers.ModelSerializer):
    @staticmethod
    def validate_mobile(data):
        if not re.match(REGEX_MOBILE, data):
            raise serializers.ValidationError("手机号码格式错误！")

        # 验证码发送频率
        # one_minutes_ago = datetime.now() - timedelta(hours=0, minutes=1, seconds=0)
        # if VerifyCode.objects.filter(add_time__gt=one_minutes_ago, mobile=data).count():
        #     raise serializers.ValidationError("距离上一次发送未超过60s！")
        return data

    class Meta:
        model = VerifyCode
        fields = ['mobile', 'code']


class WeChatCodeSerializer(serializers.ModelSerializer):

    class Meta:
        model = WeChatCode
        fields = ['code']


class WeChatLoginSerializer(serializers.ModelSerializer):

    class Meta:
        model = WeChatLogin
        fields = ['session_key', 'encrypted_data', 'iv']


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['purchase_user', 'commodity_type']


class FavoritesSerializer(serializers.ModelSerializer):
    class Meta:
        unique_together = (('house_id', 'mobile'))
        model = Favorites
        fields = '__all__'


class FavoriteHousesSerializer(serializers.ModelSerializer):
    house_id = HousesSerializer(many=False)
    class Meta:
        unique_together = (('house_id', 'mobile'))
        model = Favorites
        fields = '__all__'


class BulletinBoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = BulletinBoard
        fields = '__all__'


class HouseTemplateSerializer(serializers.ModelSerializer):
    """
    房源模板信息序列化类
    """
    class Meta:
        model = HouseTemplate
        fields = '__all__'
        read_only_fields = ['created_time', 'update_time']


class FeedbackSerializer(serializers.ModelSerializer):
    """
    反馈信息序列化类
    """
    class Meta:
        model = Feedback
        fields = '__all__'


class BatchHousesSerializer(serializers.ModelSerializer):
    """
    批量信息序列化类
    """
    class Meta:
        model = BatchHouses
        fields = '__all__'


class CheckLandlordSerializer(serializers.ModelSerializer):
    """
    检测房东是否存在序列化类
    """
    class Meta:
        model = MobileModel
        fields = '__all__'


class HistoryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoryRecord
        fields = '__all__'


class StaffLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffLocation
        fields = '__all__'


class OperatorRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperatorRecord
        fields = '__all__'


class TurnoverRecordSerializer(serializers.ModelSerializer):


    class Meta:
        model = TurnoverRecord
        fields = '__all__'



class QRCodeURLSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRCodeURLModel
        fields = '__all__'
        readly_filed = 'mobile'


class QRCodeURLViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRCodeView
        fields = '__all__'

    def to_representation(self, instance):
        ret = super(QRCodeURLViewSerializer, self).to_representation(instance)
        aes=AEScoder()
        ret.update({
            'house_id': aes.encrypt(str(instance.house_id))
        })

        return ret

class QRCodeURLOthersViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRCodeOthersView
        fields = '__all__'

    def to_representation(self, instance):
        ret = super(QRCodeURLViewSerializer, self).to_representation(instance)
        aes=AEScoder()
        ret.update({
            'house_id': aes.encrypt(str(instance.house_id))
        })

        return ret


class TurnoverOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = TurnoverOrderModel
        fields = '__all__'
