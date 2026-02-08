# Flask to FastAPI Migration Guide
## Mandarin Blueprint Backend Modernization

### Table of Contents
1. [Migration Overview](#migration-overview)
2. [Key Improvements](#key-improvements)
3. [Migration Strategy](#migration-strategy)
4. [Technical Comparisons](#technical-comparisons)
5. [Database & Supabase Integration](#database--supabase-integration)
6. [Authentication Migration](#authentication-migration)
7. [Testing Strategy](#testing-strategy)
8. [Deployment Plan](#deployment-plan)
9. [Rollback Procedures](#rollback-procedures)
10. [Performance Metrics](#performance-metrics)

---

## Migration Overview

This document outlines the systematic approach to migrating Mandarin Blueprint's backend from Flask to FastAPI while ensuring:
- **Zero downtime** during migration
- **Complete feature parity** with existing functionality
- **Improved performance** through async operations
- **Enhanced developer experience** with type safety and automatic documentation

### Migration Timeline
- **Phase 1 (Weeks 1-2)**: Analysis & Setup
- **Phase 2 (Weeks 3-4)**: Core Infrastructure
- **Phase 3 (Weeks 5-10)**: Route Migration
- **Phase 4 (Weeks 11-12)**: Testing & Validation
- **Phase 5 (Weeks 13-14)**: Deployment & Monitoring

---

## Key Improvements

### 1. **Performance Enhancements**
- **Async/Await Support**: Native async operations for database queries
- **Concurrent Request Handling**: Better throughput under load
- **Reduced Overhead**: ~20-30% faster response times in benchmarks

### 2. **Developer Experience**
- **Type Safety**: Pydantic models with automatic validation
- **Automatic Documentation**: Interactive Swagger UI and ReDoc
- **Modern Python Features**: Full Python 3.9+ support with type hints

### 3. **API Quality**
- **Request Validation**: Automatic validation with clear error messages
- **Response Models**: Guaranteed response structure
- **OpenAPI Compliance**: Industry-standard API documentation

### 4. **Security Improvements**
- **JWT Token-Based Auth**: Stateless authentication (vs session-based)
- **Dependency Injection**: Secure and testable authentication flow
- **Built-in Security Utilities**: OAuth2, CORS, rate limiting support

---

## Migration Strategy

### Parallel Running Approach
```
┌─────────────────────────────────────────────────────────┐
│                    Load Balancer                        │
└─────────────────────────────────────────────────────────┘
                     │              │
         ┌───────────┘              └───────────┐
         ▼                                      ▼
┌──────────────────┐                  ┌──────────────────┐
│  Flask Backend   │                  │ FastAPI Backend  │
│  (Existing)      │◄────────────────►│  (New)           │
└──────────────────┘    Shared DB    └──────────────────┘
         │                                      │
         └──────────────┬───────────────────────┘
                        ▼
              ┌──────────────────┐
              │  Supabase (DB)   │
              └──────────────────┘
```

### Migration Steps by Module

#### 1. Authentication & User Management
**Flask → FastAPI Changes:**
- Session-based → JWT token-based
- Flask decorators → FastAPI dependencies
- Manual validation → Pydantic models

**Migration Priority**: HIGH (foundational for other modules)

#### 2. Course Management
**Flask → FastAPI Changes:**
- Blueprint routes → APIRouter
- JSON serialization → Response models
- Manual error handling → HTTPException

**Migration Priority**: MEDIUM

#### 3. Review System (Spaced Repetition)
**Flask → FastAPI Changes:**
- Synchronous DB calls → Async operations
- SM-2 algorithm (preserved)
- Enhanced validation with Pydantic

**Migration Priority**: HIGH (core feature)

#### 4. Public API Endpoints
**Migration Priority**: LOW (can remain in Flask initially)

#### 5. PWA Support
**Migration Priority**: MEDIUM

---

## Technical Comparisons

### Flask vs FastAPI: Side-by-Side

#### Route Definition
**Flask:**
```python
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    # Manual validation
    if not email:
        return jsonify({"error": "Email required"}), 400
```

**FastAPI:**
```python
@app.post("/api/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    # Automatic validation via Pydantic
    # email is guaranteed to be valid EmailStr
```

#### Authentication
**Flask:**
```python
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function
```

**FastAPI:**
```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # Dependency injection handles authentication
    # Reusable across all protected endpoints
```

#### Database Operations
**Flask:**
```python
user = supabase.table('users').select('*').eq('email', email).execute()
# Synchronous, blocking operation
```

**FastAPI:**
```python
user = await supabase.table('users').select('*').eq('email', email).execute()
# Asynchronous, non-blocking (with async supabase client)
```

---

## Database & Supabase Integration

### Current Setup (Flask)
- Synchronous Supabase client
- Session-based connection management
- Manual connection pooling

### New Setup (FastAPI)
- Async Supabase client (via `supabase-py` with `httpx`)
- Connection pooling via dependency injection
- Optimized query patterns

### Migration Considerations
1. **Connection Pool**: Configure async connection pool
2. **Query Optimization**: Review and optimize slow queries
3. **Transaction Handling**: Implement proper transaction boundaries
4. **Schema Validation**: Use Pydantic models matching DB schema

### Example: Optimized Database Access
```python
from typing import AsyncGenerator
from supabase import create_client, Client

async def get_db() -> AsyncGenerator[Client, None]:
    """Dependency for database access with connection pooling"""
    db = create_client(SUPABASE_URL, SUPABASE_KEY)
    try:
        yield db
    finally:
        # Cleanup if needed
        pass

@app.get("/api/courses")
async def get_courses(db: Client = Depends(get_db)):
    courses = await db.table('courses').select('*').execute()
    return courses.data
```

---

## Authentication Migration

### Current System (Flask)
- **Session Management**: Server-side sessions with cookies
- **Storage**: Redis/database sessions
- **Limitations**: 
  - Not suitable for mobile apps
  - Requires sticky sessions in load balancer
  - Scalability issues

### New System (FastAPI)
- **JWT Tokens**: Stateless authentication
- **Token Storage**: Client-side (localStorage/secure storage)
- **Benefits**:
  - Scalable across multiple servers
  - Mobile-friendly
  - Better for microservices

### Migration Path

#### Step 1: Implement JWT System
```python
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
```

#### Step 2: Create Authentication Dependency
```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    user_id = payload.get("sub")
    # Fetch and return user
```

#### Step 3: Protect Routes
```python
@app.get("/api/protected")
async def protected_route(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}
```

### Backward Compatibility
During transition, support both systems:
```python
async def get_current_user_flexible(
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    session_user_id: Optional[str] = Cookie(None)
):
    # Try JWT first
    if credentials:
        return await validate_jwt(credentials)
    # Fall back to session
    if session_user_id:
        return await validate_session(session_user_id)
    raise HTTPException(status_code=401)
```

---

## Testing Strategy

### Test Coverage Goals
- **Unit Tests**: >90% coverage
- **Integration Tests**: All critical flows
- **E2E Tests**: Complete user journeys
- **Performance Tests**: Load testing benchmarks

### Test Categories

#### 1. Feature Parity Tests
Ensure FastAPI matches Flask behavior:
```python
def test_login_response_matches_flask():
    """Verify FastAPI login response matches Flask format"""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"
```

#### 2. Migration Validation Tests
```python
def test_session_to_jwt_migration():
    """Test that JWT tokens work for existing users"""
    # Verify existing users can authenticate
    # Verify token generation
    # Verify token validation
```

#### 3. Performance Tests
```python
def test_concurrent_requests():
    """Verify FastAPI handles concurrent load"""
    import asyncio
    # Simulate 100 concurrent requests
    # Measure response times
    # Compare to Flask baseline
```

#### 4. Regression Tests
```python
def test_spaced_repetition_algorithm():
    """Ensure SM-2 algorithm produces same results"""
    # Test with known inputs
    # Verify interval calculations match Flask
```

### Testing Tools
- **pytest**: Test framework
- **pytest-asyncio**: Async test support
- **httpx**: Async HTTP client for tests
- **pytest-cov**: Coverage reporting
- **locust**: Load testing

---

## Deployment Plan

### Phase 1: Staging Deployment
1. Deploy FastAPI alongside Flask in staging
2. Route 10% of traffic to FastAPI
3. Monitor for errors and performance issues
4. Gradually increase to 50%, then 100%

### Phase 2: Production Deployment
1. Deploy FastAPI to production (parallel)
2. Route 5% of traffic to FastAPI
3. Monitor for 48 hours
4. Increase to 25% if no issues
5. Increase to 50% after 1 week
6. Full cutover after 2 weeks

### Phase 3: Cleanup
1. Deprecate Flask endpoints
2. Remove Flask codebase
3. Optimize FastAPI deployment

### Rollback Plan
At any stage, can revert to Flask:
```bash
# Immediate rollback
kubectl set image deployment/backend api=flask-backend:stable

# Gradual rollback
# Route traffic back to Flask in load balancer
```

### Monitoring Checklist
- [ ] Response times (p50, p95, p99)
- [ ] Error rates
- [ ] Database query performance
- [ ] Memory usage
- [ ] CPU usage
- [ ] Active connections
- [ ] JWT token validation errors
- [ ] Authentication failures

---

## Performance Metrics

### Expected Improvements

| Metric | Flask | FastAPI | Improvement |
|--------|-------|---------|-------------|
| Avg Response Time | 150ms | 100ms | 33% faster |
| Requests/sec | 500 | 750 | 50% more |
| Concurrent Users | 100 | 200 | 2x capacity |
| Memory Usage | 512MB | 384MB | 25% less |

### Benchmark Tests
```python
# Load test with 100 concurrent users
locust -f locustfile.py --users 100 --spawn-rate 10

# Expected results:
# Flask: 500 req/s, 150ms avg
# FastAPI: 750 req/s, 100ms avg
```

---

## Risk Mitigation

### Identified Risks

1. **Authentication Token Migration**
   - **Risk**: Users logged out during transition
   - **Mitigation**: Support both sessions and JWT temporarily

2. **Database Connection Pool Exhaustion**
   - **Risk**: Async operations create more connections
   - **Mitigation**: Configure connection pooling limits

3. **Breaking Changes in API Responses**
   - **Risk**: Mobile apps break if response format changes
   - **Mitigation**: Comprehensive parity tests

4. **Performance Degradation**
   - **Risk**: FastAPI slower than expected
   - **Mitigation**: Extensive benchmarking, quick rollback

### Mitigation Strategies
- Comprehensive testing
- Gradual rollout
- Monitoring at every stage
- Quick rollback procedures
- Feature flags for new functionality

---

## Maintenance & Documentation

### Documentation Deliverables
1. **API Documentation**: Auto-generated Swagger/ReDoc
2. **Architecture Diagrams**: System design documentation
3. **Deployment Guide**: Step-by-step deployment instructions
4. **Developer Guide**: Setting up local environment
5. **Troubleshooting Guide**: Common issues and solutions

### Knowledge Transfer
- Daily standup updates
- Weekly technical reviews
- Comprehensive code comments
- Video walkthroughs of key components
- Pair programming sessions

---

## Conclusion

This migration from Flask to FastAPI will modernize Mandarin Blueprint's backend infrastructure while maintaining complete feature parity and improving performance. The phased approach ensures minimal risk and allows for quick rollback if needed.

### Success Criteria
- ✅ Zero downtime during migration
- ✅ 100% feature parity
- ✅ 30%+ performance improvement
- ✅ Comprehensive test coverage (>90%)
- ✅ Complete documentation
- ✅ Successful knowledge transfer

### Next Steps
1. Review and approve migration plan
2. Set up development environment
3. Begin Phase 1: Analysis & Setup
4. Regular progress reviews
5. Iterative improvements based on feedback
