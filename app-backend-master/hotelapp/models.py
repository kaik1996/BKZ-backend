from django.utils import timezone
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.postgres.fields import ArrayField
from django.contrib.gis.db import models as gisModels


class Houses(models.Model):
    AREA_NAME = (
        ('TH', '天河'), ('YX', '越秀'), ('LW', '荔湾'), ('HZ', '海珠'),
        ('PY', '番禺'), ('BY', '白云'), ('HP', '黄埔'), ('CH', '从化'),
        ('ZC', '增城'), ('HD', '花都'), ('NS', '南沙'), ('NH', '南海'),
        ('SD', '顺德')
    )
    HOUSE_TYPE = (
        ('0', '新小区'), ('1', '老小区'), ('2', '城中村'), ('3', '公寓')
    )
    DEGREE = (
        ('0', '差'), ('1', '一般'), ('2', '好'), ('3', '强光')
    )
    name = models.CharField(verbose_name='房屋名字', max_length=27)
    area = models.DecimalField(verbose_name='房屋面积(m^2)', max_digits=7, decimal_places=2)
    price = models.DecimalField(verbose_name='租金(元)', max_digits=7, decimal_places=2)
    mgmt_cost = models.DecimalField(verbose_name='管理费(元)', max_digits=7, decimal_places=2,  default=0)
    floor = models.SmallIntegerField(verbose_name='房间楼层')
    house_total_floor = models.SmallIntegerField(verbose_name='房屋楼层')
    room_number = models.SmallIntegerField(verbose_name='房数')
    hall_number = models.SmallIntegerField(verbose_name='厅数')
    toilet_number = models.SmallIntegerField(verbose_name='卫数')
    probably_address = models.CharField(verbose_name='定位地址', max_length=60)
    region = models.CharField(verbose_name='行政区', choices=AREA_NAME, max_length=2, default='TH')
    nextregion = models.CharField(verbose_name='next', max_length=20, blank=True, default='')
    detail_address = models.CharField(verbose_name='详细地址', null=True, blank=True, max_length=60)
    detail_house_no = models.CharField(verbose_name='门牌号', max_length=20)
    brightness = models.CharField(verbose_name='采光', choices=DEGREE, max_length=1, default='2')
    deposit = models.CharField(verbose_name='押金类型', max_length=7)
    has_balcony = models.BooleanField(verbose_name='有无阳台', default=False)
    has_elevator = models.BooleanField(verbose_name='有无电梯', default=False)
    tariff_type = models.BooleanField(verbose_name='是否商业用电', default=False)
    can_feed_dog = models.BooleanField(verbose_name='可否养狗', default=False)
    house_type = models.CharField(verbose_name='房屋类型', choices=HOUSE_TYPE, max_length=1, default='2')
    is_share = models.BooleanField(verbose_name='是否合租', default=False)
    is_rented = models.BooleanField(verbose_name='是否已租', default=False)
    rent_deadline = models.DateTimeField(verbose_name='租约截止日期', null=True)
    uploader = models.ForeignKey(to='LandlordUser', verbose_name='上传者账号', on_delete=models.DO_NOTHING)
    operator = models.CharField(verbose_name='经手人电话', max_length=11, null=True)
    contact_phone = models.CharField(verbose_name='联系电话', max_length=11)
    latitude = models.FloatField(verbose_name='纬度', null=True)
    longitude = models.FloatField(verbose_name='经度', null=True)
    created_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    updated_time = models.DateTimeField(verbose_name='更新时间', auto_now=True)
    photo_url = ArrayField(models.CharField(verbose_name='图片资源链接', max_length=1024), blank=True, default=list)
    video_url = ArrayField(models.CharField(verbose_name='视频资源链接', max_length=1024), blank=True, default=list)
    is_delete = models.BooleanField(verbose_name='是否删除', default=False)
    postscript = models.CharField(verbose_name='附加信息', null=True, blank=True, max_length=512)
    geo = gisModels.PointField(verbose_name='geo', srid=4490, null=True)
    subways = ArrayField(models.CharField(verbose_name='subway', max_length=40), blank=True, default=list)
    tag = ArrayField(models.CharField(verbose_name='tag', max_length=40), blank=True, default=list)
    # contract = models.ForeignKey(to='Contract', verbose_name='租赁状态', null=True, on_delete=models.CASCADE)

    def __str__(self):
        return f'小区：{self.probably_address}，面积：{self.area}，价格：{self.price}'

    class Meta:
        verbose_name = '房屋信息'
        ordering = ['id']


