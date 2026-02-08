# Flask Blueprint Example - Original Implementation
# This demonstrates the typical Flask structure before migration

from flask import Blueprint, request, jsonify, session
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
import jwt
import datetime
from supabase import create_client, Client

# Flask Blueprint for Authentication
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
# Supabase client (simplified)
supabase_url = "https://mjcoxnkdtxhbzaoxjpen.supabase.co"
supabase_key = "sb_publishable_p6dm-Be1gx81qgvHiFovQg__I_xcSOn"
supabase: Client = create_client(supabase_url, supabase_key)

SECRET_KEY = "your-secret-key"

# Session-based authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/register', methods=['POST'])
def register():
    """User registration endpoint"""
    data = request.get_json()
    
    # Validation
    email = data.get('email')
    password = data.get('password')
    username = data.get('username')
    invitation_code = data.get('invitation_code')
    
    if not all([email, password, username, invitation_code]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Verify invitation code
    invitation = supabase.table('invitation_codes').select('*').eq('code', invitation_code).eq('used', False).execute()
    
    if not invitation.data:
        return jsonify({"error": "Invalid or used invitation code"}), 400
    
    # Hash password
    hashed_password = generate_password_hash(password)
    
    # Create user
    try:
        user = supabase.table('users').insert({
            'email': email,
            'username': username,
            'password_hash': hashed_password,
            'created_at': datetime.datetime.utcnow().isoformat()
        }).execute()
        
        # Mark invitation code as used
        supabase.table('invitation_codes').update({
            'used': True,
            'used_by': user.data[0]['id'],
            'used_at': datetime.datetime.utcnow().isoformat()
        }).eq('code', invitation_code).execute()
        
        # Create session
        session['user_id'] = user.data[0]['id']
        session['email'] = email
        
        return jsonify({
            "message": "Registration successful",
            "user": {
                "id": user.data[0]['id'],
                "email": email,
                "username": username
            }
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """User login endpoint"""
    data = request.get_json()
    
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    
    # Get user from database
    user = supabase.table('users').select('*').eq('email', email).execute()
    
    if not user.data:
        return jsonify({"error": "Invalid credentials"}), 401
    
    user_data = user.data[0]
    
    # Verify password
    if not check_password_hash(user_data['password_hash'], password):
        return jsonify({"error": "Invalid credentials"}), 401
    
    # Create session
    session['user_id'] = user_data['id']
    session['email'] = user_data['email']
    
    return jsonify({
        "message": "Login successful",
        "user": {
            "id": user_data['id'],
            "email": user_data['email'],
            "username": user_data['username']
        }
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """User logout endpoint"""
    session.clear()
    return jsonify({"message": "Logout successful"}), 200


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current user information"""
    user_id = session.get('user_id')
    
    user = supabase.table('users').select('id, email, username, created_at').eq('id', user_id).execute()
    
    if not user.data:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({"user": user.data[0]}), 200


# Flask Blueprint for Course Management
course_bp = Blueprint('courses', __name__, url_prefix='/api/courses')


@course_bp.route('/', methods=['GET'])
def get_courses():
    """Get all available courses"""
    courses = supabase.table('courses').select('*').eq('published', True).execute()
    
    return jsonify({"courses": courses.data}), 200


@course_bp.route('/<int:course_id>', methods=['GET'])
def get_course(course_id):
    """Get specific course details"""
    course = supabase.table('courses').select('*').eq('id', course_id).execute()
    
    if not course.data:
        return jsonify({"error": "Course not found"}), 404
    
    # Get course content
    content = supabase.table('course_content').select('*').eq('course_id', course_id).order('sequence').execute()
    
    course_data = course.data[0]
    course_data['content'] = content.data
    
    return jsonify({"course": course_data}), 200


@course_bp.route('/<int:course_id>/enroll', methods=['POST'])
@login_required
def enroll_course(course_id):
    """Enroll user in a course"""
    user_id = session.get('user_id')
    
    # Check if course exists
    course = supabase.table('courses').select('*').eq('id', course_id).execute()
    if not course.data:
        return jsonify({"error": "Course not found"}), 404
    
    # Check if already enrolled
    enrollment = supabase.table('enrollments').select('*').eq('user_id', user_id).eq('course_id', course_id).execute()
    
    if enrollment.data:
        return jsonify({"error": "Already enrolled"}), 400
    
    # Create enrollment
    new_enrollment = supabase.table('enrollments').insert({
        'user_id': user_id,
        'course_id': course_id,
        'enrolled_at': datetime.datetime.utcnow().isoformat(),
        'progress': 0
    }).execute()
    
    return jsonify({
        "message": "Enrollment successful",
        "enrollment": new_enrollment.data[0]
    }), 201


# Flask Blueprint for Review System (Spaced Repetition)
review_bp = Blueprint('reviews', __name__, url_prefix='/api/reviews')


@review_bp.route('/due', methods=['GET'])
@login_required
def get_due_reviews():
    """Get reviews due for current user"""
    user_id = session.get('user_id')
    current_time = datetime.datetime.utcnow().isoformat()
    
    # Get due reviews using spaced repetition algorithm
    reviews = supabase.table('reviews').select('*, characters(*)').eq('user_id', user_id).lte('next_review', current_time).execute()
    
    return jsonify({
        "reviews": reviews.data,
        "count": len(reviews.data)
    }), 200


@review_bp.route('/submit', methods=['POST'])
@login_required
def submit_review():
    """Submit a review and update spaced repetition schedule"""
    user_id = session.get('user_id')
    data = request.get_json()
    
    review_id = data.get('review_id')
    quality = data.get('quality')  # 0-5 scale (SM-2 algorithm)
    
    if not review_id or quality is None:
        return jsonify({"error": "Missing required fields"}), 400
    
    # Get current review
    review = supabase.table('reviews').select('*').eq('id', review_id).eq('user_id', user_id).execute()
    
    if not review.data:
        return jsonify({"error": "Review not found"}), 404
    
    review_data = review.data[0]
    
    # Calculate next interval using SM-2 algorithm (simplified)
    repetition = review_data.get('repetition', 0) + 1
    easiness = review_data.get('easiness', 2.5)
    interval = review_data.get('interval', 1)
    
    # Update easiness factor
    new_easiness = easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_easiness = max(1.3, new_easiness)
    
    # Calculate new interval
    if quality < 3:
        new_interval = 1
        new_repetition = 0
    else:
        if repetition == 1:
            new_interval = 1
        elif repetition == 2:
            new_interval = 6
        else:
            new_interval = interval * new_easiness
        new_repetition = repetition
    
    # Calculate next review date
    next_review = datetime.datetime.utcnow() + datetime.timedelta(days=new_interval)
    
    # Update review
    updated_review = supabase.table('reviews').update({
        'repetition': new_repetition,
        'easiness': new_easiness,
        'interval': new_interval,
        'next_review': next_review.isoformat(),
        'last_review': datetime.datetime.utcnow().isoformat()
    }).eq('id', review_id).execute()
    
    return jsonify({
        "message": "Review submitted successfully",
        "next_review": next_review.isoformat(),
        "interval_days": new_interval
    }), 200
