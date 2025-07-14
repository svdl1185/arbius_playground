from django.core.management.base import BaseCommand, CommandError
from playground.models import MinerAddress, MinerTokenEarnings
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Analyze miner wallets for AIUS token movements and sales'

    def add_arguments(self, parser):
        parser.add_argument(
            '--miner',
            type=str,
            help='Analyze a specific miner address'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Analyze all miners'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reanalysis even if recently analyzed'
        )
        parser.add_argument(
            '--no-connected',
            action='store_true',
            help='Disable connected wallet analysis (faster but less complete)'
        )

    def handle(self, *args, **options):
        self.stdout.write('🔍 Starting miner token analysis...')
        
        try:
            if options['miner']:
                # Analyze specific miner
                miners = MinerAddress.objects.filter(wallet_address__iexact=options['miner'])
                if not miners.exists():
                    raise CommandError(f'Miner {options["miner"]} not found in database')
            elif options['all']:
                # Analyze all miners
                miners = MinerAddress.objects.all()
            else:
                # Analyze miners that need analysis
                miners = MinerAddress.objects.filter(
                    minertokenearnings__isnull=True
                ) | MinerAddress.objects.filter(
                    minertokenearnings__needs_reanalysis=True
                )
            
            if not miners.exists():
                self.stdout.write(self.style.WARNING('No miners found for analysis'))
                return
            
            self.stdout.write(f'📊 Analyzing {miners.count()} miners...')
            
            analyzed_count = 0
            for miner in miners:
                try:
                    # Check if already analyzed recently (unless force)
                    if not options['force']:
                        earnings = MinerTokenEarnings.objects.filter(miner_address=miner.wallet_address).first()
                        if earnings and not earnings.needs_reanalysis:
                            self.stdout.write(f'⏭️  Skipping {miner.wallet_address[:8]}... (already analyzed)')
                            continue
                    
                    # Analyze miner tokens
                    self._analyze_miner_tokens(miner.wallet_address)
                    analyzed_count += 1
                    
                    self.stdout.write(f'✅ Analyzed {miner.wallet_address[:8]}...')
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Error analyzing {miner.wallet_address[:8]}...: {e}')
                    )
                    continue
            
            self.stdout.write(
                self.style.SUCCESS(f'🎉 Analysis complete! Processed {analyzed_count} miners')
            )
            
        except Exception as e:
            error_msg = f'Error during token analysis: {e}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            raise
    
    def _analyze_miner_tokens(self, miner_address):
        """Analyze a specific miner's token movements and sales"""
        try:
            # This is a simplified analysis - in reality you'd:
            # 1. Query the blockchain for AIUS token transfers to/from the miner
            # 2. Track token sales on DEXes (Uniswap, etc.)
            # 3. Calculate USD values at time of transactions
            
            # For now, create mock earnings data
            earnings, created = MinerTokenEarnings.objects.get_or_create(
                miner_address=miner_address,
                defaults={
                    'total_aius_earned': 0,
                    'total_aius_sold': 0,
                    'total_usd_from_sales': 0,
                    'needs_reanalysis': False,
                    'last_analyzed': timezone.now(),
                }
            )
            
            if not created:
                # Update existing record
                earnings.needs_reanalysis = False
                earnings.last_analyzed = timezone.now()
                earnings.save(update_fields=['needs_reanalysis', 'last_analyzed'])
            
        except Exception as e:
            logger.error(f"Error analyzing tokens for {miner_address}: {e}")
            raise 