from django.urls import reverse
from django.test import TestCase
from .models import Group, Venue, Route, Hold, RoutePoint, User, Wall # Import necessary models, added Wall

class GroupHTMXViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = Group.objects.create(name="Test Group")

    def test_group_list_view(self):
        response = self.client.get(reverse('group_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'climber/group_list.html')
        self.assertContains(response, self.group.name)

    def test_group_detail_view(self):
        response = self.client.get(reverse('group_detail', kwargs={'pk': self.group.uuid})) # Use .uuid
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'climber/group_detail.html')
        self.assertContains(response, self.group.name)

class VenueHTMXViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venue = Venue.objects.create(name="Test Venue", description="A great place")

    def test_venue_list_view(self):
        response = self.client.get(reverse('venue_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'climber/venue_list.html')
        self.assertContains(response, self.venue.name)

    def test_venue_detail_view(self):
        response = self.client.get(reverse('venue_detail', kwargs={'pk': self.venue.uuid})) # Use .uuid
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'climber/venue_detail.html')
        self.assertContains(response, self.venue.name)

class RoutePointHTMXViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # RoutePoint requires Route and Hold, which requires Wall, which requires Venue
        # test_user = User.objects.create_user(username='testuser_rp', password='password') # User not directly used by RoutePoint
        venue = Venue.objects.create(name="RP Test Venue")
        wall = Wall.objects.create(name="RP Test Wall", venue=venue)
        cls.hold = Hold.objects.create(name="RP Test Hold", wall=wall, coords={"x":1,"y":1})
        cls.route = Route.objects.create(name="RP Test Route")
        cls.route_point = RoutePoint.objects.create(route=cls.route, hold=cls.hold, order=1)

    def test_routepoint_list_view(self):
        response = self.client.get(reverse('routepoint_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'climber/routepoint_list.html')
        self.assertContains(response, str(self.route_point.order)) # Check for order

    def test_routepoint_detail_view(self):
        response = self.client.get(reverse('routepoint_detail', kwargs={'pk': self.route_point.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'climber/routepoint_detail.html')
        self.assertContains(response, self.route.name)
        self.assertContains(response, self.hold.name)

# TODO: Add tests for Create, Update, Delete views, including HTMX aspects if possible with Django test client.
