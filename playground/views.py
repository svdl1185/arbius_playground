from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from django.core.cache import cache
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Q, Avg, Min, Max, Case, When, IntegerField, Exists, OuterRef
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.utils import timezone
from django.urls import reverse
from django.contrib import messages
import json
import hashlib
import logging
import re
import time
from eth_account.messages import encode_defunct
from web3 import Web3
from .models import Wallet, ArbiusImage, UserProfile, ImageUpvote, ImageComment, MinerAddress, ImageReaction
from django.core import serializers

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

# Gallery helper functions
def get_display_name_for_wallet(wallet_address):
    """Get appropriate display name for a wallet address"""
    if wallet_address.lower() == '0x708816d665eb09e5a86ba82a774dabb550bc8af5':
        return "Arbius Telegram Bot"
    else:
        return f"User {wallet_address[:8]}..."

def get_base_queryset(exclude_automine=False):
    """Get the base queryset for images with optimizations and filtering"""
    
    # Only allow the main image model - be very restrictive
    ALLOWED_MODELS = [
        '0xa473c70e9d7c872ac948d20546bc79db55fa64ca325a4b229aaffddb7f86aae0',  # Main image model only
    ]
    
    queryset = ArbiusImage.objects.select_related().prefetch_related('upvotes', 'comments').filter(
        is_accessible=True,  # Only show accessible images
        model_id__in=ALLOWED_MODELS  # Only allow whitelisted models
    )
    
    # Filter out automine images if requested
    if exclude_automine:
        # Get ALL identified miner addresses (both active and inactive)
        # Once a wallet is identified as a miner, it should always be filtered
        miner_wallets = list(MinerAddress.objects.all().values_list('wallet_address', flat=True))
        
        # Fallback to hardcoded list if no miners found in database yet
        if not miner_wallets:
            miner_wallets = [
                '0x5e33e2cead338b1224ddd34636dac7563f97c300',
                '0xdc790a53e50207861591622d349e989fef6f84bc',
                '0x4d826895b255a4f38d7ba87688604c358f4132b6',
                '0xd04c1b09576aa4310e4768d8e9cd12fac3216f95',
            ]
        
        queryset = queryset.exclude(task_submitter__in=miner_wallets)
    
    return queryset

def annotate_upvote_status(queryset, wallet_address):
    """Annotate queryset with upvote status for the given wallet address"""
    if not wallet_address:
        # If no wallet address, just add a False annotation
        return queryset.annotate(user_has_upvoted=Case(When(id__isnull=True, then=False), default=False, output_field=IntegerField()))
    
    # Annotate with whether the current user has upvoted each image
    return queryset.annotate(
        user_has_upvoted=Exists(
            ImageUpvote.objects.filter(
                image=OuterRef('pk'),
                wallet_address__iexact=wallet_address
            )
        )
    )

def get_available_models_with_categories():
    """Get available models organized by categories with restrictive filtering"""
    
    # Only allow the main image model
    ALLOWED_MODELS = [
        '0xa473c70e9d7c872ac948d20546bc79db55fa64ca325a4b229aaffddb7f86aae0',  # Main image model only
    ]
    
    # Get model stats only for allowed models
    all_models = ArbiusImage.objects.values('model_id').annotate(
        count=Count('id')
    ).filter(
        model_id__in=ALLOWED_MODELS,
        is_accessible=True
    ).order_by('-count')
    
    # Format the allowed models
    filtered_models = []
    for model in all_models:
        model_info = {
            'model_id': model['model_id'],
            'count': model['count'],
            'short_name': f"{model['model_id'][:8]}...{model['model_id'][-8:]}" if len(model['model_id']) > 16 else model['model_id']
        }
        filtered_models.append(model_info)
    
    # Simple categorization - all allowed models go to "Available"
    categorized = {'Available': filtered_models, 'Other': []}
    
    return filtered_models, categorized

