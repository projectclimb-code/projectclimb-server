from django.shortcuts import render, get_object_or_404 # Ensure get_object_or_404 is imported
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import HttpResponse, Http404 # Added for HTMX responses and Http404
from django.utils.translation import gettext_lazy as _ # For Http404 message
from rest_framework import viewsets
from .models import Group, AppUser, Venue, Wall, Hold, Route, RoutePoint # Import all models
# Ensure User is imported if AppUser.user is a ForeignKey to django.contrib.auth.models.User
from django.contrib.auth.models import User 

from .serializers import (
    GroupSerializer, AppUserSerializer, VenueSerializer, WallSerializer,
    HoldSerializer, RouteSerializer, RoutePointSerializer
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

class RoutePointViewSet(viewsets.ModelViewSet):
    queryset = RoutePoint.objects.all()
    serializer_class = RoutePointSerializer

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
        context['routepoint_count'] = RoutePoint.objects.count()
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

# RoutePoint CRUD Views
class RoutePointListView(ListView):
    model = RoutePoint
    template_name = 'climber/routepoint_list.html'
    context_object_name = 'routepoints'

class RoutePointDetailView(DetailView):
    model = RoutePoint
    template_name = 'climber/routepoint_detail.html'
    context_object_name = 'routepoint'

class RoutePointCreateView(CreateView):
    model = RoutePoint
    template_name = 'climber/routepoint_form.html'
    fields = ['route', 'hold', 'order'] # Fields for RoutePoint
    success_url = reverse_lazy('routepoint_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class RoutePointUpdateView(UpdateView):
    model = RoutePoint
    template_name = 'climber/routepoint_form.html'
    fields = ['route', 'hold', 'order']
    success_url = reverse_lazy('routepoint_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object = form.save()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)

class RoutePointDeleteView(DeleteView):
    model = RoutePoint
    template_name = 'climber/routepoint_confirm_delete.html'
    success_url = reverse_lazy('routepoint_list')

    def form_valid(self, form):
        if self.request.htmx:
            self.object.delete()
            response = HttpResponse()
            response['HX-Redirect'] = self.get_success_url()
            return response
        return super().form_valid(form)


class PoseRealtimeView(TemplateView):
    template_name = 'climber/pose_realtime.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fullscreen'] = self.request.GET.get('fullscreen', 'false').lower() == 'true'
        return context


from django.http import StreamingHttpResponse
import cv2

from django.urls import reverse_lazy

class CameraView(TemplateView):
    template_name = "climber/camera.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stream_url = self.request.GET.get('stream_url')
        context['stream_url'] = stream_url
        context['local_stream_url'] = reverse_lazy('video_feed')
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
