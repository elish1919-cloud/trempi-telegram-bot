from database import save_ride_to_mongo, get_all_rides_from_mongo

# תאריך עדכני בפורמט שהבוט מחפש
CURRENT_TIMESTAMP = "2026-05-28T22:00:00.000000"

# קואורדינטות אמיתיות של המיקומים לבדיקה גיאוגרפית
COORDS_TA = [32.0853, 34.7818]       # תל אביב
COORDS_BI = [32.0693, 34.8433]       # אוניברסיטת בר אילן
COORDS_ME = [31.9312, 35.0114]       # מודיעין עילית

fake_rides = [
    {
        "telegram_id": 999991,
        "role": "driver",
        "from": "תל אביב",
        "from_coords": COORDS_TA,
        "to": "אוניברסיטת בר אילן",
        "to_coords": COORDS_BI,
        "when": "07:00",
        "status": "open",
        "created_at": CURRENT_TIMESTAMP,
        "picked_by": None,
        "picked_at": None,
        "closed_at": None
    },
    {
        "telegram_id": 999992,
        "role": "driver",
        "from": "תל אביב",
        "from_coords": COORDS_TA,
        "to": "אוניברסיטת בר אילן",
        "to_coords": COORDS_BI,
        "when": "08:30",
        "status": "open",
        "created_at": CURRENT_TIMESTAMP,
        "picked_by": None,
        "picked_at": None,
        "closed_at": None
    },
    {
        "telegram_id": 999995,
        "role": "driver",
        "from": "מודיעין עילית",
        "from_coords": COORDS_ME,
        "to": "אוניברסיטת בר אילן",
        "to_coords": COORDS_BI,
        "when": "07:45",
        "status": "open",
        "created_at": CURRENT_TIMESTAMP,
        "picked_by": None,
        "picked_at": None,
        "closed_at": None
    }
]

print("🧹 מנקים ומזריקים נסיעות פיקטיביות מושלמות לענן...")

for ride in fake_rides:
    ride_id = save_ride_to_mongo(ride)
    print(f"✅ נשמר טרמפ מ-{ride['from']} ל-{ride['to']} עם מזהה: {ride_id}")

all_rides = get_all_rides_from_mongo()
print(f"\n📊 השתלה הושלמה! סך הכל נסיעות בענן: {len(all_rides)}")