class SuperUser(AbstractBaseUser):
    # TODO 待完善
    name = models.CharField(verbose_name='姓名', max_length=17)
    mobile = models.CharField(verbose_name='手机号码', max_length=11, unique=True)
    password = models.CharField(verbose_name='密码', max_length=27)
    USERNAME_FIELD = 'mobile'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return f'登录账号：{self.mobile}，账号类型：超级管理员账号'

    class Meta:
        verbose_name = '特权账号信息'


class LandlordUser(AbstractBaseUser):
    mobile = models.CharField(verbose_name='手机号码', max_length=11, primary_key=True)
    name = models.CharField(verbose_name='姓名', max_length=17, null=True)
    wechat = models.CharField(verbose_name='微信账号', max_length=27, null=True)
    created_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    updated_time = models.DateTimeField(verbose_name='更新时间', auto_now=True)
    # TODO 暂时只有短信登录
    password = models.CharField(verbose_name='密码', max_length=32, null=True)
    is_valid = models.BooleanField(verbose_name='账户是否激活', default=False)
    USERNAME_FIELD = 'mobile'
    REQUIRED_FIELDS = ['name', 'wechat']

    def __str__(self):
        return f'登录账号：{self.mobile}，账号类型：房东账号'

    class Meta:
        verbose_name = '房东账号信息'
        ordering = ['-created_time']


class AgencyUser(AbstractBaseUser):  # 中介账号
    VIP_TYPE = (
        ('0', '普通账号'), ('1', '三天体验会员'), ('2', '月度会员'), ('3', '季度会员'),
        ('4', '半年会员'), ('5', '年度会员')
    )
    mobile = models.CharField(verbose_name='手机号码', max_length=11, primary_key=True)
    name = models.CharField(verbose_name='姓名', max_length=17)
    wechat = models.CharField(verbose_name='微信账号', max_length=20, null=True)
    created_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    updated_time = models.DateTimeField(verbose_name='更新时间', auto_now=True)
    password = models.CharField(verbose_name='密码', max_length=32)
    vip_type = models.CharField(verbose_name='会员类型', max_length=1, choices=VIP_TYPE, default='1')
    vip_deadline = models.DateTimeField(verbose_name='会员到期时间')
    is_valid = models.BooleanField(verbose_name="账户是否激活", default=False)
    assignment_number = models.PositiveIntegerField(verbose_name='促成签约数量', default=0)
    USERNAME_FIELD = 'mobile'
    REQUIRED_FIELDS = ['name', 'wechat', 'vip_type', 'vip_deadline']

    def __str__(self):
        return f'登录账号：{self.mobile}，账号类型：中介账号，会员到期时间：{self.vip_deadline}'

    def set_vip_type(self, member_type):
        """
        用来设置会员类型
        type = '0' - '5'
        """
        self.vip_type = member_type

    def set_vip_deadline(self, date):
        """
        用来设置会员时长
        """
        self.vip_deadline = date

    class Meta:
        verbose_name = '中介账号信息'
        ordering = ['-created_time']


