from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    GroupViewSet, AppUserViewSet, VenueViewSet, WallViewSet,
    HoldViewSet, RouteViewSet, SessionViewSet, HomePageView,
    GroupListView, GroupDetailView, GroupCreateView, GroupUpdateView, GroupDeleteView,
    VenueListView, VenueDetailView, VenueCreateView, VenueUpdateView, VenueDeleteView,
    AppUserListView, AppUserDetailView, AppUserCreateView, AppUserUpdateView, AppUserDeleteView,
    WallListView, WallDetailView, WallCreateView, WallUpdateView, WallDeleteView,
    HoldListView, HoldDetailView, HoldCreateView, HoldUpdateView, HoldDeleteView,
    RouteListView, RouteDetailView, RouteCreateView, RouteUpdateView, RouteDeleteView,
    CameraView, video_feed, capture_frame, PoseRealtimeView, PoseSkeletonView, PoseSkeletonDualView, PhoneCameraView, WebSocketRelayTestView,
    SessionListView, SessionDetailView, SessionDeleteView, SessionReplayView,
    SessionRecordingViewSet, WallCalibrationViewSet,
    TaskManagementView, trigger_fake_session_task, get_task_status,
    wall_upload_svg, wall_upload_image, wall_capture_camera_image,
    WallAnimationView, DemoView, api_upload_wall_image,
)
from .calibration.views import (
    wall_calibration_list, calibration_create, calibration_detail,
    calibration_activate, calibration_delete, api_detect_markers,
    api_upload_calibration_image,
    wall_svg_overlay, wall_calibrated_svg_data, calibration_manual_points
)

router = DefaultRouter()
# Keep existing router registrations
router.register(r'groups', GroupViewSet)
router.register(r'appusers', AppUserViewSet)
router.register(r'venues', VenueViewSet)
router.register(r'walls', WallViewSet)
router.register(r'holds', HoldViewSet)
router.register(r'routes', RouteViewSet)
router.register(r'sessions', SessionViewSet)
router.register(r'session-recordings', SessionRecordingViewSet)
router.register(r'wall-calibrations', WallCalibrationViewSet)

