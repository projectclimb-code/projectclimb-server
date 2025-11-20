from django.shortcuts import render, get_object_or_404, redirect # Ensure get_object_or_404 is imported
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import HttpResponse, Http404, JsonResponse # Added for HTMX responses and Http404
from django.utils.translation import gettext_lazy as _ # For Http404 message
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Group, AppUser, Venue, Wall, Hold, Route, Session, SessionRecording, SessionFrame, WallCalibration, CeleryTask # Import all models
# Ensure User is imported if AppUser.user is a ForeignKey to django.contrib.auth.models.User
from django.contrib.auth.models import User
from django.conf import settings

from .tasks import send_fake_session_data_task, websocket_pose_session_tracker_task

from revproxy.views import ProxyView

from .serializers import (
    GroupSerializer, AppUserSerializer, VenueSerializer, WallSerializer,
    HoldSerializer, RouteSerializer, SessionSerializer,
    SessionRecordingSerializer, SessionFrameSerializer, WallCalibrationSerializer
)

# DRF ViewSets
class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer

class AppUserViewSet(viewsets.ModelViewSet):
    queryset = AppUser.objects.all()
    serializer_class = AppUserSerializer

class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.all()
    serializer_class = VenueSerializer

class WallViewSet(viewsets.ModelViewSet):
    queryset = Wall.objects.all()
    serializer_class = WallSerializer

class HoldViewSet(viewsets.ModelViewSet):
    queryset = Hold.objects.all()
    serializer_class = HoldSerializer

