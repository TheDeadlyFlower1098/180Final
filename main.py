# Import necessary libraries
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy import create_engine, text
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
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
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))

    # Add product query to prevent NameError
    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        LIMIT 5
    """)
    result = conn.execute(query)
    products = result.fetchall()

    return render_template("home.html", username=username, products=products)

@app.route("/search")
def search():
    query = request.args.get('q')
    if not query:
        return render_template("search_results.html", query=query, products=[])

    try:
        with engine.connect() as conn:
            search_query = text("""
                SELECT p.*, pi.ImageURL
                 FROM products p
                LEFT JOIN productimages pi ON p.ProductID = pi.ProductID
                 WHERE p.Title LIKE :query OR p.Description LIKE :query
                """)
            result = conn.execute(search_query, {"query": f"%{query}%"}).fetchall()
            return render_template("search_results.html", query=query, products=result)

    except Exception as e:
        return f"<h3>Error during search: {e}</h3>"

# Sign up route for new users (GET to display form, POST to process form)
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        if not email or "@" not in email:
            return render_template("signup.html", error="Please enter a valid email address.")
        if len(password) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters long.")

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        try:
            with engine.begin() as conn:
                # Check for duplicate email or username
                email_exists = conn.execute(text("SELECT * FROM User WHERE Email = :email"), {"email": email}).fetchone()
                username_exists = conn.execute(text("SELECT * FROM User WHERE Username = :username"), {"username": username}).fetchone()

                if email_exists:
                    return render_template("signup.html", error="Email is already registered.")
                if username_exists:
                    return render_template("signup.html", error="Username is already taken.")

                # Insert user
                insert_user = text("""
                    INSERT INTO User (Name, Email, Username, Password, Role)
                    VALUES (:name, :email, :username, :password, :role)
                """)
                conn.execute(insert_user, {
                    "name": name,
                    "email": email,
                    "username": username,
                    "password": hashed_password,
                    "role": role
                })

                # Get the new user ID
                user_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()

                # If vendor, insert into the Vendor table using same ID
                if role == "vendor":
                    insert_vendor = text("INSERT INTO Vendor (VendorID) VALUES (:vendor_id)")
                    conn.execute(insert_vendor, {"vendor_id": user_id})

            return render_template("signup_success.html", username=username)

        except Exception as e:
            return render_template("signup.html", error=f"An error occurred: {e}")

    return render_template("signup.html")


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
                    result = dict(result._mapping)  # Convert result to dictionary for key access

                    session["user_id"] = result["UserID"]  # FIXED: now chat works!
                    session["username"] = result["Username"]
                    session["role"] = result["Role"]
                    session["vendor_id"] = result["UserID"] if result["Role"] == "vendor" else None

                    if result["Role"] == "vendor":
                        return redirect(url_for("vendor_dashboard"))
                    elif result["Role"] == "admin":
                        return redirect(url_for("admin_manage_products"))
                    else:
                        return redirect(url_for("home2"))
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

@app.route("/vendor/dashboard")
def vendor_dashboard():
    if session.get("role") != "vendor":
        return redirect(url_for("login"))

    vendor_name = session.get("username")
    return render_template("vendor_dashboard.html", vendor_name=vendor_name)



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
    product["colors"] = product["Color"].split() if product["Color"] else []
    product["sizes"] = product["Size"].split() if product["Size"] else []
    product["categories"] = product["Category"].split() if product["Category"] else []
    return render_template("product_detail.html", product=product, current_time=datetime.utcnow())

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


from datetime import datetime

@app.route("/vendor/add_product", methods=["GET", "POST"])
def add_product():
    vendor_id = session.get("vendor_id")
    if not vendor_id:
        return redirect(url_for("login"))

    if request.method == "POST":
        # Collect form data
        title = request.form["title"]
        description = request.form["description"]
        warranty_period = request.form.get("warranty_period", type=int)
        color = request.form["color"]
        size = request.form["size"]
        inventory_amount = request.form.get("inventory_amount", type=int)
        original_price = request.form.get("original_price", type=float)
        discounted_price = request.form.get("discounted_price", type=float)
        discount_time_str = request.form.get("discount_time")
        discount_time = None

        # Ensure that discount_time is only processed if it is provided
        if discount_time_str:
            try:
                discount_time = datetime.strptime(discount_time_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                flash("Invalid discount time format! Please use YYYY-MM-DDTHH:MM", "danger")
                return render_template("add_product.html")

        # Ensure all required fields have values
        if original_price is None:
            flash("Original price is required!", "danger")
            return render_template("add_product.html")

        try:
            with engine.begin() as conn:
                # Insert product
                product_insert = text("""
                    INSERT INTO Products (Title, Description, WarrantyPeriod, Color, Size,
                        InventoryAmount, OriginalPrice, DiscountedPrice, DiscountTime, VendorID)
                    VALUES (:title, :description, :warranty_period, :color, :size,
                        :inventory_amount, :original_price, :discounted_price, :discount_time, :vendor_id)
                """)
                conn.execute(product_insert, {
                    "title": title,
                    "description": description,
                    "warranty_period": warranty_period,
                    "color": color,
                    "size": size,
                    "inventory_amount": inventory_amount,
                    "original_price": original_price,
                    "discounted_price": discounted_price if discounted_price else None,  # Handle None if not provided
                    "discount_time": discount_time,
                    "vendor_id": vendor_id
                })

                # Get new ProductID
                product_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()

                # Insert images
                image_urls = request.form.getlist("image_urls")  # Accept multiple image URLs
                for url in image_urls:
                    if url.strip():  # Avoid empty fields
                        image_insert = text("INSERT INTO ProductImages (ProductID, ImageURL) VALUES (:product_id, :image_url)")
                        conn.execute(image_insert, {"product_id": product_id, "image_url": url})

                flash("Product added successfully!", "success")
                return redirect(url_for("vendor_dashboard"))

        except Exception as e:
            flash(f"Error adding product: {e}", "danger")
            return render_template("add_product.html")

    return render_template("add_product.html")


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

def enrich_cart(cart):
    if not cart:
        return cart, 0

    product_ids = [item['product_id'] for item in cart]
    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.ProductID IN :product_ids
    """)
    
    result = conn.execute(query, {"product_ids": tuple(product_ids)})
    products = result.mappings().fetchall()

    total_price = 0
    for item in cart:
        for product in products:
            if item['product_id'] == product['ProductID']:
                item['DiscountedPrice'] = product.get('DiscountedPrice', 0)
                item['Title'] = product['Title']
                item['ImageURL'] = product.get('ImageURL', '')
                total_price += item['DiscountedPrice'] * item['quantity']
    return cart, total_price

