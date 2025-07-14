from django.core.management.base import BaseCommand
from playground.models import ImageUpvote

class Command(BaseCommand):
    help = 'Delete all upvotes from all images (reset upvotes to zero)'

    def handle(self, *args, **options):
        count = ImageUpvote.objects.count()
        ImageUpvote.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Removed {count} upvotes. All images now have 0 upvotes.')) 