# Import necessary libraries
from flask import Flask, render_template, request, redirect, url_for, session
from sqlalchemy import create_engine, text
from flask_sqlalchemy import SQLAlchemy
import hashlib

# Initialize Flask app
app = Flask(__name__)

# Database connection string and engine setup
con_str = "mysql://root:cset155@localhost/MultiVendorEcommerce"
engine = create_engine(con_str, echo=True)  # Echo True logs SQL queries
conn = engine.connect()
app.secret_key = "idkwhattoput"  # Secret key for session management
app.config['SQLALCHEMY_DATABASE_URI'] = con_str  # Set the SQLAlchemy URI
db = SQLAlchemy(app)  # Initialize SQLAlchemy with Flask

# Home route that displays the latest 5 products
@app.route("/")
def home():
    # SQL query to select top 5 products with their image URLs
    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        LIMIT 5
    """)
    result = conn.execute(query)  # Execute the query
    products = result.fetchall()  # Fetch all results
    return render_template("home.html", products=products)  # Render the home page with products

# Alternative home route with session-based username management
@app.route("/home")
def home2():
    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        LIMIT 5
    """)
    result = conn.execute(query)
    products = result.fetchall()
    username = session.get("username")  # Retrieve the username from the session
    if not username:
        return redirect(url_for("login"))  # Redirect to login if username is not found
    return render_template("home.html", username=username, products=products)

# Search functionality that queries products based on user input
@app.route("/search")
def search():
    query = request.args.get('q')  # Get the search query from the URL parameters
    if not query:
        return redirect(url_for('products'))  # Redirect if no query is provided
    # SQL query to search products by title
    search_query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.Title LIKE :search
    """)
    result = conn.execute(search_query, {"search": f"%{query}%"})  # Execute query with search parameter
    products = result.fetchall()
    return render_template("search_results.html", query=query, products=products)

# Sign up route for new users (GET to display form, POST to process form)
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":  # Handle form submission
        name = request.form["name"]
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        # Basic email validation
        if not email or "@" not in email:
            return render_template("signup.html", error="Please enter a valid email address.")
        
        # Password length validation
        if len(password) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters long.")

        # Hash the password using SHA-256
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Append '_vend' to username for vendors
        if role == "vendor":
            username += "_vend"

        try:
            with engine.connect() as conn:
                # Check if the email is already registered
                check_email_query = text("SELECT * FROM User WHERE Email = :email")
                email_result = conn.execute(check_email_query, {"email": email}).fetchone()

                if email_result:
                    return render_template("signup.html", error="Email is already registered.")

                # Check if the username is already taken
                check_username_query = text("SELECT * FROM User WHERE Username = :username")
                username_result = conn.execute(check_username_query, {"username": username}).fetchone()

                if username_result:
                    return render_template("signup.html", error="Username is already taken.")

                # Insert new user into the database
                insert_query = text("""
                    INSERT INTO User (Name, Email, Username, Password)
                    VALUES (:name, :email, :username, :password)
                """)
                with engine.begin() as conn:
                    conn.execute(insert_query, {
                        "name": name,
                        "email": email,
                        "username": username,
                        "password": hashed_password
                    })

            return render_template("signup_success.html", username=username)  # Success page

        except Exception as e:
            return render_template("signup.html", error=f"An error occurred: {e}")  # Error handling

    return render_template("signup.html")  # Render the signup form

# Login route for users (GET to display form, POST to process form)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["Email"]
        password = request.form["password"]
        hashed_password = hashlib.sha256(password.encode()).hexdigest()  # Hash the entered password

        try:
            with engine.connect() as conn:
                # SQL query to check email and password against the database
                query = text("""
                    SELECT * FROM User
                    WHERE Email = :email AND Password = :password
                """)
                result = conn.execute(query, {
                    "email": email,
                    "password": hashed_password
                }).fetchone()

                if result:
                    session["username"] = result[1]  # Set the username in the session
                    return redirect(url_for("home2"))  # Redirect to home page
                else:
                    return f"<h3>Invalid email or password.</h3><a href='{url_for('login')}'>Try again</a>"

        except Exception as e:
            return f"<h3>Login error: {e}</h3>"  # Handle any errors during login

    return render_template("login.html")  # Render the login form

# Logout route to clear the session and redirect to login page
@app.route("/logout")
def logout():
    session.clear()  # Clear the session
    return redirect(url_for("login"))  # Redirect to login page

@app.route("/products")
def products():
    category = request.args.get('category')
    color = request.args.get('color')
    size = request.args.get('size')
    availability = request.args.get('availability')  # 'in' or 'out'

    query_base = """
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL, p.Color, p.Size, 
               p.InventoryAmount, p.Category
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE 1=1
    """
    filters = {}
    if category:
        query_base += " AND p.Category = :category"
        filters['category'] = category
    if color:
        query_base += " AND FIND_IN_SET(:color, p.Color)"
        filters['color'] = color
    if size:
        query_base += " AND FIND_IN_SET(:size, p.Size)"
        filters['size'] = size
    if availability == 'in':
        query_base += " AND p.InventoryAmount > 0"
    elif availability == 'out':
        query_base += " AND p.InventoryAmount = 0"

    result = conn.execute(text(query_base), filters)
    products = result.fetchall()
    return render_template("products.html", products=products)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    query = text("""
        SELECT p.ProductID, p.Title, p.Description, p.DiscountedPrice, p.Category, 
               p.Color, p.Size, p.InventoryAmount, p.WarrantyPeriod, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.ProductID = :product_id
    """)
    result = conn.execute(query, {"product_id": product_id}).fetchone()
    if not result:
        return "<h3>Product not found.</h3>"

    product = dict(result._mapping)
    product["colors"] = product["Color"].split(",") if product["Color"] else []
    product["sizes"] = product["Size"].split(",") if product["Size"] else []
    return render_template("product_detail.html", product=product)

# Cart item model for SQLAlchemy (manages cart items in the database)
class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product', back_populates='cart_items')

# Product model for SQLAlchemy (manages product information in the database)
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    cart_items = db.relationship('CartItem', back_populates='product')

@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if 'cart' not in session:
        session['cart'] = []  # Initialize the cart if it doesn't exist

    # Retrieve form data for color, size, and quantity
    color = request.form.get('color')
    size = request.form.get('size')
    quantity = int(request.form.get('quantity', 1))

    # Check if the item with selected color and size already exists in the cart
    product_in_cart = next((item for item in session['cart'] if item['product_id'] == product_id and item['color'] == color and item['size'] == size), None)

    if product_in_cart:
        product_in_cart['quantity'] += quantity  # Increment quantity if the item is already in the cart
    else:
        session['cart'].append({
            'product_id': product_id,
            'color': color,
            'size': size,
            'quantity': quantity
        })

    session.modified = True  # Ensure session changes are saved
    return redirect(url_for('cart'))  # Redirect to cart page

@app.route('/cart')
def cart():
    cart = session.get('cart', [])  # Retrieve cart from session
    print("Cart:", cart)  # Debug: Check the contents of the cart

    if not cart:  # If the cart is empty
        return render_template("cart.html", products=[], total_price=0, cart=cart)

    # Continue with your logic here to fetch product details
    # Extract product_ids from cart
    product_ids = [item['product_id'] for item in cart]
    print("Product IDs:", product_ids)  # Debug: Check extracted product IDs

    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.ProductID IN :product_ids
    """)
    
    try:
        result = conn.execute(query, {"product_ids": tuple(product_ids)})
        products = result.mappings().fetchall()  # Use mappings to return rows as dictionaries
        print("Products Fetched:", products)  # Debug: Check fetched products
    except Exception as e:
        print("Error executing query:", e)
        return "There was an error fetching products"

    # Merge the DiscountedPrice with each cart item
    for item in cart:
        for product in products:
            if item['product_id'] == product['ProductID']:
                item['DiscountedPrice'] = product['DiscountedPrice']
                item['Title'] = product['Title']
                item['ImageURL'] = product['ImageURL']

    # Calculate total price based on cart items
    total_price = 0
    for item in cart:
        if 'DiscountedPrice' in item:
            total_price += item['DiscountedPrice'] * item['quantity']

    return render_template("cart.html", products=cart, total_price=total_price, cart=cart)

