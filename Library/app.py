import os
import certifi

os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

from datetime import datetime, timedelta
import ssl

from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_socketio import SocketIO
from dotenv import load_dotenv

import bcrypt
from supabase import create_client, Client

load_dotenv()

# Create Flask app
app = Flask(__name__)
app.secret_key = "library_management_secret_key"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

socketio = SocketIO(app, cors_allowed_origins="*")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

try:
    bcrypt.gensalt()
    print("bcrypt module ready")
except Exception as e:
    print(f"bcrypt initialization failed: {e}")
    raise

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase client created")
except Exception as e:
    print(f"Supabase SSL error: {e}")
    import httpx
    custom_client = httpx.Client(verify=False)
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY, options={
        'http_client': custom_client
    })
    print("Using fallback SSL configuration (development mode)")

def get_user_by_email(email):
    """Get user by email"""
    try:
        response = supabase.table('users').select('*').eq('email', email).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error getting user by email: {e}")
        return None

def get_user_by_username(username):
    """Get user by username"""
    try:
        response = supabase.table('users').select('*').eq('username', username).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error getting user by username: {e}")
        return None

def get_user_by_student_id(student_id):
    """Get user by student ID"""
    try:
        response = supabase.table('users').select('*').eq('student_id', student_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error getting user by student ID: {e}")
        return None

def create_student(student_id, username, email, password):
    """Create a new student"""
    try:
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
        
        user_data = {
            'student_id': student_id,
            'username': username,
            'email': email,
            'password_hash': password_hash.decode('utf-8'),
            'role': 'student'
        }
        
        print(f"Creating student: {user_data}")
        
        response = supabase.table('users').insert(user_data).execute()
        return response.data[0] if response.data else None, None
    except Exception as e:
        print(f"Error creating student: {e}")
        return None, str(e)

def create_admin(email, username, password):
    """Create a new admin"""
    try:
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
        
        user_data = {
            'username': username,
            'email': email,
            'password_hash': password_hash.decode('utf-8'),
            'role': 'admin'
        }
        
        print(f"Creating admin: {user_data}")
        
        response = supabase.table('users').insert(user_data).execute()
        return response.data[0] if response.data else None, None
    except Exception as e:
        print(f"Error creating admin: {e}")
        return None, str(e)

def authenticate_user(email, password, role):
    """Authenticate user"""
    try:
        response = supabase.table('users').select('*').eq('email', email).eq('role', role).execute()
        
        if response.data and len(response.data) > 0:
            user = response.data[0]
            if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                return user
        return None
    except Exception as e:
        print(f"Auth error: {e}")
        return None

def create_admin_if_not_exists():
    """Create default admin user if it doesn't exist"""
    try:
        response = supabase.table('users').select('*').eq('email', 'admin@library.com').eq('role', 'admin').execute()
        
        if not response.data:
            password = "admin123"
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
            
            admin_data = {
                'username': 'admin',
                'email': 'admin@library.com',
                'password_hash': password_hash.decode('utf-8'),
                'role': 'admin'
            }
            
            supabase.table('users').insert(admin_data).execute()
            print("=" * 50)
            print("Admin user created automatically!")
            print("Email: admin@library.com")
            print("Password: admin123")
            print("=" * 50)
        else:
            print("Admin user already exists")
    except Exception as e:
        print(f"Note: Admin user creation skipped - {e}")

# ============ BOOK FUNCTIONS ============
def get_all_books():
    """Get all books"""
    try:
        response = supabase.table('books').select('*').order('title').execute()
        return response.data
    except Exception as e:
        print(f"Error getting books: {e}")
        return []
    
@app.route('/update-theme', methods=['POST'])
def update_theme():
    try:
        data = request.json
        theme = data.get('theme')
        if theme:
            session['theme'] = theme
            return jsonify({'success': True})
        return jsonify({'success': False})
    except Exception as e:
        print(f"Error updating theme: {e}")
        return jsonify({'success': False})

# ============ FLASK ROUTES ============

@app.route('/', methods=['GET', 'POST'])
def login():
    theme = request.args.get('theme', session.get('theme', 'dark'))
    session['theme'] = theme

    if 'user_id' in session:
        if session.get('role') == 'student':
            return redirect(url_for('student_dashboard'))
        elif session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        form_type = request.form.get('form_type', 'login')
        
        if form_type == 'login':
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role', 'student')
            
            if not email or not password:
                return render_template('index.html', error="Please enter email and password", theme=theme)
            
            user = authenticate_user(email, password, role)
            
            if user:
                session.permanent = True
                session['user_id'] = user['id']
                session['username'] = user.get('username', '')
                session['role'] = user['role']
                session['email'] = user['email']
                session['student_id'] = user.get('student_id')
                session['theme'] = theme
                
                if role == 'student':
                    return redirect(url_for('student_dashboard', theme=theme))
                elif role == 'admin':
                    return redirect(url_for('admin_dashboard', theme=theme))
            else:
                return render_template('index.html', error="Invalid email or password", theme=theme)
        
        elif form_type == 'signup_student':
            student_id = request.form.get('student_id')
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            
            if not student_id or not username or not email or not password:
                return render_template('index.html', error="Please fill in all required fields", theme=theme)
            
            existing_user = get_user_by_email(email)
            if existing_user:
                return render_template('index.html', error="Email already registered", theme=theme)
            
            existing_username = get_user_by_username(username)
            if existing_username:
                return render_template('index.html', error="Username already taken", theme=theme)
            
            existing_student = get_user_by_student_id(student_id)
            if existing_student:
                return render_template('index.html', error="Student ID already exists", theme=theme)
            
            user, error = create_student(student_id, username, email, password)
            
            if user:
                return render_template('index.html', success="Student account created successfully! Please login.", theme=theme)
            else:
                return render_template('index.html', error=error or "Error creating account", theme=theme)
        
        elif form_type == 'signup_admin':
            email = request.form.get('email')
            username = request.form.get('username')
            password = request.form.get('password')
            
            if not email or not username or not password:
                return render_template('index.html', error="Please fill in all required fields", theme=theme)
            
            existing_user = get_user_by_email(email)
            if existing_user:
                return render_template('index.html', error="Email already registered", theme=theme)
            
            existing_username = get_user_by_username(username)
            if existing_username:
                return render_template('index.html', error="Username already taken", theme=theme)
            
            user, error = create_admin(email, username, password)
            
            if user:
                return render_template('index.html', success="Admin account created successfully! Please login.", theme=theme)
            else:
                return render_template('index.html', error=error or "Error creating account", theme=theme)
        
        elif form_type == 'forgot_password':
            email = request.form.get('email')
            new_password = request.form.get('new_password')
            
            if not email or not new_password:
                return render_template('index.html', error="Please enter email and new password", theme=theme)
            
            user = get_user_by_email(email)
            if not user:
                return render_template('index.html', error="Email not found", theme=theme)
            
            if user.get('role') != 'admin':
                return render_template('index.html', error="Password reset is only available for admin accounts.", theme=theme)
            
            result = update_user_password(email, new_password)
            
            if result:
                return render_template('index.html', success="Admin password reset successfully! Please login with your new password.", theme=theme)
            else:
                return render_template('index.html', error="Error resetting password", theme=theme)
        
        # If no form_type matched
        return render_template('index.html', error="Invalid request", theme=theme)

    # GET request - show login page
    return render_template('index.html', theme=theme)

@app.route('/student_dashboard')
def student_dashboard():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    session.permanent = True 
    
    # Get theme from session or default to dark
    theme = session.get('theme', 'dark')
    
    return render_template('student_dashboard.html', 
                         username=session.get('username'),
                         email=session.get('email'),
                         theme=theme)

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    session.permanent = True 
    
    books = get_all_books()
    # Get theme from session or default to dark
    theme = session.get('theme', 'dark')
    
    return render_template('admin_dashboard.html',
                         username=session.get('username'),
                         email=session.get('email'),
                         books=books,
                         theme=theme)

def update_user_password(email, new_password):
    """Update user password by email"""
    try:
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), salt)
        
        response = supabase.table('users').update({
            'password_hash': password_hash.decode('utf-8')
        }).eq('email', email).execute()
        
        if response.data:
            print(f"Password updated for: {email}")
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error updating password: {e}")
        return None
    


