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

Create a `api_keys.txt` file in the project root for dashboard:
```txt
BYBIT API Credentials
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here

# Bot Settings
ALL CONFIGS IN $.py file 
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
$.py
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
- Verify API credentials in `.txt` file
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

---

**Built with ❤️ by Shacko777**

*Join other traders helping to improve this bot. Your feedback matters!*
