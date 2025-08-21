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

    def __str__(self):
        return self.name



class Hold(BaseModel):
    name = models.CharField(max_length=500)
    wall = models.ForeignKey(Wall, on_delete=models.CASCADE)
    coords = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name



class Route(BaseModel):
    name = models.CharField(max_length=500)

    def __str__(self):
        return self.name



class RoutePoint(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    hold = models.ForeignKey(Hold, on_delete=models.CASCADE)
    order = models.IntegerField()

    def __str__(self):
        return f"{self.route.name} - Hold {self.order}"

