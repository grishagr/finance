import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import time
import json

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

os.environ['TZ'] = 'US/Eastern'
time.tzset()

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# API KEY is set as default in helpers.py
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    #access database, assign variables

    rows = db.execute("SELECT symbol, shares, value FROM current WHERE person_id = :id ORDER BY symbol", id=session["user_id"] )
    persons_cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    cash = persons_cash[0]["cash"]
    total = cash

    #dict that stores all stocks owned, used for index.html
    template_dict={}

    #dict stored in template_dict that shows stores information for every stock owned
    symbol_dict={}

    for row in rows:
        #lookup information for stocks owned in iex database
        quote = lookup(row["symbol"])
        price = quote["price"]
        name = quote["name"]

        #assign variables from 'finance' database 'current' table
        symbol = row["symbol"]
        shares = row["shares"]


        value = price * float(shares)

        current_value = row["value"]

        #change and %change variables
        delta = round((value - current_value), 2)
        delta_pcent = round((((value - current_value) / current_value) * 100), 2)

        #Total variable
        total += value


        #format price and value to usd (usd() in helpers.py)
        price_usd = usd(price)
        value_usd = usd(value)

        #add information for every stock owned
        symbol_dict[symbol] = {"name": name, "shares": shares, "price": price_usd, "value":value_usd, "delta":delta, "deltap":delta_pcent}

        #add all stocks owned into dict
        template_dict["symbol"] = symbol_dict


    #format cash and total to usd (usd() in helpers.py)
    cash=usd(cash)
    total = usd(total)

    #insert variables and dict into template

    return render_template("index.html", templatedict=template_dict, cash=cash, total=total)




@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "GET":
        return render_template("buy.html")

    else:
        #lookup symbol in iex
        quote = request.form.get("symbol").lower()
        symbol = lookup(quote)

        #check for invalid symbol
        if symbol == None:
            error="Invalid Symbol"
            return render_template("buy.html", error=error)


        #lookup stock's price and symbol on iex
        price = symbol["price"]
        name=symbol["name"]
        symbol = symbol["symbol"]

        #number of shares to buy requested
        shares = float(request.form.get("shares"))

        #value of shares to buy
        value = price*shares

        #time, method
        datetime = time.strftime('%X %x %Z')
        method = "Bought"

        #query for users cash
        mylist = db.execute("SELECT cash FROM users WHERE id= :id", id= session["user_id"])
        cash = float(mylist[0]['cash'])
        cash = cash - value

        #return error if value of shares > cash available
        if cash < 0:
            error="Not enough cash"
            return render_template("buy.html", error=error)

        #format value to usd
        value_usd = usd(value)

        #access current database
        stock = db.execute("SELECT symbol, shares, value FROM current WHERE person_id=:id", id=session["user_id"])

        #figure out if stock is already owned
        shares_owned = 0
        current_value=0
        owned = False
        for i in stock:
            s = i["symbol"]

            if s==symbol:
                owned = True
                shares_owned = i["shares"]
                current_value=i["value"]
                break

        #update stock's shares and value amount that user currently holds
        shares_owned += shares
        current_value += value

        #if owned update database, else insert new values
        if owned:
            db.execute("UPDATE current SET shares= :shares, value=:value WHERE person_id= :id AND symbol= :symbol", shares=shares_owned, value=current_value, id=session["user_id"], symbol=symbol)

        else:
            db.execute("INSERT INTO current (symbol, shares, value, person_id) VALUES (:symbol, :shares, :value, :id)", symbol=symbol, shares=shares_owned, value=current_value, id=session["user_id"] )

        #update information

        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cash, id=session["user_id"])
        db.execute("INSERT INTO history (method, shares, symbol, price, value, transacted, person_id) VALUES (:method, :shares, :symbol, :price, :value, :transacted, :person_id)", method=method, shares=shares, symbol=symbol, price=price, value=value_usd, transacted=datetime, person_id=session["user_id"] )

        #redirect to index with flash message
        flash(f"Bought {str(shares)} shares of {name} with total value of {value_usd}")
        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    historylist = db.execute("SELECT * FROM history WHERE person_id= :id ORDER BY order_id DESC", id=session["user_id"])

    return render_template("history.html", historylist = historylist)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            error="Please provide username"
            return render_template("login.html", error=error)

        # Ensure password was submitted
        elif not request.form.get("password"):
            error="Please provide password"
            return render_template("login.html", error=error)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            error="Invalid Username/Password"
            return render_template("login.html", error=error)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "GET":
        return render_template("quote.html")


    else:
        #query for users input
        quote = request.form.get("quote").lower()

        #lookup symbol on iex
        symbol = lookup(quote)

        #check for invalid symbol
        if symbol == None:
            error="Invalid Symbol"
            return render_template("quote.html", error=error)

        #lookup stock's information
        name = symbol["name"]
        price = usd(symbol["price"])
        ticker = symbol["symbol"]
        time= symbol["time"]

        return render_template("quoted.html", name=name, price=price, ticker=ticker, time=time)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        #check if username and password are provided

        if not request.form.get("username"):
            error="Please provide Username"
            return render_template("register.html", error=error)

        if not request.form.get("password"):
            error="Please provide password"
            return render_template("register.html", error=error)


        #check if it already exists in database

        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        if len(rows) == 1:
            error="Username already exists"
            return render_template("register.html", error=error)



        #assign users input to variables
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirmation")

        #check if password is confirmed
        if password != confirm:

            error="Passwords don't match"
            return render_template("register.html", error=error)
        #generate password's hash for security
        else:
            h = generate_password_hash(password)

        #register user into database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :h)", username=username, h=h)


        #log user in
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=username)

        session["user_id"] = rows[0]["id"]
        flash("Registered")
        return redirect("/")

    else:
        return render_template("register.html")