# TODO 暂未实装
class Contract(models.Model):
    owner = models.ForeignKey(to='LandlordUser', verbose_name='合同房东姓名', on_delete=models.DO_NOTHING)
    agency = models.ForeignKey(to='AgencyUser', verbose_name='中介姓名', on_delete=models.DO_NOTHING)
    date = models.DateTimeField(verbose_name='签约日期', auto_now_add=True)
    deadline = models.DateTimeField(verbose_name='合同到期时间')
    house_id = models.ForeignKey(to='Houses', verbose_name='房屋ID', on_delete=models.DO_NOTHING)

    def __str__(self):
        return f'签约人：{self.owner}，合同到期时间：{self.deadline}'

    class Meta:
        verbose_name = '合同信息'


class LandlordToken(models.Model):
    mobile = models.CharField(verbose_name='登录手机号', max_length=11)
    token = models.CharField(verbose_name='登录令牌', max_length=128, primary_key=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True)


class AgencyToken(models.Model):
    mobile = models.CharField(verbose_name='登录手机号', max_length=11)
    token = models.CharField(verbose_name='登录令牌', max_length=128, primary_key=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True)


class SuperUserToken(models.Model):
    mobile = models.CharField(verbose_name='登录手机号', max_length=11)
    token = models.CharField(verbose_name='登录令牌', max_length=128, primary_key=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True)


class VerifyCode(models.Model):
    code = models.CharField(verbose_name='验证码', max_length=6)
    mobile = models.CharField(verbose_name='手机号码', max_length=11)
    add_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)

    def __str__(self):
        return f'手机号：{self.mobile}, 短信验证码：{self.code}'

    class Meta:
        verbose_name = '短信验证码'


class WeChatCode(models.Model):
    code = models.CharField(verbose_name='微信小程序code', max_length=40)

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = '微信小程序code'


class WeChatLogin(models.Model):
    session_key = models.CharField(verbose_name='微信小程序会话', max_length=40)
    encrypted_data = models.TextField(verbose_name='微信小程序加密数据')
    iv = models.CharField(verbose_name='微信小程序iv', max_length=40)

    def __str__(self):
        return self.session_key

    class Meta:
        verbose_name = '微信小程序登录（验证）'


class Order(models.Model):
    COMMODITY_TYPE = (
        ('2', '月度会员'), ('3', '季度会员'), ('4', '半年会员'), ('5', '年度会员')
    )
    ORDER_STATUS = (
        ('0', '超时'), ('1', '支付中'), ('2', '成功')
    )
    out_trade_no = models.CharField(verbose_name='订单号', max_length=64)
    status = models.CharField(verbose_name='订单状态', choices=ORDER_STATUS, max_length=1)
    created_date = models.DateTimeField(verbose_name='订单创建时间', auto_now_add=True)
    commodity_type = models.CharField(verbose_name='商品种类', choices=COMMODITY_TYPE, max_length=1)
    purchase_user = models.ForeignKey(to=AgencyUser, verbose_name='购买账号', on_delete=models.DO_NOTHING)

    def __str__(self):
        return f'订单号：{self.out_trade_no}, 订单状态：{self.status}'

    class Meta:
        verbose_name = '会员购买订单'


class Favorites(models.Model):
    house_id = models.ForeignKey(to=Houses, verbose_name='房屋id', on_delete=models.CASCADE)
    mobile = models.CharField(verbose_name='手机号', max_length=11)

    class Meta:
        unique_together = (('house_id', 'mobile'))
        verbose_name = '收藏夹'


class BulletinBoard(models.Model):
    BULLETIN_BOARD_TYPE = (
        ('0', '中介'), ('1', '房东'), ('2', '管理')
    )
    name = models.CharField(verbose_name='公告名', max_length=30, default="公告")
    content_url = models.CharField(verbose_name='公告栏图片资源链接', max_length=1024, default="kong")
    created_date = models.DateTimeField(verbose_name='发布时间', auto_now=True)
    type = models.CharField(verbose_name='房东/中介公告', max_length=1, choices=BULLETIN_BOARD_TYPE, default='1')

    class Meta:
        verbose_name = '公告栏信息'
        ordering = ['-created_date']