@app.route('/cart')
def cart():
    cart = session.get('cart', [])  # Retrieve cart from session

    # Enrich cart with product data and calculate total price
    cart, total_price = enrich_cart(cart)

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

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', [])
    if not cart:
        return redirect(url_for('cart'))
    
    cart, total_price = enrich_cart(cart)  # Reuse logic

    if request.method == 'POST':
        # Payment form processing...
        order_id = create_order(cart, total_price, request.form['billing_address'])
        session['cart'] = []
        return redirect(url_for('order_confirmation', order_id=order_id))

    return render_template("checkout.html", products=cart, total_price=total_price)
def create_order(cart, total_price, billing_address):
    # Simulate order creation
    order_id = "ORD123"  # Replace with actual order ID logic
    # Here, you can save the order to the database
    return order_id

@app.route('/order_confirmation/<order_id>')
def order_confirmation(order_id):
    return render_template("order_confirmation.html", order_id=order_id)



@app.route("/vendor/manage")
def manage_products():
    vendor_id = session.get("vendor_id")
    if not vendor_id:
        return redirect(url_for("login"))

    with engine.connect() as conn:
        query = text("""
            SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
            FROM Products p
            LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
            WHERE p.VendorID = :vendor_id
        """)
        result = conn.execute(query, {"vendor_id": vendor_id})
        products = result.fetchall()

    return render_template("manage.html", products=products)


