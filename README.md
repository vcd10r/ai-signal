# 🤖 Institutional AI Trading Bot - Binance Futures

Advanced 24/7 automated trading bot for Binance Futures with machine learning, risk management, and professional features.

## 🚀 Features

### Core Trading

- ✅ **LONG & SHORT** trading (profit from both directions)
- ✅ **Multi-timeframe** confirmation (1H + 4H alignment)
- ✅ **Market orders** (instant execution, 0.04% fee)
- ✅ **Dynamic position sizing** (risk-based allocation)
- ✅ **Trailing stop loss** (maximize winning trades)
- ✅ **70.57% accuracy** ML model (LightGBM, Dec 29 2025)
- ✅ **Interactive setup** (leverage & risk selection every startup)

### Risk Management

- ✅ Stop Loss: 2% per trade
- ✅ Take Profit: 4% per trade (1:2 RR ratio)
- ✅ Interactive leverage selector (1x, 3x, 5x, 10x, 20x)
- ✅ Dynamic risk % selector (1-20% per trade)
- ✅ Max 2 concurrent positions
- ✅ Real-time margin calculation

### Professional Tools

- ✅ **Real-time display** (1-second refresh, live monitoring)
- ✅ **Live P&L tracking** (session & total with statistics)
- ✅ **Portfolio analytics** (win rate, best/worst trades)
- ✅ **SQLite database** (trade history)
- ✅ **CSV export** (tax reporting)
- ✅ **Auto-retrain** (every 7 days)
- ✅ **Model backups** (automatic versioning)
- ✅ **Complete transparency** (see ALL signals)
- ✅ **First-time setup wizard** (easy API configuration)
- ✅ **Bull market optimized** (180 days training data)

---

## � GitHub Setup (First Time)

### 1. Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `ai-trading-bot` (or your choice)
3. Description: "AI-powered crypto trading bot with 70%+ accuracy"
4. ✅ Public (or Private if you prefer)
5. ❌ Do NOT initialize with README (we already have one)
6. Click "Create repository"

### 2. Push Code to GitHub

```bash
# Navigate to your bot folder
cd C:\Users\SURYA\OneDrive\Desktop\iyyah\ai-signal

# Initialize git (if not already)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Production-ready AI trading bot"

# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/ai-trading-bot.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### 3. Verify Upload

Go to `https://github.com/YOUR_USERNAME/ai-trading-bot` and verify:

- ✅ README.md displays properly
- ✅ api_config.txt is NOT visible (protected by .gitignore)
- ✅ All code files present
- ✅ requirements.txt included

### 4. Update README URLs

After uploading, edit README.md and replace `YOUR_USERNAME` with your actual GitHub username:

```bash
# Find and replace
YOUR_USERNAME → actual_username
```

---

## �📦 Installation

### Prerequisites

- Python 3.8+
- Binance Futures account
- API keys with futures trading enabled

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-trading-bot.git
cd ai-trading-bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. First Run (Interactive Setup)

On first run, bot will guide you through setup:

```bash
python trading_bot_24_7.py

# Bot will ask:
# 1. Binance API Key
# 2. Binance API Secret
# 3. Risk per trade (1-5% recommended)
# 4. Min confidence (default 65%)
# 5. Max positions (default 2)
# 6. Trading symbols (default BTC/USDC, ETH/USDC)
```

**Or manually configure:**

```bash
# Copy example config
cp api_config.txt.example api_config.txt

# Edit with your API keys
nano api_config.txt  # or any text editor
```

**api_config.txt:**

```ini
# Binance API Configuration
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# Risk Management
RISK_PER_TRADE_PCT=2.0          # 2% risk per trade dari total portfolio

# Trading Configuration
MIN_CONFIDENCE=0.65             # 65% minimum confidence (0.40 = 40%, 0.65 = 65%)
MAX_POSITIONS=2                 # Maximum 2 concurrent positions
STOP_LOSS_PCT=0.02              # 2% stop loss per trade
TAKE_PROFIT_PCT=0.04            # 4% take profit per trade
CHECK_INTERVAL=300              # Check every 300 seconds (5 minutes)

# Symbols (comma-separated, no spaces)
SYMBOLS=BTC/USDC,ETH/USDC
```

⚠️ **IMPORTANT**:

- Enable **Futures Trading** on your API key
- Whitelist your VPS IP address
- **NEVER commit api_config.txt to git!**

---

## 🎯 Quick Start

### Run Bot

```bash
python trading_bot_24_7.py

# Interactive prompts every startup:
# 1. Select leverage (1x-20x)
# 2. Select risk per trade (1-20%)
```

**Recommendations:**

- **Conservative:** 1-3x leverage, 1-2% risk (safe, slow growth)
- **Moderate:** 3-5x leverage, 2-3% risk (balanced)
- **Aggressive:** 5-10x leverage, 3-5% risk (bull market strategy)

Bot will display ALL signals and execute only profitable ones!

---

## 📊 Output Example

