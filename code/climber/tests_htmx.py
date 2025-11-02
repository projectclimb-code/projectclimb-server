from django.urls import reverse
from django.test import TestCase
from .models import Group, Venue, Route, Hold, User, Wall # Import necessary models, added Wall

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


# TODO: Add tests for Create, Update, Delete views, including HTMX aspects if possible with Django test client.
