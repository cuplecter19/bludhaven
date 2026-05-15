# leitner/urls.py
from django.urls import path
from . import views

app_name = 'leitner'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('upload/', views.upload_words, name='upload_words'),
    path('submit/', views.submit_answer, name='submit_answer'),
    path('words/', views.word_list, name='word_list'),
    path('log/', views.review_log, name='review_log'),
]
