import yfinance as yf
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import json
import os
import time

# ========================
# CONFIGURATION
# ========================
# Get credentials from environment variables
SENDER_EMAIL = os.environ.get('SENDER_EMAIL')
SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')

# Define top stocks in each category
TOP_STOCKS = {
    "Semiconductor": ['NVDA', 'TSM', 'ASML', 'AMD', 'INTC', 'AVGO', 'QCOM', 'TXN', 'MU', 'ADI'],
    "AI": ['MSFT', 'GOOG', 'AMZN', 'META', 'ORCL', 'IBM', 'CRM', 'NOW', 'PATH', 'AI'],
    "Defense": ['LMT', 'RTX', 'BA', 'GD', 'NOC', 'HII', 'LHX', 'KBR', 'LDOS', 'BWXT']
}

# File path for reference prices
REFERENCE_FILE = "stock_reference.json"

# Time periods for comparison (in trading days)
TIME_PERIODS = {
    "1d": 1,    # Yesterday
    "1w": 5,    # Last week (5 trading days)
    "15d": 15,  # Last 15 trading days
    "30d": 30,  # Last 30 trading days
    "2m": 60    # Last 60 trading days (2 months)
}

# ========================
# FUNCTIONS
# ========================
def get_stock_data(ticker):
    """Fetch stock data for multiple time periods"""
    stock = yf.Ticker(ticker)
    try:
        # Get max period needed (60 trading days + buffer)
        data = stock.history(period='80d')
        
        if data.empty:
            return None
            
        # Get today's price (last available data point)
        current_price = data['Close'][-1]
        
        # Calculate changes for each time period
        changes = {}
        for period_name, days in TIME_PERIODS.items():
            if len(data) > days:
                # Get price from 'days' trading days ago
                past_price = data['Close'][-days-1]
                change = ((current_price - past_price) / past_price) * 100
                changes[period_name] = change
            else:
                changes[period_name] = None
        
        return {
            'symbol': ticker,
            'price': current_price,
            'changes': changes
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {str(e)}")
    return None

def load_reference_prices():
    """Load reference prices from file"""
    if os.path.exists(REFERENCE_FILE):
        with open(REFERENCE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_reference_prices(prices):
    """Save reference prices to file"""
    with open(REFERENCE_FILE, 'w') as f:
        json.dump(prices, f)

def generate_stock_report():
    """Generate stock performance report"""
    reference_prices = load_reference_prices()
    today = datetime.now().strftime("%Y-%m-%d")
    
    report = {}
    new_references = False

    # Process each category
    for category, tickers in TOP_STOCKS.items():
        category_data = []
        
        for ticker in tickers:
            stock_data = get_stock_data(ticker)
            if not stock_data:
                continue
                
            current_price = stock_data['price']
            ref_key = f"{ticker}_reference"
            
            # Set reference price if first run or not exists
            if ref_key not in reference_prices:
                reference_prices[ref_key] = current_price
                new_references = True
                
            ref_price = reference_prices[ref_key]
            ref_change = ((current_price - ref_price) / ref_price) * 100
            
            # Prepare row data with all time periods
            row = {
                'Symbol': ticker,
                'Current Price': f"${current_price:.2f}",
                'Change vs Reference': f"{ref_change:+.2f}%"
            }
            
            # Add all time period changes
            for period_name in TIME_PERIODS:
                change = stock_data['changes'].get(period_name)
                if change is not None:
                    row[f'{period_name} Change'] = f"{change:+.2f}%"
                else:
                    row[f'{period_name} Change'] = "N/A"
            
            category_data.append(row)
        
        # Create DataFrame for the category
        report[category] = pd.DataFrame(category_data)
    
    # Save updated reference prices if new stocks added
    if new_references:
        save_reference_prices(reference_prices)
    
    return report

def send_stock_report(report):
    """Send stock report via email"""
    today = datetime.now().strftime("%B %d, %Y")
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = f"Multi-Period Stock Report - {today}"
    
    # Create HTML content
    html = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th {{ background-color: #f2f2f2; text-align: left; padding: 10px; }}
                td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                tr:hover {{ background-color: #f5f5f5; }}
                .positive {{ color: green; }}
                .negative {{ color: red; }}
            </style>
        </head>
        <body>
            <h2>📈 Multi-Period Stock Performance Report ({today})</h2>
            <p>Time period changes show today's price vs:</p>
            <ul>
                <li><strong>1d</strong>: Yesterday's close</li>
                <li><strong>1w</strong>: 5 trading days ago</li>
                <li><strong>15d</strong>: 15 trading days ago</li>
                <li><strong>30d</strong>: 30 trading days ago</li>
                <li><strong>2m</strong>: 60 trading days ago (approx 2 months)</li>
            </ul>
    """
    
    for category, df in report.items():
        # Apply color coding to all percentage columns
        for col in df.columns:
            if 'Change' in col:
                df[col] = df[col].apply(
                    lambda x: 
                        f'<span class="positive">{x}</span>' if isinstance(x, str) and '+' in x and 'N/A' not in x
                        else (f'<span class="negative">{x}</span>' if isinstance(x, str) and '-' in x 
                        else x)
                )
        
        html += f"""
        <h3>🔧 {category} Sector (Top 10)</h3>
        {df.to_html(index=False, border=0, justify='left', escape=False)}
        <br>
        """
    
    html += """
            <p style="color: #666; font-size: 0.9em;">
                Note: Data from Yahoo Finance | Trading days only (excludes weekends/holidays)
            </p>
        </body>
    </html>
    """
    
    msg.attach(MIMEText(html, 'html'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print("Stock report email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {str(e)}")

# ========================
# MAIN EXECUTION
# ========================
if __name__ == "__main__":
    print("Generating multi-period stock report...")
    start_time = time.time()
    stock_report = generate_stock_report()
    print(f"Report generated in {time.time() - start_time:.2f} seconds")
    print("Sending email report...")
    send_stock_report(stock_report)
    print("Process completed!")