def get_popular_keywords(exclude_automine=True, limit=20):
    """Get the most popular keywords from image prompts, excluding miner images"""
    from collections import Counter
    import re
    
    # Get base queryset
    queryset = get_base_queryset(exclude_automine=exclude_automine)
    
    # Get all prompts
    prompts = queryset.exclude(prompt__isnull=True).exclude(prompt='').values_list('prompt', flat=True)
    
    # Extract meaningful keywords (focus on nouns, proper nouns, and specific terms)
    keywords = []
    for prompt in prompts:
        # Clean the prompt
        clean_prompt = prompt.lower()
        
        # Remove the "Additional instruction" text that gets appended
        if "additional instruction:" in clean_prompt:
            clean_prompt = re.sub(r'additional instruction:.*?(?=\s|$)', '', clean_prompt, flags=re.IGNORECASE)
        
        # Extract words that are likely to be meaningful keywords
        # Look for capitalized words (proper nouns), words with underscores (tags), and specific patterns
        meaningful_words = []
        
        # Extract capitalized words (proper nouns like "Pikachu", "Dragon", etc.)
        capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', prompt)
        meaningful_words.extend(capitalized_words)
        
        # Extract words with underscores (common in AI art prompts like "blue_hair", "dragon_scale")
        underscore_words = re.findall(r'\b[a-z]+_[a-z]+\b', clean_prompt)
        meaningful_words.extend(underscore_words)
        
        # Extract specific character names and objects (look for patterns)
        # Common anime/game character patterns
        character_patterns = [
            r'\b(pikachu|charizard|bulbasaur|squirtle|misty|ash|goku|naruto|sasuke|link|zelda|mario|luigi|peach|bowser)\b',
            r'\b(dragon|phoenix|unicorn|griffin|dragon|wizard|witch|knight|princess|prince|queen|king)\b',
            r'\b(robot|cyborg|android|mecha|gundam|evangelion|transformers)\b',
            r'\b(cat|dog|wolf|fox|bear|tiger|lion|elephant|giraffe|penguin|owl|eagle)\b',
            r'\b(castle|tower|bridge|forest|mountain|ocean|desert|jungle|space|planet|star|moon|sun)\b',
            r'\b(sword|shield|bow|arrow|gun|laser|lightsaber|magic|spell|fire|ice|lightning|thunder)\b',
            r'\b(car|bike|plane|ship|spaceship|rocket|train|bus|helicopter)\b',
            r'\b(flower|tree|grass|leaf|rose|tulip|sunflower|cherry|apple|orange|banana)\b',
        ]
        
        for pattern in character_patterns:
            matches = re.findall(pattern, clean_prompt, re.IGNORECASE)
            meaningful_words.extend(matches)
        
        # Extract words that are 4+ characters and not common stop words
        # This catches other meaningful terms
        longer_words = re.findall(r'\b[a-z]{4,}\b', clean_prompt)
        stop_words = {'this', 'that', 'with', 'have', 'will', 'from', 'they', 'know', 'want', 'been', 'good', 'much', 'some', 'time', 'very', 'when', 'come', 'just', 'into', 'than', 'more', 'other', 'about', 'many', 'then', 'them', 'these', 'people', 'only', 'well', 'even', 'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first', 'over', 'think', 'also', 'your', 'could', 'would', 'there', 'their', 'what', 'said', 'each', 'which', 'she', 'do', 'how', 'if', 'will', 'up', 'out', 'many', 'then', 'them', 'these', 'so', 'some', 'her', 'would', 'make', 'like', 'into', 'him', 'time', 'has', 'two', 'more', 'go', 'no', 'way', 'could', 'my', 'than', 'first', 'been', 'call', 'who', 'its', 'now', 'find', 'long', 'down', 'day', 'did', 'get', 'come', 'made', 'may', 'part', 'over', 'new', 'sound', 'take', 'only', 'little', 'work', 'know', 'place', 'year', 'live', 'me', 'back', 'give', 'most', 'very', 'after', 'thing', 'our', 'just', 'name', 'good', 'sentence', 'man', 'think', 'say', 'great', 'where', 'help', 'through', 'much', 'before', 'line', 'right', 'too', 'mean', 'old', 'any', 'same', 'tell', 'boy', 'follow', 'came', 'want', 'show', 'also', 'around', 'form', 'three', 'small', 'set', 'put', 'end', 'does', 'another', 'well', 'large', 'must', 'big', 'even', 'such', 'because', 'turn', 'here', 'why', 'ask', 'went', 'men', 'read', 'need', 'land', 'different', 'home', 'us', 'move', 'try', 'kind', 'hand', 'picture', 'again', 'change', 'off', 'play', 'spell', 'air', 'away', 'animal', 'house', 'point', 'page', 'letter', 'mother', 'answer', 'found', 'study', 'still', 'learn', 'should', 'America', 'world', 'high', 'every', 'near', 'add', 'food', 'between', 'own', 'below', 'country', 'plant', 'last', 'school', 'father', 'keep', 'tree', 'never', 'start', 'city', 'earth', 'eye', 'light', 'thought', 'head', 'under', 'story', 'saw', 'left', 'don', 'few', 'while', 'along', 'might', 'close', 'something', 'seem', 'next', 'hard', 'open', 'example', 'begin', 'life', 'always', 'those', 'both', 'paper', 'together', 'got', 'group', 'often', 'run', 'important', 'until', 'children', 'side', 'feet', 'car', 'mile', 'night', 'walk', 'white', 'sea', 'began', 'grow', 'took', 'river', 'four', 'carry', 'state', 'once', 'book', 'hear', 'stop', 'without', 'second', 'late', 'miss', 'idea', 'enough', 'eat', 'face', 'watch', 'far', 'Indian', 'real', 'almost', 'let', 'above', 'girl', 'sometimes', 'mountain', 'cut', 'young', 'talk', 'soon', 'list', 'song', 'being', 'leave', 'family', 'it', 'body', 'music', 'color', 'stand', 'sun', 'questions', 'fish', 'area', 'mark', 'dog', 'horse', 'birds', 'problem', 'complete', 'room', 'knew', 'since', 'ever', 'piece', 'told', 'usually', 'didn', 'friends', 'easy', 'heard', 'order', 'red', 'door', 'sure', 'become', 'top', 'ship', 'across', 'today', 'during', 'short', 'better', 'best', 'however', 'low', 'hours', 'black', 'products', 'happened', 'whole', 'measure', 'remember', 'early', 'waves', 'reached', 'listen', 'wind', 'rock', 'space', 'covered', 'fast', 'several', 'hold', 'himself', 'toward', 'five', 'step', 'morning', 'passed', 'vowel', 'true', 'hundred', 'against', 'pattern', 'numeral', 'table', 'north', 'slowly', 'money', 'map', 'farm', 'pulled', 'draw', 'voice', 'seen', 'cold', 'cried', 'plan', 'notice', 'south', 'sing', 'war', 'ground', 'fall', 'king', 'town', 'I', 'unit', 'figure', 'certain', 'field', 'travel', 'wood', 'fire', 'upon'}
        meaningful_words.extend([word for word in longer_words if word not in stop_words])
        
        # Add to keywords list
        keywords.extend(meaningful_words)
    
    # Count and return most common
    keyword_counts = Counter(keywords)
    # Filter out very short keywords and return the most common ones
    meaningful_keywords = [(keyword, count) for keyword, count in keyword_counts.most_common(limit*2) 
                          if len(keyword) >= 3 and count >= 2]  # At least 3 chars and appears at least twice
    return [keyword for keyword, count in meaningful_keywords[:limit]]