class RouteViewSet(viewsets.ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer


class SessionViewSet(viewsets.ModelViewSet):
    queryset = Session.objects.all()
    serializer_class = SessionSerializer
    
    def get_queryset(self):
        # Filter by current user, handle anonymous users
        if self.request.user.is_anonymous:
            return Session.objects.none()
        return Session.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        # Handle anonymous users - don't allow creation
        if not self.request.user.is_anonymous:
            serializer.save(user=self.request.user)

class PhoneCameraView(TemplateView):
    """View for phone camera page."""
    template_name = 'climber/phone_camera.html'

class WebSocketRelayTestView(TemplateView):
    """View for WebSocket relay test page."""
    template_name = 'climber/websocket_relay_test.html'

class SessionRecordingViewSet(viewsets.ModelViewSet):
    queryset = SessionRecording.objects.all()
    serializer_class = SessionRecordingSerializer
    
    def get_queryset(self):
        # Filter by current user, handle anonymous users
        if self.request.user.is_anonymous:
            return SessionRecording.objects.none()
        return SessionRecording.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        # Handle anonymous users - don't allow creation
        if not self.request.user.is_anonymous:
            serializer.save(user=self.request.user)

class WallCalibrationViewSet(viewsets.ModelViewSet):
    queryset = WallCalibration.objects.all()
    serializer_class = WallCalibrationSerializer

# Template Views
class HomePageView(TemplateView):
    template_name = "climber/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['group_count'] = Group.objects.count()
        context['appuser_count'] = AppUser.objects.count()
        context['venue_count'] = Venue.objects.count()
        context['wall_count'] = Wall.objects.count()
        context['hold_count'] = Hold.objects.count()
        context['route_count'] = Route.objects.count()
        return context

class UUIDLookupMixin:
    """Mixin to look up objects by UUID from the URL."""
    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        
        pk_from_url = self.kwargs.get('pk')

        if pk_from_url is None:
            raise AttributeError(
                f"Generic detail view {self.__class__.__name__} must be called with "
                f"an object pk in the URLconf."
            )
        
        queryset = queryset.filter(uuid=pk_from_url)
        
        try:
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

# Group CRUD Views
class GroupListView(ListView):
    model = Group
    template_name = 'climber/group_list.html'
    context_object_name = 'groups'

class GroupDetailView(UUIDLookupMixin, DetailView):
    model = Group
    template_name = 'climber/group_detail.html'
    context_object_name = 'group'

class GroupCreateView(CreateView):
    model = Group
    template_name = 'climber/group_form.html'
    fields = ['name']
    success_url = reverse_lazy('group_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class GroupUpdateView(UUIDLookupMixin, UpdateView):
    model = Group
    template_name = 'climber/group_form.html'
    fields = ['name']
    success_url = reverse_lazy('group_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class GroupDeleteView(UUIDLookupMixin, DeleteView):
    model = Group
    template_name = 'climber/group_confirm_delete.html'
    success_url = reverse_lazy('group_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object.delete()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

# Venue CRUD Views
class VenueListView(ListView):
    model = Venue
    template_name = 'climber/venue_list.html'
    context_object_name = 'venues'

class VenueDetailView(UUIDLookupMixin, DetailView):
    model = Venue
    template_name = 'climber/venue_detail.html'
    context_object_name = 'venue'

class VenueCreateView(CreateView):
    model = Venue
    template_name = 'climber/venue_form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('venue_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class VenueUpdateView(UUIDLookupMixin, UpdateView):
    model = Venue
    template_name = 'climber/venue_form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('venue_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class VenueDeleteView(UUIDLookupMixin, DeleteView):
    model = Venue
    template_name = 'climber/venue_confirm_delete.html'
    success_url = reverse_lazy('venue_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object.delete()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

# AppUser CRUD Views
class AppUserListView(ListView):
    model = AppUser
    template_name = 'climber/appuser_list.html'
    context_object_name = 'appusers'

class AppUserDetailView(UUIDLookupMixin, DetailView):
    model = AppUser
    template_name = 'climber/appuser_detail.html'
    context_object_name = 'appuser'

class AppUserCreateView(CreateView):
    model = AppUser
    template_name = 'climber/appuser_form.html'
    fields = ['user', 'group'] # Fields for AppUser
    success_url = reverse_lazy('appuser_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class AppUserUpdateView(UUIDLookupMixin, UpdateView):
    model = AppUser
    template_name = 'climber/appuser_form.html'
    fields = ['user', 'group']
    success_url = reverse_lazy('appuser_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class AppUserDeleteView(UUIDLookupMixin, DeleteView):
    model = AppUser
    template_name = 'climber/appuser_confirm_delete.html'
    success_url = reverse_lazy('appuser_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object.delete()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

# Wall CRUD Views
class WallListView(ListView):
    model = Wall
    template_name = 'climber/wall_list.html'
    context_object_name = 'walls'

class WallDetailView(UUIDLookupMixin, DetailView):
    model = Wall
    template_name = 'climber/wall_detail.html'
    context_object_name = 'wall'

class WallCreateView(CreateView):
    model = Wall
    template_name = 'climber/wall_form.html'
    fields = ['name', 'venue'] # Fields for Wall
    success_url = reverse_lazy('wall_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class WallUpdateView(UUIDLookupMixin, UpdateView):
    model = Wall
    template_name = 'climber/wall_form.html'
    fields = ['name', 'venue']
    success_url = reverse_lazy('wall_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class WallDeleteView(UUIDLookupMixin, DeleteView):
    model = Wall
    template_name = 'climber/wall_confirm_delete.html'
    success_url = reverse_lazy('wall_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object.delete()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)


#@login_required
@require_POST
def wall_upload_svg(request, pk):
    """Upload SVG file for a wall."""
    wall = get_object_or_404(Wall, uuid=pk)
    
    if 'svg_file' not in request.FILES:
        messages.error(request, 'Please select an SVG file to upload.')
        return redirect('wall_detail', pk=wall.uuid)
    
    svg_file = request.FILES['svg_file']
    
    # Validate file type
    if not svg_file.name.lower().endswith('.svg'):
        messages.error(request, 'Please upload a valid SVG file.')
        return redirect('wall_detail', pk=wall.uuid)
    
    try:
        # Save the SVG file
        wall.svg_file = svg_file
        wall.save()
        
        messages.success(request, f'SVG file "{svg_file.name}" uploaded successfully!')
        
    except Exception as e:
        messages.error(request, f'Error uploading SVG file: {str(e)}')
    
    return redirect('wall_detail', pk=wall.uuid)


#@login_required
@require_POST
def wall_upload_image(request, pk):
    """Upload wall image with drag and drop support"""
    wall = get_object_or_404(Wall, uuid=pk)
    
    # Check for both field names to handle different form submissions
    if 'wall_image' in request.FILES:
        image_file = request.FILES['wall_image']
    elif 'image_file' in request.FILES:
        image_file = request.FILES['image_file']
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Please select an image to upload.'})
        messages.error(request, 'Please select an image to upload.')
        return redirect('wall_detail', pk=wall.uuid)
    
    # Validate file type
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    if image_file.content_type not in allowed_types:
        error_msg = 'Please upload a valid image file (JPEG, PNG, or WebP).'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
        return redirect('wall_detail', pk=wall.uuid)
    
    try:
        # Save the image
        wall.wall_image = image_file
        wall.save()
        
        success_msg = f'Wall image "{image_file.name}" uploaded successfully!'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': success_msg})
        messages.success(request, success_msg)
        return redirect('wall_detail', pk=wall.uuid)
        
    except Exception as e:
        error_msg = f'Error uploading image: {str(e)}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
        return redirect('wall_detail', pk=wall.uuid)


#@login_required
def wall_capture_camera_image(request, pk):
    """Capture image from camera and save as wall image"""
    wall = get_object_or_404(Wall, uuid=pk)
    
    if request.method == 'POST':
        try:
            # Get image data from request
            image_data = request.POST.get('image_data')
            if not image_data:
                messages.error(request, 'No image data received from camera.')
                return JsonResponse({'success': False, 'error': 'No image data received'})
            
            # Decode base64 image
            import base64
            from django.core.files.base import ContentFile
            import io
            from PIL import Image
            
            # Remove data URL prefix if present
            if 'data:image/' in image_data:
                # Find the comma separating metadata from the actual data
                comma_pos = image_data.find(',')
                if comma_pos != -1:
                    image_data = image_data[comma_pos + 1:]
            
            # Decode base64
            try:
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))
                
                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Save to ContentFile
                image_io = io.BytesIO()
                image.save(image_io, format='JPEG', quality=85)
                image_file = ContentFile(image_io.getvalue(), name=f'camera_capture_{wall.uuid}.jpg')
                
                # Save to wall model
                wall.wall_image = image_file
                wall.save()
                
                messages.success(request, 'Camera image captured and saved successfully!')
                return JsonResponse({'success': True, 'message': 'Image saved successfully'})
                
            except Exception as e:
                messages.error(request, f'Error processing camera image: {str(e)}')
                return JsonResponse({'success': False, 'error': str(e)})
                
        except Exception as e:
            messages.error(request, f'Error saving camera image: {str(e)}')
            return JsonResponse({'success': False, 'error': str(e)})
    
    # For GET requests, just return error
    return JsonResponse({'success': False, 'error': 'Only POST requests are supported'})


# Hold CRUD Views
class HoldListView(ListView):
    model = Hold
    template_name = 'climber/hold_list.html'
    context_object_name = 'holds'

class HoldDetailView(UUIDLookupMixin, DetailView):
    model = Hold
    template_name = 'climber/hold_detail.html'
    context_object_name = 'hold'

class HoldCreateView(CreateView):
    model = Hold
    template_name = 'climber/hold_form.html'
    fields = ['name', 'wall', 'coords'] # Fields for Hold
    success_url = reverse_lazy('hold_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class HoldUpdateView(UUIDLookupMixin, UpdateView):
    model = Hold
    template_name = 'climber/hold_form.html'
    fields = ['name', 'wall', 'coords']
    success_url = reverse_lazy('hold_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class HoldDeleteView(UUIDLookupMixin, DeleteView):
    model = Hold
    template_name = 'climber/hold_confirm_delete.html'
    success_url = reverse_lazy('hold_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object.delete()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

# Route CRUD Views
class RouteListView(ListView):
    model = Route
    template_name = 'climber/route_list.html'
    context_object_name = 'routes'

class RouteDetailView(UUIDLookupMixin, DetailView):
    model = Route
    template_name = 'climber/route_detail.html'
    context_object_name = 'route'

class RouteCreateView(CreateView):
    model = Route
    template_name = 'climber/route_form.html'
    fields = ['name'] # Field for Route
    success_url = reverse_lazy('route_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class RouteUpdateView(UUIDLookupMixin, UpdateView):
    model = Route
    template_name = 'climber/route_form.html'
    fields = ['name']
    success_url = reverse_lazy('route_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class RouteDeleteView(UUIDLookupMixin, DeleteView):
    model = Route
    template_name = 'climber/route_confirm_delete.html'
    success_url = reverse_lazy('route_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object.delete()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)



# Session Recording Views
class SessionListView(ListView):
    model = SessionRecording
    template_name = 'climber/session_list.html'
    context_object_name = 'sessions'
    
    def get_queryset(self):
        # Handle anonymous users - return empty queryset for now
        if self.request.user.is_anonymous:
            return SessionRecording.objects.none()
        return SessionRecording.objects.filter(user=self.request.user)

class SessionDetailView(UUIDLookupMixin, DetailView):
    model = SessionRecording
    template_name = 'climber/session_detail.html'
    context_object_name = 'session'

class SessionDeleteView(UUIDLookupMixin, DeleteView):
    model = SessionRecording
    template_name = 'climber/session_confirm_delete.html'
    success_url = reverse_lazy('session_list')

class SessionReplayView(UUIDLookupMixin, DetailView):
    model = SessionRecording
    template_name = 'climber/session_replay.html'
    context_object_name = 'session'


class PoseRealtimeView(TemplateView):
    template_name = 'climber/pose_realtime.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fullscreen'] = self.request.GET.get('fullscreen', 'false').lower() == 'true'
        return context


class PoseSkeletonView(TemplateView):
    """View for displaying pose skeleton from custom WebSocket."""
    template_name = 'climber/pose_skeleton_dual.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['websocket_url'] = self.request.GET.get('ws_url', 'wss://climber.dev.maptnh.net:443/ws/pose/')
        return context


class PoseSkeletonDualView(TemplateView):
    """View for displaying dual pose skeleton visualizations from two WebSockets."""
    template_name = 'climber/pose_skeleton_dual.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['websocket_url'] = self.request.GET.get('ws_url', 'wss://climber.dev.maptnh.net:443/ws/pose/')
        return context


from django.http import StreamingHttpResponse
import cv2

from django.urls import reverse_lazy

class CameraView(TemplateView):
    template_name = "climber/camera.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stream_url = self.request.GET.get('stream_url')
        
        # Default to go2rtc stream if no external URL is provided
        if not stream_url:
            stream_url = "http://localhost:1984/stream.mp4?src=camera"
        
        context['stream_url'] = stream_url
        context['local_stream_url'] = reverse_lazy('video_feed')
        context['go2rtc_stream_url'] = "http://localhost:1984/stream.mp4?src=camera"
        context['go2rtc_api_url'] = "http://localhost:1984/api/info"
        return context

import asyncio

async def stream_video():
    """Video streaming async generator function."""
    # Explicitly use the AVFoundation backend for macOS
    cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        print("Error: Cannot open camera. Check permissions and connections.")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to grab frame. The camera may have been disconnected.")
            break
        
        # Encode frame as JPEG
        (flag, encodedImage) = cv2.imencode(".jpg", frame)
        if not flag:
            # This warning is useful to keep for debugging encoding issues
            print("Warning: Failed to encode frame.")
            continue
        
        # Yield the frame in the multipart response format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')
        
        # Yield control to the event loop
        await asyncio.sleep(0.01) # A small delay is good practice
    
    cap.release()


def capture_frame(request):
    """Capture a single frame from the camera and return it as a JPEG image."""
    cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        return HttpResponse("Error: Cannot open camera.", status=500)

    # Allow the camera to warm up by reading and discarding a few frames
    for _ in range(10):
        cap.read()

    # Now, capture the actual frame
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return HttpResponse("Error: Failed to capture frame.", status=500)

    # Encode frame as JPEG
    (flag, encodedImage) = cv2.imencode(".jpg", frame)
    if not flag:
        return HttpResponse("Error: Failed to encode frame.", status=500)

    return HttpResponse(encodedImage.tobytes(), content_type='image/jpeg')


def video_feed(request):
    """Video streaming route. Put this in the src attribute of an img tag."""
    return StreamingHttpResponse(stream_video(),
                                 content_type='multipart/x-mixed-replace; boundary=frame')



# HTMX example view
def check_username(request):
    username = request.POST.get('username')


# Task Management Views
class TaskManagementView(TemplateView):
    """View for managing Celery tasks, including the fake session data task."""
    template_name = 'climber/task_management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any context data needed for the task management page
        # Add walls and routes for dropdown selection
        context['walls'] = Wall.objects.all()
        context['routes'] = Route.objects.all()
        return context


#@login_required
@require_POST
def trigger_fake_session_task(request):
    """Trigger the fake session data task via Celery."""
    try:
        # Get parameters from the request
        session_id = request.POST.get('session_id')
        ws_url = request.POST.get('ws_url', 'ws://localhost:8000/ws/session-live/')
        duration = int(request.POST.get('duration', 60))
        create_session = request.POST.get('create_session') == 'on'
        
        # Trigger the Celery task
        task = send_fake_session_data_task.delay(
            session_id=session_id,
            ws_url=ws_url,
            duration=duration,
            create_session=create_session
        )
        
        return JsonResponse({
            'status': 'success',
            'message': f'Task started successfully with ID: {task.id}',
            'task_id': task.id
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


#@login_required
@require_POST
def trigger_websocket_tracker_task(request):
    """Trigger WebSocket pose session tracker task via Celery."""
    try:
        # Get parameters from request
        wall_id = request.POST.get('wall_id')
        input_websocket_url = request.POST.get('input_websocket_url')
        output_websocket_url = request.POST.get('output_websocket_url')
        proximity_threshold = request.POST.get('proximity_threshold')
        touch_duration = request.POST.get('touch_duration')
        reconnect_delay = request.POST.get('reconnect_delay')
        debug = request.POST.get('debug') == 'on'
        route_id = request.POST.get('route_id')
        
        # Convert parameters to appropriate types
        task_kwargs = {}
        if wall_id:
            task_kwargs['wall_id'] = int(wall_id)
        if input_websocket_url:
            task_kwargs['input_websocket_url'] = input_websocket_url
        if output_websocket_url:
            task_kwargs['output_websocket_url'] = output_websocket_url
        if proximity_threshold:
            task_kwargs['proximity_threshold'] = float(proximity_threshold)
        if touch_duration:
            task_kwargs['touch_duration'] = float(touch_duration)
        if reconnect_delay:
            task_kwargs['reconnect_delay'] = float(reconnect_delay)
        if debug:
            task_kwargs['debug'] = debug
        if route_id:
            task_kwargs['route_id'] = int(route_id)
        
        # Trigger Celery task
        task = websocket_pose_session_tracker_task.delay(**task_kwargs)
        
        return JsonResponse({
            'status': 'success',
            'message': f'WebSocket pose session tracker task started successfully with ID: {task.id}',
            'task_id': task.id
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@api_view(['GET'])
def get_running_tasks(request):
    """Get list of currently running Celery tasks."""
    from loguru import logger
    
    try:
        from celery.result import AsyncResult
        from celery import current_app
        from climber.models import CeleryTask
        
        # Get all task IDs from database
        task_records = CeleryTask.objects.filter(status__in=['PENDING', 'PROGRESS', 'RETRY']).order_by('-created')
        
        running_tasks = []
        for task_record in task_records:
            try:
                # Get task result
                result = AsyncResult(task_record.task_id)
                
                task_info = {
                    'task_id': task_record.task_id,
                    'task_name': task_record.task_name,
                    'status': result.status,
                    'start_time': task_record.created.isoformat(),
                    'elapsed_time': None,
                    'result': None
                }
                
                # Calculate elapsed time if task is running
                if result.status in ['PENDING', 'PROGRESS', 'RETRY']:
                    if task_record.created:
                        from datetime import datetime, timezone
                        elapsed = (datetime.now(timezone.utc) - task_record.created).total_seconds()
                        task_info['elapsed_time'] = elapsed
                
                # Get result if available
                if result.result:
                    task_info['result'] = result.result
                
                running_tasks.append(task_info)
                
            except Exception as e:
                logger.error(f"Error getting task info for {task_record.task_id}: {e}")
                continue
        
        return JsonResponse({
            'tasks': running_tasks
        })
        
    except Exception as e:
        return JsonResponse({
            'tasks': [],
            'error': str(e)
        }, status=500)


#@login_required
def get_task_status(request, task_id):
    """Get the status of a Celery task."""
    try:
        from celery.result import AsyncResult
        
        task = AsyncResult(task_id)
        
        response_data = {
            'task_id': task_id,
            'status': task.status,
            'result': task.result
        }
        
        # Add progress information if available
        if task.status == 'PROGRESS' and isinstance(task.result, dict):
            response_data.update(task.result)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


class WallAnimationView(UUIDLookupMixin, DetailView):
    """View for displaying animated wall with random objects."""
    model = Wall
    template_name = 'climber/wall_animation.html'
    context_object_name = 'wall'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any additional context needed for the animation
        return context


class DemoView(TemplateView):
    """View for demo page."""
    template_name = 'climber/demo.html'


@api_view(['POST'])
#@permission_classes([IsAuthenticated])
def api_upload_wall_image(request):
    """
    API endpoint to accept base64 encoded image and wall ID,
    and save the image as JPEG to wall.wall_image field.
    """
    try:
        # Get data from request
        wall_id = request.data.get('wall_id')
        image_data = request.data.get('image_data')
        
        if not wall_id or not image_data:
            return JsonResponse({
                'success': False,
                'error': 'Both wall_id and image_data are required'
            }, status=400)
        
        # Get the wall object
        try:
            wall = Wall.objects.get(uuid=wall_id)
        except Wall.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Wall with ID {wall_id} not found'
            }, status=404)
        
        # Process base64 image
        import base64
        from django.core.files.base import ContentFile
        import io
        from PIL import Image
        
        # Remove data URL prefix if present
        if 'data:image/' in image_data:
            # Find the comma separating metadata from the actual data
            comma_pos = image_data.find(',')
            if comma_pos != -1:
                image_data = image_data[comma_pos + 1:]
        
        # Decode base64
        try:
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if necessary (for JPEG compatibility)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save to ContentFile as JPEG
            image_io = io.BytesIO()
            image.save(image_io, format='JPEG', quality=85)
            image_file = ContentFile(image_io.getvalue(), name=f'wall_image_{wall.uuid}.jpg')
            
            # Save to wall model
            wall.wall_image = image_file
            wall.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Wall image uploaded successfully',
                'wall_id': str(wall.uuid),
                'image_url': wall.wall_image.url if wall.wall_image else None
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error processing image: {str(e)}'
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)




class ClientProxyView(ProxyView):
    upstream = settings.CLIENT_URL
    rewrite = (
        (r'^/client/(.*)$', r'\1'),
     )
