from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from django.core.cache import cache
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
import json
import hashlib
import logging
import re
import time
from eth_account.messages import encode_defunct
from web3 import Web3
from .models import Wallet

# Set up logging
logger = logging.getLogger(__name__)

# Security constants
MAX_SIGNATURE_ATTEMPTS = 5  # Max attempts per IP per hour
SIGNATURE_TIMEOUT = 300  # 5 minutes for signature validity
MIN_MESSAGE_LENGTH = 10
MAX_MESSAGE_LENGTH = 1000

def is_valid_ethereum_address(address):
    """Validate Ethereum address format"""
    if not address or not isinstance(address, str):
        return False
    # Check if it's a valid Ethereum address format
    pattern = re.compile(r'^0x[a-fA-F0-9]{40}$')
    return bool(pattern.match(address))

def is_valid_signature(signature):
    """Validate signature format"""
    if not signature or not isinstance(signature, str):
        return False
    # Ethereum signatures are 132 characters (0x + 130 hex chars)
    pattern = re.compile(r'^0x[a-fA-F0-9]{130}$')
    return bool(pattern.match(signature))

def check_rate_limit(request, action):
    """Rate limiting for security-sensitive actions"""
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
    cache_key = f"rate_limit:{action}:{client_ip}"
    
    attempts = cache.get(cache_key, 0)
    if attempts >= MAX_SIGNATURE_ATTEMPTS:
        return False
    
    cache.set(cache_key, attempts + 1, 3600)  # 1 hour expiry
    return True

def validate_message_content(message):
    """Validate message content for security"""
    if not message or not isinstance(message, str):
        return False, "Invalid message format"
    
    if len(message) < MIN_MESSAGE_LENGTH:
        return False, f"Message too short (minimum {MIN_MESSAGE_LENGTH} characters)"
    
    if len(message) > MAX_MESSAGE_LENGTH:
        return False, f"Message too long (maximum {MAX_MESSAGE_LENGTH} characters)"
    
    # Check for suspicious content
    suspicious_patterns = [
        r'<script',  # XSS attempts
        r'javascript:',  # JavaScript injection
        r'data:text/html',  # Data URI attacks
        r'vbscript:',  # VBScript injection
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            return False, "Message contains suspicious content"
    
    return True, None

# Create your views here.

def home(request):
    return render(request, 'home.html')

def playground(request):
    return render(request, 'playground.html')

@csrf_exempt
@require_http_methods(["GET"])
def check_auth_status(request):
    """Check current authentication status and wallet connection"""
    try:
        if request.user.is_authenticated:
            # Check if user has a wallet
            try:
                wallet = Wallet.objects.get(user=request.user)  # type: ignore
                return JsonResponse({
                    'success': True,
                    'authenticated': True,
                    'address': wallet.address,
                    'username': request.user.username
                })
            except ObjectDoesNotExist:
                return JsonResponse({
                    'success': True,
                    'authenticated': True,
                    'address': None,
                    'username': request.user.username
                })
        else:
            return JsonResponse({
                'success': True,
                'authenticated': False,
                'address': None,
                'username': None
            })
    except Exception as e:
        logger.error(f"Error in check_auth_status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def logout_wallet(request):
    """Logout user and clear wallet session"""
    try:
        logout(request)
        return JsonResponse({
            'success': True,
            'message': 'Logged out successfully'
        })
    except Exception as e:
        logger.error(f"Error in logout_wallet: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def verify_signature(request):
    """Verify Ethereum signature and connect wallet with enhanced security"""
    try:
        # Rate limiting
        if not check_rate_limit(request, 'signature_verify'):
            return JsonResponse({
                'success': False,
                'error': 'Too many signature verification attempts. Please try again later.'
            }, status=429)
        
        # Parse and validate JSON
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON format'
            }, status=400)
        
        # Extract and validate required fields
        address = data.get('address', '').strip()
        message = data.get('message', '').strip()
        signature = data.get('signature', '').strip()
        
        # Input validation
        if not all([address, message, signature]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required parameters'
            }, status=400)
        
        # Validate Ethereum address format
        if not is_valid_ethereum_address(address):
            return JsonResponse({
                'success': False,
                'error': 'Invalid Ethereum address format'
            }, status=400)
        
        # Validate signature format
        if not is_valid_signature(signature):
            return JsonResponse({
                'success': False,
                'error': 'Invalid signature format'
            }, status=400)
        
        # Validate message content
        is_valid, error_msg = validate_message_content(message)
        if not is_valid:
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=400)
        
        # Check for expected message format (nonce protection)
        expected_prefix = "Welcome to Arbius Playground!"
        if not message.startswith(expected_prefix):
            return JsonResponse({
                'success': False,
                'error': 'Invalid message format'
            }, status=400)
        
        # Extract timestamp from message for additional validation
        timestamp_match = re.search(r'Timestamp: (.+)', message)
        if timestamp_match:
            try:
                import datetime
                timestamp_str = timestamp_match.group(1)
                message_time = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                current_time = datetime.datetime.now(datetime.timezone.utc)
                time_diff = abs((current_time - message_time).total_seconds())
                
                if time_diff > SIGNATURE_TIMEOUT:
                    return JsonResponse({
                        'success': False,
                        'error': 'Signature has expired'
                    }, status=400)
            except (ValueError, AttributeError):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid timestamp in message'
                }, status=400)
        
        # Verify the signature using Web3
        try:
            w3 = Web3()
            message_hash = encode_defunct(text=message)
            recovered_address = w3.eth.account.recover_message(message_hash, signature=signature)
            
            # Case-insensitive comparison
            if recovered_address.lower() != address.lower():
                logger.warning(f"Signature verification failed - recovered: {recovered_address}, expected: {address}")
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid signature'
                }, status=400)
                
        except Exception as e:
            logger.error(f"Web3 signature verification error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Signature verification failed'
            }, status=400)
        
        # Create or update wallet record with additional security
        try:
            wallet, created = Wallet.objects.get_or_create(  # type: ignore
                address=address.lower(),
                defaults={
                    'signature': signature,
                    'message_hash': hashlib.sha256(message.encode('utf-8')).hexdigest()
                }
            )
            
            if not created:
                # Update existing wallet with new signature
                wallet.signature = signature
                wallet.message_hash = hashlib.sha256(message.encode('utf-8')).hexdigest()
                wallet.save()
            
            # Create anonymous user if none exists
            if not wallet.user:
                username = f"user_{address[:8].lower()}"
                # Ensure username uniqueness
                counter = 1
                original_username = username
                while User.objects.filter(username=username).exists():
                    username = f"{original_username}_{counter}"
                    counter += 1
                
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@arbius.local",  # Use local domain
                    password=None  # No password for wallet-based auth
                )
                wallet.user = user
                wallet.save()
            
            # Log in the user
            login(request, wallet.user)
            
            # Store wallet address in session
            request.session['wallet_address'] = wallet.address
            
            logger.info(f"Successful wallet connection for address: {address[:10]}...")
            return JsonResponse({
                'success': True,
                'message': 'Wallet connected successfully',
                'address': address,
                'username': wallet.user.username
            })
            
        except Exception as e:
            logger.error(f"Database error during wallet creation: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to create wallet record'
            }, status=500)
        
    except Exception as e:
        logger.error(f"Unexpected error in verify_signature: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)