class HouseTemplate(models.Model):
    DEGREE = (
        ('0', '差'), ('1', '一般'), ('2', '好'), ('3', '强光')
    )
    name = models.CharField(verbose_name='模板名称', max_length=30)
    area = models.DecimalField(verbose_name='房屋面积(m^2)', max_digits=7, decimal_places=2)
    room_number = models.SmallIntegerField(verbose_name='房数')
    hall_number = models.SmallIntegerField(verbose_name='厅数')
    toilet_number = models.SmallIntegerField(verbose_name='卫数')
    brightness = models.CharField(verbose_name='采光', choices=DEGREE, max_length=1, default='2')
    has_balcony = models.BooleanField(verbose_name='有无阳台', default=False)
    is_share = models.BooleanField(verbose_name='是否合租', default=False)
    uploader = models.ForeignKey(to='LandlordUser', verbose_name='上传者账号', on_delete=models.DO_NOTHING)
    created_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    updated_time = models.DateTimeField(verbose_name='更新时间', auto_now=True)
    photo_url = ArrayField(models.CharField(verbose_name='图片资源链接', max_length=1024), blank=True, default=list)
    video_url = ArrayField(models.CharField(verbose_name='视频资源链接', max_length=1024), blank=True, default=list)
    postscript = models.CharField(verbose_name='附加信息', null=True, blank=True, max_length=512)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = '模板信息'
        ordering = ['id']


class Feedback(models.Model):
    creator = models.CharField(verbose_name='反馈者', max_length=30)
    endpoint = models.CharField(verbose_name='反馈端', max_length=30)
    content = models.TextField(verbose_name='反馈的内容', default="kong")
    created_time = models.DateTimeField(verbose_name='提交时间', auto_now=True)

    class Meta:
        verbose_name = '反馈信息'
        ordering = ['-created_time']


class BatchHouses(models.Model):
    houses = models.JSONField(verbose_name='房源')

    class Meta:
        verbose_name = '房源信息'


class MobileModel(models.Model):
    mobile = models.CharField(verbose_name='手机号', max_length=11)

    class Meta:
        verbose_name = '手机号'


class SubwayModel(models.Model):
    name = models.CharField(verbose_name='subway name', max_length=40)
    geo = gisModels.PointField(srid=4490, verbose_name='subway name', null=True)
    province = models.CharField(verbose_name='province', max_length=40, default='广州市')

    class Meta:
        verbose_name = 'subway'


class ReginModel(models.Model):
    name = models.CharField(verbose_name='subway name', max_length=40)
    geo = gisModels.PolygonField(srid=4490, verbose_name='subway name', null=True)
    province = models.CharField(verbose_name='province', max_length=40, default='广州市')

    class Meta:
        verbose_name = 'regin'


class HistoryRecord(models.Model):
    account = models.CharField(verbose_name='staff account', max_length=11)
    time = models.DateTimeField(verbose_name='glance time', auto_now=True)
    house_id = models.IntegerField(verbose_name='house id')


class StaffLocation(models.Model):
    account = models.CharField(verbose_name='staff account', max_length=11)
    time = models.DateTimeField(verbose_name='locate time', auto_now=True)
    latitude = models.FloatField(verbose_name='纬度')
    longitude = models.FloatField(verbose_name='经度')
    address_name = models.CharField(verbose_name='address name', max_length=64)


