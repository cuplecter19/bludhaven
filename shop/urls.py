from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.shop, name='shop'),
    path('buy/<int:item_id>/', views.buy_item, name='buy_item'),
    path('add_item/', views.add_item, name='add_item'),
    path('delete_item/<int:item_id>/', views.delete_item, name='delete_item'),
    path('update_default_review_image/', views.update_default_review_image, name='update_default_review_image'),
    path('reviews/add/', views.add_review, name='add_review'),
    path('reviews/delete/<int:review_id>/', views.delete_review, name='delete_review'),
]