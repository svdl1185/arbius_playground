from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

# Create your models here.

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    address = models.CharField(max_length=42, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.address}"

# Gallery Models
class ArbiusImage(models.Model):
    """Model to store information about Arbius generated images"""
    
    # Transaction details
    transaction_hash = models.CharField(max_length=66, unique=True, db_index=True)
    task_id = models.CharField(max_length=66, db_index=True)
    block_number = models.BigIntegerField()
    timestamp = models.DateTimeField()
    
    # Image details
    cid = models.CharField(max_length=100, db_index=True)
    ipfs_url = models.URLField()
    image_url = models.URLField()
    
    # AI Generation details
    model_id = models.CharField(max_length=66, blank=True, null=True, help_text="The AI model used to generate this image")
    prompt = models.TextField(blank=True, null=True, help_text="The prompt used to generate this image")
    input_parameters = models.JSONField(blank=True, null=True, help_text="Full input parameters including prompt and other settings")
    
    # Addresses - clarified for accuracy
    solution_provider = models.CharField(max_length=42, default='0x0000000000000000000000000000000000000000', help_text="Address of the miner who provided the solution/image")
    task_submitter = models.CharField(max_length=42, null=True, blank=True, help_text="Address of the user who originally submitted the task/prompt")
    
    # Legacy field for backward compatibility (will be removed later)
    miner_address = models.CharField(max_length=42, null=True, blank=True, help_text="DEPRECATED: Use solution_provider instead")
    owner_address = models.CharField(max_length=42, null=True, blank=True)
    gas_used = models.BigIntegerField(null=True, blank=True)
    
    # Tracking
    discovered_at = models.DateTimeField(default=timezone.now)
    is_accessible = models.BooleanField(default=True)
    last_checked = models.DateTimeField(default=timezone.now)
    ipfs_gateway = models.CharField(max_length=200, blank=True, default='')
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['cid']),
            models.Index(fields=['transaction_hash']),
        ]
    
    def __str__(self):
        return f"Arbius Image {self.cid[:10]}... (Block {self.block_number})"
    
    @property
    def short_cid(self):
        """Return a shortened version of the CID for display"""
        return f"{self.cid[:8]}...{self.cid[-8:]}" if len(self.cid) > 16 else self.cid
    
    @property
    def short_tx_hash(self):
        """Return a shortened version of the transaction hash for display"""
        return f"{self.transaction_hash[:10]}...{self.transaction_hash[-8:]}"
    
    @property
    def short_model_id(self):
        """Return a shortened version of the model ID for display"""
        if not self.model_id:
            return "Unknown Model"
        return f"{self.model_id[:8]}...{self.model_id[-8:]}" if len(self.model_id) > 16 else self.model_id

    @property
    def clean_prompt(self):
        """Return the prompt with additional instruction text removed"""
        if not self.prompt:
            return ""
        
        # Remove the additional instruction text that gets appended to prompts
        clean_text = self.prompt
        
        # Remove the "Additional instruction: Make sure to keep response short and consice." part (with typo)
        if "Additional instruction: Make sure to keep response short and consice." in clean_text:
            clean_text = clean_text.replace("Additional instruction: Make sure to keep response short and consice.", "").strip()
        
        # Also handle slight variations in spacing/punctuation (correct spelling)
        if "Additional instruction: Make sure to keep response short and concise." in clean_text:
            clean_text = clean_text.replace("Additional instruction: Make sure to keep response short and concise.", "").strip()
            
        # Handle the specific variation mentioned by the user: "very short and consice"
        if "Additional instruction: Make sure to keep response very short and consice." in clean_text:
            clean_text = clean_text.replace("Additional instruction: Make sure to keep response very short and consice.", "").strip()
            
        # Handle the correct spelling version of the above
        if "Additional instruction: Make sure to keep response very short and concise." in clean_text:
            clean_text = clean_text.replace("Additional instruction: Make sure to keep response very short and concise.", "").strip()
            
        return clean_text

    @property
    def upvote_count(self):
        """Return the number of upvotes for this image"""
        return self.upvotes.count()
    
    @property 
    def comment_count(self):
        """Return the number of comments for this image"""
        return self.comments.count()
    
    def has_upvoted(self, wallet_address):
        """Check if a wallet address has upvoted this image"""
        if not wallet_address:
            return False
        return self.upvotes.filter(wallet_address__iexact=wallet_address).exists()


class UserProfile(models.Model):
    """User profile linked to wallet address"""
    wallet_address = models.CharField(max_length=42, unique=True, db_index=True)
    display_name = models.CharField(max_length=50, blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True, null=True)
    avatar_url = models.URLField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    twitter_handle = models.CharField(max_length=50, blank=True, null=True)
    
    # Stats (will be updated via signals or periodic tasks)
    total_images_created = models.IntegerField(default=0)
    total_upvotes_received = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['wallet_address']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return self.display_name or f"User {self.wallet_address[:10]}..."
    
    @property
    def short_address(self):
        """Return a shortened version of the wallet address"""
        return f"{self.wallet_address[:6]}...{self.wallet_address[-4:]}"
    
    def update_stats(self):
        """Update user statistics"""
        self.total_images_created = ArbiusImage.objects.filter(
            task_submitter__iexact=self.wallet_address
        ).count()
        
        self.total_upvotes_received = ImageUpvote.objects.filter(
            image__task_submitter__iexact=self.wallet_address
        ).count()
        
        self.save()