class OperatorRecord(models.Model):
    account = models.CharField(verbose_name='staff account', max_length=11)
    time = models.DateTimeField(verbose_name='locate time', auto_now=True)
    operator_name = models.CharField(verbose_name='operator name', max_length=10)
    house_id = models.IntegerField(verbose_name='house id', null=True)
    name = models.CharField(verbose_name='房屋名字', max_length=27, null=True)
    area = models.DecimalField(verbose_name='房屋面积(m^2)', max_digits=7, decimal_places=2, null=True)
    price = models.DecimalField(verbose_name='租金(元)', max_digits=7, decimal_places=2, null=True)
    mgmt_cost = models.DecimalField(verbose_name='管理费(元)', max_digits=7, decimal_places=2, default=0, null=True)
    floor = models.SmallIntegerField(verbose_name='房间楼层', null=True)
    house_total_floor = models.SmallIntegerField(verbose_name='房屋楼层', null=True)
    room_number = models.SmallIntegerField(verbose_name='房数', null=True)
    hall_number = models.SmallIntegerField(verbose_name='厅数', null=True)
    toilet_number = models.SmallIntegerField(verbose_name='卫数', null=True)
    probably_address = models.CharField(verbose_name='定位地址', max_length=60, null=True)
    region = models.CharField(verbose_name='行政区', max_length=2, default='TH', null=True)
    nextregion = models.CharField(verbose_name='next', max_length=20, blank=True, default='', null=True)
    detail_address = models.CharField(verbose_name='详细地址', null=True, blank=True, max_length=60)
    detail_house_no = models.CharField(verbose_name='门牌号', max_length=20, null=True)
    brightness = models.CharField(verbose_name='采光', max_length=1, default='2', null=True)
    deposit = models.CharField(verbose_name='押金类型', max_length=7, null=True)
    has_balcony = models.BooleanField(verbose_name='有无阳台', default=False, null=True)
    has_elevator = models.BooleanField(verbose_name='有无电梯', default=False, null=True)
    tariff_type = models.BooleanField(verbose_name='是否商业用电', default=False, null=True)
    can_feed_dog = models.BooleanField(verbose_name='可否养狗', default=False, null=True)
    house_type = models.CharField(verbose_name='房屋类型', max_length=1, default='2', null=True)
    is_share = models.BooleanField(verbose_name='是否合租', default=False, null=True)
    is_rented = models.BooleanField(verbose_name='是否已租', default=False, null=True)
    rent_deadline = models.DateTimeField(verbose_name='租约截止日期', null=True)
    uploader = models.CharField(verbose_name='上传者账号', max_length=11, null=True)
    operator = models.CharField(verbose_name='经手人电话', max_length=11, null=True)
    contact_phone = models.CharField(verbose_name='联系电话', max_length=11, null=True)
    latitude = models.FloatField(verbose_name='纬度', null=True)
    longitude = models.FloatField(verbose_name='经度', null=True)
    created_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True, null=True)
    updated_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, null=True)
    photo_url = ArrayField(models.CharField(verbose_name='图片资源链接', max_length=1024), blank=True, default=list, null=True)
    video_url = ArrayField(models.CharField(verbose_name='视频资源链接', max_length=1024), blank=True, default=list, null=True)
    is_delete = models.BooleanField(verbose_name='是否删除', default=False, null=True)
    postscript = models.CharField(verbose_name='附加信息', null=True, blank=True, max_length=512)
    geo = gisModels.PointField(verbose_name='geo', srid=4490, null=True)
    subways = ArrayField(models.CharField(verbose_name='subway', max_length=40), blank=True, default=list, null=True)
    tag = ArrayField(models.CharField(verbose_name='tag', max_length=40), blank=True, default=list, null=True)


class TurnoverRecord(models.Model):
    ORDER_STATUS = (
        ('0', '订单已创建'), ('1', '未支付'), ('2', '已支付'), ('3', '退款中'), ('4', '已退款'), ('5', '已关闭'), ('9', '旧订单')
    )
    name = models.CharField(verbose_name='名称', max_length=30, blank=True, null=True)
    organization = models.CharField(verbose_name='organization name', max_length=64, blank=True, null=True)
    address = models.CharField(verbose_name='address', max_length=64, blank=True, null=True)
    house_no = models.CharField(verbose_name='house number', max_length=10, blank=True, null=True)
    rent_fee = models.DecimalField(verbose_name='租金(元)', max_digits=7, decimal_places=2)
    rent_time = models.DateTimeField()
    update_time = models.DateTimeField(auto_now=True)
    account = models.CharField(verbose_name='staff phone', max_length=11)
    image_urls = ArrayField(models.CharField(verbose_name='图片资源链接', max_length=1024), blank=True, default=list,
                            null=True)
    # pay
    orderno = models.CharField(verbose_name=u'订单号', max_length=50, null=True)
    status = models.CharField(verbose_name='订单状态', choices=ORDER_STATUS, max_length=1, default='0')