# Create your views here.

def home(request):
    return render(request, 'home.html')

def playground(request):
    return render(request, 'playground.html')

# Gallery Views
def gallery_index(request):
    """Main gallery view with Web3 integration"""
    # Get filter parameters
    search_query = request.GET.get('q', '').strip()
    selected_task_submitter = request.GET.get('task_submitter', '').strip()
    selected_model = request.GET.get('model', '').strip()
    sort_by = request.GET.get('sort', 'upvotes')  # Default to most upvoted
    # Hide Automine ON by default for initial page loads
    # Check if this is a form submission (has any filter parameters) or initial load
    has_filter_params = bool(search_query or selected_task_submitter or selected_model or 
                           request.GET.get('sort') or 'exclude_automine' in request.GET)
    
    if has_filter_params:
        # This is a form submission - respect the checkbox state
        exclude_automine = request.GET.get('exclude_automine', '').lower() in ['true', '1', 'on']
    else:
        # Initial page load - default to True (Hide Automine ON)
        exclude_automine = True
    
    # Get current user's wallet address
    current_wallet_address = getattr(request, 'wallet_address', None)
    
    # Base queryset - now includes comprehensive filtering
    images = get_base_queryset(exclude_automine=exclude_automine)
    
    # Apply filters (existing logic)
    if search_query:
        images = images.filter(
            Q(prompt__icontains=search_query) |
            Q(cid__icontains=search_query) |
            Q(transaction_hash__icontains=search_query) |
            Q(task_id__icontains=search_query)
        )
    
    if selected_task_submitter:
        images = images.filter(task_submitter__iexact=selected_task_submitter)
    
    if selected_model:
        images = images.filter(model_id=selected_model)
    
    # Apply sorting
    if sort_by == 'upvotes':
        images = images.annotate(upvote_count_db=Count('upvotes')).order_by('-upvote_count_db', '-timestamp')
    elif sort_by == 'comments':
        images = images.annotate(comment_count_db=Count('comments')).order_by('-comment_count_db', '-timestamp')
    elif sort_by == 'newest':
        images = images.order_by('-timestamp')
    elif sort_by == 'oldest':
        images = images.order_by('timestamp')
    else:
        # Default fallback to most upvoted
        images = images.annotate(upvote_count_db=Count('upvotes')).order_by('-upvote_count_db', '-timestamp')
    
    # Annotate with upvote status for current user
    images = annotate_upvote_status(images, current_wallet_address)
    
    # Get available models with improved categorization
    available_models, model_categories = get_available_models_with_categories()
    
    # Get popular keywords (excluding miner images)
    popular_keywords = get_popular_keywords(exclude_automine=True, limit=15)
    
    # Pagination
    paginator = Paginator(images, 24)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'selected_task_submitter': selected_task_submitter,
        'selected_model': selected_model,
        'sort_by': sort_by,
        'exclude_automine': exclude_automine,
        'available_models': available_models,
        'model_categories': model_categories,
        'total_images': ArbiusImage.objects.filter(is_accessible=True).count(),  # Use filtered count
        'wallet_address': current_wallet_address,
        'user_profile': getattr(request, 'user_profile', None),
        'popular_keywords': popular_keywords,
    }
    return render(request, 'gallery/index.html', context)

