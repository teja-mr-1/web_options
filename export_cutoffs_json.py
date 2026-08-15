#!/usr/bin/env python3
import sqlite3
import json
import os
from bs4 import BeautifulSoup

DB_PATH = "/mnt/linuxdata/web_options_repo/ap_eapcet_allotments.db"
COLLEGE_DETAILS_HTML = "/mnt/linuxdata/EAPCET/college_details.html"
OUTPUT_JSON = "/mnt/linuxdata/web_options_repo/cutoffs_data.json"

def main():
    print("Step 1: Reading college details metadata...")
    college_meta = {}
    if os.path.exists(COLLEGE_DETAILS_HTML):
        with open(COLLEGE_DETAILS_HTML, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
            for r in soup.find_all("tr"):
                cells = [td.get_text(strip=True) for td in r.find_all("td")]
                if len(cells) >= 12:
                    code = cells[1].strip()
                    if code and code not in college_meta:
                        college_meta[code] = {
                            "name": cells[2].strip().replace("OFENGINEERING", "OF ENGINEERING"),
                            "city": cells[3].strip(),
                            "district": cells[4].strip(),
                            "region": cells[5].strip(),
                            "type": cells[6].strip(),
                            "univ": cells[9].strip(),
                            "fee": int(cells[11].strip()) if cells[11].strip().isdigit() else 0
                        }

    # Add hardcoded metadata for VVITPU if not in HTML
    if "VVITPU" not in college_meta:
        college_meta["VVITPU"] = {
            "name": "V V I T - UNIVERSITY",
            "city": "GUNTUR",
            "district": "GTR",
            "region": "AU",
            "type": "Private University",
            "univ": "VVITPU",
            "fee": 65200
        }

    print("Step 2: Querying SQLite database for cutoffs and branches...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get branches map
    branches_map = {}
    for code, name in cur.execute("SELECT branch_code, branch_name FROM branches ORDER BY branch_code"):
        branches_map[code.strip()] = name.strip()

    # Get colleges from DB if not in college_meta
    for code, name in cur.execute("SELECT inst_code, inst_name FROM colleges"):
        c_code = code.strip()
        if c_code not in college_meta:
            college_meta[c_code] = {
                "name": name.strip().replace("OFENGINEERING", "OF ENGINEERING"),
                "city": "",
                "district": "",
                "region": "",
                "type": "",
                "univ": "",
                "fee": 0
            }

    # Query allotments grouped by college, branch, category, community, gender
    # Filter out empty/null ranks
    query = """
    SELECT 
        inst_code,
        branch_code,
        allot_category,
        community,
        gender,
        COUNT(*) as allotted_count,
        MIN(CAST(rank AS INTEGER)) as opening_rank,
        MAX(CAST(rank AS INTEGER)) as closing_rank
    FROM allotments
    WHERE rank IS NOT NULL 
      AND rank != '' 
      AND CAST(rank AS INTEGER) > 0
    GROUP BY inst_code, branch_code, allot_category, community, gender
    ORDER BY inst_code, branch_code, allot_category, community, gender
    """
    
    cur.execute(query)
    rows = cur.fetchall()
    print(f"Loaded {len(rows)} cutoff group rows.")

    # Distinct lists for filter dropdowns
    castes_set = set()
    categories_set = set()
    genders_set = set()

    cutoffs = []
    for inst_code, branch_code, allot_category, community, gender, count, open_r, close_r in rows:
        c_code = inst_code.strip()
        b_code = branch_code.strip()
        cat = allot_category.strip()
        com = community.strip()
        gen = gender.strip()

        if com: castes_set.add(com)
        if cat: categories_set.add(cat)
        if gen: genders_set.add(gen)

        cutoffs.append([
            c_code,
            b_code,
            cat,
            com,
            gen,
            count,
            open_r,
            close_r
        ])

    conn.close()

    data = {
        "colleges": college_meta,
        "branches": branches_map,
        "castes": sorted(list(castes_set)),
        "categories": sorted(list(categories_set)),
        "genders": sorted(list(genders_set)),
        "cutoffs": cutoffs
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(',', ':'))

    file_size_kb = os.path.getsize(OUTPUT_JSON) / 1024
    print(f"Successfully generated {OUTPUT_JSON} ({file_size_kb:.1f} KB, {len(cutoffs)} cutoff records).")

if __name__ == "__main__":
    main()