urlpatterns = [
    path('', HomePageView.as_view(), name='home'),  # New home page
    path('api/', include(router.urls)),  # Existing API urls, now prefixed
    path('api/capture_frame/', capture_frame, name='capture_frame'),
    path('api/upload-wall-image/', api_upload_wall_image, name='api_upload_wall_image'),

    # Group CRUD URLs
    path('groups/', GroupListView.as_view(), name='group_list'),
    path('groups/create/', GroupCreateView.as_view(), name='group_create'),
    path('groups/<uuid:pk>/', GroupDetailView.as_view(), name='group_detail'),
    path('groups/<uuid:pk>/update/', GroupUpdateView.as_view(), name='group_update'),
    path('groups/<uuid:pk>/delete/', GroupDeleteView.as_view(), name='group_delete'),

    # Venue CRUD URLs
    path('venues/', VenueListView.as_view(), name='venue_list'),
    path('venues/create/', VenueCreateView.as_view(), name='venue_create'),
    path('venues/<uuid:pk>/', VenueDetailView.as_view(), name='venue_detail'),
    path('venues/<uuid:pk>/update/', VenueUpdateView.as_view(), name='venue_update'),
    path('venues/<uuid:pk>/delete/', VenueDeleteView.as_view(), name='venue_delete'),

    # AppUser CRUD URLs
    path('appusers/', AppUserListView.as_view(), name='appuser_list'),
    path('appusers/create/', AppUserCreateView.as_view(), name='appuser_create'),
    path('appusers/<uuid:pk>/', AppUserDetailView.as_view(), name='appuser_detail'),
    path('appusers/<uuid:pk>/update/', AppUserUpdateView.as_view(), name='appuser_update'),
    path('appusers/<uuid:pk>/delete/', AppUserDeleteView.as_view(), name='appuser_delete'),

    # Wall CRUD URLs
    path('walls/', WallListView.as_view(), name='wall_list'),
    path('walls/create/', WallCreateView.as_view(), name='wall_create'),
    path('walls/<uuid:pk>/', WallDetailView.as_view(), name='wall_detail'),
    path('walls/<uuid:pk>/update/', WallUpdateView.as_view(), name='wall_update'),
    path('walls/<uuid:pk>/delete/', WallDeleteView.as_view(), name='wall_delete'),
    path('walls/<uuid:pk>/upload-svg/', wall_upload_svg, name='wall_upload_svg'),
    path('walls/<uuid:pk>/upload-image/', wall_upload_image, name='wall_upload_image'),
    path('walls/<uuid:pk>/capture-camera/', wall_capture_camera_image, name='wall_capture_camera_image'),
    path('walls/<uuid:pk>/animation/', WallAnimationView.as_view(), name='wall_animation'),
    
    # Calibration URLs
    path('calibration/wall/<int:wall_id>/', wall_calibration_list, name='wall_calibration_list'),
    path('calibration/wall/<int:wall_id>/create/', calibration_create, name='calibration_create'),
    path('calibration/wall/<int:wall_id>/manual-points/', calibration_manual_points, name='calibration_manual_points'),
    path('calibration/wall/<int:wall_id>/<int:calibration_id>/', calibration_detail, name='calibration_detail'),
    path('calibration/wall/<int:wall_id>/<int:calibration_id>/activate/', calibration_activate, name='calibration_activate'),
    path('calibration/wall/<int:wall_id>/<int:calibration_id>/delete/', calibration_delete, name='calibration_delete'),
    path('calibration/wall/<int:wall_id>/detect-markers/', api_detect_markers, name='api_detect_markers'),
    path('calibration/wall/<int:wall_id>/upload-calibration-image/', api_upload_calibration_image, name='api_upload_calibration_image'),
    path('calibration/wall/<int:wall_id>/svg-overlay/', wall_svg_overlay, name='wall_svg_overlay'),
    path('calibration/wall/<int:wall_id>/svg-data/', wall_calibrated_svg_data, name='wall_calibrated_svg_data'),

    # Hold CRUD URLs
    path('holds/', HoldListView.as_view(), name='hold_list'),
    path('holds/create/', HoldCreateView.as_view(), name='hold_create'),
    path('holds/<uuid:pk>/', HoldDetailView.as_view(), name='hold_detail'),
    path('holds/<uuid:pk>/update/', HoldUpdateView.as_view(), name='hold_update'),
    path('holds/<uuid:pk>/delete/', HoldDeleteView.as_view(), name='hold_delete'),

    # Route CRUD URLs
    path('routes/', RouteListView.as_view(), name='route_list'),
    path('routes/create/', RouteCreateView.as_view(), name='route_create'),
    path('routes/<uuid:pk>/', RouteDetailView.as_view(), name='route_detail'),
    path('routes/<uuid:pk>/update/', RouteUpdateView.as_view(), name='route_update'),
    path('routes/<uuid:pk>/delete/', RouteDeleteView.as_view(), name='route_delete'),


    # Camera Stream URL
    path('camera/', CameraView.as_view(), name='camera'),
    path('video_feed/', video_feed, name='video_feed'),
    path('pose/', PoseRealtimeView.as_view(), name='pose_realtime'),
    path('pose-skeleton/', PoseSkeletonView.as_view(), name='pose_skeleton'),
    path('pose-skeleton-dual/', PoseSkeletonDualView.as_view(), name='pose_skeleton_dual'),
    path('phone-camera/', PhoneCameraView.as_view(), name='phone_camera'),
    path('websocket-relay-test/', WebSocketRelayTestView.as_view(), name='websocket_relay_test'),
    
    # Session Recording URLs
    path('sessions/', SessionListView.as_view(), name='session_list'),
    path('sessions/<uuid:pk>/', SessionDetailView.as_view(), name='session_detail'),
    path('sessions/<uuid:pk>/delete/', SessionDeleteView.as_view(), name='session_delete'),
    path('sessions/<uuid:pk>/replay/', SessionReplayView.as_view(), name='session_replay'),
    
    # Task Management URLs
    path('tasks/', TaskManagementView.as_view(), name='task_management'),
    path('tasks/trigger-fake-session/', trigger_fake_session_task, name='trigger_fake_session_task'),
    path('tasks/status/<str:task_id>/', get_task_status, name='get_task_status'),
    
    # Demo Page
    path('demo/', DemoView.as_view(), name='demo'),
]
