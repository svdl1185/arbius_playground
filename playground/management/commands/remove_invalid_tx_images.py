from django.core.management.base import BaseCommand
from playground.models import ArbiusImage
import re

class Command(BaseCommand):
    help = 'Remove all images with invalid Ethereum transaction hashes.'

    def handle(self, *args, **options):
        eth_tx_pattern = re.compile(r'^0x[a-fA-F0-9]{64}$')
        invalid_images = ArbiusImage.objects.exclude(transaction_hash__regex=r'^0x[a-fA-F0-9]{64}$')
        count = invalid_images.count()
        invalid_images.delete()
        self.stdout.write(self.style.SUCCESS(f'Removed {count} images with invalid transaction hashes.')) 