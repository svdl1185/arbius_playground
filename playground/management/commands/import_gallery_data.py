from django.core.management.base import BaseCommand
from django.utils import timezone
from playground.models import ArbiusImage, MinerAddress
import random
from datetime import timedelta

class Command(BaseCommand):
    help = 'Import sample gallery data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Importing sample gallery data...')
        
        # Create some sample miner addresses
        miner_addresses = [
            '0x5e33e2cead338b1224ddd34636dac7563f97c300',
            '0xdc790a53e50207861591622d349e989fef6f84bc',
            '0x4d826895b255a4f38d7ba87688604c358f4132b6',
            '0xd04c1b09576aa4310e4768d8e9cd12fac3216f95',
        ]
        
        for address in miner_addresses:
            MinerAddress.objects.get_or_create(
                wallet_address=address,
                defaults={
                    'first_seen': timezone.now(),
                    'last_seen': timezone.now(),
                    'total_solutions': random.randint(10, 100),
                    'total_commitments': random.randint(5, 50),
                    'is_active': True
                }
            )
        
        # Sample prompts for generating images
        sample_prompts = [
            "A futuristic cityscape with flying cars and neon lights",
            "A serene mountain landscape at sunset",
            "A cyberpunk robot in a neon-lit alley",
            "A magical forest with glowing mushrooms",
            "A steampunk airship flying over Victorian London",
            "A space station orbiting a colorful nebula",
            "A medieval castle on a floating island",
            "A robot playing chess with a human",
            "A underwater city with bioluminescent creatures",
            "A time machine in a steampunk laboratory",
            "A dragon flying over a medieval village",
            "A futuristic sports car on a neon highway",
            "A magical library with floating books",
            "A robot gardener tending to alien plants",
            "A cyberpunk street market at night",
            "A floating island with waterfalls",
            "A space battle between starships",
            "A magical portal in an ancient temple",
            "A robot chef cooking in a futuristic kitchen",
            "A steampunk submarine exploring the deep sea"
        ]
        
        # Create sample images
        model_id = '0xa473c70e9d7c872ac948d20546bc79db55fa64ca325a4b229aaffddb7f86aae0'
        
        for i in range(50):
            # Generate random data
            prompt = random.choice(sample_prompts)
            timestamp = timezone.now() - timedelta(days=random.randint(0, 30))
            block_number = 1000000 + random.randint(0, 100000)
            
            # Create a unique transaction hash
            tx_hash = f"0x{random.randint(1000000000000000000000000000000000000000, 9999999999999999999999999999999999999999):040x}"
            task_id = f"0x{random.randint(1000000000000000000000000000000000000000, 9999999999999999999999999999999999999999):040x}"
            cid = f"Qm{random.randint(1000000000000000000000000000000000000000, 9999999999999999999999999999999999999999):040x}"
            
            # Randomly assign to a miner or user
            if random.random() < 0.3:  # 30% chance to be a miner
                task_submitter = random.choice(miner_addresses)
                solution_provider = random.choice(miner_addresses)
            else:
                task_submitter = f"0x{random.randint(1000000000000000000000000000000000000000, 9999999999999999999999999999999999999999):040x}"
                solution_provider = random.choice(miner_addresses)
            
            # Create the image
            image = ArbiusImage.objects.create(
                transaction_hash=tx_hash,
                task_id=task_id,
                block_number=block_number,
                timestamp=timestamp,
                cid=cid,
                ipfs_url=f"https://ipfs.io/ipfs/{cid}",
                image_url=f"https://ipfs.io/ipfs/{cid}",
                model_id=model_id,
                prompt=prompt,
                input_parameters={
                    "prompt": prompt,
                    "model": model_id,
                    "parameters": {
                        "width": 512,
                        "height": 512,
                        "steps": 20
                    }
                },
                solution_provider=solution_provider,
                task_submitter=task_submitter,
                discovered_at=timestamp,
                is_accessible=True,
                last_checked=timestamp,
                ipfs_gateway="https://ipfs.io"
            )
            
            self.stdout.write(f'Created image {i+1}/50: {image.short_cid}')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully imported sample gallery data!')
        ) 