def image_detail(request, image_id):
    """Detailed view for a single image"""
    image = get_object_or_404(ArbiusImage, id=image_id, is_accessible=True)
    
    # Get current user's wallet address
    current_wallet_address = getattr(request, 'wallet_address', None)
    
    # Check if user has upvoted this image
    user_has_upvoted = False
    if current_wallet_address:
        user_has_upvoted = image.has_upvoted(current_wallet_address)
    
    # Get comments for this image
    comments = image.comments.all().order_by('-created_at')
    
    context = {
        'image': image,
        'comments': comments,
        'user_has_upvoted': user_has_upvoted,
        'wallet_address': current_wallet_address,
        'user_profile': getattr(request, 'user_profile', None),
    }
    return render(request, 'gallery/image_detail.html', context)

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

# Gallery API Views
@csrf_exempt
@require_POST
def toggle_upvote(request, image_id):
    """Toggle upvote for an image"""
    try:
        # Get wallet address from session
        wallet_address = request.session.get('wallet_address')
        if not wallet_address:
            return JsonResponse({
                'success': False,
                'error': 'Wallet not connected'
            }, status=401)
        
        # Get the image
        image = get_object_or_404(ArbiusImage, id=image_id, is_accessible=True)
        
        # Check if user already upvoted
        existing_upvote = ImageUpvote.objects.filter(
            image=image,
            wallet_address__iexact=wallet_address
        ).first()
        
        if existing_upvote:
            # Remove upvote
            existing_upvote.delete()
            action = 'removed'
        else:
            # Add upvote
            ImageUpvote.objects.create(
                image=image,
                wallet_address=wallet_address
            )
            action = 'added'
        
        # Get updated counts
        upvote_count = image.upvote_count
        user_has_upvoted = image.has_upvoted(wallet_address)
        
        return JsonResponse({
            'success': True,
            'action': action,
            'upvote_count': upvote_count,
            'user_has_upvoted': user_has_upvoted
        })
        
    except Exception as e:
        logger.error(f"Error in toggle_upvote: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

@csrf_exempt
@require_POST
def add_comment(request, image_id):
    """Add a comment to an image"""
    try:
        # Get wallet address from session
        wallet_address = request.session.get('wallet_address')
        if not wallet_address:
            return JsonResponse({
                'success': False,
                'error': 'Wallet not connected'
            }, status=401)
        
        # Get the image
        image = get_object_or_404(ArbiusImage, id=image_id, is_accessible=True)
        
        # Get comment content
        data = json.loads(request.body)
        content = data.get('content', '').strip()
        
        if not content:
            return JsonResponse({
                'success': False,
                'error': 'Comment content is required'
            }, status=400)
        
        if len(content) > 1000:
            return JsonResponse({
                'success': False,
                'error': 'Comment too long (max 1000 characters)'
            }, status=400)
        
        # Create comment
        comment = ImageComment.objects.create(
            image=image,
            wallet_address=wallet_address,
            content=content
        )
        
        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'wallet_address': comment.wallet_address,
                'created_at': comment.created_at.isoformat(),
                'display_name': get_display_name_for_wallet(comment.wallet_address)
            }
        })
        
    except Exception as e:
        logger.error(f"Error in add_comment: {str(e)}")
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
                defaults={}
            )
            
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

