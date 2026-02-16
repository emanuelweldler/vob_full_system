import json
import os
import sqlite3
import hashlib
import secrets
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from http.cookies import SimpleCookie

# POINT THIS AT YOUR SQLITE DB FILE:
DB_PATH = r"C:\data\VOB_DB\vob.db"

# Serve files from the "public" folder (your UI)
WEB_ROOT = os.path.join(os.path.dirname(__file__), "public")

# In-memory session storage (username -> session_token)
# In production, you'd use Redis or database
SESSIONS = {}


# ========== AUTHENTICATION FUNCTIONS ==========
def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_session_token():
    """Generate a secure random session token"""
    return secrets.token_urlsafe(32)


def verify_login(username, password):
    """Verify username and password against database"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
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
    """Get user data from session token"""
    username = SESSIONS.get(session_token)
    if not username:
        return None
    
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
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


# ========== DATABASE HELPER FUNCTIONS ==========
def table_has_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    """Check if a table has a specific column"""
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return any(r[1] == col for r in rows)


# ========== VOB QUERIES ==========
def query_vob(member_id="", dob="", payer="", bcbs_state="", facility="", employer="", first_name="", last_name="", limit=50):
    """Query VOB records table"""
    limit = max(1, min(int(limit or 50), 200))

    where = []
    params = {}

    if member_id:
        where.append("""
            (
              insurance_id_clean LIKE :memberLike COLLATE NOCASE
              OR insurance_id LIKE :memberLike COLLATE NOCASE
            )
        """)
        params["memberLike"] = f"%{member_id}%"

    if dob:
        where.append("(dob = :dob)")
        params["dob"] = dob

    if payer:
        # Check if this is a BCBS search with state
        if bcbs_state and ("bcbs" in payer.lower() or "blue" in payer.lower()):
            # Smart BCBS + state search (includes Anthem BCBS and Blue Cross)
            where.append("""
                (
                  (insurance_name_raw LIKE :bcbsLike COLLATE NOCASE
                   OR insurance_name_raw LIKE :blueCrossLike COLLATE NOCASE
                   OR insurance_name_raw LIKE :anthemLike COLLATE NOCASE)
                  AND (
                    insurance_name_raw LIKE :stateLike COLLATE NOCASE
                    OR insurance_name_raw LIKE :stateFullLike COLLATE NOCASE
                  )
                )
            """)
            params["bcbsLike"] = "%bcbs%"
            params["blueCrossLike"] = "%blue%cross%"
            params["anthemLike"] = "%anthem%"
            params["stateLike"] = f"%{bcbs_state}%"
            # Also search for "OF [State]" pattern
            params["stateFullLike"] = f"%OF {bcbs_state}%"
        else:
            # Regular payer search - only search insurance_name_raw since payer_canonical is NULL
            where.append("(insurance_name_raw LIKE :payerLike COLLATE NOCASE)")
            params["payerLike"] = f"%{payer}%"
    elif bcbs_state:
        # BCBS state specified without payer text - auto-search BCBS (includes Anthem and Blue Cross)
        where.append("""
            (
              (insurance_name_raw LIKE :bcbsLike COLLATE NOCASE
               OR insurance_name_raw LIKE :blueCrossLike COLLATE NOCASE
               OR insurance_name_raw LIKE :anthemLike COLLATE NOCASE)
              AND (
                insurance_name_raw LIKE :stateLike COLLATE NOCASE
                OR insurance_name_raw LIKE :stateFullLike COLLATE NOCASE
              )
            )
        """)
        params["bcbsLike"] = "%bcbs%"
        params["blueCrossLike"] = "%blue%cross%"
        params["anthemLike"] = "%anthem%"
        params["stateLike"] = f"%{bcbs_state}%"
        params["stateFullLike"] = f"%OF {bcbs_state}%"

    if facility:
        where.append("(facility_name LIKE :facilityLike COLLATE NOCASE)")
        params["facilityLike"] = f"%{facility}%"

    if employer:
        where.append("(employer_name LIKE :employerLike COLLATE NOCASE)")
        params["employerLike"] = f"%{employer}%"

    if first_name:
        where.append("(first_name LIKE :firstNameLike COLLATE NOCASE)")
        params["firstNameLike"] = f"%{first_name}%"

    if last_name:
        where.append("(last_name LIKE :lastNameLike COLLATE NOCASE)")
        params["lastNameLike"] = f"%{last_name}%"

    if not where:
        raise ValueError(
            "Provide at least one filter (memberId, dob, payer, bcbsState, facility, employer, firstName, lastName)."
        )

    sql = f"""
        SELECT
          id,
          created_at,
          facility_name,
          payer_canonical,
          insurance_name_raw,
          insurance_id,
          insurance_id_clean,
          group_number,
          group_number_clean,
          in_out_network,
          deductible_individual,
          family_deductible,
          oop_individual,
          oop_family,
          self_or_commercial_funded,
          exchange_or_employer,
          employer_name,
          first_name,
          last_name,
          dob,
          source_file,
          error_details
        FROM vob_records
        WHERE {" AND ".join(where)}
        ORDER BY id DESC
        LIMIT {limit};
    """

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ========== REIMBURSEMENT QUERIES ==========
def reimb_summary(prefix="", payer="", bcbs_state="", employer="", first_name="", last_name=""):
    """Query reimbursement summary grouped by member/payer/loc"""
    prefix = (prefix or "").strip()
    payer = (payer or "").strip()
    employer = (employer or "").strip()
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()

    if not prefix and not payer and not bcbs_state and not employer and not first_name and not last_name:
        raise ValueError("Provide at least one filter (prefix/memberId, payer, bcbsState, employer, firstName, lastName).")

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        has_employer = table_has_column(conn, "reimbursement_rates", "employer_name")

        where = []
        params = {}

        if prefix:
            where.append("(member_id LIKE :prefixLike COLLATE NOCASE)")
            params["prefixLike"] = f"{prefix}%"

        if payer:
            # Check if this is a BCBS search with state
            if bcbs_state and ("bcbs" in payer.lower() or "blue" in payer.lower()):
                # Smart BCBS + state search (includes Anthem BCBS and Blue Cross)
                where.append("""
                    (
                      (payer_name LIKE :bcbsLike COLLATE NOCASE
                       OR payer_name LIKE :blueCrossLike COLLATE NOCASE
                       OR payer_name LIKE :anthemLike COLLATE NOCASE)
                      AND (
                        payer_name LIKE :stateLike COLLATE NOCASE
                        OR payer_name LIKE :stateFullLike COLLATE NOCASE
                      )
                    )
                """)
                params["bcbsLike"] = "%bcbs%"
                params["blueCrossLike"] = "%blue%cross%"
                params["anthemLike"] = "%anthem%"
                params["stateLike"] = f"%{bcbs_state}%"
                params["stateFullLike"] = f"%OF {bcbs_state}%"
            else:
                # Regular payer search
                where.append("(payer_name LIKE :payerLike COLLATE NOCASE)")
                params["payerLike"] = f"%{payer}%"
        elif bcbs_state:
            # BCBS state specified without payer text - auto-search BCBS (includes Anthem and Blue Cross)
            where.append("""
                (
                  (payer_name LIKE :bcbsLike COLLATE NOCASE
                   OR payer_name LIKE :blueCrossLike COLLATE NOCASE
                   OR payer_name LIKE :anthemLike COLLATE NOCASE)
                  AND (
                    payer_name LIKE :stateLike COLLATE NOCASE
                    OR payer_name LIKE :stateFullLike COLLATE NOCASE
                  )
                )
            """)
            params["bcbsLike"] = "%bcbs%"
            params["blueCrossLike"] = "%blue%cross%"
            params["anthemLike"] = "%anthem%"
            params["stateLike"] = f"%{bcbs_state}%"
            params["stateFullLike"] = f"%OF {bcbs_state}%"

        if employer and has_employer:
            where.append("(employer_name LIKE :employerLike COLLATE NOCASE)")
            params["employerLike"] = f"%{employer}%"

        if first_name:
            where.append("(first_name LIKE :firstNameLike COLLATE NOCASE)")
            params["firstNameLike"] = f"%{first_name}%"

        if last_name:
            where.append("(last_name LIKE :lastNameLike COLLATE NOCASE)")
            params["lastNameLike"] = f"%{last_name}%"

        sql = f"""
          SELECT
            last_name,
            first_name,
            member_id,
            payer_name,
            loc,
            COUNT(*) AS n_rows,
            AVG(allowed_amount) AS avg_allowed
          FROM reimbursement_rates
          WHERE {" AND ".join(where)}
            AND loc IN ('DTX','RTC','PHP','IOP')
            AND allowed_amount > 0
          GROUP BY last_name, first_name, member_id, payer_name, loc
          ORDER BY member_id, loc;
        """

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def reimb_rows(member_id="", loc="", limit=500):
    """Query detailed reimbursement rows for a specific member/loc"""
    member_id = (member_id or "").strip()
    loc = (loc or "").strip().upper()
    limit = max(1, min(int(limit or 500), 2000))

    if not member_id or not loc:
        raise ValueError("Provide memberId and loc.")

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        sql = f"""
          SELECT
            service_date_from,
            service_date_to,
            payer_name,
            allowed_amount
          FROM reimbursement_rates
          WHERE member_id = :member_id
            AND loc = :loc
          ORDER BY service_date_from DESC
          LIMIT {limit};
        """
        rows = conn.execute(sql, {"member_id": member_id, "loc": loc}).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def check_member_reimb(member_ids):
    """Check which member IDs have reimbursement data"""
    if not member_ids:
        return []
    
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        # Create placeholders for SQL IN clause
        placeholders = ','.join('?' * len(member_ids))
        sql = f"""
            SELECT DISTINCT member_id
            FROM reimbursement_rates
            WHERE member_id IN ({placeholders})
            AND loc IN ('DTX','RTC','PHP','IOP')
            AND allowed_amount > 0
        """
        rows = conn.execute(sql, member_ids).fetchall()
        return [r['member_id'] for r in rows]
    finally:
        conn.close()


# ========== HTTP HANDLER ==========
class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = urlparse(path).path
        path = path.lstrip("/")
        return os.path.join(WEB_ROOT, path)

    def _send_json(self, status, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _get_session_token(self):
        """Extract session token from cookies"""
        cookie_header = self.headers.get('Cookie')
        if not cookie_header:
            return None
        
        cookies = SimpleCookie()
        cookies.load(cookie_header)
        
        if 'session_token' in cookies:
            return cookies['session_token'].value
        return None

    def _set_session_cookie(self, session_token):
        """Set session cookie in response"""
        # Cookie expires in 24 hours
        self.send_header('Set-Cookie', f'session_token={session_token}; Path=/; Max-Age=86400; HttpOnly')

    def _clear_session_cookie(self):
        """Clear session cookie"""
        self.send_header('Set-Cookie', 'session_token=; Path=/; Max-Age=0; HttpOnly')

    def do_GET(self):
        parsed = urlparse(self.path)

        # Health check
        if parsed.path == "/api/health":
            ok = os.path.exists(DB_PATH)
            return self._send_json(200, {"ok": ok, "dbPath": DB_PATH})

        # Check current session
        if parsed.path == "/api/auth/check":
            session_token = self._get_session_token()
            user = get_user_by_session(session_token) if session_token else None
            
            if user:
                return self._send_json(200, {"authenticated": True, "user": user})
            else:
                return self._send_json(200, {"authenticated": False})

        # Logout
        if parsed.path == "/api/auth/logout":
            session_token = self._get_session_token()
            if session_token and session_token in SESSIONS:
                del SESSIONS[session_token]
            
            self.send_response(200)
            self._clear_session_cookie()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
            return

        # VOB search
        if parsed.path == "/api/vob/search":
            qs = parse_qs(parsed.query)
            member_id = (qs.get("memberId", [""])[0] or "").strip()
            dob = (qs.get("dob", [""])[0] or "").strip()
            payer = (qs.get("payer", [""])[0] or "").strip()
            bcbs_state = (qs.get("bcbsState", [""])[0] or "").strip()
            facility = (qs.get("facility", [""])[0] or "").strip()
            employer = (qs.get("employer", [""])[0] or "").strip()
            first_name = (qs.get("firstName", [""])[0] or "").strip()
            last_name = (qs.get("lastName", [""])[0] or "").strip()
            limit = (qs.get("limit", ["50"])[0] or "50").strip()

            try:
                rows = query_vob(
                    member_id=member_id,
                    dob=dob,
                    payer=payer,
                    bcbs_state=bcbs_state,
                    facility=facility,
                    employer=employer,
                    first_name=first_name,
                    last_name=last_name,
                    limit=limit
                )
                return self._send_json(200, {"count": len(rows), "rows": rows})
            except Exception as e:
                return self._send_json(500, {"error": str(e)})

        # Reimbursement summary
        if parsed.path == "/api/reimb/summary":
            qs = parse_qs(parsed.query)
            prefix = (qs.get("prefix", [""])[0] or "").strip()
            payer = (qs.get("payer", [""])[0] or "").strip()
            bcbs_state = (qs.get("bcbsState", [""])[0] or "").strip()
            employer = (qs.get("employer", [""])[0] or "").strip()
            first_name = (qs.get("firstName", [""])[0] or "").strip()
            last_name = (qs.get("lastName", [""])[0] or "").strip()
            try:
                rows = reimb_summary(prefix=prefix, payer=payer, bcbs_state=bcbs_state, employer=employer, first_name=first_name, last_name=last_name)
                return self._send_json(200, {"count": len(rows), "rows": rows})
            except Exception as e:
                return self._send_json(500, {"error": str(e)})

        # Reimbursement detail rows
        if parsed.path == "/api/reimb/rows":
            qs = parse_qs(parsed.query)
            member_id = (qs.get("memberId", [""])[0] or "").strip()
            loc = (qs.get("loc", [""])[0] or "").strip()
            limit = (qs.get("limit", ["500"])[0] or "500").strip()
            try:
                rows = reimb_rows(member_id=member_id, loc=loc, limit=limit)
                return self._send_json(200, {"count": len(rows), "rows": rows})
            except Exception as e:
                return self._send_json(500, {"error": str(e)})

        # Check which member IDs have reimbursement data
        if parsed.path == "/api/reimb/check-members":
            qs = parse_qs(parsed.query)
            member_ids = qs.get("memberIds[]", [])
            try:
                has_data = check_member_reimb(member_ids)
                return self._send_json(200, {"memberIds": has_data})
            except Exception as e:
                return self._send_json(500, {"error": str(e)})

        # Protected pages - require authentication
        if parsed.path == "/portal.html":
            session_token = self._get_session_token()
            user = get_user_by_session(session_token) if session_token else None
            
            if not user:
                # Redirect to login
                self.send_response(302)
                self.send_header('Location', '/index.html')
                self.end_headers()
                return
            
            return SimpleHTTPRequestHandler.do_GET(self)

        # Serve index.html (login page) by default
        if parsed.path == "/" or parsed.path == "":
            self.path = "/index.html"
            return SimpleHTTPRequestHandler.do_GET(self)

        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        parsed = urlparse(self.path)

        # Login endpoint
        if parsed.path == "/api/auth/login":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                username = data.get('username', '').strip()
                password = data.get('password', '').strip()
                
                if not username or not password:
                    return self._send_json(400, {"error": "Username and password required"})
                
                user = verify_login(username, password)
                
                if user:
                    # Create session
                    session_token = generate_session_token()
                    SESSIONS[session_token] = username
                    
                    # Send response with session cookie
                    self.send_response(200)
                    self._set_session_cookie(session_token)
                    self.send_header("Content-Type", "application/json")
                    data = json.dumps({"success": True, "user": user}).encode()
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    return self._send_json(401, {"error": "Invalid username or password"})
                    
            except Exception as e:
                return self._send_json(500, {"error": str(e)})
            return

        return self._send_json(404, {"error": "Not found"})


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"⚠️  DB file not found at: {DB_PATH}")
        print("   Fix DB_PATH at the top of server.py")

    os.chdir(WEB_ROOT)

    PORT = 8000
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"✓ Healthcare Portal with Auth running: http://localhost:{PORT}")
    print(f"✓ Login at: http://localhost:{PORT}")
    httpd.serve_forever()