@app.route("/vendor/delete_product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    vendor_id = session.get("vendor_id")
    if not vendor_id:
        return redirect(url_for("login"))
    
    with engine.connect() as conn:
        product_check = text("SELECT * FROM Products WHERE ProductID = :product_id AND VendorID = :vendor_id")
        product = conn.execute(product_check, {"product_id": product_id, "vendor_id": vendor_id}).fetchone()

    if product:
        try:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM ProductImages WHERE ProductID = :product_id"), {"product_id": product_id})
                conn.execute(text("DELETE FROM Products WHERE ProductID = :product_id"), {"product_id": product_id})
                
            flash("Product deleted successfully!", "success")
        except Exception as e:
            flash(f"Error deleting product: {e}", "error")
    else:
        flash("You can only delete your own products.", "danger")

    return redirect(url_for("manage_products"))


@app.route("/admin/manage", methods=["GET"])
def admin_manage_products():
    if session.get("role") != "admin":
        flash("Unauthorized access. Admins only.", "danger")
        return redirect(url_for("login"))

    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
    """)
    products = conn.execute(query).fetchall()

    return render_template("admin.html", products=products)


@app.route("/admin/delete_product/<int:product_id>", methods=["POST"])
def admin_delete_product(product_id):
    if session.get("role") != "admin":
        flash("Unauthorized access. Admins only.", "danger")
        return redirect(url_for("login"))

    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM ProductImages WHERE ProductID = :product_id"), {"product_id": product_id})
            conn.execute(text("DELETE FROM Products WHERE ProductID = :product_id"), {"product_id": product_id})
        flash("Product deleted successfully by admin.", "success")

    except Exception as e:
        # Re-open a fresh connection to safely check for related orders
        with engine.connect() as conn:
            order_check = conn.execute(
                text("SELECT 1 FROM OrderItems WHERE ProductID = :product_id LIMIT 1"),
                {"product_id": product_id}
            ).fetchone()

        if order_check:
            flash("Cannot delete: Product is part of an existing order.", "danger")
        else:
            flash(f"Error deleting product: {e}", "danger")

    return redirect(url_for("admin_manage_products"))

from datetime import datetime

@app.route("/admin/edit_product/<int:product_id>", methods=["GET", "POST"])
def admin_edit_product(product_id):
    if session.get("role") != "admin":
        flash("Unauthorized access. Admins only.", "danger")
        return redirect(url_for("login"))

    with engine.begin() as conn:
        product = conn.execute(
            text("SELECT * FROM Products WHERE ProductID = :product_id"),
            {"product_id": product_id}
        ).fetchone()

        if not product:
            flash("Product not found.", "warning")
            return redirect(url_for("admin_manage_products"))

        if request.method == "POST":
            try:
                title = request.form["title"]
                description = request.form["description"]
                original_price = request.form.get("original_price", type=float)
                discounted_price = request.form.get("discounted_price", type=float)
                discount_time_str = request.form.get("discount_time")
                discount_time = datetime.strptime(discount_time_str, "%Y-%m-%dT%H:%M") if discount_time_str else None

                conn.execute(text("""
                    UPDATE Products
                    SET Title = :title,
                        Description = :description,
                        OriginalPrice = :original_price,
                        DiscountedPrice = :discounted_price,
                        DiscountTime = :discount_time
                    WHERE ProductID = :product_id
                """), {
                    "title": title,
                    "description": description,
                    "original_price": original_price,
                    "discounted_price": discounted_price,
                    "discount_time": discount_time,
                    "product_id": product_id
                })

                flash("Product updated successfully.", "success")
                return redirect(url_for("admin_manage_products"))

            except Exception as e:
                flash(f"Error updating product: {e}", "danger")

    return render_template("edit_product.html", product=product)

@app.route("/vendor/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    vendor_id = session.get("vendor_id")
    if not vendor_id:
        return redirect(url_for("login"))

    with engine.begin() as conn: 
        query = text("SELECT * FROM Products WHERE ProductID = :product_id AND VendorID = :vendor_id")
        product = conn.execute(query, {"product_id": product_id, "vendor_id": vendor_id}).fetchone()

        if not product:
            flash("Product not found or not authorized.", "danger")
            return redirect(url_for("manage_products"))

        if request.method == "POST":
            try:
                title = request.form["title"]
                description = request.form["description"]
                original_price = request.form.get("original_price", type=float)
                discounted_price = request.form.get("discounted_price", type=float)
                discount_time_str = request.form.get("discount_time")
                discount_time = datetime.strptime(discount_time_str, "%Y-%m-%dT%H:%M") if discount_time_str else None

                conn.execute(text("""
                    UPDATE Products
                    SET Title = :title,
                        Description = :description,
                        OriginalPrice = :original_price,
                        DiscountedPrice = :discounted_price,
                        DiscountTime = :discount_time
                    WHERE ProductID = :product_id AND VendorID = :vendor_id
                """), {
                    "title": title,
                    "description": description,
                    "original_price": original_price,
                    "discounted_price": discounted_price,
                    "discount_time": discount_time,
                    "product_id": product_id,
                    "vendor_id": vendor_id
                })

                flash("Product updated successfully!", "success")
                return redirect(url_for("manage_products"))

            except Exception as e:
                flash(f"Error updating product: {e}", "danger")

    return render_template("edit_product.html", product=product)


@app.route("/chat/<int:receiver_id>", methods=["GET", "POST"])
def chat(receiver_id):
    sender_id = session.get("user_id") #get the id of user thats logged in
    if not sender_id:
        flash("Please log in to chat.", "warning")
        return redirect(url_for("login")) #return to log in page if user not in session

    if request.method == "POST":
        message = request.form["message"] #where the messages send
        image_url = request.form.get("image_url")  #sending images

        with engine.begin() as conn: #insert into databse
            conn.execute(text("""
                INSERT INTO Chat (SenderID, ReceiverID, Message, ImageURL, Timestamp)
                VALUES (:sender, :receiver, :message, :image_url, :timestamp)
            """), {
                "sender": sender_id,
                "receiver": receiver_id,
                "message": message,
                "image_url": image_url,
                "timestamp": datetime.utcnow()
            })

    
        return redirect(url_for("chat", receiver_id=receiver_id)) #reloads page to show new messages

   #get both messages
    messages = fetch_messages(sender_id, receiver_id)
    receiver = fetch_receiver_name(receiver_id)

   #check role in database to determine the base
    base_template = "vendor_base.html" if session.get("role") == "vendor" else "base.html"

    return render_template(
        "chat.html",
        messages=messages,
        receiver_name=receiver,
        receiver_id=receiver_id,
        base_template=base_template  #pass the logic to not have duplicate chat
    )

# fetch messages between the sender and receiver
def fetch_messages(sender_id, receiver_id):
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT c.*, u.Username AS SenderName
            FROM Chat c
            JOIN User u ON c.SenderID = u.UserID
            WHERE (c.SenderID = :sender_id AND c.ReceiverID = :receiver_id)
               OR (c.SenderID = :receiver_id AND c.ReceiverID = :sender_id)
            ORDER BY c.Timestamp ASC
        """), {
            "sender_id": sender_id,
            "receiver_id": receiver_id
        })
        return result.fetchall()

