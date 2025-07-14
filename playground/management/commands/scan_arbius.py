from django.core.management.base import BaseCommand
from playground.services import ArbitrumScanner
from playground.models import ArbiusImage
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scan for new Arbius images on the blockchain and update the gallery'

    def add_arguments(self, parser):
        parser.add_argument(
            '--blocks',
            type=int,
            default=1000,
            help='Number of recent blocks to scan (default: 1000)'
        )
        parser.add_argument(
            '--minutes',
            type=int,
            help='Scan the last N minutes of blocks for images with prompts only'
        )
        parser.add_argument(
            '--deep-scan',
            action='store_true',
            help='Run a deep scan to catch missed historical images (last 3 days)'
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress output (for scheduled runs)'
        )

    def handle(self, *args, **options):
        scanner = ArbitrumScanner()
        
        if not options['quiet']:
            self.stdout.write('🚀 Starting Arbius blockchain scan...')
            self.stdout.write('💡 Scanning for new images and updating gallery...')
        
        try:
            if options['minutes']:
                # Scan recent minutes
                new_images = scanner.scan_recent_minutes(options['minutes'])
                period = f"last {options['minutes']} minutes"
            elif options['deep_scan']:
                # Deep scan
                new_images = scanner.scan_recent_blocks(10000)  # ~3 days worth
                period = "last 3 days"
            else:
                # Scan recent blocks
                new_images = scanner.scan_recent_blocks(options['blocks'])
                period = f"last {options['blocks']} blocks"
            
            total_images = ArbiusImage.objects.count()
            
            if not options['quiet']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Scan complete! Found {len(new_images)} new images in {period}\n'
                        f'📊 Database now contains {total_images} total images'
                    )
                )
            else:
                logger.info(f'Scan found {len(new_images)} new images ({total_images} total)')
                
        except Exception as e:
            error_msg = f'Error during scan: {e}'
            if not options['quiet']:
                self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            raise 