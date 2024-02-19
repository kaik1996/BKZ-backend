from django.conf.urls import url, include
from rest_framework.routers import DefaultRouter
from . import views
from openunipay.api.views_weixin import process_qr_notify, process_notify

app_name = 'hotel'

router = DefaultRouter()
# 房东视图
router.register(r'landlord/stat', views.LandlordStat, basename='stat-landlord')
router.register(r'landlord/user', views.LandlordUserView, basename='page-landlord')
router.register(r'landlord/house', views.LandlordCRUDView, basename='crud-landlord')
router.register(r'landlord/house_address', views.HouseAddress, basename='house-addresses-landlord')
router.register(r'landlord/house_template', views.HouseTemplateView, basename='crud-house-template')
router.register(r'landlord/house_batch', views.BatchHousesView, basename='batch-crud-landlord')
router.register(r'landlord/feedback', views.FeedbackView, basename='feeback-landlord')
router.register(r'landlord/get_wx_session', views.LandlordWeChatSessionView, basename='get-wx-session-landlord')
router.register(r'landlord/wx_login', views.LandlordWeChatLoginView, basename='wx-login-landlord')
router.register(r'landlord/refresh_token', views.LandlordRefreshTokenView, basename='refresh-token-landlord')
router.register(r'landlord/code_send', views.LandlordCodeSendView, basename='code-send-landlord')
router.register(r'landlord/code_check', views.LandlordCodeCheckView, basename='code-check-landlord')
router.register(r'landlord/bulletin_board', views.LandlordBulletinBoardView, basename='bulletin-board-landlord')
router.register(r'landlord/qrcode', views.QRCodeURLView, basename='crud-qrcode-landlord')
router.register(r'landlord/get_qrcode_url', views.GetQRCodeURL, basename='get-qrcode-url-landlord')
router.register(r'landlord/get_house_options', views.LandlordHouseOptions, basename='get-house-options-landlord')

# 中介视图
router.register(r'agency/user', views.AgencyUserView, basename='page-agency')
router.register(r'agency/house', views.AgencyCRUDView, basename='crud-agency')
router.register(r'agency/tips', views.SearchTipsView, basename='tips-agency')
router.register(r'agency/find_subways', views.SearchSubwayView, basename='find-subways-agency')
router.register(r'agency/get_wx_session', views.AgencyWeChatSessionView, basename='get-wx-session-agency')
router.register(r'agency/wx_login', views.AgencyWeChatLoginView, basename='wx-login-agency')
router.register(r'agency/favorites', views.FavoritesView, basename='favorites-agency')
router.register(r'agency/code_send', views.AgencyCodeSendView, basename='code-send-agency')
router.register(r'agency/code_check', views.AgencyCodeCheckView, basename='code-check-agency')
router.register(r'agency/refresh_token', views.AgencyRefreshTokenView, basename='refresh-token-agency')
router.register(r'agency/bulletin_board', views.AgencyBulletinBoardView, basename='bulletin-board-agency')
router.register(r'agency/feedback', views.FeedbackView, basename='feedback-agency')
# router.register(r'agency/wxpayresult', views.WxNotifyURLView, basename='WxPay-result')

# 管理员视图
router.register(r'superuser/house', views.SuperUserCRUDView, basename='crud-superuser')
# router.register(r'superuser/user', views.SuperUserView, basename='page-superuser')
router.register(r'superuser/get_wx_session', views.SuperUserWeChatSessionView, basename='get-wx-session-superuser')
router.register(r'superuser/wx_login', views.SuperUserWeChatLoginView, basename='wx-login-superuser')
router.register(r'superuser/stat', views.SuperUserStat, basename='stat-superuser')
router.register(r'superuser/checkLandlord', views.CheckLandlord, basename='check-landlord-superuser')
router.register(r'superuser/house_template', views.HouseTemplateView, basename='crud-house-template')
router.register(r'superuser/house_batch', views.SuperUserBatchHousesView, basename='batch-crud-superuser')
router.register(r'superuser/feedback', views.FeedbackView, basename='feeback-superuser')
router.register(r'superuser/get_wx_session', views.SuperUserWeChatSessionView, basename='get-wx-session-superuser')
router.register(r'superuser/wx_login', views.SuperUserWeChatLoginView, basename='wx-login-superuser')
router.register(r'superuser/refresh_token', views.SuperUserRefreshTokenView, basename='refresh-token-superuser')
router.register(r'superuser/code_send', views.SuperUserCodeSendView, basename='code-send-superuser')
router.register(r'superuser/code_check', views.SuperUserCodeCheckView, basename='code-check-superuser')
router.register(r'superuser/bulletin_board', views.SuperUserBulletinBoardView, basename='bulletin-board-superuser')
router.register(r'superuser/history_record', views.HistoryRecordView, basename='history-record-superuser')
router.register(r'superuser/staff_location', views.StaffLocationView, basename='staff-location-superuser')
router.register(r'superuser/operator_record', views.OperatorRecordView, basename='operator-record-superuser')
router.register(r'superuser/turnover_record', views.TurnoverRecordView, basename='turnover-record-superuser')
router.register(r'superuser/turnover_stat', views.TurnoverStatView, basename='turnover-record-superuser')
router.register(r'superuser/turnover_wx_pay', views.TurnoverPayView, basename='turnover-pay')
# router.register(r'purchase', views.AlipayView, basename='alipay-purchase')
# router.register(r'contract', views.ContractView)

router.register(r'pubilc/get_houses', views.QRCodeQueryView, basename='qr-code-query-pubilc')
router.register(r'pubilc/get_other_houses', views.QRCodeQueryView, basename='qr-code-query-others-pubilc')
router.register(r'pubilc/get_house', views.PublicGetHouseView, basename='get-house-pubilc')
router.register(r'pubilc/other_app_get_house', views.OtherAppGetHouseView, basename='other-app-get-house-pubilc')
router.register(r'pubilc/other_app_get_house_address', views.OtherAppGetHouseAddress, basename='other-app-get-house-address-pubilc')

# router.register(r'public/turnover_wx_notify', views.TurnoverPayNotifyView.as_view(), basename='turnover-wx-notify-public')

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^find_subway/', views.find_closest_subway),
    url(r'turnover_wx_notify', views.TurnoverPayNotifyView.as_view()),
    url(r'turnover_wx_query', views.TurnoverPayQuery.as_view()),
    # url(r'turnover_wx_pay_url', views.TurnoverPayUrl.as_view()),
    url(r'turnover_wx_pay_mini', views.TurnoverPayMini.as_view()),
    url(r'turnover_wx_pay_qrcode', views.TurnoverPayQrcode.as_view()),
    url(r'^notify/weixin/$', process_notify)
]
