# SHACKOBOT - BYBIT Trading Bot with Dashboard

A Python-based trading bot for BYBIT that uses technical analysis indicators (SMA, MACD) with advanced filtering to automatically identify and execute long/short trading opportunities. Includes a real-time dashboard and Telegram notifications.

## Features

### Trading Strategy
- **SMA Crossover Analysis**: 20, 50, 100, 200-period Simple Moving Averages
- **Price Action Filter**: Confirms price is above/below key moving averages
- **MACD Indicator**: Cross above/below zero line for entry signals
- **Multi-Signal Confirmation**: All indicators must align for trade entry
- **Advanced Filters**: 5 additional customizable filters (toggleable)

### Entry Signals
- **LONG Trades**: Price above SMAs, MACD crosses above zero + all filters pass
- **SHORT Trades**: Price below SMAs, MACD crosses below zero + all filters pass

### Additional Features
- 📊 **Real-time Dashboard**: Monitor bot status, trades, and performance
- 📲 **Telegram Notifications**: Instant alerts for trade entries, exits, and signals
- 🔧 **Configurable Filters**: Enable/disable additional analysis filters
- 📈 **Multi-timeframe Support**: Analyze trends across different intervals
- 🛑 **Risk Management**: Built-in position sizing and stop-loss controls

## Requirements

- Python 3.8+
- pip (Python package manager)

## Installation

1. **Clone the repository**
```bash
git clone https://github.com/Shacko777/legendary-spoon.git
cd legendary-spoon
```

2. **Create a virtual environment** (recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

## Configuration

### API Credentials (BYBIT)

1. Go to [BYBIT API Management](https://www.bybit.com/app/user-api-management)
2. Create a new API key with trading permissions
3. Copy your API Key and Secret

### Environment Setup

Create a `.env` file in the project root:

```env
# BYBIT API Credentials
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here

# Telegram Notifications (Optional)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Bot Settings
TRADING_PAIR=BTCUSDT
TIMEFRAME=15  # in minutes
LEVERAGE=1  # Use cautiously with higher values
POSITION_SIZE=1  # USDT amount per trade
RISK_PERCENTAGE=1  # Risk % of account per trade
```

### Telegram Setup (Optional but Recommended)

1. **Create a Telegram Bot**:
   - Chat with [@BotFather](https://t.me/botfather) on Telegram
   - Use `/newbot` command
   - Follow the setup wizard
   - Copy the **Bot Token**

2. **Get Your Chat ID**:
   - Chat with [@userinfobot](https://t.me/userinfobot) on Telegram
   - It will send you your Chat ID
   - Copy the **Chat ID**

3. **Add credentials to `.env`**:
   ```env
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
   TELEGRAM_CHAT_ID=1234567890
   ```

## Usage

### Start the Bot

```bash
python main.py
```

### Dashboard Access

Once running, the dashboard will be available at:
```
http://localhost:5000
```

Monitor in real-time:
- Active trades and positions
- Entry/exit signals
- Performance metrics
- Filter status
- Telegram notification logs

### Command Line Options

```bash
# Run with custom config file
python main.py --config config.json

# Dry run (no real trades, signals only)
python main.py --dry-run

# Enable verbose logging
python main.py --verbose

# Disable Telegram notifications
python main.py --no-telegram
```

## Trading Logic Explained

### Entry Conditions for LONG
```
1. Price > SMA 20 AND Price > SMA 50 AND Price > SMA 100 AND Price > SMA 200
2. MACD Histogram crosses above the zero line
3. All 5 additional filters pass (or are disabled)
```

### Entry Conditions for SHORT
```
1. Price < SMA 20 AND Price < SMA 50 AND Price < SMA 100 AND Price < SMA 200
2. MACD Histogram crosses below the zero line
3. All 5 additional filters pass (or are disabled)
```

### Available Filters (Can be toggled on/off)

Each filter can be individually enabled/disabled in the configuration:

1. **RSI Filter**: Prevents overbought/oversold entries
2. **Bollinger Bands Filter**: Confirms volatility conditions
3. **ATR Filter**: Ensures sufficient volatility for the trade
4. **Volume Filter**: Confirms adequate trading volume
5. **Trend Strength Filter**: Validates momentum direction

## Configuration Examples

### Conservative Trading
```env
LEVERAGE=1
POSITION_SIZE=0.5  # Smaller position
RISK_PERCENTAGE=0.5  # Lower risk per trade
```

### Aggressive Trading
```env
LEVERAGE=2
POSITION_SIZE=5
RISK_PERCENTAGE=2
```

## Known Limitations & Notes

⚠️ **Disclaimer**: This bot is provided as-is. Trading cryptocurrency involves significant risk. Always start with paper trading or minimal position sizes.

- **Backtest Before Live Trading**: Always verify strategy on historical data first
- **Market Conditions Matter**: Performance varies significantly by market conditions
- **No Guarantee**: Past backtests do not guarantee future results
- **Network Reliability**: Requires stable internet connection
- **API Rate Limits**: Be aware of BYBIT API rate limiting
- **Capital Risk**: Only trade with capital you can afford to lose

## Troubleshooting

### Bot won't connect to BYBIT
- Verify API credentials in `.env` file
- Check API key has trading permissions enabled
- Ensure IP whitelist includes your current IP (if enabled)

### No signals being generated
- Check internet connection
- Verify trading pair exists on BYBIT
- Review logs for data fetch errors
- Ensure sufficient candle history is available

### Telegram notifications not working
- Verify Bot Token is correct
- Confirm Chat ID is correct
- Check bot has permission to send messages
- Ensure `.env` variables are properly set

## Contributing

This bot is open-source and contributions are welcome! Ways you can help:

- 🐛 **Report Bugs**: Found an issue? Open a GitHub Issue
- 💡 **Suggest Features**: Have an idea? Let's discuss it
- 📝 **Improve Documentation**: Help others understand the code
- 🧪 **Backtest Results**: Share your findings and optimizations
- 🔧 **Code Improvements**: Submit pull requests with enhancements

### Before Contributing
1. Test your changes thoroughly
2. Follow the existing code style
3. Update documentation as needed
4. Clearly describe what your changes do

## Support & Feedback

Have questions or suggestions? 

- 📌 Open a GitHub Issue for bugs or feature requests
- 💬 Check existing issues to avoid duplicates
- 🤝 Share your trading results and learnings with the community

## License

This project is provided as-is for educational and trading purposes. See LICENSE file for details.

## Roadmap

- [ ] Multi-pair support
- [ ] Advanced risk management (trailing stops)
- [ ] Machine learning filter optimization
- [ ] WebSocket streaming for real-time data
- [ ] Historical backtesting module
- [ ] Mobile dashboard app
- [ ] Support for additional exchanges

---

**Built with ❤️ by Shacko777**

*Join other traders helping to improve this bot. Your feedback matters!*
