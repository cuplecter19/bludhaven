from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.shop, name='shop'),
    path('buy/<int:item_id>/', views.buy_item, name='buy_item'),
    path('spend_credit/', views.spend_credit, name='spend_credit'),
    path('add_item/', views.add_item, name='add_item'),
    path('delete_item/<int:item_id>/', views.delete_item, name='delete_item'),
]