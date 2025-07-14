import logging
import requests
from web3 import Web3
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from .models import ArbiusImage, MinerAddress

logger = logging.getLogger(__name__)

class ArbitrumScanner:
    """Service to scan Arbitrum blockchain for Arbius images and miner activity"""
    
    def __init__(self):
        # Initialize Web3 connection to Arbitrum
        self.w3 = Web3(Web3.HTTPProvider('https://arb1.arbitrum.io/rpc'))
        
        # Arbius contract addresses (mainnet)
        self.ENGINE_CONTRACT = '0x5FbDB2315678afecb367f032d93F642f64180aa3'  # Replace with actual contract
        self.TASK_CONTRACT = '0x5FbDB2315678afecb367f032d93F642f64180aa3'    # Replace with actual contract
        
        # Known miner addresses for automine filtering
        self.KNOWN_MINERS = [
            '0x5e33e2cead338b1224ddd34636dac7563f97c300',
            '0xdc790a53e50207861591622d349e989fef6f84bc',
            '0x4d826895b255a4f38d7ba87688604c358f4132b6',
            '0xd04c1b09576aa4310e4768d8e9cd12fac3216f95',
        ]
    
    def get_latest_block(self):
        """Get the latest block number"""
        try:
            return self.w3.eth.block_number
        except Exception as e:
            logger.error(f"Error getting latest block: {e}")
            return None
    
    def scan_recent_blocks(self, blocks=100):
        """Scan recent blocks for new images"""
        latest_block = self.get_latest_block()
        if not latest_block:
            return []
        
        start_block = max(0, latest_block - blocks)
        logger.info(f"Scanning blocks {start_block} to {latest_block}")
        
        new_images = []
        
        for block_num in range(start_block, latest_block + 1):
            try:
                block = self.w3.eth.get_block(block_num, full_transactions=True)
                
                for tx in block.transactions:
                    # Check if this is a solution submission
                    if self._is_solution_submission(tx):
                        image_data = self._extract_image_data(tx, block_num)
                        if image_data:
                            # Check if image already exists
                            if not ArbiusImage.objects.filter(transaction_hash=image_data['transaction_hash']).exists():
                                # Create new image
                                image = ArbiusImage.objects.create(**image_data)
                                new_images.append(image)
                                logger.info(f"Found new image: {image.transaction_hash}")
                                
                                # Update miner activity
                                self._update_miner_activity(image.solution_provider)
                
            except Exception as e:
                logger.error(f"Error scanning block {block_num}: {e}")
                continue
        
        logger.info(f"Scan complete. Found {len(new_images)} new images")
        return new_images
    
    def scan_recent_minutes(self, minutes=10):
        """Scan recent minutes for new images with prompts"""
        latest_block = self.get_latest_block()
        if not latest_block:
            return []
        
        # Estimate blocks per minute (roughly 1 block per 12 seconds)
        blocks_per_minute = 5
        blocks_to_scan = minutes * blocks_per_minute
        
        start_block = max(0, latest_block - blocks_to_scan)
        logger.info(f"Scanning last {minutes} minutes (blocks {start_block} to {latest_block})")
        
        new_images = []
        
        for block_num in range(start_block, latest_block + 1):
            try:
                block = self.w3.eth.get_block(block_num, full_transactions=True)
                
                for tx in block.transactions:
                    if self._is_solution_submission(tx):
                        image_data = self._extract_image_data(tx, block_num)
                        if image_data and image_data.get('prompt'):
                            # Only process images with prompts
                            if not ArbiusImage.objects.filter(transaction_hash=image_data['transaction_hash']).exists():
                                image = ArbiusImage.objects.create(**image_data)
                                new_images.append(image)
                                logger.info(f"Found new image with prompt: {image.transaction_hash}")
                                
                                # Update miner activity
                                self._update_miner_activity(image.solution_provider)
                
            except Exception as e:
                logger.error(f"Error scanning block {block_num}: {e}")
                continue
        
        logger.info(f"Recent scan complete. Found {len(new_images)} new images with prompts")
        return new_images
    
    def scan_for_miners(self, hours_back=1, mark_inactive=False):
        """Scan for miner activity and update miner database"""
        latest_block = self.get_latest_block()
        if not latest_block:
            return []
        
        # Estimate blocks per hour
        blocks_per_hour = 300  # ~5 blocks per minute
        blocks_to_scan = hours_back * blocks_per_hour
        
        start_block = max(0, latest_block - blocks_to_scan)
        logger.info(f"Scanning for miners in blocks {start_block} to {latest_block}")
        
        found_miners = []
        
        for block_num in range(start_block, latest_block + 1):
            try:
                block = self.w3.eth.get_block(block_num, full_transactions=True)
                
                for tx in block.transactions:
                    if self._is_solution_submission(tx):
                        miner_address = self._extract_miner_address(tx)
                        if miner_address:
                            found_miners.append(miner_address)
                            self._update_miner_activity(miner_address)
                
            except Exception as e:
                logger.error(f"Error scanning block {block_num} for miners: {e}")
                continue
        
        # Mark inactive miners if requested
        if mark_inactive:
            self._mark_inactive_miners()
        
        logger.info(f"Miner scan complete. Found {len(set(found_miners))} unique miners")
        return list(set(found_miners))
    
    def _is_solution_submission(self, tx):
        """Check if transaction is a solution submission to the engine contract"""
        try:
            # Check if transaction is to the engine contract
            if tx.to and tx.to.lower() == self.ENGINE_CONTRACT.lower():
                # Check if it's a submitSolution call
                if tx.input and len(tx.input) > 10:
                    # This is a simplified check - in reality you'd decode the function call
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking solution submission: {e}")
            return False
    
    def _extract_image_data(self, tx, block_num):
        """Extract image data from transaction"""
        try:
            # This is a simplified extraction - in reality you'd decode the transaction data
            # and fetch the actual image data from IPFS
            
            # Mock data for demonstration
            image_data = {
                'transaction_hash': tx.hash.hex(),
                'task_id': f"task_{block_num}_{tx.nonce}",
                'block_number': block_num,
                'timestamp': datetime.fromtimestamp(tx.timestamp),
                'cid': f"QmMock{block_num}{tx.nonce}",
                'ipfs_url': f"https://ipfs.io/ipfs/QmMock{block_num}{tx.nonce}",
                'image_url': f"https://ipfs.io/ipfs/QmMock{block_num}{tx.nonce}/out-1.png",
                'model_id': '0xa473c70e9d7c872ac948d20546bc79db55fa64ca325a4b229aaffddb7f86aae0',
                'prompt': f"Generated image from block {block_num}",
                'solution_provider': tx['from'],
                'task_submitter': tx['from'],  # Simplified - would be extracted from transaction data
                'is_accessible': True,
            }
            
            return image_data
            
        except Exception as e:
            logger.error(f"Error extracting image data: {e}")
            return None
    
    def _extract_miner_address(self, tx):
        """Extract miner address from transaction"""
        try:
            return tx['from']
        except Exception as e:
            logger.error(f"Error extracting miner address: {e}")
            return None
    
    def _update_miner_activity(self, miner_address):
        """Update miner activity in database"""
        try:
            miner, created = MinerAddress.objects.get_or_create(
                wallet_address=miner_address,
                defaults={
                    'first_seen': timezone.now(),
                    'last_seen': timezone.now(),
                    'total_solutions': 1,
                    'is_active': True,
                }
            )
            
            if not created:
                # Update existing miner
                miner.last_seen = timezone.now()
                miner.total_solutions += 1
                miner.is_active = True
                miner.save(update_fields=['last_seen', 'total_solutions', 'is_active'])
                
        except Exception as e:
            logger.error(f"Error updating miner activity: {e}")
    
    def _mark_inactive_miners(self):
        """Mark miners as inactive if not seen for 7+ days"""
        try:
            cutoff_date = timezone.now() - timedelta(days=7)
            inactive_count = MinerAddress.objects.filter(
                last_seen__lt=cutoff_date,
                is_active=True
            ).update(is_active=False)
            
            if inactive_count > 0:
                logger.info(f"Marked {inactive_count} miners as inactive")
                
        except Exception as e:
            logger.error(f"Error marking inactive miners: {e}")
    
    def recheck_accessibility(self, batch_size=50):
        """Recheck IPFS accessibility for images marked as not accessible"""
        try:
            inaccessible_images = ArbiusImage.objects.filter(
                is_accessible=False
            )[:batch_size]
            
            updated_count = 0
            for image in inaccessible_images:
                try:
                    # Check if image is accessible
                    response = requests.head(image.image_url, timeout=5)
                    if response.status_code == 200:
                        image.is_accessible = True
                        image.last_checked = timezone.now()
                        image.save(update_fields=['is_accessible', 'last_checked'])
                        updated_count += 1
                        
                except Exception as e:
                    logger.debug(f"Image {image.cid} still not accessible: {e}")
                    continue
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error rechecking accessibility: {e}")
            return 0 