```
================================================================================
 🤖 AI TRADING BOT - LIVE [2025-12-29 15:45:32]
================================================================================

[BALANCE]
  Portfolio: $77.32 (Initial: $70.32)
  Free: $77.32 (100.0% available)

[PORTFOLIO PERFORMANCE]
  📈 Total P&L: +$7.00 (+9.96%)
  💵 Session P&L: +$7.00
  🎯 Total Trades: 1
  ✅ Win Rate: 100.0% (1W/0L)
  💰 Best Trade: +$7.00
  📈 Avg Win: +$7.00

[RISK MANAGEMENT]
  Risk per Trade: 5.0% → $3.87 max loss
  Position Size: $193.50 (exposure)
  Margin Required: $19.35 (25.0% of portfolio)
  Stop Loss: 2.0% → $3.87 loss if hit
  Leverage: 10x
  Max Buying Power: $773.20 (all-in)

[MONITOR] No open positions

[SCAN] Scanning for signals...

[SIGNALS] Found 1 signal(s):
  ⭐ HIGH PRIORITY BTC/USDC: 72.3% - High confidence (72.3%) LONG
    Price: $90234.50 | Buy: 72% | Sell: 28%
    SL: $88429.81 | TP: $93843.78
    MTF: 1H=N/A, 4H=N/A, Strength=N/A

[EXECUTION] Processing executable signals...
  ✓ Executing: BTC/USDC (72.3%)

[TRADE] Executing LONG BUY for BTC/USDC
  Priority: ⭐ HIGH
  Entry Price: $90234.50
  Amount: 0.00214
  Position Size: $193.50 (exposure)
  Margin Required: $19.35 (25.0% of portfolio)
  Risk Amount: $3.87 (5% of portfolio)
  Leverage: 10x
  Confidence: 72.3%
  Order Type: MARKET (instant execution)
[FILLED] Order executed at $90245.12
[SUCCESS] Position opened: LONG BTC/USDC

# Screen refreshes every 1 second with live price updates!

[POSITION] LONG BTC/USDC: $90789.34 | P&L: +0.60% (+$1.16)

[TRAILING SL] BTC/USDC: $88429.81 → $88973.55 (Locked 0.60% profit)

[CLOSED] LONG BTC/USDC - TAKE_PROFIT
  Entry: $90245.12
  Exit: $93855.13
  Trade P&L: +$7.72 (+4.00% of position)
  Portfolio Impact: +10.98% (from $70.32 initial)
  New Balance: $85.04
  Session Total P&L: +$14.72
```

**Real-time Features:**

- ✅ Display updates every 1 second
- ✅ Live position P&L tracking
- ✅ Portfolio performance statistics
- ✅ No cycle spam (clean interface)

---

## 🛠️ VPS Setup (Ubuntu 22.04 LTS)

### Step-by-Step Installation

#### 1. Update System

```bash
sudo apt update && sudo apt upgrade -y
```

#### 2. Install Python 3.10+ and Dependencies

```bash
# Install Python and essential tools
sudo apt install -y python3 python3-pip python3-venv git screen htop

# Verify Python version (should be 3.10+)
python3 --version
```

#### 3. Clone Repository

```bash
# Clone from GitHub
git clone https://github.com/YOUR_USERNAME/ai-trading-bot.git
cd ai-trading-bot

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
```

#### 4. Install Python Packages

```bash
# Upgrade pip first
pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt
```

#### 5. Configure Trading Bot

```bash
# Copy config example
cp api_config.txt.example api_config.txt

# Edit config with your API keys
nano api_config.txt
```

**Enter your Binance API credentials:**

```ini
BINANCE_API_KEY=your_actual_api_key_here
BINANCE_API_SECRET=your_actual_secret_here
RISK_PER_TRADE_PCT=2.0
MIN_CONFIDENCE=0.65
# ... other settings
```

**Save:** `Ctrl+O`, Enter, `Ctrl+X`

#### 6. Test Run

```bash
# Test bot (will ask for leverage and risk)
python3 trading_bot_24_7.py

# If successful, press Ctrl+C to stop
```

---

### 🚀 Run Bot 24/7 (3 Methods)

#### **Method 1: Screen (Recommended for Beginners)**

```bash
# Start new screen session
screen -S trading-bot

# Activate venv and run bot
cd ~/ai-trading-bot
source venv/bin/activate
python3 trading_bot_24_7.py

# Detach from screen: Ctrl+A then D
```

**Useful Commands:**

```bash
# List all screens
screen -ls

# Reattach to bot
screen -r trading-bot

# Kill screen session
screen -X -S trading-bot quit
```

#### **Method 2: Systemd Service (Auto-restart on crash)**

Create service file:

```bash
sudo nano /etc/systemd/system/trading-bot.service
```

**Content:**

```ini
[Unit]
Description=AI Trading Bot
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/ai-trading-bot
Environment="PATH=/home/YOUR_USERNAME/ai-trading-bot/venv/bin"
ExecStart=/home/YOUR_USERNAME/ai-trading-bot/venv/bin/python3 trading_bot_24_7.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Replace `YOUR_USERNAME` with your actual username!**

**Enable and Start:**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable trading-bot

# Start service
sudo systemctl start trading-bot

# Check status
sudo systemctl status trading-bot

# View logs
sudo journalctl -u trading-bot -f
```

