from django.db import models
from django.contrib.auth.models import User
import hashlib
import hmac
import json

# Create your models here.

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    address = models.CharField(max_length=42, unique=True)  # Ethereum address
    signature = models.TextField(blank=True, null=True)  # Store signature for verification
    message_hash = models.TextField(blank=True, null=True)  # Hash of the signed message
    connected_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Wallet: {self.address}"
    
    class Meta:
        db_table = 'wallets'
