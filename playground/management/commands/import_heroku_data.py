from django.core.management.base import BaseCommand
import requests
import tempfile
import os
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Download and import gallery data from GitHub to Heroku'

    def handle(self, *args, **options):
        self.stdout.write('Downloading gallery data from GitHub...')
        
        # Download the data file from GitHub
        url = 'https://raw.githubusercontent.com/svdl1185/arbius_playground/main/gallery_data.json'
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(response.text)
                temp_file = f.name
            
            self.stdout.write(f'Data downloaded to {temp_file}')
            self.stdout.write(f'File size: {len(response.text)} characters')
            
            # Load the data
            self.stdout.write('Loading data into database...')
            call_command('loaddata', temp_file)
            
            # Clean up
            os.unlink(temp_file)
            
            self.stdout.write(self.style.SUCCESS('Successfully imported gallery data!'))
            
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Failed to download data: {e}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to load data: {e}')) 