@app.route('/update_cart', methods=['POST'])
def update_cart():
    if 'cart' not in session:
        return redirect(url_for('cart'))  # Redirect if cart doesn't exist in session

    cart = session['cart']
    updated_cart = []

    for item in cart:
        product_id = item['product_id']
        
        # Get updated quantity
        quantity = int(request.form.get(f'quantities[{product_id}]', item['quantity']))  # Default to existing quantity if no update
        
        # Check if item should be deleted
        if f'delete_{product_id}' in request.form and request.form.get(f'delete_{product_id}') == '1':
            continue  # Skip adding this item to the updated cart if it's marked for deletion

        item['quantity'] = quantity  # Update quantity
        updated_cart.append(item)  # Add updated item to the new cart

    session['cart'] = updated_cart  # Update session cart
    session.modified = True
    return redirect(url_for('cart'))  # Redirect to cart page


# Checkout route to display the checkout page with total price
@app.route("/checkout")
def checkout():
    cart = session.get('cart', [])
    total_price = 0
    product_ids = [item['product_id'] for item in cart]

    # Fixed the SQL query here:
    query = text("""
        SELECT p.ProductID, p.DiscountedPrice
        FROM Products p
        WHERE p.ProductID IN :product_ids
    """)
    result = conn.execute(query, {"product_ids": tuple(product_ids)})
    products = result.fetchall()

    for product in products:
        for item in cart:
            if item['product_id'] == product['ProductID']:
                total_price += product['DiscountedPrice'] * item['quantity']

    return render_template("checkout.html", products=products, total_price=total_price)

# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)