@csrf_exempt
@require_POST
def toggle_reaction(request, image_id):
    """Toggle emoji reaction for an image"""
    try:
        # Get wallet address from session
        wallet_address = request.session.get('wallet_address')
        if not wallet_address:
            return JsonResponse({
                'success': False,
                'error': 'Wallet not connected'
            }, status=401)
        
        # Get the image
        image = get_object_or_404(ArbiusImage, id=image_id, is_accessible=True)
        
        # Get emoji from request
        data = json.loads(request.body)
        emoji = data.get('emoji', '')
        
        # Validate emoji
        valid_emojis = [choice[0] for choice in ImageReaction.EMOJI_CHOICES]
        if emoji not in valid_emojis:
            return JsonResponse({
                'success': False,
                'error': 'Invalid emoji'
            }, status=400)
        
        # Check if user already reacted with this emoji
        existing_reaction = ImageReaction.objects.filter(
            image=image,
            wallet_address__iexact=wallet_address,
            emoji=emoji
        ).first()
        
        if existing_reaction:
            # Remove reaction
            existing_reaction.delete()
            action = 'removed'
        else:
            # Add reaction
            ImageReaction.objects.create(
                image=image,
                wallet_address=wallet_address,
                emoji=emoji
            )
            action = 'added'
        
        # Get updated reactions
        reactions = image.reactions
        
        return JsonResponse({
            'success': True,
            'action': action,
            'reactions': reactions
        })
        
    except Exception as e:
        logger.error(f"Error in toggle_reaction: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

def gallery_images_api(request):
    """API endpoint for infinite scroll: returns a page of images as JSON"""
    search_query = request.GET.get('q', '').strip()
    selected_task_submitter = request.GET.get('task_submitter', '').strip()
    selected_model = request.GET.get('model', '').strip()
    sort_by = request.GET.get('sort', 'upvotes')
    exclude_automine = request.GET.get('exclude_automine', '').lower() in ['true', '1', 'on']  # Default to False
    
    # Get base queryset with filtering
    images = get_base_queryset(exclude_automine=exclude_automine)
    
    # Apply filters
    if search_query:
        images = images.filter(
            Q(prompt__icontains=search_query) |
            Q(cid__icontains=search_query) |
            Q(transaction_hash__icontains=search_query) |
            Q(task_id__icontains=search_query)
        )
    
    if selected_task_submitter:
        images = images.filter(task_submitter__iexact=selected_task_submitter)
    
    if selected_model:
        images = images.filter(model_id=selected_model)
    
    # Apply sorting
    if sort_by == 'upvotes':
        images = images.annotate(upvote_count_db=Count('upvotes')).order_by('-upvote_count_db', '-timestamp')
    elif sort_by == 'comments':
        images = images.annotate(comment_count_db=Count('comments')).order_by('-comment_count_db', '-timestamp')
    elif sort_by == 'newest':
        images = images.order_by('-timestamp')
    elif sort_by == 'oldest':
        images = images.order_by('timestamp')
    else:
        images = images.annotate(upvote_count_db=Count('upvotes')).order_by('-upvote_count_db', '-timestamp')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(images, 20)  # 20 images per page
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    # Serialize images
    images_data = []
    for image in page_obj:
        images_data.append({
            'id': image.id,
            'transaction_hash': image.transaction_hash,
            'task_id': image.task_id,
            'cid': image.cid,
            'ipfs_url': image.ipfs_url,
            'image_url': image.image_url,
            'prompt': image.prompt,
            'model_id': image.model_id,
            'task_submitter': image.task_submitter,
            'solution_provider': image.solution_provider,
            'timestamp': image.timestamp.isoformat(),
            'upvote_count': image.upvotes.count(),
            'comment_count': image.comments.count(),
            'is_upvoted': image.upvotes.filter(wallet_address=getattr(request, 'wallet_address', None)).exists(),
            'reactions': image.reactions,
        })
    
    return JsonResponse({
        'images': images_data,
        'has_next': page_obj.has_next(),
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        'total_pages': paginator.num_pages,
        'total_count': paginator.count,
    })


def stats_dashboard(request):
    """Live Statistics Dashboard - shows image generation and user activity stats"""
    from django.db.models import Count, Q
    from django.db.models.functions import TruncDate
    from datetime import datetime, timedelta
    import json
    
    # Get current user's wallet address
    current_wallet_address = getattr(request, 'wallet_address', None)
    
    # Calculate time periods
    now = timezone.now()
    one_week_ago = now - timedelta(days=7)
    one_day_ago = now - timedelta(days=1)
    
    # Get base queryset (accessible images only)
    base_queryset = get_base_queryset(exclude_automine=False)
    
    # Calculate statistics
    total_images = base_queryset.count()
    images_week = base_queryset.filter(timestamp__gte=one_week_ago).count()
    images_24h = base_queryset.filter(timestamp__gte=one_day_ago).count()
    
    # Unique users (task submitters)
    unique_users = base_queryset.values('task_submitter').distinct().count()
    users_week = base_queryset.filter(timestamp__gte=one_week_ago).values('task_submitter').distinct().count()
    
    # Unique models
    unique_models = base_queryset.values('model_id').distinct().count()
    
    # Get cumulative images over time data (last 30 days)
    thirty_days_ago = now - timedelta(days=30)
    cumulative_data = []
    
    # Get daily counts for the last 30 days
    daily_counts = base_queryset.filter(
        timestamp__gte=thirty_days_ago
    ).annotate(
        date=TruncDate('timestamp')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Create cumulative data
    cumulative_count = 0
    for day_data in daily_counts:
        cumulative_count += day_data['count']
        cumulative_data.append({
            'date': day_data['date'].strftime('%m/%d'),
            'count': cumulative_count
        })
    
    # Get daily images for last 25 days
    twenty_five_days_ago = now - timedelta(days=25)
    daily_images_data = []
    
    daily_images = base_queryset.filter(
        timestamp__gte=twenty_five_days_ago
    ).annotate(
        date=TruncDate('timestamp')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Create daily images data
    for day_data in daily_images:
        daily_images_data.append({
            'date': day_data['date'].strftime('%m/%d'),
            'count': day_data['count']
        })
    
    context = {
        'total_images': total_images,
        'images_week': images_week,
        'images_24h': images_24h,
        'unique_users': unique_users,
        'users_week': users_week,
        'unique_models': unique_models,
        'cumulative_data': json.dumps(cumulative_data),
        'daily_images_data': json.dumps(daily_images_data),
        'wallet_address': current_wallet_address,
        'user_profile': getattr(request, 'user_profile', None),
    }
    
    return render(request, 'playground/stats_dashboard.html', context)
