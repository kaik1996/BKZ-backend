from django_filters import rest_framework as filters
from .models import Houses, TurnoverRecord


class HousesFilter(filters.FilterSet):
    """
    自定义房屋资源过滤器
    """
    area__gt = filters.NumberFilter(field_name='area', lookup_expr='gt')
    area__lt = filters.NumberFilter(field_name='area', lookup_expr='lt')

    price__gt = filters.NumberFilter(field_name='price', lookup_expr='gt')
    price__lt = filters.NumberFilter(field_name='price', lookup_expr='lt')
    price__gte = filters.NumberFilter(field_name='price', lookup_expr='gte')
    price__lte = filters.NumberFilter(field_name='price', lookup_expr='lte')

    floor__gt = filters.NumberFilter(field_name='floor', lookup_expr='gt')
    floor__lt = filters.NumberFilter(field_name='floor', lookup_expr='lt')
    floor__gte = filters.NumberFilter(field_name='floor', lookup_expr='gte')
    floor__lte = filters.NumberFilter(field_name='floor', lookup_expr='lte')

    room_number__gte = filters.NumberFilter(field_name='room_number', lookup_expr='gte')
    hall_number__gte = filters.NumberFilter(field_name='hall_number', lookup_expr='gte')

    class Meta:
        model = Houses
        fields = {
            'name','area', 'price', 'probably_address', 'detail_address', 'has_balcony', 'has_elevator', 'house_type',
            'room_number', 'hall_number', 'toilet_number', 'is_rented', 'is_share', 'floor', 'nextregion', 'brightness',
            'can_feed_dog'
        }


class TurnOverFilter(filters.FilterSet):
    """
    自定义过滤器
    """
    rent_fee__gte = filters.NumberFilter(field_name='rent_fee', lookup_expr='gte')
    rent_fee__lte = filters.NumberFilter(field_name='rent_fee', lookup_expr='lte')

    rent_time__gte = filters.DateTimeFilter(field_name='rent_time', lookup_expr='gte')
    rent_time__lte = filters.DateTimeFilter(field_name='rent_time', lookup_expr='lte')

    class Meta:
        model = TurnoverRecord
        fields = {
            'rent_fee','rent_time'
        }
