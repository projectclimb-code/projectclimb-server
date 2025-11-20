from django.contrib import admin
from .models import (
    Group, AppUser, Venue, Wall, Hold, Route,
    Session, SessionRecording, SessionFrame, WallCalibration, CeleryTask
)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'created', 'updated']
    search_fields = ['name']
    ordering = ['name']


@admin.register(AppUser)
class AppUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'created', 'updated']
    list_filter = ['group', 'created']
    search_fields = ['user__username', 'user__email', 'group__name']
    ordering = ['user__username']


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ['name', 'created', 'updated']
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(Wall)
class WallAdmin(admin.ModelAdmin):
    list_display = ['name', 'venue', 'width_mm', 'height_mm', 'created', 'updated']
    list_filter = ['venue', 'created']
    search_fields = ['name', 'venue__name']
    ordering = ['venue', 'name']
    readonly_fields = ['uuid', 'slug', 'created', 'updated']


@admin.register(Hold)
class HoldAdmin(admin.ModelAdmin):
    list_display = ['name', 'wall', 'created', 'updated']
    list_filter = ['wall', 'created']
    search_fields = ['name', 'wall__name']
    ordering = ['wall', 'name']
    readonly_fields = ['uuid', 'slug', 'created', 'updated']


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ['name', 'created', 'updated']
    search_fields = ['name']
    ordering = ['name']
    readonly_fields = ['uuid', 'slug', 'created', 'updated']
    fieldsets = (
        (None, {
            'fields': ('name', 'data')
        }),
        ('Metadata', {
            'fields': ('uuid', 'slug', 'created', 'updated'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['uuid', 'user', 'route', 'status', 'start_time', 'end_time']
    list_filter = ['status', 'start_time', 'user']
    search_fields = ['user__username', 'route__name']
    ordering = ['-start_time']
    readonly_fields = ['uuid', 'slug', 'created', 'updated']
    date_hierarchy = 'start_time'


class SessionFrameInline(admin.TabularInline):
    model = SessionFrame
    extra = 0
    readonly_fields = ['timestamp', 'frame_number', 'pose_data']
    fields = ['frame_number', 'timestamp']
    can_delete = False


@admin.register(SessionRecording)
class SessionRecordingAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'session', 'status', 'duration', 'frame_count', 'created']
    list_filter = ['status', 'created', 'user']
    search_fields = ['name', 'user__username', 'description']
    ordering = ['-created']
    readonly_fields = ['uuid', 'slug', 'created', 'updated']
    inlines = [SessionFrameInline]


@admin.register(SessionFrame)
class SessionFrameAdmin(admin.ModelAdmin):
    list_display = ['session', 'frame_number', 'timestamp']
    list_filter = ['session']
    search_fields = ['session__name']
    ordering = ['session', 'frame_number']
    readonly_fields = ['pose_data']


@admin.register(WallCalibration)
class WallCalibrationAdmin(admin.ModelAdmin):
    list_display = ['wall', 'name', 'calibration_type', 'is_active', 'reprojection_error', 'created']
    list_filter = ['calibration_type', 'is_active', 'created', 'wall']
    search_fields = ['wall__name', 'name', 'description']
    ordering = ['-created']
    readonly_fields = ['uuid', 'slug', 'created', 'updated']
    fieldsets = (
        (None, {
            'fields': ('wall', 'name', 'description', 'calibration_type', 'is_active')
        }),
        ('Hand Landmark Extension', {
            'fields': ('hand_extension_percent',),
            'description': 'Configure how far to extend hand landmarks beyond the palm for pose transformation.'
        }),
        ('Camera Calibration', {
            'fields': ('camera_matrix', 'distortion_coeffs'),
            'classes': ('collapse',)
        }),
        ('Perspective Transformation', {
            'fields': ('perspective_transform',),
            'classes': ('collapse',)
        }),
        ('ArUco Calibration', {
            'fields': ('aruco_markers', 'aruco_dictionary', 'marker_size_meters'),
            'classes': ('collapse',)
        }),
        ('Manual Calibration', {
            'fields': ('manual_image_points', 'manual_svg_points'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('calibration_image', 'reprojection_error'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CeleryTask)
class CeleryTaskAdmin(admin.ModelAdmin):
    list_display = ['task_id', 'task_name', 'status', 'created', 'updated']
    list_filter = ['status', 'task_name', 'created']
    search_fields = ['task_id', 'task_name']
    ordering = ['-created']
    readonly_fields = ['task_id', 'created', 'updated']
    
    fieldsets = (
        (None, {
            'fields': ('task_name', 'status')
        }),
        ('Task Information', {
            'fields': ('task_id',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
