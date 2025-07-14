from django.core.management.base import BaseCommand
from playground.models import ArbiusImage, MinerAddress, UserProfile, ImageUpvote, ImageComment

class Command(BaseCommand):
    help = 'Remove all sample data created by import_gallery_data command'

    def handle(self, *args, **options):
        self.stdout.write('Removing sample data...')
        
        # Count before deletion
        images_before = ArbiusImage.objects.count()
        miners_before = MinerAddress.objects.count()
        profiles_before = UserProfile.objects.count()
        upvotes_before = ImageUpvote.objects.count()
        comments_before = ImageComment.objects.count()
        
        # Remove sample data
        # First, remove upvotes and comments that reference sample images
        sample_images = ArbiusImage.objects.filter(
            transaction_hash__startswith='0x' + '0' * 60  # Sample transaction hashes
        )
        
        if sample_images.exists():
            # Remove related upvotes and comments
            ImageUpvote.objects.filter(image__in=sample_images).delete()
            ImageComment.objects.filter(image__in=sample_images).delete()
            
            # Remove the sample images
            sample_images.delete()
        
        # Remove sample miner addresses (the hardcoded ones from the import script)
        sample_miners = [
            '0x5e33e2cead338b1224ddd34636dac7563f97c300',
            '0xdc790a53e50207861591622d349e989fef6f84bc',
            '0x4d826895b255a4f38d7ba87688604c358f4132b6',
            '0xd04c1b09576aa4310e4768d8e9cd12fac3216f95',
        ]
        
        MinerAddress.objects.filter(wallet_address__in=sample_miners).delete()
        
        # Count after deletion
        images_after = ArbiusImage.objects.count()
        miners_after = MinerAddress.objects.count()
        profiles_after = UserProfile.objects.count()
        upvotes_after = ImageUpvote.objects.count()
        comments_after = ImageComment.objects.count()
        
        self.stdout.write(f'Removed {images_before - images_after} sample images')
        self.stdout.write(f'Removed {miners_before - miners_after} sample miner addresses')
        self.stdout.write(f'Removed {profiles_before - profiles_after} sample user profiles')
        self.stdout.write(f'Removed {upvotes_before - upvotes_after} sample upvotes')
        self.stdout.write(f'Removed {comments_before - comments_after} sample comments')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully removed all sample data!')
        ) 