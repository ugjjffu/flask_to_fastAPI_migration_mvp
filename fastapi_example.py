# FastAPI Migration Example - Modernized Implementation
# This demonstrates the converted FastAPI structure with improvements

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
from supabase import create_client, Client
import os
from fastapi.responses import JSONResponse
import logging

# Initialize FastAPI app
app = FastAPI(
    title="Mandarin Blueprint API",
    description="Modernized FastAPI backend for Mandarin learning platform",
    version="2.0.0"
)
logger = logging.getLogger(__name__)
# Supabase configuration
# supabase_url = os.getenv("SUPABASE_URL", "YOUR_SUPABASE_URL")
# supabase_key = os.getenv("SUPABASE_KEY", "YOUR_SUPABASE_KEY")
supabase_url = "https://mjcoxnkdtxhbzaoxjpen.supabase.co"
supabase_key = "sb_publishable_p6dm-Be1gx81qgvHiFovQg__I_xcSOn"
supabase: Client = create_client(supabase_url, supabase_key)

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


# ============= Pydantic Models (Request/Response) =============

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    username: str
    invitation_code: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CourseResponse(BaseModel):
    id: int
    title: str
    description: str
    published: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class EnrollmentResponse(BaseModel):
    id: int
    user_id: int
    course_id: int
    enrolled_at: datetime
    progress: int
    
    class Config:
        from_attributes = True


class ReviewResponse(BaseModel):
    id: int
    user_id: int
    character_id: int
    repetition: int
    easiness: float
    interval: float
    next_review: datetime
    last_review: Optional[datetime]
    
    class Config:
        from_attributes = True


class ReviewSubmit(BaseModel):
    review_id: int
    quality: int
    
    @validator('quality')
    def validate_quality(cls, v):
        if not 0 <= v <= 5:
            raise ValueError('Quality must be between 0 and 5')
        return v


# ============= Authentication & Security =============

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    # Get user from database
    user = supabase.table('users').select('id, email, username, created_at').eq('id', user_id).execute()
    
    if not user.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user.data[0]


# ============= Authentication Routes =============

@app.post("/api/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    """User registration endpoint with improved validation"""
    
    # Verify invitation code
    invitation = supabase.table('invitation_codes').select('*').eq(
        'code', user_data.invitation_code
    ).eq('used', False).execute()
    
    if not invitation.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or used invitation code"
        )
    
    # Check if user already exists
    existing_user = supabase.table('users').select('id').eq('email', user_data.email).execute()
    if existing_user.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password
    hashed_password = get_password_hash(user_data.password)
    
    # Create user
    try:
        user = supabase.table('users').insert({
            'email': user_data.email,
            'username': user_data.username,
            'password_hash': hashed_password,
            'created_at': datetime.utcnow().isoformat()
        }).execute()
        
        user_record = user.data[0]
        
        # Mark invitation code as used
        supabase.table('invitation_codes').update({
            'used': True,
            'used_by': user_record['id'],
            'used_at': datetime.utcnow().isoformat()
        }).eq('code', user_data.invitation_code).execute()
        
        # Create access token
        access_token = create_access_token(data={"sub": user_record['id']})
        
        return Token(
            access_token=access_token,
            user=UserResponse(**user_record)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@app.post("/api/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    """User login endpoint with JWT token generation"""
    
    # Get user from database
    user = supabase.table('users').select('*').eq('email', credentials.email).execute()
    
    if not user.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    user_data = user.data[0]
    
    # Verify password
    if not verify_password(credentials.password, user_data['password_hash']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": user_data['id']})
    
    return Token(
        access_token=access_token,
        user=UserResponse(
            id=user_data['id'],
            email=user_data['email'],
            username=user_data['username'],
            created_at=user_data['created_at']
        )
    )


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user information"""
    return UserResponse(**current_user)


# ============= Course Management Routes =============

@app.get("/api/courses", response_model=List[CourseResponse])
async def get_courses():
    """Get all published courses"""
    courses = supabase.table('courses').select('*').eq('published', True).execute()
    return [CourseResponse(**course) for course in courses.data]


@app.get("/api/courses/{course_id}", response_model=dict)
async def get_course(course_id: int):
    """Get specific course with content"""
    
    # Get course
    course = supabase.table('courses').select('*').eq('id', course_id).execute()
    
    if not course.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Get course content
    content = supabase.table('course_content').select('*').eq(
        'course_id', course_id
    ).order('sequence').execute()
    
    course_data = course.data[0]
    course_data['content'] = content.data
    
    return course_data


@app.post("/api/courses/{course_id}/enroll", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll_course(course_id: int, current_user: dict = Depends(get_current_user)):
    """Enroll authenticated user in a course"""
    
    # Check if course exists
    course = supabase.table('courses').select('id').eq('id', course_id).execute()
    if not course.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if already enrolled
    enrollment = supabase.table('enrollments').select('*').eq(
        'user_id', current_user['id']
    ).eq('course_id', course_id).execute()
    
    if enrollment.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already enrolled in this course"
        )
    
    # Create enrollment
    new_enrollment = supabase.table('enrollments').insert({
        'user_id': current_user['id'],
        'course_id': course_id,
        'enrolled_at': datetime.utcnow().isoformat(),
        'progress': 0
    }).execute()
    
    return EnrollmentResponse(**new_enrollment.data[0])


# ============= Review System Routes (Spaced Repetition) =============

@app.get("/api/reviews/due", response_model=dict)
async def get_due_reviews(current_user: dict = Depends(get_current_user)):
    """Get reviews due for current user using spaced repetition algorithm"""
    
    current_time = datetime.utcnow().isoformat()
    
    # Get due reviews
    reviews = supabase.table('reviews').select('*, characters(*)').eq(
        'user_id', current_user['id']
    ).lte('next_review', current_time).execute()
    
    return {
        "reviews": reviews.data,
        "count": len(reviews.data)
    }


@app.post("/api/reviews/submit", response_model=dict)
async def submit_review(review_data: ReviewSubmit, current_user: dict = Depends(get_current_user)):
    """Submit review and update spaced repetition schedule using SM-2 algorithm"""
    
    # Get current review
    review = supabase.table('reviews').select('*').eq(
        'id', review_data.review_id
    ).eq('user_id', current_user['id']).execute()
    
    if not review.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    
    review_record = review.data[0]
    
    # SM-2 Algorithm Implementation
    repetition = review_record.get('repetition', 0) + 1
    easiness = review_record.get('easiness', 2.5)
    interval = review_record.get('interval', 1)
    quality = review_data.quality
    
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
    next_review = datetime.utcnow() + timedelta(days=new_interval)
    
    # Update review
    updated_review = supabase.table('reviews').update({
        'repetition': new_repetition,
        'easiness': new_easiness,
        'interval': new_interval,
        'next_review': next_review.isoformat(),
        'last_review': datetime.utcnow().isoformat()
    }).eq('id', review_data.review_id).execute()
    
    return {
        "message": "Review submitted successfully",
        "next_review": next_review.isoformat(),
        "interval_days": new_interval,
        "easiness_factor": new_easiness
    }


# ============= Health Check =============

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


@app.exception_handler(Exception)
async def global_exception(request, exc):
    logger.error(f"Global error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal error"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
