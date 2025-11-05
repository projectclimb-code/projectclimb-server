from django.urls import re_path
from .consumers import PoseConsumer, TestPoseConsumer, SessionReplayConsumer, SessionConsumer, RelayConsumer, TransformedPoseConsumer

websocket_urlpatterns = [
    re_path(r'ws/pose/$', PoseConsumer.as_asgi()),
    re_path(r'ws/transformed_pose/$', TransformedPoseConsumer.as_asgi()),
    re_path(r'ws/test_pose/$', TestPoseConsumer.as_asgi()),
    re_path(r'ws/session/(?P<session_id>[^/]+)/$', SessionReplayConsumer.as_asgi()),
    re_path(r'ws/session-live/$', SessionConsumer.as_asgi()),
    re_path(r'ws/holds/$', RelayConsumer.as_asgi()),
]