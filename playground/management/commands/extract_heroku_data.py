from django.core.management.base import BaseCommand
from django.conf import settings
import psycopg2
import os
from playground.models import ArbiusImage, MinerAddress, UserProfile, ImageUpvote, ImageComment
from django.utils import timezone
from datetime import datetime
import json

class Command(BaseCommand):
    help = 'Extract data from Heroku PostgreSQL database and import to local database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--heroku-db-url',
            type=str,
            help='Heroku PostgreSQL database URL (e.g., postgresql://user:pass@host:port/db)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )

    def handle(self, *args, **options):
        heroku_db_url = options['heroku_db_url']
        dry_run = options['dry_run']
        
        if not heroku_db_url:
            self.stdout.write(
                self.style.ERROR('Please provide --heroku-db-url parameter')
            )
            return
        
        if dry_run:
            self.stdout.write('DRY RUN MODE - No data will be imported')
        
        try:
            # Connect to Heroku database
            self.stdout.write('Connecting to Heroku database...')
            conn = psycopg2.connect(heroku_db_url)
            cursor = conn.cursor()
            
            # Extract data from Heroku
            self.extract_miner_addresses(cursor, dry_run)
            self.extract_arbius_images(cursor, dry_run)
            self.extract_user_profiles(cursor, dry_run)
            self.extract_image_upvotes(cursor, dry_run)
            self.extract_image_comments(cursor, dry_run)
            
            if not dry_run:
                self.stdout.write(
                    self.style.SUCCESS('Successfully extracted all data from Heroku!')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('Dry run completed - check the output above')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error connecting to Heroku database: {str(e)}')
            )
        finally:
            if 'conn' in locals():
                conn.close()

    def extract_miner_addresses(self, cursor, dry_run):
        """Extract miner addresses from Heroku database"""
        self.stdout.write('Extracting miner addresses...')
        
        cursor.execute("""
            SELECT wallet_address, first_seen, last_seen, total_solutions, 
                   total_commitments, is_active
            FROM gallery_mineraddress
        """)
        
        miners = cursor.fetchall()
        self.stdout.write(f'Found {len(miners)} miner addresses')
        
        if not dry_run:
            for miner_data in miners:
                wallet_address, first_seen, last_seen, total_solutions, total_commitments, is_active = miner_data
                
                MinerAddress.objects.get_or_create(
                    wallet_address=wallet_address,
                    defaults={
                        'first_seen': first_seen or timezone.now(),
                        'last_seen': last_seen or timezone.now(),
                        'total_solutions': total_solutions or 0,
                        'total_commitments': total_commitments or 0,
                        'is_active': is_active if is_active is not None else True,
                    }
                )

    def extract_arbius_images(self, cursor, dry_run):
        """Extract Arbius images from Heroku database"""
        self.stdout.write('Extracting Arbius images...')
        
        cursor.execute("""
            SELECT transaction_hash, task_id, block_number, timestamp, cid, ipfs_url, 
                   image_url, model_id, prompt, input_parameters, solution_provider, 
                   task_submitter, miner_address, owner_address, gas_used, discovered_at, 
                   is_accessible, last_checked, ipfs_gateway
            FROM gallery_arbiusimage
        """)
        
        images = cursor.fetchall()
        self.stdout.write(f'Found {len(images)} images')
        
        if not dry_run:
            for image_data in images:
                (transaction_hash, task_id, block_number, timestamp, cid, ipfs_url, 
                 image_url, model_id, prompt, input_parameters, solution_provider, 
                 task_submitter, miner_address, owner_address, gas_used, discovered_at, 
                 is_accessible, last_checked, ipfs_gateway) = image_data
                
                # Parse input_parameters if it's a string
                if input_parameters and isinstance(input_parameters, str):
                    try:
                        input_parameters = json.loads(input_parameters)
                    except:
                        input_parameters = {}
                
                ArbiusImage.objects.get_or_create(
                    transaction_hash=transaction_hash,
                    defaults={
                        'task_id': task_id,
                        'block_number': block_number or 0,
                        'timestamp': timestamp or timezone.now(),
                        'cid': cid,
                        'ipfs_url': ipfs_url,
                        'image_url': image_url,
                        'model_id': model_id,
                        'prompt': prompt,
                        'input_parameters': input_parameters or {},
                        'solution_provider': solution_provider or '0x0000000000000000000000000000000000000000',
                        'task_submitter': task_submitter,
                        'miner_address': miner_address,
                        'owner_address': owner_address,
                        'gas_used': gas_used,
                        'discovered_at': discovered_at or timezone.now(),
                        'is_accessible': is_accessible if is_accessible is not None else True,
                        'last_checked': last_checked or timezone.now(),
                        'ipfs_gateway': ipfs_gateway or '',
                    }
                )

    def extract_user_profiles(self, cursor, dry_run):
        """Extract user profiles from Heroku database"""
        self.stdout.write('Extracting user profiles...')
        
        cursor.execute("""
            SELECT wallet_address, display_name, bio, avatar_url, website, 
                   twitter_handle, total_images_created, total_upvotes_received, 
                   created_at, updated_at
            FROM gallery_userprofile
        """)
        
        profiles = cursor.fetchall()
        self.stdout.write(f'Found {len(profiles)} user profiles')
        
        if not dry_run:
            for profile_data in profiles:
                (wallet_address, display_name, bio, avatar_url, website, 
                 twitter_handle, total_images_created, total_upvotes_received, 
                 created_at, updated_at) = profile_data
                
                UserProfile.objects.get_or_create(
                    wallet_address=wallet_address,
                    defaults={
                        'display_name': display_name,
                        'bio': bio,
                        'avatar_url': avatar_url,
                        'website': website,
                        'twitter_handle': twitter_handle,
                        'total_images_created': total_images_created or 0,
                        'total_upvotes_received': total_upvotes_received or 0,
                        'created_at': created_at or timezone.now(),
                    }
                )

    def extract_image_upvotes(self, cursor, dry_run):
        """Extract image upvotes from Heroku database"""
        self.stdout.write('Extracting image upvotes...')
        
        cursor.execute("""
            SELECT image_id, wallet_address, created_at
            FROM gallery_imageupvote
        """)
        
        upvotes = cursor.fetchall()
        self.stdout.write(f'Found {len(upvotes)} upvotes')
        
        if not dry_run:
            for upvote_data in upvotes:
                image_id, wallet_address, created_at = upvote_data
                
                try:
                    image = ArbiusImage.objects.get(id=image_id)
                    ImageUpvote.objects.get_or_create(
                        image=image,
                        wallet_address=wallet_address,
                        defaults={
                            'created_at': created_at or timezone.now(),
                        }
                    )
                except ArbiusImage.DoesNotExist:
                    self.stdout.write(f'Warning: Image {image_id} not found, skipping upvote')

    def extract_image_comments(self, cursor, dry_run):
        """Extract image comments from Heroku database"""
        self.stdout.write('Extracting image comments...')
        
        cursor.execute("""
            SELECT image_id, wallet_address, content, created_at, updated_at
            FROM gallery_imagecomment
        """)
        
        comments = cursor.fetchall()
        self.stdout.write(f'Found {len(comments)} comments')
        
        if not dry_run:
            for comment_data in comments:
                image_id, wallet_address, content, created_at, updated_at = comment_data
                
                try:
                    image = ArbiusImage.objects.get(id=image_id)
                    ImageComment.objects.get_or_create(
                        image=image,
                        wallet_address=wallet_address,
                        content=content,
                        defaults={
                            'created_at': created_at or timezone.now(),
                        }
                    )
                except ArbiusImage.DoesNotExist:
                    self.stdout.write(f'Warning: Image {image_id} not found, skipping comment') 