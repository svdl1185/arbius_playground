from django.core.management.base import BaseCommand
from django.core.management import call_command
import requests
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Import real gallery data from GitHub JSON file'

    def handle(self, *args, **options):
        self.stdout.write('Downloading and importing real gallery data...')
        
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
            
            self.stdout.write(self.style.SUCCESS('Successfully imported real gallery data!'))
            
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Failed to download data: {e}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to load data: {e}')) 