@app.route('/logout')
def logout():
    # Preserve theme when logging out
    theme = session.get('theme', 'dark')
    session.clear()
    session['theme'] = theme  # Keep theme in session
    return redirect(url_for('login', theme=theme))

# ============ API ROUTES ============

@app.route('/api/books', methods=['GET'])
def api_get_books():
    books = get_all_books()
    return jsonify(books)

@app.route('/api/test-connection')
def test_connection():
    try:
        response = supabase.table('users').select('count').execute()
        return jsonify({'status': 'connected', 'message': 'Supabase connection successful!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
# ============ API ROUTES FOR ADMIN DASHBOARD ============

@app.route('/api/admin/reservations', methods=['GET'])
def api_admin_get_reservations():
    """Get all pending reservations - oldest first (FIFO)"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Order by reserved_on ascending (oldest first)
        response = supabase.table('reservations').select('*').eq('status', 'pending').order('reserved_on', desc=False).execute()
        reservations = []
        for res in response.data:
            reservations.append({
                'id': res.get('id'),
                'book_id': res.get('book_id'),
                'book_title': res.get('book_title'),
                'book_author': res.get('book_author'),
                'student_id': res.get('student_id'),
                'student_name': res.get('student_name'),
                'pickup_date': res.get('pickup_date'),
                'reserved_on': res.get('reserved_on')[:10] if res.get('reserved_on') else ''
            })
        return jsonify(reservations)
    except Exception as e:
        print(f"Error getting reservations: {e}")
        return jsonify([])
    
@app.route('/api/admin/reservations/approve/<int:reservation_id>', methods=['POST'])
def api_admin_approve_reservation(reservation_id):
    """Approve a reservation"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get reservation details
        reservation = supabase.table('reservations').select('*').eq('id', reservation_id).execute()
        if not reservation.data:
            return jsonify({'error': 'Reservation not found'}), 404
        
        res = reservation.data[0]
        
        # Get the student_id from users table
        user_response = supabase.table('users').select('student_id, username, email').eq('username', res.get('student_name')).execute()
        
        student_id = res.get('student_id')
        if user_response.data and user_response.data[0].get('student_id'):
            student_id = user_response.data[0].get('student_id')
        
        print(f"Approving reservation - Book: {res.get('book_title')}, Student: {res.get('student_name')}, Student ID: {student_id}")
        
        # Update reservation status
        supabase.table('reservations').update({'status': 'approved'}).eq('id', reservation_id).execute()
        
        current_time = datetime.now()
        
        # Update book status to borrowed
        supabase.table('books').update({
            'status': 'borrowed',
            'borrowed_by': res.get('student_name'),
            'borrowed_by_id': student_id,
            'borrowed_date': current_time.strftime('%Y-%m-%d'),
            'borrowed_datetime': current_time.isoformat(),
            'reserved_by': None,
            'reserved_by_id': None,
            'reserved_date': None
        }).eq('id', res.get('book_id')).execute()
        
        # Add to borrowing history
        history_data = {
            'book_id': res.get('book_id'),
            'book_title': res.get('book_title'),
            'student_name': res.get('student_name'),
            'student_id': student_id,
            'action': 'borrowed',
            'date': current_time.strftime('%Y-%m-%d'),
            'time': current_time.strftime('%H:%M:%S'),
            'full_datetime': current_time.isoformat()
        }
        result = supabase.table('borrowing_history').insert(history_data).execute()
        print(f"History added: {result.data}")
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error approving reservation: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/admin/reserve', methods=['POST'])
def api_admin_reserve_book():
    """Admin reserves a book for a student"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    book_id = data.get('book_id')
    book_title = data.get('book_title')
    book_author = data.get('book_author')
    pickup_date = data.get('pickup_date')
    pickup_time = data.get('pickup_time')
    return_time = data.get('return_time')
    student_id = data.get('student_id')
    
    if not book_id or not pickup_date or not student_id:
        return jsonify({'error': 'Missing required fields (book_id, pickup_date, student_id)'}), 400
    
    try:
        # Fetch student info from database using student_id
        user_response = supabase.table('users').select('username, email').eq('student_id', student_id).execute()
        if not user_response.data:
            return jsonify({'error': 'Student ID not found'}), 404
        
        student_name = user_response.data[0].get('username')
        student_email = user_response.data[0].get('email')
        
        # Check if book exists
        book_response = supabase.table('books').select('*').eq('id', book_id).execute()
        if not book_response.data:
            return jsonify({'error': 'Book not found'}), 404
        
        book = book_response.data[0]
        
        # Check for time slot conflicts
        available, message = is_book_available_for_time(book_id, pickup_date, pickup_time, return_time)
        if not available:
            return jsonify({'error': message}), 400
        
        # Check if student already has a pending reservation for this book on same day
        existing = supabase.table('reservations').select('*').eq('book_id', book_id).eq('student_id', student_id).eq('status', 'pending').execute()
        
        for ex in existing.data:
            if ex.get('pickup_date') == pickup_date:
                return jsonify({'error': 'Student already has a reservation for this book on the same day'}), 400
        
        # Calculate queue position
        existing_reservations = supabase.table('reservations').select('*').eq('book_id', book_id).eq('status', 'pending').execute()
        queue_position = len(existing_reservations.data) + 1
        
        # Create reservation record with student's info (not admin's)
        reservation_data = {
            'book_id': book_id,
            'book_title': book_title,
            'book_author': book_author,
            'student_id': student_id,
            'student_name': student_name,      # Student's name from database
            'student_email': student_email,    # Student's email from database
            'pickup_date': pickup_date,
            'pickup_time': pickup_time,
            'return_time': return_time,
            'reserved_on': datetime.now().isoformat(),
            'queue_position': queue_position,
            'status': 'pending'
        }
        
        result = supabase.table('reservations').insert(reservation_data).execute()
        
        message = f'Book "{book_title}" reserved for {student_name}! Queue position: {queue_position}'
        
        return jsonify({'success': True, 'message': message, 'queue_position': queue_position})
        
    except Exception as e:
        print(f"Error in admin reserve: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/reservations/reject/<int:reservation_id>', methods=['DELETE'])
def api_admin_reject_reservation(reservation_id):
    """Reject/cancel a reservation"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get reservation details
        reservation = supabase.table('reservations').select('*').eq('id', reservation_id).execute()
        if not reservation.data:
            return jsonify({'error': 'Reservation not found'}), 404
        
        res = reservation.data[0]
        
        # Update book status back to available
        supabase.table('books').update({
            'status': 'available',
            'reserved_by': None,
            'reserved_by_id': None,
            'reserved_date': None
        }).eq('id', res.get('book_id')).execute()
        
        # Delete reservation
        supabase.table('reservations').delete().eq('id', reservation_id).execute()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error rejecting reservation: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/admin/books', methods=['GET'])
def api_admin_get_books():
    """Get all books with reservation info"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        response = supabase.table('books').select('*').order('title').execute()
        books = []
        for book in response.data:
            books.append({
                'id': book.get('id'),
                'isbn': book.get('isbn', ''),  # ← ADD THIS LINE
                'title': book.get('title'),
                'author': book.get('author'),
                'status': book.get('status', 'available'),
                'borrowed_by': book.get('borrowed_by'),
                'borrowed_by_id': book.get('borrowed_by_id'),
                'reserved_by': book.get('reserved_by'),
                'reserved_by_id': book.get('reserved_by_id'),
                'reserved_date': book.get('reserved_date'),
                'archive_reason': book.get('archive_reason'),
                'archived_date': book.get('archived_date')
            })
        return jsonify(books)
    except Exception as e:
        print(f"Error getting books: {e}")
        return jsonify([])

@app.route('/api/admin/books', methods=['POST'])
def api_admin_add_book():
    """Add a new book with ISBN"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    isbn = data.get('isbn')
    title = data.get('title')
    author = data.get('author')
    publisher = data.get('publisher', '')
    year = data.get('year', '')
    
    if not isbn or not title or not author:
        return jsonify({'error': 'Missing required fields (ISBN, title, author)'}), 400
    
    try:
        # Check if book already exists by ISBN
        existing = supabase.table('books').select('*').eq('isbn', isbn).execute()
        if existing.data:
            return jsonify({'error': 'ISBN already exists'}), 400
        
        # Generate a simple ID from ISBN (remove dashes, take last 8 chars)
        book_id = isbn.replace('-', '')[-8:]
        
        # Insert new book with both id and isbn
        book_data = {
            'id': book_id,               # Keep for backward compatibility
            'isbn': isbn,                # The real ISBN
            'title': title,
            'author': author,
            'publisher': publisher,
            'published_year': year,
            'status': 'available'
        }
        result = supabase.table('books').insert(book_data).execute()
        return jsonify(result.data[0] if result.data else {})
    except Exception as e:
        print(f"Error adding book: {e}")
        return jsonify({'error': str(e)}), 500

# Update get_all_books to work with both
def get_all_books():
    """Get all books"""
    try:
        response = supabase.table('books').select('*').order('title').execute()
        return response.data
    except Exception as e:
        print(f"Error getting books: {e}")
        return []

@app.route('/api/admin/books/<book_id>', methods=['PUT'])
def api_admin_update_book(book_id):
    """Update a book"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    title = data.get('title')
    author = data.get('author')
    
    if not title or not author:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        result = supabase.table('books').update({
            'title': title,
            'author': author
        }).eq('id', book_id).execute()
        return jsonify(result.data[0] if result.data else {})
    except Exception as e:
        print(f"Error updating book: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/books/<book_id>/borrow', methods=['POST'])
def api_admin_borrow_book(book_id):
    """Borrow a book"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    student_id = data.get('student_id')
    student_name = data.get('student_name')
    return_date = data.get('return_date')
    return_time = data.get('return_time')
    
    if not student_id or not student_name:
        return jsonify({'error': 'Student ID and name required'}), 400
    
    try:
        # Get book details first
        book_result = supabase.table('books').select('*').eq('id', book_id).execute()
        if not book_result.data:
            return jsonify({'error': 'Book not found'}), 404
        
        book = book_result.data[0]
        
        # Get the correct student_id from users table
        user_response = supabase.table('users').select('student_id, username').eq('username', student_name).execute()
        
        actual_student_id = student_id
        if user_response.data and user_response.data[0].get('student_id'):
            actual_student_id = user_response.data[0].get('student_id')
        
        current_time = datetime.now()
        
        # Update book status
        supabase.table('books').update({
            'status': 'borrowed',
            'borrowed_by': student_name,
            'borrowed_by_id': actual_student_id,
            'borrowed_datetime': current_time.isoformat(),
            'borrowed_date': current_time.strftime('%Y-%m-%d'),
            'return_date': return_date,
            'return_time': return_time
        }).eq('id', book_id).execute()
        
        # Add to active borrowings table
        active_borrow_data = {
            'book_id': book_id,
            'book_title': book.get('title'),
            'student_id': actual_student_id,
            'student_name': student_name,
            'borrowed_datetime': current_time.isoformat(),
            'borrowed_date': current_time.strftime('%Y-%m-%d'),
            'return_date': return_date,
            'return_time': return_time,
            'status': 'active'
        }
        supabase.table('active_borrowings').insert(active_borrow_data).execute()
        
        # Add to borrowing history
        history_data = {
            'book_id': book_id,
            'book_title': book.get('title'),
            'student_name': student_name,
            'student_id': actual_student_id,
            'action': 'borrowed',
            'date': current_time.strftime('%Y-%m-%d'),
            'time': current_time.strftime('%H:%M:%S'),
            'full_datetime': current_time.isoformat(),
            'return_date': return_date,
            'return_time': return_time
        }
        supabase.table('borrowing_history').insert(history_data).execute()
        
        return jsonify({'success': True, 'student_name': student_name})
    except Exception as e:
        print(f"Error borrowing book: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/books/<book_id>/return', methods=['POST'])
def api_admin_return_book(book_id):
    """Return a book"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    condition = data.get('condition', '')
    notes = data.get('notes', '')
    
    try:
        # Get current book info
        book = supabase.table('books').select('*').eq('id', book_id).execute()
        if not book.data:
            return jsonify({'error': 'Book not found'}), 404
        
        book_data = book.data[0]
        
        # Get active borrowing record
        active_borrow = supabase.table('active_borrowings').select('*').eq('book_id', book_id).eq('status', 'active').execute()
        
        current_time = datetime.now()
        
        if active_borrow.data:
            # Calculate days borrowed
            borrowed_datetime = active_borrow.data[0].get('borrowed_datetime')
            days_borrowed = (current_time - datetime.fromisoformat(borrowed_datetime)).days if borrowed_datetime else 0
            
            # Move to return history
            return_record = {
                'book_id': book_id,
                'book_title': book_data.get('title'),
                'student_id': book_data.get('borrowed_by_id'),
                'student_name': book_data.get('borrowed_by'),
                'borrowed_datetime': borrowed_datetime,
                'returned_datetime': current_time.isoformat(),
                'returned_date': current_time.strftime('%Y-%m-%d'),
                'returned_time': current_time.strftime('%H:%M:%S'),
                'days_borrowed': days_borrowed
            }
            supabase.table('return_history').insert(return_record).execute()
            
            # Delete from active borrowings
            supabase.table('active_borrowings').delete().eq('book_id', book_id).eq('status', 'active').execute()
        
        # Update book status
        supabase.table('books').update({
            'status': 'available',
            'borrowed_by': None,
            'borrowed_by_id': None,
            'borrowed_datetime': None
        }).eq('id', book_id).execute()
        
        # Add to borrowing history WITH condition and notes
        history_data = {
            'book_id': book_id,
            'book_title': book_data.get('title'),
            'student_name': book_data.get('borrowed_by'),
            'student_id': book_data.get('borrowed_by_id'),
            'action': 'returned',
            'date': current_time.strftime('%Y-%m-%d'),
            'time': current_time.strftime('%H:%M:%S'),
            'full_datetime': current_time.isoformat(),
            'days_borrowed': days_borrowed if active_borrow.data else 0,
            'condition': condition,  # Add this
            'notes': notes  # Add this
        }
        supabase.table('borrowing_history').insert(history_data).execute()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error returning book: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/books/<book_id>/archive', methods=['POST'])
def api_admin_archive_book(book_id):
    """Archive a book (soft delete)"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    reason = data.get('reason', 'disposed')
    
    print(f"Archiving book with identifier: {book_id} with reason: {reason}")
    
    try:
        # Try to find by id first, if not found try by isbn
        result = supabase.table('books').update({
            'status': 'archived',
            'archive_reason': reason,
            'archived_date': datetime.now().isoformat()
        }).eq('isbn', book_id).execute()  # Changed from 'id' to 'isbn'
        
        # If no result, try with id (for backward compatibility)
        if not result.data:
            result = supabase.table('books').update({
                'status': 'archived',
                'archive_reason': reason,
                'archived_date': datetime.now().isoformat()
            }).eq('id', book_id).execute()
        
        print(f"Update result: {result.data}")
        
        if result.data:
            return jsonify({'success': True, 'message': f'Book archived as {reason}'})
        else:
            return jsonify({'error': 'Book not found'}), 404
            
    except Exception as e:
        print(f"Error archiving book: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/admin/books/archived', methods=['GET'])
def api_admin_get_archived_books():
    """Get archived books"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        response = supabase.table('books').select('*').eq('status', 'archived').order('archived_date', desc=True).execute()
        books = []
        for book in response.data:
            books.append({
                'id': book.get('isbn'), 
                'isbn': book.get('isbn'),
                'title': book.get('title'),
                'author': book.get('author'),
                'archive_reason': book.get('archive_reason'),
                'archived_date': book.get('archived_date')
            })
        return jsonify(books)
    except Exception as e:
        print(f"Error getting archived books: {e}")
        return jsonify([])

@app.route('/api/admin/students', methods=['GET'])
def api_admin_get_students():
    """Get all students"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        response = supabase.table('users').select('*').eq('role', 'student').execute()
        students = []
        for user in response.data:
            students.append({
                'id': user.get('student_id') or f"STU-{user.get('id')}",
                'name': user.get('username'),
                'email': user.get('email'),
                'student_id': user.get('student_id'),
                'grade': 'Not set',
                'section': 'Not set'
            })
        return jsonify(students)
    except Exception as e:
        print(f"Error getting students: {e}")
        return jsonify([])

@app.route('/api/admin/students/<student_id>/reset-password', methods=['POST'])
def api_admin_reset_student_password(student_id):
    """Reset student password"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    new_password = data.get('new_password')
    new_email = data.get('new_email')
    
    if not new_password and not new_email:
        return jsonify({'error': 'Nothing to update'}), 400
    
    try:
        update_data = {}
        if new_password:
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), salt)
            update_data['password_hash'] = password_hash.decode('utf-8')
        if new_email:
            update_data['email'] = new_email
        
        result = supabase.table('users').update(update_data).eq('student_id', student_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error resetting password: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/students/<student_id>', methods=['DELETE'])
def api_admin_delete_student(student_id):
    """Delete a student"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        supabase.table('users').delete().eq('student_id', student_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting student: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/students/<student_id>/history', methods=['GET'])
def api_admin_student_history(student_id):
    """Get student borrowing history"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # First, get the actual student_id from users table if needed
        response = supabase.table('borrowing_history').select('*').eq('student_id', student_id).order('date', desc=True).execute()
        
        # If no results, try to find by student_id in users table
        if not response.data:
            user_response = supabase.table('users').select('student_id').eq('student_id', student_id).execute()
            if user_response.data:
                response = supabase.table('borrowing_history').select('*').eq('student_id', user_response.data[0].get('student_id')).order('date', desc=True).execute()
        
        history = []
        for record in response.data:
            history.append({
                'action': record.get('action'),
                'details': record.get('book_title'),
                'date': record.get('date')[:10] if record.get('date') else '',
                'time': record.get('time', ''),
                'condition': record.get('condition', ''),
                'notes': record.get('notes', ''),
                'days_borrowed': record.get('days_borrowed', 0)
            })
        return jsonify(history)
    except Exception as e:
        print(f"Error getting history: {e}")
        return jsonify([])

# ============ API ROUTES FOR STUDENT DASHBOARD ============
@app.route('/api/student/books', methods=['GET'])
def api_student_get_books():
    """Get all books for students with waitlist count"""
    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        response = supabase.table('books').select('*').neq('status', 'archived').execute()
        books = []
        for book in response.data:
            # Get waitlist count for borrowed books
            waitlist_count = 0
            if book.get('status') == 'borrowed':
                waitlist_result = supabase.table('waitlist').select('*').eq('book_id', book.get('id')).eq('status', 'waiting').execute()
                waitlist_count = len(waitlist_result.data)
            
            books.append({
                'id': book.get('id'),
                'title': book.get('title'),
                'author': book.get('author'),
                'status': book.get('status', 'available'),
                'waitlist_count': waitlist_count
            })
        return jsonify(books)
    except Exception as e:
        print(f"Error getting books: {e}")
        return jsonify([])

@app.route('/api/student/reservations', methods=['GET'])
def api_student_get_reservations():
    """Get student's reservations with queue position"""
    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    
    student_id = session.get('student_id') or session.get('email')
    
    try:
        # Get all reservations (pending, approved, notified)
        response = supabase.table('reservations').select('*').eq('student_id', student_id).order('queue_position').execute()
        reservations = []
        for res in response.data:
            reservations.append({
                'id': res.get('book_id'),
                'title': res.get('book_title'),
                'author': res.get('book_author'),
                'pickupDate': res.get('pickup_date'),
                'pickupTime': res.get('pickup_time', '09:00'),
                'returnTime': res.get('return_time', '17:00'),
                'queuePosition': res.get('queue_position'),
                'status': res.get('status'),  # pending, approved, notified, completed
                'reservedOn': res.get('reserved_on')
            })
        return jsonify(reservations)
    except Exception as e:
        print(f"Error getting reservations: {e}")
        return jsonify([])

@app.route('/api/student/reserve', methods=['POST'])
def api_student_reserve_book():
    """Reserve a book with time slot (checks for conflicts)"""
    # Allow both student and admin to make reservations
    if 'user_id' not in session or (session.get('role') != 'student' and session.get('role') != 'admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    book_id = data.get('book_id')
    book_title = data.get('book_title')
    book_author = data.get('book_author')
    pickup_date = data.get('pickup_date')
    pickup_time = data.get('pickup_time')
    return_time = data.get('return_time')
    
    if not book_id or not pickup_date:
        return jsonify({'error': 'Missing required fields'}), 400
    
    student_id = session.get('student_id') or session.get('email')
    student_name = session.get('username')
    student_email = session.get('email')
    
    try:
        # Check if book exists
        book_response = supabase.table('books').select('*').eq('id', book_id).execute()
        if not book_response.data:
            return jsonify({'error': 'Book not found'}), 404
        
        book = book_response.data[0]
        
        # Check for time slot conflicts
        available, message = is_book_available_for_time(book_id, pickup_date, pickup_time, return_time)
        if not available:
            return jsonify({'error': message}), 400
        
        # Check if student already has a pending reservation for this book on same day
        existing = supabase.table('reservations').select('*').eq('book_id', book_id).eq('student_id', student_id).eq('status', 'pending').execute()
        
        # Check if same day conflict
        for ex in existing.data:
            if ex.get('pickup_date') == pickup_date:
                return jsonify({'error': 'You already have a reservation for this book on the same day'}), 400
        
        # Calculate queue position
        existing_reservations = supabase.table('reservations').select('*').eq('book_id', book_id).eq('status', 'pending').execute()
        queue_position = len(existing_reservations.data) + 1
        
        # Create reservation record
        reservation_data = {
            'book_id': book_id,
            'book_title': book_title,
            'book_author': book_author,
            'student_id': student_id,
            'student_name': student_name,
            'student_email': student_email,
            'pickup_date': pickup_date,
            'pickup_time': pickup_time,
            'return_time': return_time,
            'reserved_on': datetime.now().isoformat(),
            'queue_position': queue_position,
            'status': 'pending'  # Always pending, no auto-approve
        }
        
        result = supabase.table('reservations').insert(reservation_data).execute()
        
        # REMOVED AUTO-APPROVE CODE - Admin must approve all reservations
        message = f'Book "{book_title}" reserved! Queue position: {queue_position}'
        
        return jsonify({'success': True, 'message': message, 'queue_position': queue_position})
        
    except Exception as e:
        print(f"Error reserving book: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/student/cancel-reservation/<book_id>', methods=['DELETE'])
def api_student_cancel_reservation(book_id):
    """Cancel a reservation"""
    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    
    student_id = session.get('student_id') or session.get('email')
    
    try:
        # Update book status back to available
        supabase.table('books').update({
            'status': 'available',
            'reserved_by': None,
            'reserved_by_id': None,
            'reserved_date': None
        }).eq('id', book_id).execute()
        
        # Delete reservation
        supabase.table('reservations').delete().eq('book_id', book_id).eq('student_id', student_id).execute()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error canceling reservation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/student/history', methods=['GET'])
def api_student_get_history():
    """Get student's borrowing history with time and notes"""
    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session.get('user_id')
    
    try:
        user_response = supabase.table('users').select('student_id, username').eq('id', user_id).execute()
        
        if not user_response.data:
            return jsonify([])
        
        user = user_response.data[0]
        student_id = user.get('student_id')
        
        if not student_id:
            student_id = user.get('username')
        
        response = supabase.table('borrowing_history').select('*').eq('student_id', student_id).order('full_datetime', desc=True).execute()
        
        if len(response.data) == 0:
            response = supabase.table('borrowing_history').select('*').eq('student_name', user.get('username')).order('full_datetime', desc=True).execute()
        
        history = []
        for record in response.data:
            history.append({
                'title': record.get('book_title'),
                'date': record.get('date', ''),
                'time': record.get('time', ''),
                'action': record.get('action'),
                'full_datetime': record.get('full_datetime', ''),
                'days_borrowed': record.get('days_borrowed', 0),
                'condition': record.get('condition', ''),  # Add this
                'notes': record.get('notes', '')  # Add this
            })
        return jsonify(history)
    except Exception as e:
        print(f"Error getting history: {e}")
        return jsonify([])
    
# ============ WAITLIST/ RESERVATION QUEUE ============

@app.route('/api/student/waitlist', methods=['POST'])
def api_student_add_to_waitlist():
    """Add student to waitlist for a borrowed book"""
    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    book_id = data.get('book_id')
    book_title = data.get('book_title')
    book_author = data.get('book_author')
    email = data.get('email')
    
    student_id = session.get('student_id') or session.get('email')
    student_name = session.get('username')
    
    try:
        # Check if already on waitlist
        existing = supabase.table('waitlist').select('*').eq('book_id', book_id).eq('student_id', student_id).execute()
        if existing.data:
            return jsonify({'error': 'You are already on the waitlist for this book'}), 400
        
        # Add to waitlist
        waitlist_data = {
            'book_id': book_id,
            'book_title': book_title,
            'book_author': book_author,
            'student_id': student_id,
            'student_name': student_name,
            'email': email,
            'joined_date': datetime.now().isoformat(),
            'status': 'waiting',
            'position': 0  # Will be calculated
        }
        
        result = supabase.table('waitlist').insert(waitlist_data).execute()
        
        # Update waitlist position for all entries
        update_waitlist_positions(book_id)
        
        return jsonify({'success': True, 'message': 'Added to waitlist'})
    except Exception as e:
        print(f"Error adding to waitlist: {e}")
        return jsonify({'error': str(e)}), 500

def update_waitlist_positions(book_id):
    """Update waitlist positions based on join date"""
    try:
        waitlist = supabase.table('waitlist').select('*').eq('book_id', book_id).eq('status', 'waiting').order('joined_date').execute()
        for idx, entry in enumerate(waitlist.data):
            supabase.table('waitlist').update({'position': idx + 1}).eq('id', entry['id']).execute()
    except Exception as e:
        print(f"Error updating positions: {e}")

@app.route('/api/student/waitlist/<book_id>', methods=['GET'])
def api_student_get_waitlist(book_id):
    """Get waitlist count for a book"""
    try:
        response = supabase.table('waitlist').select('*').eq('book_id', book_id).eq('status', 'waiting').execute()
        return jsonify({'count': len(response.data), 'waitlist': response.data})
    except Exception as e:
        print(f"Error getting waitlist: {e}")
        return jsonify({'count': 0, 'waitlist': []})

@app.route('/api/admin/books/<book_id>/notify-waitlist', methods=['POST'])
def api_admin_notify_waitlist(book_id):
    """Notify all students on waitlist that book is available"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        waitlist = supabase.table('waitlist').select('*').eq('book_id', book_id).eq('status', 'waiting').order('position').execute()
        
        notified_count = 0
        for entry in waitlist.data:
            print(f"NOTIFY: {entry['email']} - Book '{entry['book_title']}' is now available!")
            
            supabase.table('waitlist').update({'status': 'notified', 'notified_date': datetime.now().isoformat()}).eq('id', entry['id']).execute()
            notified_count += 1
        
        return jsonify({'success': True, 'notified_count': notified_count})
    except Exception as e:
        print(f"Error notifying waitlist: {e}")
        return jsonify({'error': str(e)}), 500

def is_book_available_for_time(book_id, pickup_date, pickup_time, return_time, exclude_reservation_id=None):
    """Check if book is available for the requested time slot"""
    try:
        reservations = supabase.table('reservations').select('*').eq('book_id', book_id).eq('status', 'pending').execute()
        
        requested_start = f"{pickup_date} {pickup_time}"
        requested_end = f"{pickup_date} {return_time}"
        
        for res in reservations.data:
            if exclude_reservation_id and res.get('id') == exclude_reservation_id:
                continue
                
            existing_date = res.get('pickup_date')
            existing_pickup = res.get('pickup_time', '09:00')
            existing_return = res.get('return_time', '17:00')
            
            existing_start = f"{existing_date} {existing_pickup}"
            existing_end = f"{existing_date} {existing_return}"
            
            if (requested_start < existing_end and requested_end > existing_start):
                return False, f"Time slot conflicts with existing reservation (Pickup: {existing_pickup}, Return: {existing_return})"
        
        book = supabase.table('books').select('*').eq('id', book_id).execute()
        if book.data and book.data[0].get('status') == 'borrowed':
            borrowed_until = book.data[0].get('borrowed_until')
            if borrowed_until and borrowed_until > datetime.now().isoformat():
                return False, "Book is currently borrowed and not yet returned"
        
        return True, "Available"
    except Exception as e:
        print(f"Error checking availability: {e}")
        return True, "Available" 

# ============ ANALYTICS API ROUTES ============

@app.route('/api/admin/analytics/daily', methods=['GET'])
def api_admin_analytics_daily():
    """Get most borrowed books for today"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        response = supabase.table('borrowing_history').select('book_title').eq('date', today).execute()
        
        # Count occurrences
        book_counts = {}
        for record in response.data:
            title = record.get('book_title')
            if title:
                book_counts[title] = book_counts.get(title, 0) + 1
        
        # Sort by count and get top 5
        sorted_books = sorted(book_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return jsonify({
            'labels': [book[0] for book in sorted_books],
            'data': [book[1] for book in sorted_books],
            'period': 'today'
        })
    except Exception as e:
        print(f"Error getting daily analytics: {e}")
        return jsonify({'labels': [], 'data': [], 'period': 'today'})

@app.route('/api/admin/analytics/monthly', methods=['GET'])
def api_admin_analytics_monthly():
    """Get most borrowed books for this month"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        current_month = datetime.now().strftime('%Y-%m')
        response = supabase.table('borrowing_history').select('book_title, date').execute()
        
        # Filter by current month
        book_counts = {}
        for record in response.data:
            date = record.get('date', '')
            if date and date.startswith(current_month):
                title = record.get('book_title')
                if title:
                    book_counts[title] = book_counts.get(title, 0) + 1
        
        # Sort by count and get top 5
        sorted_books = sorted(book_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return jsonify({
            'labels': [book[0] for book in sorted_books],
            'data': [book[1] for book in sorted_books],
            'period': 'this month'
        })
    except Exception as e:
        print(f"Error getting monthly analytics: {e}")
        return jsonify({'labels': [], 'data': [], 'period': 'this month'})

@app.route('/api/admin/analytics/yearly', methods=['GET'])
def api_admin_analytics_yearly():
    """Get most borrowed books for this year"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        current_year = datetime.now().strftime('%Y')
        response = supabase.table('borrowing_history').select('book_title, date').execute()
        
        # Filter by current year
        book_counts = {}
        for record in response.data:
            date = record.get('date', '')
            if date and date.startswith(current_year):
                title = record.get('book_title')
                if title:
                    book_counts[title] = book_counts.get(title, 0) + 1
        
        # Sort by count and get top 5
        sorted_books = sorted(book_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return jsonify({
            'labels': [book[0] for book in sorted_books],
            'data': [book[1] for book in sorted_books],
            'period': 'this year'
        })
    except Exception as e:
        print(f"Error getting yearly analytics: {e}")
        return jsonify({'labels': [], 'data': [], 'period': 'this year'}) 

with app.app_context():
    create_admin_if_not_exists()
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)