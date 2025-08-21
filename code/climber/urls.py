from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    GroupViewSet, AppUserViewSet, VenueViewSet, WallViewSet,
    HoldViewSet, RouteViewSet, RoutePointViewSet, HomePageView,
    GroupListView, GroupDetailView, GroupCreateView, GroupUpdateView, GroupDeleteView,
    VenueListView, VenueDetailView, VenueCreateView, VenueUpdateView, VenueDeleteView,
    AppUserListView, AppUserDetailView, AppUserCreateView, AppUserUpdateView, AppUserDeleteView,
    WallListView, WallDetailView, WallCreateView, WallUpdateView, WallDeleteView,
    HoldListView, HoldDetailView, HoldCreateView, HoldUpdateView, HoldDeleteView,
    RouteListView, RouteDetailView, RouteCreateView, RouteUpdateView, RouteDeleteView,
    RoutePointListView, RoutePointDetailView, RoutePointCreateView, RoutePointUpdateView, RoutePointDeleteView, # Add RoutePoint CRUD views
    CameraView, video_feed, capture_frame, PoseRealtimeView,
)

router = DefaultRouter()
# Keep existing router registrations
router.register(r'groups', GroupViewSet)
router.register(r'appusers', AppUserViewSet)
router.register(r'venues', VenueViewSet)
router.register(r'walls', WallViewSet)
router.register(r'holds', HoldViewSet)
router.register(r'routes', RouteViewSet)
router.register(r'routepoints', RoutePointViewSet)

urlpatterns = [
    path('', HomePageView.as_view(), name='home'),  # New home page
    path('api/', include(router.urls)),  # Existing API urls, now prefixed
    path('api/capture_frame/', capture_frame, name='capture_frame'),

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

    # RoutePoint CRUD URLs
    path('routepoints/', RoutePointListView.as_view(), name='routepoint_list'),
    path('routepoints/create/', RoutePointCreateView.as_view(), name='routepoint_create'),
    path('routepoints/<int:pk>/', RoutePointDetailView.as_view(), name='routepoint_detail'), # Note: int:pk
    path('routepoints/<int:pk>/update/', RoutePointUpdateView.as_view(), name='routepoint_update'), # Note: int:pk
    path('routepoints/<int:pk>/delete/', RoutePointDeleteView.as_view(), name='routepoint_delete'), # Note: int:pk

    # Camera Stream URL
    path('camera/', CameraView.as_view(), name='camera'),
    path('video_feed/', video_feed, name='video_feed'),
    path('pose/', PoseRealtimeView.as_view(), name='pose_realtime'),
]
