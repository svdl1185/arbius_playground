# Automated Gallery Updates & Stats Dashboard Setup

This guide explains how to set up automated gallery updates and the stats dashboard for the Arbius Playground.

## 🎯 Features Integrated

### 1. Stats Dashboard (`/dashboard/`)
- **Live Statistics**: View image generation and user activity statistics
- **Real-time Data**: Live metrics including total images, users, and models
- **Interactive Charts**: Cumulative images over time and daily image generation
- **Clean Design**: Matches the playground's modern UI with dark theme

### 2. Automated Gallery Updates
- **Blockchain Scanning**: Automatically scan for new Arbius images
- **Miner Detection**: Identify and track miner wallet addresses
- **IPFS Monitoring**: Check image accessibility and update status
- **Scheduled Updates**: Run every 5 minutes via Heroku Scheduler

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install web3 requests
```

### 2. Configure Blockchain Settings
Update the contract addresses in `playground/services.py`:
```python
# Replace with actual Arbius contract addresses
self.ENGINE_CONTRACT = '0x...'  # Arbius engine contract
self.TASK_CONTRACT = '0x...'    # Arbius task contract
```

### 3. Run Initial Setup
```bash
# Initial blockchain scan
python manage.py scan_arbius --blocks 1000

# Identify miners
python manage.py identify_miners --initial-scan

# Analyze miner tokens (optional)
python manage.py analyze_miner_tokens --all
```

## ⏰ Automated Updates Setup

### Option 1: Heroku Scheduler (Recommended)

1. **Install Heroku Scheduler**:
```bash
heroku addons:create scheduler:standard --app your-app-name
heroku addons:open scheduler --app your-app-name
```

2. **Add Scheduled Jobs**:
```bash
# Gallery updates (every 5 minutes)
python manage.py scan_arbius --minutes 10 --quiet

# Miner identification (every hour)
python manage.py identify_miners --hours 1 --quiet

# Token analysis (daily)
python manage.py analyze_miner_tokens --all --quiet
```

### Option 2: GitHub Actions (Free, 1-minute intervals)

1. **Create `.github/workflows/gallery-updates.yml`**:
```yaml
name: Gallery Updates
on:
  schedule:
    - cron: '*/5 * * * *'  # Every 5 minutes
  workflow_dispatch:  # Manual trigger

jobs:
  update-gallery:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Heroku
        uses: akhileshns/heroku-deploy@v3.12.14
        with:
          heroku_api_key: ${{ secrets.HEROKU_API_KEY }}
          heroku_app_name: ${{ secrets.HEROKU_APP_NAME }}
          heroku_email: ${{ secrets.HEROKU_EMAIL }}
          run_cmd: "python manage.py scan_arbius --minutes 10 --quiet"
```

2. **Add Repository Secrets**:
   - `HEROKU_API_KEY`: Your Heroku API token
   - `HEROKU_APP_NAME`: Your Heroku app name
   - `HEROKU_EMAIL`: Your Heroku email

### Option 3: Local Cron Jobs

1. **Create a script** (`update_gallery.sh`):
```bash
#!/bin/bash
cd /path/to/arbius_playground
python manage.py scan_arbius --minutes 10 --quiet
python manage.py identify_miners --hours 1 --quiet
```

2. **Add to crontab**:
```bash
# Edit crontab
crontab -e

# Add these lines:
*/5 * * * * /path/to/update_gallery.sh >> /var/log/gallery_updates.log 2>&1
0 * * * * cd /path/to/arbius_playground && python manage.py analyze_miner_tokens --all --quiet >> /var/log/token_analysis.log 2>&1
```

## 🔧 Management Commands

### Gallery Scanning
```bash
# Scan recent blocks
python manage.py scan_arbius --blocks 1000

# Scan recent minutes (for prompts only)
python manage.py scan_arbius --minutes 10

# Deep scan for missed images
python manage.py scan_arbius --deep-scan

# Quiet mode for automation
python manage.py scan_arbius --quiet
```

### Miner Identification
```bash
# Regular hourly scan
python manage.py identify_miners --hours 1

# Initial 24-hour scan
python manage.py identify_miners --initial-scan

# Mark inactive miners
python manage.py identify_miners --mark-inactive

# Quiet mode
python manage.py identify_miners --quiet
```

### Token Analysis
```bash
# Analyze all miners
python manage.py analyze_miner_tokens --all