**Manage Service:**

```bash
# Stop bot
sudo systemctl stop trading-bot

# Restart bot
sudo systemctl restart trading-bot

# Disable auto-start
sudo systemctl disable trading-bot
```

#### **Method 3: tmux (Alternative to Screen)**

```bash
# Install tmux
sudo apt install tmux -y

# Start tmux session
tmux new -s trading

# Run bot
cd ~/ai-trading-bot
source venv/bin/activate
python3 trading_bot_24_7.py

# Detach: Ctrl+B then D
# Reattach: tmux attach -t trading
```

---

### 📊 Monitoring

#### Check Bot Status

```bash
# If using screen
screen -r trading-bot

# If using systemd
sudo systemctl status trading-bot
sudo journalctl -u trading-bot -f --lines 100

# Check logs file
tail -f ~/ai-trading-bot/trading_bot_24_7.log
```

#### Check System Resources

```bash
# CPU and memory usage
htop

# Disk space
df -h

# Python processes
ps aux | grep python
```

#### Check Trade Database

```bash
cd ~/ai-trading-bot
sqlite3 trades.db

# SQL queries
SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10;
SELECT COUNT(*), SUM(pnl) FROM trades;
SELECT COUNT(*) as wins FROM trades WHERE pnl > 0;
.quit
```

---

### 🔧 Troubleshooting Ubuntu

#### Port Issues

```bash
# Check if port 443 is open (Binance API)
sudo ufw status
sudo ufw allow 443/tcp
```

#### Time Sync Issues

```bash
# Install NTP
sudo apt install ntp -y

# Sync time
sudo ntpdate pool.ntp.org

# Enable automatic time sync
sudo timedatectl set-ntp true
```

#### Permission Issues

```bash
# Fix file permissions
cd ~/ai-trading-bot
chmod +x trading_bot_24_7.py
chmod 600 api_config.txt  # Secure config file
```

#### Memory Issues (Low RAM VPS)

```bash
# Create swap file (2GB)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

### 🔄 Update Bot

```bash
# Navigate to repo
cd ~/ai-trading-bot

# Stop bot first (if using systemd)
sudo systemctl stop trading-bot

# Pull latest changes
git pull origin main

# Update dependencies
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Restart bot
sudo systemctl start trading-bot
```

---

### 🔒 Security Best Practices

1. **Secure API Config:**

   ```bash
   chmod 600 api_config.txt
   ```

2. **Enable Firewall:**

   ```bash
   sudo ufw enable
   sudo ufw allow ssh
   sudo ufw allow 443/tcp
   ```

3. **Use SSH Keys (Disable Password Login):**

   ```bash
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   sudo systemctl restart sshd
   ```

4. **Regular Backups:**
   ```bash
   # Backup database daily
   crontab -e
   # Add: 0 0 * * * cp ~/ai-trading-bot/trades.db ~/backups/trades_$(date +\%Y\%m\%d).db
   ```

---

### 📱 Remote Monitoring

#### SSH from Phone/Laptop

```bash
ssh username@your_vps_ip
screen -r trading-bot  # View bot
```

#### Telegram Bot (Optional - Future Feature)

Coming soon: Real-time trade notifications via Telegram!

---

## ⚠️ Risk Warning

- **Crypto trading is EXTREMELY RISKY**
- **You can lose MORE than you invest with leverage**
- **Start with SMALL amounts ($10-50)**
- **Test with 1x leverage first**
- **Never risk more than you can afford to lose**

---

## 🐛 Troubleshooting

### Timestamp Error (-1021)

Bot auto-syncs time. If fails, sync VPS:

```bash
sudo ntpdate pool.ntp.org
```

### API Error (-2015)

- Enable **Futures Trading** on API key
- Whitelist VPS IP in Binance

### No Trades

- Check balance > $20 (minimum for 10x leverage)
- Wait for signals with confidence ≥65% (default threshold)
- Review logs for skip reasons
- Ensure margin sufficient (Risk% / SL% / Leverage)

### Margin Insufficient Error

**Error:** `Margin is insufficient`

**Solution:**

- Lower leverage (e.g., 10x → 5x)
- Lower risk % (e.g., 5% → 2%)
- Increase balance
- Formula: Margin needed = (Balance × Risk%) / (SL% × Leverage)

**Example:**

- Balance: $70, Risk: 5%, SL: 2%, Leverage: 10x
- Margin needed = ($70 × 5%) / (2% × 10x) = $17.50 ✅

---

## 📈 Database Analytics

```python
from trading_bot_24_7 import InstitutionalTradingBot

bot = InstitutionalTradingBot()
stats = bot.get_analytics()
print(f"Win Rate: {stats['win_rate']:.1f}%")

bot.export_to_csv('trades.csv')  # For taxes
```

---

## 📞 Support

- GitHub Issues: [Report bugs](https://github.com/YOUR_USERNAME/ai-trading-bot/issues)
- Star ⭐ if helpful!

---

**Happy Trading! 🚀📈💰**

_Start small, test thoroughly, never risk more than you can lose!_
