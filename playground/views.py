from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
import json
import hashlib
import logging
from eth_account.messages import encode_defunct
from web3 import Web3
from .models import Wallet

# Set up logging
logger = logging.getLogger(__name__)

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
                wallet = Wallet.objects.get(user=request.user)  # type: ignore[attr-defined]
                return JsonResponse({
                    'success': True,
                    'authenticated': True,
                    'address': wallet.address,
                    'username': request.user.username
                })
            except Wallet.DoesNotExist:  # type: ignore[attr-defined]
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
            'error': str(e)
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
            'error': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def verify_signature(request):
    """Verify Ethereum signature and connect wallet"""
    try:
        logger.info("Starting signature verification")
        data = json.loads(request.body)
        address = data.get('address')
        message = data.get('message')
        signature = data.get('signature')
        
        logger.info(f"Received data - address: {address}, message length: {len(message) if message else 0}, signature length: {len(signature) if signature else 0}")
        
        if not all([address, message, signature]):
            logger.error("Missing required parameters")
            return JsonResponse({
                'success': False,
                'error': 'Missing required parameters'
            }, status=400)
        
        # Verify the signature
        logger.info("Creating Web3 instance")
        w3 = Web3()
        logger.info("Encoding message")
        message_hash = encode_defunct(text=message)
        logger.info("Recovering address from signature")
        recovered_address = w3.eth.account.recover_message(message_hash, signature=signature)
        
        logger.info(f"Recovered address: {recovered_address}, Original address: {address}")
        
        if recovered_address.lower() != address.lower():
            logger.error(f"Invalid signature - recovered: {recovered_address}, expected: {address}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid signature'
            }, status=400)
        
        # Create or update wallet record
        logger.info("Creating/updating wallet record")
        wallet, created = Wallet.objects.get_or_create(  # type: ignore[attr-defined]
            address=address.lower(),
            defaults={
                'signature': signature,
                'message_hash': hashlib.sha256(message.encode()).hexdigest()
            }
        )
        
        if not created:
            wallet.signature = signature
            wallet.message_hash = hashlib.sha256(message.encode()).hexdigest()
            wallet.save()
        
        # Create anonymous user if none exists
        if not wallet.user:
            logger.info("Creating new user for wallet")
            username = f"user_{address[:8]}"
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password=None  # No password for wallet-based auth
            )
            wallet.user = user
            wallet.save()
        
        # Log in the user
        logger.info("Logging in user")
        login(request, wallet.user)
        
        request.session['wallet_address'] = wallet.address
        
        logger.info("Signature verification successful")
        return JsonResponse({
            'success': True,
            'message': 'Wallet connected successfully',
            'address': address,
            'username': wallet.user.username
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in verify_signature: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