class QRCodeURLModel(models.Model):
    mobile = models.CharField(verbose_name='owner phone', max_length=11)
    name = models.CharField(verbose_name='building name', max_length=64)
    house_list = ArrayField(models.IntegerField(verbose_name='house id'), blank=True, default=list)


class QRCodeView(models.Model):
    class Meta:
        managed = False
    mobile = models.CharField(verbose_name='owner phone', max_length=11)
    name = models.CharField(verbose_name='building name', max_length=64)
    house_id = models.CharField(verbose_name='building name', max_length=32)
    house_total_floor = models.SmallIntegerField(verbose_name='房屋楼层')
    floor = models.SmallIntegerField(verbose_name='房间楼层')
    price = models.DecimalField(verbose_name='租金(元)', max_digits=7, decimal_places=2)
    detail_house_no = models.CharField(verbose_name='门牌号', max_length=20)
    room_number = models.SmallIntegerField(verbose_name='房数')
    hall_number = models.SmallIntegerField(verbose_name='厅数')
    toilet_number = models.SmallIntegerField(verbose_name='卫数')
    photo_url = ArrayField(models.CharField(verbose_name='图片资源链接', max_length=1024), blank=True, default=list)


class QRCodeOthersView(models.Model):
    class Meta:
        managed = False
    mobile = models.CharField(verbose_name='owner phone', max_length=11)
    house_id = models.CharField(verbose_name='building name',max_length=32)
    house_total_floor = models.SmallIntegerField(verbose_name='房屋楼层')
    floor = models.SmallIntegerField(verbose_name='房间楼层')
    price = models.DecimalField(verbose_name='租金(元)', max_digits=7, decimal_places=2)
    detail_house_no = models.CharField(verbose_name='门牌号', max_length=20)
    room_number = models.SmallIntegerField(verbose_name='房数')
    hall_number = models.SmallIntegerField(verbose_name='厅数')
    toilet_number = models.SmallIntegerField(verbose_name='卫数')
    photo_url = ArrayField(models.CharField(verbose_name='图片资源链接', max_length=1024), blank=True, default=list)


class TurnoverOrderModel(models.Model):
    ORDER_STATUS = (
        ('0', '支付成功'), ('1', '转入退款'), ('2', '未支付'), ('3', '已关闭'), ('4', '已撤销'), ('5', '用户支付中'),
        ('6', '支付失败'), ('7', '订单已创建')
    )
    out_trade_no = models.CharField(verbose_name='订单号', max_length=32)
    status = models.CharField(verbose_name='订单状态', choices=ORDER_STATUS, max_length=1, default='7')
    created_date = models.DateTimeField(verbose_name='订单创建时间', auto_now_add=True)
    salesman_mobile = models.CharField(verbose_name='业务员手机号', max_length=11)
    turnover_id = models.ForeignKey(to=TurnoverRecord, verbose_name='turnover id', on_delete=models.DO_NOTHING)
    money = models.DecimalField(verbose_name='金额', max_digits=7, decimal_places=2)
    pay_url = models.CharField(verbose_name='支付链接', max_length=64, null=True)
    prepay_id = models.CharField(verbose_name='支付id', max_length=64, null=True)

    def __str__(self):
        return f'订单类型：员工流水, 订单号：{self.out_trade_no}, 订单状态：{self.status}'

    class Meta:
        verbose_name = '员工流水订单'


class PublicWhiteListModel(models.Model):

    mobile = models.CharField(verbose_name='owner phone', max_length=11, unique=True)