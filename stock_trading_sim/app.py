import os
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd
from cs50 import SQL
from datetime import datetime


# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure SQLite database
db = SQL("sqlite:///trades.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/")
@login_required
def index():
    """Home Screen: Show portfolio of stocks"""

    # User currently logged in
    user_id = session["user_id"]

    # Pulling user's shares from db
    shares = db.execute("SELECT symbol, SUM(shares) FROM transactions WHERE user_id = ? GROUP BY symbol HAVING shares > 0;", user_id)

    # Displaying user's live stock portfolio
    shares_value = 0
    for row in shares:
        stock = lookup(row["symbol"])
        price_cents = int(stock["price"] * 100)
        row["price"] = price_cents / 100
        row["holding_value"] = row["SUM(shares)"] * row["price"]
        shares_value += row["holding_value"]

    # Displaying users cash balance
    user_cash_dict = db.execute("SELECT cash FROM users WHERE id = ?;", user_id)
    user_cash_cents = int(user_cash_dict[0]["cash"] * 100)
    user_cash = user_cash_cents / 100

    return render_template("index.html", shares=shares, shares_value=shares_value, user_cash=user_cash)

@app.route("/account", methods=["GET", "POST"])
@login_required
def addmoney():
    """Add money to users account"""

    if request.method == "POST":

        # Get user's requested cash value
        user_id = session["user_id"]
        cash = float(request.form.get("money"))

        # Make sure it's a postitive number
        if cash < 1:
            return apology("Cash value must be greater than $1.00", 403)

        # Make sure the number is within limit 100k or less
        if cash > 100000:
            return apology("Maximum funds limited to $100,000 per transfer", 403)

        # Checks passed, add inputted cash to their account
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?;", user_id)
        new_user_cash = user_cash[0]["cash"] + cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?;", new_user_cash, user_id)

        # Redirect them home
        return redirect("/")

    else:
        # Serve them the money request form
        return render_template("account.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        # Get requested stock
        stock = lookup(request.form.get("symbol"))

        # Ensure stock exists and is valid
        if not stock:
            return apology("Stock field left empty or symbol doesn't exist", 400)

        # Ensure share number is a positive integer
        shares = int(request.form.get("shares"))
        if shares < 1:
            return apology("Share number must be 1 or greater", 400)

        # Get user's cash value and live stock price
        user_id = session["user_id"]
        symbol = request.form.get("symbol")
        price_cents = stock["price"] * 100
        price = (price_cents / 100)
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?;", session["user_id"])
        user_cash[0]["cash"]
        transaction_price = price * shares

        # Ensure they have enough cash for purchase
        if (stock["price"] * shares) > user_cash[0]["cash"]:
            return apology("Not enough cash", 403)

        # Execute the transaction
        time = datetime.now()
        transaction_type = "BUY"
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time, type) VALUES (?, ?, ?, ?, ?, ?);", user_id, symbol, shares, price, time, transaction_type)

        # Subtract cash from user
        new_user_cash = user_cash[0]["cash"] - transaction_price
        db.execute("UPDATE users SET cash = ? WHERE id = ?;", new_user_cash, user_id)

        # Redirect them home
        return redirect("/")

    else:
        # Serve them stock buying form
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Get user's transactions from db
    user_id = session["user_id"]
    rows = db.execute("SELECT symbol, shares, price, time, type FROM transactions WHERE user_id = ?;", user_id)

    # Display their history and include stock's current price too
    for row in rows:
        shares = abs(row["shares"])
        price = row["price"]
        row["transaction_price"] = shares * price

    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any past sessions
    session.clear()

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    else:
        # Bring them to login page
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget their user_id
    session.clear()

    # Redirect user home, which brings them to login
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote"""

    if request.method == 'POST':

        # Looking up the requested stock symbol
        result = lookup(request.form.get("symbol"))

        # Ensure lookup is successful
        if not result:
            return apology("Stock doesn't exist", 400)

        # Display live price
        return render_template("quoted.html", name=result["name"], price=result["price"])

    else:
        # Display the form to request a stock quote
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == 'POST':

        # Ensure username was submitted
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password confirmation was submitted
        elif not request.form.get('confirmation'):
            return apology("must confirm password", 400)

        # Ensure password and confirmation match
        elif request.form.get('password') != request.form.get('confirmation'):
            return apology("passwords must match", 400)

        # Ensure username not taken
        elif len(rows) != 0:
            return apology('username already taken', 400)

        # Inserting username and hashed password into db
        username = request.form.get("username")
        password = request.form.get("password")
        hash = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?);", username, hash)

        # Log new user in
        id = db.execute("SELECT id FROM users WHERE username = ?;", username)
        session["user_id"] = id[0]["id"]

        # Redirect them home
        return redirect("/")

    else:
        # Display registration form
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        # User currently logged in
        user_id = session["user_id"]

        # Getting user transactions from db
        rows = db.execute("SELECT symbol, SUM(shares) FROM transactions WHERE user_id = ? GROUP BY symbol HAVING shares > 0;", user_id)

        # Ensure they chose a real stock
        stock_symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        if not stock_symbol:
            return apology("Invalid symbol", 403)

        # Ensure they own that stock
        for row in rows:
            if row["symbol"] == stock_symbol:
                break
        else:
            return apology("Stock not owned", 403)

        # Make sure they are selling 1 or more shares
        if int(request.form.get("shares")) < 1:
            return apology("Share number must be greater than 0", 403)

        # Ensure they own more or equal shares than trying to sell
        for row in rows:
            if row["symbol"] == stock_symbol:
                if row["SUM(shares)"] < int(shares):
                    return apology("Don't have enough shares", 403)

        # Get user's live portfolio and cash balance
        stock = lookup(stock_symbol)
        price_cents = stock["price"] * 100
        price = (price_cents / 100)
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?;", session["user_id"])
        user_cash[0]["cash"]
        transaction_price = price * shares
        selling_shares = (shares * -1)

        # Ensure they have enough cash for purchase
        if (stock["price"] * shares) > user_cash[0]["cash"]:
            return apology("Not enough cash", 403)

        # Execute the sale
        time = datetime.now()
        transaction_type = "SELL"
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time, type) VALUES (?, ?, ?, ?, ?, ?);", user_id, stock_symbol, selling_shares, price, time, transaction_type)

        # Add cash from sale to user's balance
        new_user_cash = user_cash[0]["cash"] + transaction_price
        db.execute("UPDATE users SET cash = ? WHERE id = ?;", new_user_cash, user_id)

        # Redirect them home
        return redirect("/")

    else:
        # User currently logged in
        user_id = session["user_id"]

        # Get user's current shares
        rows = db.execute("SELECT symbol, SUM(shares) FROM transactions WHERE user_id = ? GROUP BY symbol HAVING shares > 0;", user_id)

        # Display the form to sell a stock
        return render_template("sell.html", rows=rows)