class ImageUpvote(models.Model):
    """Track upvotes on images"""
    image = models.ForeignKey(ArbiusImage, on_delete=models.CASCADE, related_name='upvotes')
    wallet_address = models.CharField(max_length=42, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ['image', 'wallet_address']  # Prevent duplicate votes
        indexes = [
            models.Index(fields=['wallet_address']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Upvote by {self.wallet_address[:10]}... on {self.image.short_cid}"


class ImageComment(models.Model):
    """Comments on images"""
    image = models.ForeignKey(ArbiusImage, on_delete=models.CASCADE, related_name='comments')
    wallet_address = models.CharField(max_length=42, db_index=True)
    content = models.TextField(max_length=1000)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet_address']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Comment by {self.wallet_address[:10]}... on {self.image.short_cid}"
    
    @property
    def short_content(self):
        """Return a shortened version of the comment content"""
        return self.content[:100] + "..." if len(self.content) > 100 else self.content


class ScanStatus(models.Model):
    """Model to track blockchain scanning progress"""
    
    last_scanned_block = models.BigIntegerField(default=0)
    last_scan_time = models.DateTimeField(default=timezone.now)
    scan_in_progress = models.BooleanField(default=False)
    
    class Meta:
        verbose_name_plural = "Scan statuses"
    
    def __str__(self):
        return f"Scan Status - Last Block: {self.last_scanned_block}"


class MinerAddress(models.Model):
    """Model to track identified miner wallet addresses"""
    
    wallet_address = models.CharField(max_length=42, unique=True, db_index=True, help_text="Ethereum wallet address of the miner")
    first_seen = models.DateTimeField(default=timezone.now, help_text="When this miner was first identified")
    last_seen = models.DateTimeField(default=timezone.now, help_text="When this miner was last seen submitting solutions/commitments")
    total_solutions = models.PositiveIntegerField(default=0, help_text="Total number of solutions submitted by this miner")
    total_commitments = models.PositiveIntegerField(default=0, help_text="Total number of commitments submitted by this miner")
    is_active = models.BooleanField(default=True, help_text="Whether this miner is currently considered active")
    
    def __str__(self):
        return f"Miner {self.wallet_address[:10]}..."
    
    def update_activity(self, activity_type='solution'):
        """Update miner activity tracking"""
        self.last_seen = timezone.now()
        if activity_type == 'solution':
            self.total_solutions += 1
        elif activity_type == 'commitment':
            self.total_commitments += 1
        self.save()
    
    class Meta:
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['wallet_address']),
            models.Index(fields=['last_seen']),
            models.Index(fields=['is_active']),
        ]
        verbose_name_plural = "Miner addresses"


class TokenTransaction(models.Model):
    """Model to track AIUS token transactions"""
    
    transaction_hash = models.CharField(max_length=66, unique=True, db_index=True)
    from_address = models.CharField(max_length=42, db_index=True)
    to_address = models.CharField(max_length=42, db_index=True)
    amount = models.DecimalField(max_digits=36, decimal_places=18)  # Support large token amounts
    block_number = models.BigIntegerField(db_index=True)
    timestamp = models.DateTimeField(db_index=True)
    gas_price = models.BigIntegerField(null=True, blank=True)
    gas_used = models.BigIntegerField(null=True, blank=True)
    
    # Token sale tracking
    is_sale = models.BooleanField(default=False)
    sale_price_usd = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    exchange_address = models.CharField(max_length=42, null=True, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['transaction_hash']),
            models.Index(fields=['from_address']),
            models.Index(fields=['to_address']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['is_sale']),
        ]
    
    def __str__(self):
        return f"Token TX {self.transaction_hash[:10]}... ({self.amount} AIUS)"


class MinerTokenEarnings(models.Model):
    """Model to track calculated earnings for each miner"""
    
    miner_address = models.CharField(max_length=42, unique=True, db_index=True)
    total_aius_earned = models.DecimalField(max_digits=36, decimal_places=18, default=0)
    total_aius_sold = models.DecimalField(max_digits=36, decimal_places=18, default=0)
    total_usd_from_sales = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    
    # Tracking metrics
    first_earning_date = models.DateTimeField(null=True, blank=True)
    last_earning_date = models.DateTimeField(null=True, blank=True)
    last_sale_date = models.DateTimeField(null=True, blank=True)
    
    # Analysis status
    last_analyzed = models.DateTimeField(null=True, blank=True)
    needs_reanalysis = models.BooleanField(default=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-total_usd_from_sales']
    
    def __str__(self):
        return f"Miner {self.miner_address[:10]}... - ${self.total_usd_from_sales}"
