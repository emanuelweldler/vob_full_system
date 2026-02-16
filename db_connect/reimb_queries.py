"""
Reimbursement database queries
"""
from db_connect.db_utils import get_connection, table_has_column


def reimb_summary(prefix="", payer="", bcbs_state="", employer="", first_name="", last_name=""):
    """
    Query reimbursement summary grouped by member/payer/location
    
    Args:
        prefix: Member ID prefix to search (starts with)
        payer: Insurance payer name (partial match)
        bcbs_state: State for BCBS plans (e.g., "California", "Texas")
        employer: Employer name (partial match)
        first_name: Client first name (partial match)
        last_name: Client last name (partial match)
        
    Returns:
        list: List of reimbursement summary dictionaries with:
            - last_name, first_name, member_id, payer_name, loc
            - n_rows: count of rows
            - avg_allowed: average allowed amount
            
    Raises:
        ValueError: If no filters provided
    """
    prefix = (prefix or "").strip()
    payer = (payer or "").strip()
    employer = (employer or "").strip()
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()

    if not prefix and not payer and not bcbs_state and not employer and not first_name and not last_name:
        raise ValueError("Provide at least one filter (prefix/memberId, payer, bcbsState, employer, firstName, lastName).")

    conn = get_connection()
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
    """
    Query detailed reimbursement rows for a specific member/location
    
    Args:
        member_id: Member ID to search for
        loc: Location code (DTX, RTC, PHP, IOP)
        limit: Maximum number of results (1-2000)
        
    Returns:
        list: List of reimbursement detail dictionaries with:
            - service_date_from, service_date_to
            - payer_name, allowed_amount
            
    Raises:
        ValueError: If memberId or loc not provided
    """
    member_id = (member_id or "").strip()
    loc = (loc or "").strip().upper()
    limit = max(1, min(int(limit or 500), 2000))

    if not member_id or not loc:
        raise ValueError("Provide memberId and loc.")

    conn = get_connection()
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
    """
    Check which member IDs have reimbursement data
    
    This is a lightweight check used to show green dot indicators
    in the VOB results without loading full reimbursement details.
    
    Args:
        member_ids: List of member IDs to check
        
    Returns:
        list: List of member IDs that have reimbursement data
    """
    if not member_ids:
        return []
    
    conn = get_connection()
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