@app.route("/manual", methods=["GET", "POST"])
@login_required
def manual():
    if request.method == "GET":

        #access history database for stocks owned
        stocks_owned = db.execute("SELECT symbol, shares FROM current WHERE person_id = :id ORDER BY symbol", id=session["user_id"] )

        #create dict for later storage
        blist={}

        #iterate over stocks_owned and insert needed information to blist dictionary
        for row in stocks_owned:

            #point variables to information from database
            symbol = row["symbol"]
            shares = row["shares"]


            #assign shares to a symbol in a dict
            blist[symbol] = shares


        return render_template("manual.html", blist=blist)

    else:

        # record buy or sell method
        method = request.form.get("method")

        # buy

        if method == "Bought":
            quote = request.form.get("symbol_bought").lower()
            symbol = lookup(quote)

            if symbol == None:

                error="Invalid symbol"
                return render_template("manual.html", error=error)



            price = float(request.form.get("price"))
            name=symbol["name"]
            symbol = symbol["symbol"]
            shares = float(request.form.get("shares"))
            datetime = "Manual"

            mylist = db.execute("SELECT cash FROM users WHERE id= :id", id= session["user_id"])
            cash = float(mylist[0]['cash'])
            value = (price*shares)
            cash = cash - value

            value_usd = usd(value)

            if cash < 0:
                error="Not enough cash"
                return render_template("manual.html", error=error)

            #access current database
            stock = db.execute("SELECT symbol, shares, value FROM current WHERE person_id=:id", id=session["user_id"])

            #figure out if stock is already owned
            shares_owned = 0
            current_value=0
            owned = False
            for i in stock:
                s = i["symbol"]

                if s==symbol:
                    owned = True
                    shares_owned = i["shares"]
                    current_value=i["value"]
                    break


            shares_owned += shares
            current_value += value

            #if owned update database, else insert new values
            if owned:
                db.execute("UPDATE current SET shares= :shares, value=:value WHERE person_id= :id AND symbol= :symbol", shares=shares_owned, value=current_value, id=session["user_id"], symbol=symbol)

            else:
                db.execute("INSERT INTO current (symbol, shares, value, person_id) VALUES (:symbol, :shares, :value, :id)", symbol=symbol, shares=shares_owned, value=current_value, id=session["user_id"] )


            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cash, id=session["user_id"])
            db.execute("INSERT INTO history (method, shares, symbol, price, value, transacted, person_id) VALUES (:method, :shares, :symbol, :price, :value, :transacted, :person_id)", method=method, shares=shares, symbol=symbol, price=price, value=value_usd, transacted=datetime, person_id=session["user_id"] )
            flash(f"Bought {str(shares)} shares of {name} with total value of {value_usd}")
        else:
            #access stock requested in IEX
            quote = request.form.get("symbol_sold").lower()
            quote1 = quote.replace('"', '')
            quote = lookup(quote1)

            if quote == None:
                error="Invalid symbol"
                return render_template("manual.html", error=error)

            #lookup price and symbol from IEX
            price = float(request.form.get("price"))
            symbol = quote["symbol"]
            name = quote["name"]

            #shares requested to sell
            shares = float(request.form.get("shares"))

            #shares owned in database
            shares_ownedlist = (db.execute("SELECT shares FROM current WHERE person_id= :id AND symbol= :symbol", id= session["user_id"], symbol=symbol))
            shares_owned = shares_ownedlist[0]["shares"]

            #if user tried to sell more shares than he actually owned
            if float(shares_owned) < shares:
                shares_owned = str(shares_owned)
                error="Excessive amount of shares. You own ", shares_owned, "shares of ", name
                error=" ".join(error)
                return render_template("manual.html", error=error)


            datetime = "Manual"
            mylist = db.execute("SELECT cash FROM users WHERE id= :id", id= session["user_id"])
            cash = float(mylist[0]['cash'])
            value = price*shares
            cash = cash + value

            value_usd = usd(value)
            shares = 0 - shares

            #access current database
            stock = db.execute("SELECT symbol, shares, value FROM current WHERE person_id=:id", id=session["user_id"])

            #get current_value and shares_owned amount
            shares_owned = 0
            current_value=0
            for i in stock:
                s = i["symbol"]

                if s==symbol:
                    shares_owned = i["shares"]
                    current_value=i["value"]
                    break


            shares_owned += shares
            current_value -= value

            #update current database
            if shares_owned == 0:
                db.execute("DELETE FROM current WHERE symbol=:symbol AND person_id=:id", symbol=symbol, id=session["user_id"])
            else:
                db.execute("UPDATE current SET shares= :shares, value=:value WHERE person_id= :id AND symbol= :symbol", shares=shares_owned, value=current_value, id=session["user_id"], symbol=symbol)



            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cash, id=session["user_id"])
            db.execute("INSERT INTO history (method, shares, symbol, price, value, transacted, person_id) VALUES (:method, :shares, :symbol, :price, :value, :transacted, :person_id)", method=method, shares=shares, symbol=symbol, price=price, value=value_usd, transacted=datetime, person_id=session["user_id"] )
            flash(f"Sold {str(0-shares)} shares of {name} with total value of {value_usd}")
        return redirect("/")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        #access history database for stocks owned
        stocks_owned = db.execute("SELECT symbol, shares FROM current WHERE person_id = :id ORDER BY symbol", id=session["user_id"] )

        #create dict for later storage (could be improved and blist will eventually be gone)
        blist={}

        #iterate over stocks_owned and insert needed information to blist dictionary
        for row in stocks_owned:

            #point variables to information from database
            symbol = row["symbol"]
            shares = row["shares"]


            #assign shares to a symbol in a dict
            blist[symbol] = shares

        count = len(blist)

        return render_template("sell.html", blist=blist, count=count)

    else:
        #access stock requested in IEX
        quote = request.form.get("symbol").lower()
        quote1 = quote.replace('"', '')
        quote = lookup(quote1)

        #lookup price and symbol from IEX
        price = quote["price"]
        symbol = quote["symbol"]
        name = quote["name"]

        #shares requested to sell
        shares = float(request.form.get("shares"))

        #shares owned in database
        shares_ownedlist = (db.execute("SELECT SUM(shares) FROM history WHERE person_id= :id AND symbol= :symbol", id= session["user_id"], symbol=symbol))
        shares_owned = shares_ownedlist[0]["SUM(shares)"]

        #if user tried to sell more shares than he actually owned
        if float(shares_owned) < shares:
            shares_owned = str(shares_owned)
            error="Excessive amount of shares. You own ", shares_owned, "shares of ", name
            error=" ".join(error)
            return render_template("sell.html", error=error)


        datetime = time.strftime('%X %x %Z')
        method = "Sold"
        mylist = db.execute("SELECT cash FROM users WHERE id= :id", id= session["user_id"])
        cash = float(mylist[0]['cash'])
        value = price*shares
        cash = cash + value

        value_usd = usd(value)
        shares = 0 - shares

        #access current database
        stock = db.execute("SELECT symbol, shares, value FROM current WHERE person_id=:id", id=session["user_id"])

        #get current_value and shares_owned amount
        shares_owned = 0
        current_value=0
        for i in stock:
            s = i["symbol"]

            if s==symbol:
                shares_owned = i["shares"]
                current_value=i["value"]
                break


        shares_owned += shares
        current_value -= value

        #update current database
        if shares_owned == 0:
            db.execute("DELETE FROM current WHERE symbol=:symbol AND person_id=:id", symbol=symbol, id=session["user_id"])
        else:
            db.execute("UPDATE current SET shares= :shares, value=:value WHERE person_id= :id AND symbol= :symbol", shares=shares_owned, value=current_value, id=session["user_id"], symbol=symbol)



        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cash, id=session["user_id"])
        db.execute("INSERT INTO history (method, shares, symbol, price, value, transacted, person_id) VALUES (:method, :shares, :symbol, :price, :value, :transacted, :person_id)", method=method, shares=shares, symbol=symbol, price=price, value=value_usd, transacted=datetime, person_id=session["user_id"] )
        flash(f"Sold {str(0-shares)} shares of {name} with total value of {value_usd}")

        return redirect("/")

@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():

    if request.method == "GET":
        return render_template("cash.html")

    else:
        method = request.form.get("method")
        money = float(request.form.get("money"))
        persons_cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        cash = persons_cash[0]["cash"]
        if method == "Add":
            cash += money
            flash(f"Added $ {str(money)} to your account")

        if method == "Withdraw":
            cash -= money
            if cash < 0:
                cash = cash+money
                cash = str(cash)
                error="You only own $", cash
                error=" ".join(error)
                return render_template("cash.html", error=error)
            flash(f"Withdrawn $ {str(money)} from your account")
        money_usd = usd(money)
        datetime = time.strftime('%X %x %Z')

        db.execute("UPDATE users SET cash = :cash WHERE id= :id", cash = cash, id = session["user_id"])
        db.execute("INSERT INTO history (method, shares, symbol, price, value, transacted, person_id) VALUES (:method, :shares, :symbol, :price, :value, :transacted, :person_id)", method=method, shares=0, symbol="MONEY", price=0, value=money_usd, transacted=datetime, person_id=session["user_id"] )
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


