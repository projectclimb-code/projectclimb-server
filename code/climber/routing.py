from django.urls import re_path
from .consumers import PoseConsumer, TestPoseConsumer

websocket_urlpatterns = [
    re_path(r'ws/pose/$', PoseConsumer.as_asgi()),
    re_path(r'ws/test_pose/$', TestPoseConsumer.as_asgi()),
]