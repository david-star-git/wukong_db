def get_existing_years(db):
    rows = db.execute("SELECT DISTINCT year FROM weeks ORDER BY year").fetchall()
    return {row["year"] for row in rows}


def get_existing_kws_for_year(db, year):
    rows = db.execute(
        "SELECT week_number FROM weeks WHERE year = ? ORDER BY week_number", (year,)
    ).fetchall()
    return {row["week_number"] for row in rows}
