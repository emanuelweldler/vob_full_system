"""
VOB (Verification of Benefits) database queries
"""
from db_connect.db_utils import get_connection


def query_vob(member_id="", dob="", payer="", bcbs_state="", facility="", employer="", first_name="", last_name="", limit=50):
    """
    Query VOB records table with various filters
    
    Args:
        member_id: Member/Insurance ID (partial match)
        dob: Date of birth (exact match)
        payer: Insurance payer name (partial match)
        bcbs_state: State for BCBS plans (e.g., "California", "Texas")
        facility: Facility name (partial match)
        employer: Employer name (partial match)
        first_name: Client first name (partial match)
        last_name: Client last name (partial match)
        limit: Maximum number of results (1-200)
        
    Returns:
        list: List of VOB record dictionaries
        
    Raises:
        ValueError: If no filters provided
    """
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

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()