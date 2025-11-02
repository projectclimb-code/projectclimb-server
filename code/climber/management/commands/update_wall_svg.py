from django.core.management.base import BaseCommand
from django.db import models
from climber.models import Wall
import os

class Command(BaseCommand):
    help = 'Update wall SVG file paths to use the media directory'

    def handle(self, *args, **options):
        # Get all walls without an SVG file
        walls_without_svg = Wall.objects.filter(svg_file='')
        
        if not walls_without_svg.exists():
            self.stdout.write(self.style.SUCCESS('All walls already have SVG files.'))
            return
        
        # Path to the default SVG file in media
        default_svg_path = 'svg_files/stena_export.svg'
        
        for wall in walls_without_svg:
            # Update the wall to use the default SVG file
            wall.svg_file = default_svg_path
            wall.save()
            self.stdout.write(self.style.SUCCESS(f'Updated wall "{wall.name}" with SVG file: {default_svg_path}'))
        
        self.stdout.write(self.style.SUCCESS(f'Updated {walls_without_svg.count()} wall(s) with SVG files.'))