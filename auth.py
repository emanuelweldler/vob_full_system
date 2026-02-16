"""
Authentication and session management
"""
import hashlib
import secrets
from db_connect.db_utils import get_connection

# In-memory session storage (session_token -> username)
# In production, you'd use Redis or database-backed sessions
SESSIONS = {}


def hash_password(password):
    """
    Hash password using SHA256
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hexadecimal hash of the password
    """
    return hashlib.sha256(password.encode()).hexdigest()


def generate_session_token():
    """
    Generate a secure random session token
    
    Returns:
        str: URL-safe random token (32 bytes)
    """
    return secrets.token_urlsafe(32)


def verify_login(username, password):
    """
    Verify username and password against database
    
    Args:
        username: Username to check
        password: Plain text password to verify
        
    Returns:
        dict: User information if credentials valid, None otherwise
        Dictionary contains: id, username, first_name, last_name, role, 
                            department, login_count, last_login, is_active
    """
    conn = get_connection()
    try:
        password_hash = hash_password(password)
        
        sql = """
            SELECT id, username, first_name, last_name, role, department, 
                   login_count, last_login, is_active
            FROM users
            WHERE username = ? AND password_hash = ? AND is_active = 1
        """
        
        user = conn.execute(sql, (username, password_hash)).fetchone()
        
        if user:
            # Update login count and last login time
            user_id = user['id']
            conn.execute("""
                UPDATE users 
                SET login_count = login_count + 1,
                    last_login = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (user_id,))
            conn.commit()
            
            return dict(user)
        
        return None
    finally:
        conn.close()


def get_user_by_session(session_token):
    """
    Get user data from session token
    
    Args:
        session_token: Session token from cookie
        
    Returns:
        dict: User information if session valid, None otherwise
        Dictionary contains: id, username, first_name, last_name, role, 
                            department, login_count, last_login
    """
    username = SESSIONS.get(session_token)
    if not username:
        return None
    
    conn = get_connection()
    try:
        sql = """
            SELECT id, username, first_name, last_name, role, department,
                   login_count, last_login
            FROM users
            WHERE username = ? AND is_active = 1
        """
        user = conn.execute(sql, (username,)).fetchone()
        return dict(user) if user else None
    finally:
        conn.close()


def create_session(username):
    """
    Create a new session for a user
    
    Args:
        username: Username to create session for
        
    Returns:
        str: New session token
    """
    session_token = generate_session_token()
    SESSIONS[session_token] = username
    return session_token


def destroy_session(session_token):
    """
    Destroy a session (logout)
    
    Args:
        session_token: Session token to destroy
        
    Returns:
        bool: True if session existed and was destroyed, False otherwise
    """
    if session_token in SESSIONS:
        del SESSIONS[session_token]
        return True
    return False


def get_all_sessions():
    """
    Get all active sessions (for debugging/admin purposes)
    
    Returns:
        dict: Current sessions dictionary
    """
    return SESSIONS.copy()