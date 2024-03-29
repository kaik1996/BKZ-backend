"""
Django settings for Hotel project.

Generated by 'django-admin startproject' using Django 3.1.3.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""
import os
from datetime import datetime
from django.utils import timezone
from pathlib import Path
from alipay_interface.alipay_view import client_init

# Build paths inside the project like this: BASE_DIR / 'subdir'.

BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '*m=dac)a#4wi4l@6n8g6uix=0$(c%ahgd*nuf=&6v6le-$797_'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    # 'django.contrib.staticfiles',
    'drf_yasg',
    'django.contrib.gis',
    'django_filters',  # 注册django_filters
    'openunipay',
    'hotelapp',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'hotelapp.middle.DisableCSRFCheck'
]

ROOT_URLCONF = 'hotel.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'hotel.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    'default': {
        # 'ENGINE': 'django.db.backends.postgresql_psycopg2',
        # 'NAME': 'app',
        # 'USER': 'pengsiji',
        # 'PASSWORD': 'pengsiji',
        # 'HOST': 'localhost',

        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        #'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'app',
        'USER': 'pengsiji',
        'PASSWORD': 'pengsiji',
        'HOST': 'localhost',
        'PORT': '5432'
    }
}
# DATABASES = {
#     'default': {
#         # 'ENGINE': 'django.contrib.gis.db.backends.postgis',
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'app',
#         'USER': 'pengsiji',
#         'PASSWORD': 'pengsiji',
#         'HOST': '106.52.14.160',
#         'PORT': '5432'
#     },
# }


# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'zh-Hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_L10N = True

# USE_TZ为False,TIME_ZONE设置为其它时区
USE_TZ = False

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATIC_URL = '/static/'

# MEDIA_ROOT = os.path.join(BASE_DIR, 'Media')

# 配置Redis为Django缓存
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://106.52.14.160:6379",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
            "PASSWORD": "pengsiji"
        }
    }
}

SESSION_ENGINE = 'redis_sessions.session'
SESSION_REDIS = {
    'host': '106.52.14.160',
    'port': 6379,
    'db': 0,
    'password': 'pengsiji',
    'prefix': 'session',
    'socket_timeout': 10
}

# 设置session失效时间,单位为秒
SESSION_COOKIE_AGE = 60*60*24*7

# GDAL_LIBRARY_PATH='C:/ProgramData/Anaconda3/envs/djangoProject/Lib/site-packages/osgeo/gdal301.dll'
# GEOS_LIBRARY_PATH='C:/ProgramData/Anaconda3/envs/djangoProject/Lib/site-packages/osgeo/geos_c.dll'

# 配置log
if not os.path.exists('log_file'):
    os.makedirs('log_file', 776)
if not os.path.exists('log_file/default'):
    os.makedirs('log_file/default', 776)
if not os.path.exists('log_file/info'):
    os.makedirs('log_file/info', 776)
if not os.path.exists('log_file/error'):
    os.makedirs('log_file/error', 776)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(levelname)s - %(message)s'
        },
        # 日志格式
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        }
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(os.path.abspath(BASE_DIR), 'log_file/default/default.log'),
            # 'maxBytes': 1024 * 1024 * 5,  # 文件大小
            'when': 'MIDNIGHT',
            'interval': 1,
            'backupCount': 5,  # 备份数
            'formatter': 'standard',  # 输出格式
            'encoding': 'utf-8',  # 设置默认编码，否则打印出来汉字乱码
        },
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
        'error': {
            'level': 'ERROR',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(os.path.abspath(BASE_DIR), 'log_file/error/error.log'),
            # 'maxBytes': 1024*1024*20,
            'when': 'MIDNIGHT',
            'interval': 1,
            'backupCount': 5,
            'formatter': 'standard',
            'encoding': 'utf-8',
        },
        'info': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(os.path.abspath(BASE_DIR), 'log_file/info/info.log'),
            # 'maxBytes': 1024*1024*20,
            'when': 'MIDNIGHT',
            'interval': 1,
            'backupCount': 5,
            'formatter': 'standard',
            'encoding': 'utf-8',

        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True
        },
        'log': {
            'handlers': ['error', 'info', 'console'],
            'level': 'INFO',
            'propagate': True
        }
    }
}

# 支付宝初始化
# Alipay_Client = client_init()

# 定时任务配置
# CRONJOBS = [
#     ('* * * * *', 'FUNCTION')
# ]

#####支付宝支付配置
ALIPAY = {
    'partner':'XXX', #支付宝partner ID
    'seller_id':'XXX', #收款方支付宝账号如 pan.weifeng@live.cn
    'notify_url':'https://XXX/notify/alipay/', #支付宝异步通知接收URL
    'ali_public_key_pem':'PATH to PEM File', #支付宝公钥的PEM文件路径,在支付宝合作伙伴密钥管理中查看(需要使用合作伙伴支付宝公钥)。如何查看，请参看支付宝文档
    'rsa_private_key_pem':'PATH to PEM File', #您自己的支付宝账户的私钥的PEM文件路径。如何设置，请参看支付宝文档
    'rsa_public_key_pem':'PATH to PEM File', #您自己的支付宝账户的公钥的PEM文件路径。如何设置，请参看支付宝文档
}
#####微信支付配置
WEIXIN = {
    'app_id':'wx1e9705c9750ee114', #微信APPID
    'app_seckey':'XXX', #微信APP Sec Key
    'mch_id':'1608112493', #微信商户ID
    'mch_seckey':'BangKeZuYuanGongZhiFu20217777777', #微信商户seckey
    'mch_notify_url':'https://zulaizuqu.cool/hotelapp/notify/weixin/', #微信支付异步通知接收URL
    'clientIp':'61.140.220.32', #扫码支付时，会使用这个IP地址发送给微信API, 请设置为您服务器的IP
}