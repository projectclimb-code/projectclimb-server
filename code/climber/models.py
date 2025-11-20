from django.db import models
from django.contrib.auth.models import User
import uuid

class BaseModel(models.Model):
    # Base model for all other models to inherit from
    uuid = models.UUIDField(default = uuid.uuid4, editable = False)
    slug = models.SlugField(null=True, blank=True)
    deleted = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta: 
        abstract = True


class Group(BaseModel):
    name = models.CharField(max_length=500)

    def __str__(self):
        return self.name



class AppUser(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    def __str__(self):
        return self.user.username



class Venue(BaseModel):
    name = models.CharField(max_length=500)
    description = models.TextField()

    def __str__(self):
        return self.name



class Wall(BaseModel):
    name = models.CharField(max_length=500)
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE)
    svg_file = models.FileField(upload_to='svg_files/', null=True, blank=True)
    wall_image = models.ImageField(upload_to='wall_images/', null=True, blank=True, help_text="Wall image for calibration and overlay display")
    width_mm = models.FloatField(default=2500.0, help_text="Wall width in millimeters")
    height_mm = models.FloatField(default=3330.0, help_text="Wall height in millimeters")
    
    def __str__(self):
        return self.name
    
    @property
    def active_calibration(self):
        """Get the most recent active calibration for this wall"""
        return self.calibrations.filter(is_active=True).order_by('-created').first()



class Hold(BaseModel):
    name = models.CharField(max_length=500)
    wall = models.ForeignKey(Wall, on_delete=models.CASCADE)
    coords = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name



class Route(BaseModel):
    name = models.CharField(max_length=500)
    data = models.JSONField(default=dict, blank=True, help_text="Route data including holds and sequence")

    def __str__(self):
        return self.name


class Session(BaseModel):
    """Represents a climbing session (a single climbing attempt)."""
    route = models.ForeignKey(Route, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('started', 'Started'),
            ('completed', 'Completed'),
            ('abandoned', 'Abandoned'),
        ],
        default='started'
    )
    climb_data = models.JSONField(default=dict, blank=True)  # Store climb progress data
    
    def __str__(self):
        return f"Session {self.uuid} - {self.user.username} ({self.status})"


class SessionRecording(BaseModel):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, null=True, blank=True, related_name='recordings')
    duration = models.IntegerField(default=0)  # Duration in seconds
    frame_count = models.IntegerField(default=0)
    video_file_path = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('recording', 'Recording'),
            ('completed', 'Completed'),
            ('processing', 'Processing'),
        ],
        default='recording'
    )
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"


class SessionFrame(models.Model):
    session = models.ForeignKey(SessionRecording, on_delete=models.CASCADE, related_name='frames')
    timestamp = models.FloatField()  # Timestamp in seconds from start
    frame_number = models.IntegerField()
    pose_data = models.JSONField()  # Store pose landmarks as JSON
    image_path = models.CharField(max_length=500, blank=True, null=True)
    
    class Meta:
        ordering = ['frame_number']
        indexes = [
            models.Index(fields=['session', 'frame_number']),
        ]
    
    def __str__(self):
        return f"Frame {self.frame_number} of {self.session.name}"


class WallCalibration(BaseModel):
    """Stores calibration data for a climbing wall"""
    wall = models.ForeignKey(Wall, on_delete=models.CASCADE, related_name='calibrations')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Calibration type
    calibration_type = models.CharField(
        max_length=20,
        choices=[
            ('aruco', 'ArUco Markers'),
            ('manual_points', 'Manual Point Calibration'),
        ],
        default='aruco',
        help_text="Type of calibration used"
    )
    
    # Camera calibration parameters
    camera_matrix = models.JSONField(default=dict, help_text="3x3 camera intrinsic matrix")
    distortion_coeffs = models.JSONField(default=list, help_text="Camera distortion coefficients")
    
    # Perspective transformation parameters
    perspective_transform = models.JSONField(default=dict, help_text="3x3 perspective transformation matrix")
    
    # ArUco marker data
    aruco_markers = models.JSONField(default=dict, help_text="ArUco marker positions and IDs")
    aruco_dictionary = models.CharField(max_length=50, default='DICT_4X4_50')
    marker_size_meters = models.FloatField(default=0.1, help_text="Physical size of ArUco markers in meters")
    
    # Manual calibration data
    manual_image_points = models.JSONField(
        default=list,
        blank=True,
        help_text="List of manually selected image points [(x1,y1), (x2,y2), ...]"
    )
    manual_svg_points = models.JSONField(
        default=list,
        blank=True,
        help_text="List of corresponding SVG points [(x1,y1), (x2,y2), ...]"
    )
    
    # Calibration metadata
    calibration_image = models.ImageField(upload_to='calibration_images/', null=True, blank=True)
    reprojection_error = models.FloatField(null=True, blank=True, help_text="Calibration accuracy measure")
    overlay_image = models.ImageField(upload_to='calibration_overlays/', null=True, blank=True, help_text="Generated image with SVG overlay")
    
    # Hand landmark extension parameters
    hand_extension_percent = models.FloatField(
        default=20.0,
        help_text="Percentage to extend hand landmarks beyond the palm (0-100)"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.wall.name} - {self.name}"
    
    class Meta:
        ordering = ['-created']
 

class CeleryTask(BaseModel):
    """Track Celery tasks in the database for monitoring running tasks."""
    task_id = models.CharField(max_length=255, unique=True)
    task_name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, default='PENDING')
    created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.task_name} ({self.task_id})"


