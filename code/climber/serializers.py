from rest_framework import serializers
from .models import Group, AppUser, Venue, Wall, Hold, Route, Session, SessionRecording, SessionFrame, WallCalibration

class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'

class AppUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppUser
        fields = '__all__'

class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = '__all__'

class WallSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wall
        fields = '__all__'

class HoldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hold
        fields = '__all__'

class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = '__all__'


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = '__all__'

class SessionRecordingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionRecording
        fields = ['uuid', 'name', 'description', 'created', 'duration',
                 'frame_count', 'status', 'user', 'session']
        read_only_fields = ['uuid', 'created', 'user']

class SessionFrameSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionFrame
        fields = ['timestamp', 'frame_number', 'pose_data', 'image_path']

class WallCalibrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WallCalibration
        fields = '__all__'