# Fetch the name of the receiver
def fetch_receiver_name(receiver_id):
    with engine.connect() as conn:
        return conn.execute(text("SELECT Username FROM User WHERE UserID = :id"), {"id": receiver_id}).scalar()


#list all the users 
@app.route("/chat_users", methods=["GET", "POST"])
def chat_users():
    current_user_id = session.get("user_id")
    if not current_user_id:
        flash("Please log in to view users.", "warning")
        return redirect(url_for("login"))
    
    search_query = request.form.get("search_query", "") 

    with engine.connect() as conn:
        if search_query:
            #search for user
            users = conn.execute(text("""
                SELECT UserID, Username 
                FROM User 
                WHERE UserID != :current_user_id 
                AND Username LIKE :search_query
            """), {"current_user_id": current_user_id, "search_query": f"%{search_query}%"}).fetchall()
        else:
            # show all the users if you cant find the searched one
            users = conn.execute(text("""
                SELECT UserID, Username 
                FROM User 
                WHERE UserID != :current_user_id
            """), {"current_user_id": current_user_id}).fetchall()

    # Set base_template here
    base_template = "vendor_base.html" if session.get("role") == "vendor" else "base.html"
    
    return render_template("chat_users.html", users=users, search_query=search_query, base_template=base_template)

@app.route("/account")
def account():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in to view your account info.", "warning")
        return redirect(url_for("login"))

    with engine.connect() as conn:
        user = conn.execute(text("SELECT * FROM User WHERE UserID = :uid"), {"uid": user_id}).fetchone()

    # Determine base template based on role
    role = session.get("role", "customer")
    base_template = "vendor_base.html" if role == "vendor" else "base.html"

    return render_template("account.html", user=user, base_template=base_template)



# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)