# Analyze specific miner
python manage.py analyze_miner_tokens --miner 0x...

# Force reanalysis
python manage.py analyze_miner_tokens --all --force

# Quiet mode
python manage.py analyze_miner_tokens --all --quiet
```

## 📊 Stats Dashboard Features

### Key Metrics
- **Total Images**: Complete count of all generated images
- **Images (Week)**: Images generated in the last 7 days
- **New (24H)**: Images generated in the last 24 hours
- **Unique Users**: Total number of unique task submitters
- **Users (Week)**: Unique users active in the last 7 days
- **Models**: Number of unique AI models used

### Interactive Charts
- **Cumulative Images Over Time**: Line chart showing total image growth over 30 days
- **Daily Images (Last 25 Days)**: Bar chart showing daily image generation activity

### Real-time Updates
- **Live Data**: Statistics update automatically as new images are scanned
- **Responsive Design**: Works seamlessly on desktop and mobile devices

## 🔍 Monitoring & Troubleshooting

### Check Automation Status
```bash
# Check recent scans
python manage.py shell -c "
from playground.models import ArbiusImage;
latest = ArbiusImage.objects.order_by('-discovered_at').first();
print(f'Latest image: {latest.discovered_at if latest else \"None\"}');
print(f'Total images: {ArbiusImage.objects.count()}');
"

# Check miner database
python manage.py shell -c "
from playground.models import MinerAddress;
total = MinerAddress.objects.count();
active = MinerAddress.objects.filter(is_active=True).count();
print(f'Miners: {total} total, {active} active');
"
```

### Common Issues

#### **Scanner Not Finding Images**
- Check contract addresses in `services.py`
- Verify Web3 connection to Arbitrum
- Check for blockchain API rate limits

#### **Miner Detection Not Working**
- Run initial scan: `python manage.py identify_miners --initial-scan`
- Check miner database: `MinerAddress.objects.count()`
- Verify automine filter is working

#### **Token Analysis Issues**
- Run analysis: `python manage.py analyze_miner_tokens --all`
- Check earnings data: `MinerTokenEarnings.objects.count()`
- Verify blockchain token contract addresses

#### **Scheduler Not Running**
- Check Heroku logs: `heroku logs --tail --app your-app-name`
- Verify scheduler add-on is installed
- Test commands manually on Heroku

## 🎨 Customization

### Update Scanning Frequency
- **Frequent Updates**: Change cron to `*/2 * * * *` (every 2 minutes)
- **Less Frequent**: Change to `*/10 * * * *` (every 10 minutes)

### Add More Analytics
- Extend `stats_dashboard` view in `views.py`
- Add new metrics to the dashboard template
- Create additional management commands

### Custom Blockchain Integration
- Update contract addresses in `services.py`
- Modify transaction parsing logic
- Add support for additional networks

## 📈 Performance Optimization

### Database Indexing
```sql
-- Add indexes for better performance
CREATE INDEX idx_arbius_image_timestamp ON playground_arbiusimage(timestamp);
CREATE INDEX idx_arbius_image_solution_provider ON playground_arbiusimage(solution_provider);
CREATE INDEX idx_miner_address_wallet ON playground_mineraddress(wallet_address);
```

### Caching
```python
# Add Redis caching for expensive queries
from django.core.cache import cache

# Cache miner statistics for 5 minutes
cache_key = f"miner_stats_{miner_address}"
cached_stats = cache.get(cache_key)
if not cached_stats:
    cached_stats = calculate_miner_stats(miner_address)
    cache.set(cache_key, cached_stats, 300)
```

### Rate Limiting
- Implement API rate limiting for blockchain calls
- Use multiple RPC endpoints for redundancy
- Add exponential backoff for failed requests

## 🔒 Security Considerations

### API Keys
- Store blockchain API keys in environment variables
- Use Heroku config vars for sensitive data
- Rotate API keys regularly

### Access Control
- Stats dashboard is publicly accessible (consider adding auth)
- Monitor for unusual scanning activity
- Implement request rate limiting

### Data Validation
- Validate all blockchain data before saving
- Sanitize user inputs in management commands
- Add error handling for malformed transactions

## 📞 Support

For issues with automated updates:
1. Check Heroku logs: `heroku logs --tail`
2. Test commands locally first
3. Verify blockchain connectivity
4. Check database for corrupted data

The automated system will keep your gallery fresh and provide comprehensive mining analytics! 