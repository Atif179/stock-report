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
SENDER_EMAIL = os.environ.get('atifmd894@gmail.com')
SENDER_PASSWORD = os.environ.get('vagomnuknnobhtap')
RECIPIENT_EMAIL = os.environ.get('atifuddin64@gmail.com')

# Define top stocks in each category
TOP_STOCKS = {
    "Semiconductor": ['NVDA', 'TSM', 'ASML', 'AMD', 'INTC', 'AVGO', 'QCOM', 'TXN', 'MU', 'ADI'],
    "AI": ['MSFT', 'GOOG', 'AMZN', 'META', 'ORCL', 'IBM', 'CRM', 'NOW', 'PATH', 'AI'],
    "Defense": ['LMT', 'RTX', 'BA', 'GD', 'NOC', 'HII', 'LHX', 'KBR', 'LDOS', 'BWXT']
}

# File path for reference prices
REFERENCE_FILE = "stock_reference.json"

# ========================
# FUNCTIONS
# ========================
def get_stock_data(ticker):
    """Fetch current stock data using Yahoo Finance"""
    stock = yf.Ticker(ticker)
    try:
        # Get today's data
        today = datetime.today().date()
        data = stock.history(period='1d')
        
        if data.empty:
            # Try getting last available data if today is holiday
            data = stock.history(period='5d').tail(1)
        
        if not data.empty:
            current_price = data['Close'][-1]
            previous_close = data['Close'][0] if len(data) > 1 else current_price
            daily_change = ((current_price - previous_close) / previous_close) * 100
            
            return {
                'symbol': ticker,
                'price': current_price,
                'daily_change': daily_change
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
            
            category_data.append({
                'Symbol': ticker,
                'Current Price': f"${current_price:.2f}",
                'Change vs Reference': f"{ref_change:+.2f}%",
                'Daily Change': f"{stock_data['daily_change']:+.2f}%"
            })
        
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
    msg['Subject'] = f"Daily Stock Report - {today}"
    
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
            <h2>📈 Daily Stock Performance Report ({today})</h2>
            <p>Reference prices are locked from initial run date. Daily changes show performance vs this reference.</p>
    """
    
    for category, df in report.items():
        # Format percentage changes with color coding
        df['Change vs Reference'] = df['Change vs Reference'].apply(
            lambda x: f'<span class="{"positive" if "+" in x else "negative"}">{x}</span>')
        df['Daily Change'] = df['Daily Change'].apply(
            lambda x: f'<span class="{"positive" if "+" in x else "negative"}">{x}</span>')
        
        html += f"""
        <h3>🔧 {category} Sector (Top 10)</h3>
        {df.to_html(index=False, border=0, justify='left', escape=False)}
        <br>
        """
    
    html += """
            <p style="color: #666; font-size: 0.9em;">
                Note: Data from Yahoo Finance | Reference prices set on first run
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
    print("Generating stock report...")
    stock_report = generate_stock_report()
    print("Sending email report...")
    send_stock_report(stock_report)
    print("Process completed!")
