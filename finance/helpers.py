import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        response = requests.get(f"https://cloud-sse.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={urllib.parse.quote_plus(api_key)}")
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"],
            "time": quote["latestTime"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"



""" 1.(DONE) Average price of stocks_owned compared to current price
    -keep track of total value of each stock owned

        -maybe create a new database to store current total value and stocks owned for all stocks
        -/sell: delete row in database everytime shares get sold to 0, else update stocks owned and total value
            by subtracting requested shares and market_price*shares

        -/buy: when buying stocks, if exists already —update, else insert shares and market_price*shares

    -index:
        -total value of shares owned / shares owned = avg price of share owned
        -!!!market price - avg price = delta!!!
        -!!!((market price - avg price) / avg price) *100% = %delta!!!


    2. Find online database for all stocks that would return their symbols

"""
