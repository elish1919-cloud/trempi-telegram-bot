import datetime
import certifi  # לוודא שהשורה הזו קיימת למעלה
from pymongo import MongoClient

# התחברות לשרת בענן בעזרת הקישור שלך
CONNECTION_STRING = "mongodb+srv://elish1919:ez102030@cluster0.pesg1r3.mongodb.net/?appName=Cluster0"

# אנחנו אומרים למונגו להשתמש בתעודות של certifi וגם מאפשרים ביטול אימות מקומי אם הרשת חוסמת
client = MongoClient(
    CONNECTION_STRING, 
    tls=True,
    tlsCAFile=certifi.where(),
    tlsAllowInvalidCertificates=True
)

# יצירת בסיס נתונים בשם TrempiDB
db = client["TrempiDB"]

# יצירת הטבלאות (Collections) שלנו
rides_collection = db["rides"]
users_collection = db["users"]


# --- פונקציות עזר שיחליפו את ה-JSON ---


def save_ride_to_mongo(ride_data):
    """שומר נסיעה חדשה של נהג"""
    # השורות החדשות שהוספנו כדי לעבוד על הבוט בבדיקות:
    if ride_data.get("telegram_id") == 6320213595:
        import random
        ride_data["telegram_id"] = random.randint(100000, 999000)

    # הקוד המקורי והמעולה שלך שנשאר בדיוק אותו הדבר:
    result = rides_collection.insert_one(ride_data)
    return result.inserted_id


def get_all_rides_from_mongo():
    """שולף את כל הנסיעות הפתוחות"""
    return list(rides_collection.find({"status": "open"}))


def save_user_history(user_id, action_type, details):
    """שומר היסטוריית פעולות של המשתמש (מעולה להציג למרצה!)"""
    history_data = {
        "user_id": user_id,
        "action": action_type,  # למשל: "search" או "offer"
        "details": details,
        "timestamp": datetime.datetime.utcnow(),
    }
    db["history"].insert_one(history_data)

    from bson.objectid import ObjectId

def update_ride_in_mongo(ride_id_str, updates):
    """מעדכן טרמפ ספציפי במונגו לפי ה-ID שלו"""
    try:
        # מונגו מזהה שורות לפי ObjectId, אז נמיר את הטקסט חזרה למזהה שלו
        result = rides_collection.update_one(
            {"_id": ObjectId(ride_id_str)}, 
            {"$set": updates}
        )
        return result.modified_count > 0
    except Exception:
        # למקרה שה-ID לא בפורמט תקין של מונגו (למשל מהטסטים הישנים ב-JSON)
        return False

def get_ride_by_id_from_mongo(ride_id_str):
    """שולף טרמפ בודד מהמונגו לפי ה-ID שלו"""
    try:
        ride = rides_collection.find_one({"_id": ObjectId(ride_id_str)})
        if ride:
            # נמיר את ה-ID חזרה לטקסט רגיל כדי שהבוט יבין אותו
            ride["ride_id"] = str(ride["_id"])
        return ride
    except Exception:
        return None        

def get_user_rides_from_mongo(telegram_id):
    """שולף את כל הנסיעות שנוצרו על ידי משתמש ספציפי"""
    # מוצאים את כל הנסיעות שבהן ה-telegram_id מתאים
    cursor = rides_collection.find({"telegram_id": telegram_id})
    rides = list(cursor)
    
    # נמיר את ה-ID של מונגו לטקסט רגיל עבור הבוט
    for ride in rides:
        ride["ride_id"] = str(ride["_id"])
        
    return rides 

def get_open_rides_by_role_from_mongo(wanted_role):
    """שולף ממונגו נסיעות פתוחות לפי תפקיד מסוים"""
    # חיפוש משולב: גם הסטטוס פתוח וגם התפקיד מתאים למה שחיפשנו
    cursor = rides_collection.find({"status": "open", "role": wanted_role})
    rides = list(cursor)
    
    # המרת המזהים של מונגו לטקסט עבור הבוט
    for ride in rides:
        ride["ride_id"] = str(ride["_id"])
        
    return rides    

def get_rides_by_route_from_mongo(wanted_role, from_text, to_text):
    """מחפש נסיעות פתוחות לפי תפקיד ומסלול ספציפי"""
    query = {
        "status": "open",
        "role": wanted_role,
        "from": from_text,
        "to": to_text
    }
    cursor = rides_collection.find(query)
    rides = list(cursor)
    
    for ride in rides:
        ride["ride_id"] = str(ride["_id"])
        
    return rides

def get_last_searched_destination(user_id):
    try:
        # שינינו את user_id ל-telegram_id כדי שיתאים בדיוק לדאטה שלך
        last_ride = db["rides"].find_one(
            {"telegram_id": int(user_id)}, 
            sort=[("_id", -1)]
        )
        if last_ride and last_ride.get("to"):
            return last_ride.get("to")
    except Exception as e:
        print(f"[ERROR MONGO RECOMMENDATION] {e}")
    return None

