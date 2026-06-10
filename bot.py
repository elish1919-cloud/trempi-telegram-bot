import os
import json
from datetime import datetime
import re
import requests
import asyncio

from database import save_ride_to_mongo, get_all_rides_from_mongo, get_last_searched_destination

from database import save_ride_to_mongo, get_all_rides_from_mongo, update_ride_in_mongo

from database import save_ride_to_mongo, get_all_rides_from_mongo, update_ride_in_mongo, get_ride_by_id_from_mongo

from database import save_ride_to_mongo, get_all_rides_from_mongo, update_ride_in_mongo, get_ride_by_id_from_mongo, get_user_rides_from_mongo 

from database import save_ride_to_mongo, get_all_rides_from_mongo, update_ride_in_mongo, get_ride_by_id_from_mongo, get_user_rides_from_mongo, get_open_rides_by_role_from_mongo

from database import (
    save_ride_to_mongo, 
    get_all_rides_from_mongo, 
    update_ride_in_mongo, 
    get_ride_by_id_from_mongo, 
    get_user_rides_from_mongo, 
    get_open_rides_by_role_from_mongo,
    get_rides_by_route_from_mongo
)

from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

USERS_FILE = "users.json"
GEO_CACHE_FILE = "geocache.json"
MAX_PICKUP_DISTANCE_KM = 5


ASK_FROM, ASK_TO, ASK_WHEN = range(3)

SEARCH_DAY, SEARCH_DATE, SEARCH_FROM, SEARCH_TO, SEARCH_TIME, SEARCH_FLEX, SEARCH_RECOMMENDATION = range(7)

REG_AGE, REG_GENDER, REG_ADDRESS, REG_PHONE, REG_ROLE = range(100, 105)
EDIT_CHOOSE_FIELD, EDIT_AGE, EDIT_GENDER, EDIT_ADDRESS, EDIT_PHONE, EDIT_ROLE = range(200, 206)

BTN_NEW = "יצירת טרמפ"
BTN_OPEN = "מה פתוח עכשיו"
BTN_MY = "הבקשות שלי"
BTN_HELP = "עזרה"
BTN_PROFILE = "הפרופיל שלי"
BTN_REGISTER = "התחלת הרשמה"

CB_NEXT = "browse_next"
CB_JOIN_PREFIX = "browse_join:"  # browse_join:<ride_id>
CB_FLEX_15 = "flex_15"
CB_FLEX_30 = "flex_30"
CB_FLEX_ANY = "flex_any"

CB_GENDER_MALE = "gender_male"
CB_GENDER_FEMALE = "gender_female"
CB_GENDER_OTHER = "gender_other"

CB_ROLE_DRIVER = "reg_role_driver"
CB_ROLE_PASSENGER = "reg_role_passenger"
CB_ROLE_BOTH = "reg_role_both"

CB_EDIT_AGE = "edit_age"
CB_EDIT_GENDER = "edit_gender"
CB_EDIT_ADDRESS = "edit_address"
CB_EDIT_PHONE = "edit_phone"
CB_EDIT_ROLE = "edit_role"


# Day selection buttons (search)
BTN_DAY_TODAY = "היום"
BTN_DAY_TOMORROW = "מחר"
BTN_DAY_OTHER = "תאריך אחר"

CB_DAY_TODAY = "day_today"
CB_DAY_TOMORROW = "day_tomorrow"
CB_DAY_OTHER = "day_other"

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user_data = get_user(telegram_id)

    if not user_data or not user_data.get("is_registered"):
        await update.message.reply_text("טרם השלמת הרשמה. לחץ על /start")
        return

    text = build_profile_text(user_data)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("עריכת פרטים ✏️", callback_data="start_registration")]
    ])
    
    await update.message.reply_text(text, reply_markup=keyboard)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(BTN_NEW), KeyboardButton(BTN_OPEN)],
        [KeyboardButton(BTN_MY), KeyboardButton(BTN_HELP)],
        [KeyboardButton(BTN_PROFILE)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def gender_keyboard() -> InlineKeyboardMarkup:
    keyboard = [[
        InlineKeyboardButton("זכר", callback_data=CB_GENDER_MALE),
        InlineKeyboardButton("נקבה", callback_data=CB_GENDER_FEMALE),
        InlineKeyboardButton("אחר", callback_data=CB_GENDER_OTHER),
    ]]
    return InlineKeyboardMarkup(keyboard)


def default_role_keyboard() -> InlineKeyboardMarkup:
    keyboard = [[
        InlineKeyboardButton("נהג", callback_data=CB_ROLE_DRIVER),
        InlineKeyboardButton("נוסע", callback_data=CB_ROLE_PASSENGER),
    ], [
        InlineKeyboardButton("גם וגם", callback_data=CB_ROLE_BOTH),
    ]]
    return InlineKeyboardMarkup(keyboard)


def profile_edit_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("עריכת גיל", callback_data=CB_EDIT_AGE)],
        [InlineKeyboardButton("עריכת מין", callback_data=CB_EDIT_GENDER)],
        [InlineKeyboardButton("עריכת כתובת", callback_data=CB_EDIT_ADDRESS)],
        [InlineKeyboardButton("עריכת טלפון", callback_data=CB_EDIT_PHONE)],
        [InlineKeyboardButton("עריכת תפקיד", callback_data=CB_EDIT_ROLE)],
    ]
    return InlineKeyboardMarkup(keyboard)

def registration_start_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(BTN_REGISTER, callback_data="start_registration")]
    ]
    return InlineKeyboardMarkup(keyboard)

def _load_json_list(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_json_list(path: str, data: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def register_or_update_user(update: Update) -> dict:
    user = update.effective_user

    users = _load_json_list(USERS_FILE)
    existing = next((u for u in users if u.get("telegram_id") == user.id), None)

    now_iso = datetime.now().isoformat()

    if existing is None:
        new_user = {
            "telegram_id": user.id,
            "first_name": user.first_name,
            "username": user.username,

            # שדות הרשמה חדשים
            "age": None,
            "gender": None,
            "address": None,
            "phone": None,
            "default_role": None,

            # משאירים גם role כדי לא לשבור את המערכת הקיימת
            "role": None,

            "is_registered": False,
            "registered_at": None,
            "updated_at": now_iso,
        }
        users.append(new_user)
        _save_json_list(USERS_FILE, users)
        return new_user

    # עדכון פרטים שמגיעים מטלגרם
    existing["first_name"] = user.first_name
    existing["username"] = user.username

    # אם זה משתמש ישן, נוסיף לו את השדות החדשים אם הם לא קיימים
    if "age" not in existing:
        existing["age"] = None
    if "gender" not in existing:
        existing["gender"] = None
    if "address" not in existing:
        existing["address"] = None
    if "phone" not in existing:
        existing["phone"] = None
    if "default_role" not in existing:
        existing["default_role"] = existing.get("role")
    if "role" not in existing:
        existing["role"] = existing.get("default_role")
    if "is_registered" not in existing:
        existing["is_registered"] = False
    if "registered_at" not in existing:
        existing["registered_at"] = None

    existing["updated_at"] = now_iso

    _save_json_list(USERS_FILE, users)
    return existing

def set_user_role(telegram_id: int, role: str) -> None:
    users = _load_json_list(USERS_FILE)
    for u in users:
        if u.get("telegram_id") == telegram_id:
            u["role"] = role
            break
    _save_json_list(USERS_FILE, users)


def get_user(telegram_id: int) -> dict | None:
    users = _load_json_list(USERS_FILE)
    return next((u for u in users if u.get("telegram_id") == telegram_id), None)

def update_user_fields(telegram_id: int, updates: dict) -> bool:
    users = _load_json_list(USERS_FILE)
    found = False

    for u in users:
        if u.get("telegram_id") == telegram_id:
            u.update(updates)
            u["updated_at"] = datetime.now().isoformat()
            found = True
            break

    if found:
        _save_json_list(USERS_FILE, users)

    return found


def _gender_he(value: str | None) -> str:
    if value == "male":
        return "זכר"
    if value == "female":
        return "נקבה"
    if value == "other":
        return "אחר"
    return "לא הוגדר"


def _role_pref_he(value: str | None) -> str:
    if value == "driver":
        return "נהג"
    if value == "passenger":
        return "נוסע"
    if value == "both":
        return "גם נהג וגם נוסע"
    return "לא הוגדר"


def build_profile_text(user_data: dict) -> str:
    first_name = user_data.get("first_name") or "לא הוגדר"
    age = user_data.get("age")
    gender = _gender_he(user_data.get("gender"))
    address = user_data.get("address") or "לא הוגדר"
    phone = user_data.get("phone") or "לא הוגדר"
    default_role = _role_pref_he(user_data.get("default_role"))

    age_text = str(age) if age is not None else "לא הוגדר"

    return (
        "הפרופיל שלי\n\n"
        f"שם: {first_name}\n"
        f"גיל: {age_text}\n"
        f"מין: {gender}\n"
        f"כתובת: {address}\n"
        f"טלפון: {phone}\n"
        f"תפקיד מועדף: {default_role}"
    )

def _is_valid_age(text: str) -> bool:
    try:
        age = int((text or "").strip())
        return 16 <= age <= 120
    except Exception:
        return False


def _is_valid_phone(text: str) -> bool:
    phone = re.sub(r"\D", "", (text or "").strip())
    return len(phone) >= 9 and len(phone) <= 10


def _normalize_phone(text: str) -> str:
    return re.sub(r"\D", "", (text or "").strip())

async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("reg_data", None)

    await update.effective_message.reply_text(
        "מה הגיל שלך?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return REG_AGE

async def start_registration_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    return await start_registration(update, context)

async def reg_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if not _is_valid_age(text):
        await update.message.reply_text(
            "הגיל צריך להיות מספר תקין בין 16 ל־120.\n"
            "בבקשה כתוב גיל תקין."
        )
        return REG_AGE

    context.user_data["reg_data"] = {
        "age": int(text)
    }

    await update.message.reply_text(
        "מה המין שלך?",
        reply_markup=gender_keyboard()
    )
    return REG_GENDER


async def reg_gender_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if "reg_data" not in context.user_data:
        context.user_data["reg_data"] = {}

    if query.data == CB_GENDER_MALE:
        context.user_data["reg_data"]["gender"] = "male"
    elif query.data == CB_GENDER_FEMALE:
        context.user_data["reg_data"]["gender"] = "female"
    elif query.data == CB_GENDER_OTHER:
        context.user_data["reg_data"]["gender"] = "other"
    else:
        return REG_GENDER

    await query.message.reply_text("מה הכתובת או אזור המגורים שלך?")
    return REG_ADDRESS


async def reg_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if not text:
        await update.message.reply_text("בבקשה כתוב כתובת או אזור מגורים.")
        return REG_ADDRESS

    if "reg_data" not in context.user_data:
        context.user_data["reg_data"] = {}

    context.user_data["reg_data"]["address"] = text

    await update.message.reply_text("מה מספר הטלפון שלך?")
    return REG_PHONE


async def reg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if not _is_valid_phone(text):
        await update.message.reply_text(
            "מספר הטלפון לא נראה תקין.\n"
            "בבקשה כתוב מספר טלפון תקין."
        )
        return REG_PHONE

    if "reg_data" not in context.user_data:
        context.user_data["reg_data"] = {}

    context.user_data["reg_data"]["phone"] = _normalize_phone(text)

    await update.message.reply_text(
        "מה התפקיד המועדף עליך?",
        reply_markup=default_role_keyboard()
    )
    return REG_ROLE


async def reg_role_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if "reg_data" not in context.user_data:
        context.user_data["reg_data"] = {}

    if query.data == CB_ROLE_DRIVER:
        chosen_role = "driver"
    elif query.data == CB_ROLE_PASSENGER:
        chosen_role = "passenger"
    elif query.data == CB_ROLE_BOTH:
        chosen_role = "both"
    else:
        return REG_ROLE

    context.user_data["reg_data"]["default_role"] = chosen_role

    telegram_id = query.from_user.id
    reg_data = context.user_data.get("reg_data", {})

    ok = update_user_fields(telegram_id, {
        "age": reg_data.get("age"),
        "gender": reg_data.get("gender"),
        "address": reg_data.get("address"),
        "phone": reg_data.get("phone"),
        "default_role": reg_data.get("default_role"),
        "role": "driver" if reg_data.get("default_role") == "both" else reg_data.get("default_role"),
        "is_registered": True,
        "registered_at": datetime.now().isoformat(),
    })

    context.user_data.pop("reg_data", None)

    if not ok:
        await query.message.reply_text(
            "הייתה בעיה בשמירת ההרשמה. נסה שוב /start",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    updated_user = get_user(telegram_id) or {}

    await query.message.reply_text(
        "ההרשמה הושלמה בהצלחה 🎉\n\n" + build_profile_text(updated_user),
        reply_markup=main_menu_keyboard(),
    )

    await query.message.reply_text(
        "מכאן אפשר להמשיך לאחת הפעולות דרך הכפתורים שמופיעים למטה.",
        reply_markup=main_menu_keyboard(),
    )

    return ConversationHandler.END  

def _next_ride_id(rides: list) -> int:
    max_id = 0
    for r in rides:
        rid = r.get("ride_id")
        if isinstance(rid, int) and rid > max_id:
            max_id = rid
    return max_id + 1


def add_ride(ride: dict) -> dict:
    # 1. שמירת הנסיעה ישירות ב-MongoDB בענן
    inserted_id = save_ride_to_mongo(ride)
    
    # 2. נשמור את המזהה שמונגו יצר בתוך הדיקשנרי לטובת שאר חלקי הבוט
    ride["ride_id"] = str(inserted_id)
    
    return ride


def update_ride(ride_id: str, updates: dict) -> bool:
    # עדכון ישיר וממוקד בבסיס הנתונים בענן
    return update_ride_in_mongo(str(ride_id), updates)


def find_ride(ride_id: str) -> dict | None:
    # שליפה ישירה של הטרמפ הספציפי מהענן - מוודאים שהמזהה מועבר כמחרוזת
    return get_ride_by_id_from_mongo(str(ride_id))


def list_my_rides(telegram_id: int) -> list:
    # שליפת הנסיעות של המשתמש הספציפי הזה ישירות מהענן
    return get_user_rides_from_mongo(telegram_id)


def list_open_for_role(viewer_role: str) -> list:
    # 1. חישוב התפקיד ההפוך (בדיוק כמו שעשית בקוד המקורי שלך)
    wanted_role = "passenger" if viewer_role == "driver" else "driver"
    
def list_open_for_role_and_route(viewer_role: str, from_text: str, to_text: str) -> list:
    wanted_role = "passenger" if viewer_role == "driver" else "driver"
    return get_rides_by_route_from_mongo(wanted_role, from_text, to_text)
    

def _role_he(role: str | None) -> str:
    if role == "driver":
        return "נהג"
    if role == "passenger":
        return "נוסע"
    return "לא ידוע"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = register_or_update_user(update)

    first_name = user_data.get("first_name") or "שלום"

    if not user_data.get("is_registered"):
        await update.message.reply_text(
            f"{first_name} שלום 😊\n"
            "ברוך הבא ל-Trempi.\n"
            "כדי להתחיל להשתמש בבוט, יש להשלים הרשמה קצרה.",
            reply_markup=registration_start_keyboard(),
        )
        return ConversationHandler.END

    role = user_data.get("role")
    role_text = _role_he(role)

# 1. שליפת השם והתפקיד
    user_name = update.effective_user.first_name
    user_role = context.user_data.get("role", "passenger")
    role_display = "נהג/ת 🚗" if user_role == "driver" else "נוסע/ת 🎒"

    # 2.הודעת פתיחה
    msg = (
        f"שלום {user_name}, איזה כיף לראות אותך ב-Trempi! ✨\n\n"
        f"הפרופיל שלך מוגדר כרגע כ: **{role_display}**\n\n"
        "בכפתורים למטה תוכל.י לחפש טרמפ או להציע אחד משלך.\n\n"
    )

    # 3. שליחת ההודעה 
    await update.message.reply_text(
        msg, 
        reply_markup=main_menu_keyboard(), 
        parse_mode="Markdown"
    )


async def role_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    telegram_id = query.from_user.id

    if query.data == "role_driver":
        role = "driver"
        role_text = "נהג"
    elif query.data == "role_passenger":
        role = "passenger"
        role_text = "נוסע"
    else:
        return

    set_user_role(telegram_id, role)

    first_name = query.from_user.first_name or "שלום"
    await query.edit_message_text(
        f"{first_name} מעולה\nהתפקיד נשמר: {role_text}"
    )

    await query.message.reply_text(
        "מה עושים עכשיו?",
        reply_markup=main_menu_keyboard(),
    )


async def new_ride_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = register_or_update_user(update)
    role = user_data.get("role")

    if not role:
        await update.message.reply_text("לפני שיוצרים טרמפ, צריך לבחור תפקיד עם /start")
        return ConversationHandler.END

    await update.message.reply_text("מאיפה יוצאים?", reply_markup=ReplyKeyboardRemove())
    return ASK_FROM


async def ask_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("רק תכתבי מאיפה יוצאים.")
        return ASK_FROM

    context.user_data["ride_from"] = text
    await update.message.reply_text("לאן נוסעים?")
    return ASK_TO


async def ask_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("רק תכתבי לאן נוסעים.")
        return ASK_TO

    context.user_data["ride_to"] = text
    await update.message.reply_text("מתי זה? אפשר לכתוב למשל: עכשיו / 18:30 / מחר בבוקר")
    return ASK_WHEN


async def ask_when(update: Update, context: ContextTypes.DEFAULT_TYPE):
    when_text = (update.message.text or "").strip()
    if not when_text:
        await update.message.reply_text("רק תכתבי מתי.")
        return ASK_WHEN

    telegram_id = update.effective_user.id
    user_data = get_user(telegram_id) or {}

    # שליפת קואורדינטות לשני הקצוות (השיפור המרכזי!)
    from_coords = await geocode_place(context.user_data.get("ride_from"))
    to_coords = await geocode_place(context.user_data.get("ride_to"))

    ride = {
        "telegram_id": telegram_id,
        "role": user_data.get("role"),
        "from": context.user_data.get("ride_from"),
        "from_coords": from_coords,
        "to": context.user_data.get("ride_to"),
        "to_coords": to_coords,  # עכשיו הבוט שומר גם את מיקום היעד
        "when": when_text,
        "created_at": datetime.now().isoformat(),
        "status": "open",
        "picked_by": None,
        "picked_at": None,
        "closed_at": None,
    }

    saved = add_ride(ride)

    await update.message.reply_text(
        f"קיבלתי.\n"
        f"מספר בקשה: {saved['ride_id']}\n"
        f"מוצא: {saved['from']}\n"
        f"יעד: {saved['to']}\n"
        f"מתי: {saved['when']}",
        reply_markup=main_menu_keyboard(),
    )

    await update.message.reply_text(
        "מעולה.\n"
        "הבקשה נשמרה והמערכת מחפשת עבורך התאמה.",
        reply_markup=main_menu_keyboard(),
    )

    context.user_data.pop("ride_from", None)
    context.user_data.pop("ride_to", None)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("ride_from", None)
    context.user_data.pop("ride_to", None)
    await update.message.reply_text("בוטל.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def my_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    rides = list_my_rides(telegram_id)

    if not rides:
        await update.message.reply_text("אין לך עדיין בקשות.", reply_markup=main_menu_keyboard())
        return

    lines = []
    for r in sorted(rides, key=lambda x: x.get("ride_id", 0), reverse=True)[:10]:
        lines.append(
            f"#{r.get('ride_id')} | {_role_he(r.get('role'))} | {r.get('from')} -> {r.get('to')} | {r.get('when')} | {r.get('status')}"
        )

    await update.message.reply_text(
        "הבקשות האחרונות שלך:\n" + "\n".join(lines),
        reply_markup=main_menu_keyboard(),
    )

def _browse_keyboard(current_ride_id, next_ride_id=None):
    keyboard = [
        [InlineKeyboardButton("מושלם, אני רוצה להצטרף", callback_data=f"join_{current_ride_id}")]
    ]
    # אם יש טרמפ נוסף ברשימה, נוסיף את כפתור הדפדוף ונדביק לו את ה-ID שלו!
    if next_ride_id:
        keyboard.append([InlineKeyboardButton("תראה לי טרמפ אחר", callback_data=f"next_{next_ride_id}")])
    else:
        keyboard.append([InlineKeyboardButton("חזרה לתפריט הראשי", callback_data="main_menu")])
        
    return InlineKeyboardMarkup(keyboard)

def _day_choice_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(BTN_DAY_TODAY, callback_data=CB_DAY_TODAY),
            InlineKeyboardButton(BTN_DAY_TOMORROW, callback_data=CB_DAY_TOMORROW),
        ],
        [
            InlineKeyboardButton(BTN_DAY_OTHER, callback_data=CB_DAY_OTHER),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def _show_browse_ride(update: Update, context: ContextTypes.DEFAULT_TYPE, *, edit: bool = False):
    # מאפשרים ל-ids להיות מחרוזות (strings) בצורה גמישה
    ids = context.user_data.get("browse_ids", [])
    idx = context.user_data.get("browse_idx", 0)

    if not ids or idx >= len(ids):
        text = "זהו, אין עוד טרמפים זמינים כרגע\nאבל ממש שווה לנסות שוב בעוד כמה דקות"
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.effective_message.reply_text(text, reply_markup=main_menu_keyboard())
        return

    # מנסים לקחת את הטרמפ המלא ישירות מהזיכרון ששמרנו בחיפוש
    browse_rides = context.user_data.get("browse_rides", [])
    if idx < len(browse_rides):
        ride = browse_rides[idx]
        ride_id = ride.get("ride_id") or str(ride.get("_id"))
    else:
        ride_id = str(ids[idx])
        ride = find_ride(ride_id)

    if not ride:
        context.user_data["browse_idx"] = idx + 1
        await _show_browse_ride(update, context, edit=edit)
        return
    
    user_name = update.effective_user.first_name or "נוסע/ת"

    msg = (
        f"איזה כיף {user_name}! מצאתי טרמפ 👇\n\n"
        f"מוצא: {ride.get('from')}\n"
        f"יעד: {ride.get('to')}\n"
        f"מתי: {ride.get('when')}\n\n"
        "מה תרצה לעשות?"
    )

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=_browse_keyboard(ride_id))
    else:
        await update.effective_message.reply_text(msg, reply_markup=_browse_keyboard(ride_id))


async def open_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user_data = get_user(telegram_id)

    if not user_data or not user_data.get("role"):
        await update.message.reply_text("צריך לבחור תפקיד קודם: /start")
        return

    viewer_role = user_data["role"]
    rides = list_open_for_role(viewer_role)

    # נייצר רשימת ride_id לדפדוף
    browse_ids = [r.get("ride_id") for r in sorted(rides, key=lambda x: x.get("created_at", ""), reverse=True)]
    browse_ids = [rid for rid in browse_ids if rid is not None]

    context.user_data["browse_ids"] = browse_ids
    context.user_data["browse_idx"] = 0

    if not browse_ids:
        await update.message.reply_text(
            "כרגע אין טרמפים פתוחים שמתאימים לך 😕\nתרצה ליצור בקשה חדשה?",
            reply_markup=main_menu_keyboard(),
        )
        return

    await _show_browse_ride(update, context, edit=False)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "איך משתמשים:\n"
        f"- לחצי על {BTN_NEW} כדי ליצור בקשה\n"
        f"- לחצי על {BTN_OPEN} כדי לראות מה פתוח\n"
        f"- לחצי על {BTN_MY} כדי לראות את הבקשות שלך\n"
        "פקודות (אופציונלי): /open /my /new /pick /close /cancel",
        reply_markup=main_menu_keyboard(),
    )


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    print(f"[DEBUG] הבוט קיבל את הטקסט: '{text}'") # זה יופיע לך ב-VS Code למטה

    if text == BTN_MY:
        return await my_cmd(update, context)

    if text == BTN_HELP:
        return await help_cmd(update, context)

    # נסי לבדוק אם הטקסט מכיל את המילה פרופיל (ליתר ביטחון)
    if text == BTN_PROFILE or "פרופיל" in text:
        print("[DEBUG] מפעיל את פונקציית הפרופיל...")
        return await profile_cmd(update, context)

    await update.message.reply_text("אפשר להשתמש בכפתורים למטה.", reply_markup=main_menu_keyboard())

async def browse_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # שליפת ה-ID של הטרמפ הבא ישירות מנתוני הלחיצה של הכפתור
    data = query.data
    next_ride_id = data.replace("next_", "")

    print(f"[DEBUG DYNAMIC_NEXT] מחפש במונגו את הטרמפ הבא לפי ID: {next_ride_id}")
    
    # שליפת הטרמפ ישירות מה-DB
    ride = find_ride(next_ride_id)

    if not ride:
        text = "זהו, אין עוד טרמפים זמינים כרגע\nאבל ממש שווה לנסות שוב בעוד כמה דקות"
        await query.message.reply_text(text, reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    await query.message.reply_text("סבבה, מחפש טרמפ נוסף…")
    
    # המרה בטוחה של ה-ID הנוכחי לטקסט בשביל טלגרם
    current_id = str(ride.get("_id"))
    user_name = update.effective_user.first_name or "נוסע/ת"

    msg = (
        f"איזה כיף {user_name}! מצאתי טרמפ 👇\n\n"
        f"מוצא: {ride.get('from')}\n"
        f"יעד: {ride.get('to')}\n"
        f"מתי: {ride.get('when')}\n\n"
        "מה תרצה לעשות?"
    )

    # הטרמפ השני הוא האחרון בטסט, אז נשלח לו None כטרמפ הבא
    await query.message.reply_text(msg, reply_markup=_browse_keyboard(current_id, None))
    return ConversationHandler.END

async def browse_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    try:
        ride_id = int(data.split(":", 1)[1])
    except Exception:
        return

    ride = find_ride(ride_id)

    # Race condition / כבר נלקח
    if not ride or ride.get("status") != "open":
        await query.message.reply_text(
            "אופס, בדיוק עכשיו מישהו אחר לקח את הטרמפ הזה.\nבוא ננסה טרמפ אחר."
        )
        context.user_data["browse_idx"] = int(context.user_data.get("browse_idx", 0)) + 1
        await _show_browse_ride(update, context, edit=False)
        return

    ok = update_ride(ride_id, {
        "status": "picked",
        "picked_by": query.from_user.id,
        "picked_at": datetime.now().isoformat(),
    })

    if not ok:
        await query.message.reply_text(
            "אופס, בדיוק עכשיו מישהו אחר לקח את הטרמפ הזה.\nבוא ננסה טרמפ אחר."
        )
        context.user_data["browse_idx"] = int(context.user_data.get("browse_idx", 0)) + 1
        await _show_browse_ride(update, context, edit=False)
        return

    await query.message.reply_text(
        "מעולה! שריינתי לך את הטרמפ ✅\nכדי לתאם, מומלץ לפנות לצד השני בהודעה פרטית.",
        reply_markup=main_menu_keyboard(),
    )

async def open_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user_name = update.effective_user.first_name or "נוסע/ת"
    
    # 1. בדיקת אבטחה קיימת: לוודא שהמשתמש רשום במערכת ויש לו תפקיד
    user_data = get_user(telegram_id)
    if not user_data or not user_data.get("role"):
        if update.callback_query:
            await update.callback_query.message.reply_text("צריך לבחור תפקיד קודם: /start")
        else:
            await update.message.reply_text("צריך לבחור תפקיד קודם: /start")
        return ConversationHandler.END

    # 2. הפעלת מערכת ההמלצות החכמה - שליפת יעד אחרון ממונגו
    recommended_destination = get_last_searched_destination(telegram_id)
    
    if recommended_destination:
        # שומרים את היעד בזיכרון הזמני למקרה שהמשתמש ילחץ "כן"
        context.user_data["recommended_to"] = recommended_destination
        
        # בניית כפתורי אינליין להמלצה המהירה
        keyboard = [
            [InlineKeyboardButton(f"כן, ל{recommended_destination} 👍", callback_data="rec_yes")],
            [InlineKeyboardButton("לא, ליעד אחר 🗺️", callback_data="rec_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        msg = f"היי {user_name}! שמתי לב שנסעת לאחרונה ל**{recommended_destination}**.\nרוצה שנחפש לך טרמפ לשם גם הפעם?"
        
        if update.callback_query:
            await update.callback_query.message.reply_text(msg, reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, reply_markup=reply_markup)
            
        # עוברים למצב החדש שמחכה ללחיצה על כפתורי המלצה
        return SEARCH_RECOMMENDATION
        
    # 3. אם אין היסטוריה במונגו (משתמש חדש) - ממשיכים בזרימה הרגילה שלך (שאלת היום)
    msg = "כדי שאוכל להתאים לך טרמפים בצורה מדויקת 😊\nלאיזה יום הנסיעה?"
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=_day_choice_keyboard())
    else:
        await update.message.reply_text(msg, reply_markup=_day_choice_keyboard())
        
    return SEARCH_DAY

async def handle_recommendation_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    כאשר המשתמש לוחץ 'כן' - שומרים את היעד המומלץ וממשיכים ישר לשאלת היום הסטנדרטית
    """
    query = update.callback_query
    await query.answer()
    
    recommended_to = context.user_data.get("recommended_to")
    context.user_data["search_to"] = recommended_to  # מזינים את היעד המומלץ מראש
    
    print(f"[DEBUG RECOMMENDATION] המשתמש קיבל את ההמלצה ליעד: {recommended_to}")
    
    # ממשיכים לשאלה הראשונה המקורית שלך (בחירת יום)
    await query.message.reply_text(
        f"אחלה, שמרתי שנרצה לנסוע ל**{recommended_to}**! 👌\nעכשיו, לאיזה יום הנסיעה?",
        reply_markup=_day_choice_keyboard()
    )
    return SEARCH_DAY

async def handle_recommendation_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    כאשר המשתמש לוחץ 'לא' - מנקים את ההמלצה וממשיכים לשאלת היום כרגיל (הוא יקליד יעד בהמשך)
    """
    query = update.callback_query
    await query.answer()
    
    context.user_data.pop("recommended_to", None)  # מנקים את ההמלצה
    
    await query.message.reply_text(
        "אין בעיה, נבחר מסלול מאפס. 😊\nלאיזה יום הנסיעה?",
        reply_markup=_day_choice_keyboard()
    )
    return SEARCH_DAY    

def time_flex_keyboard() -> InlineKeyboardMarkup:
    keyboard = [[
        InlineKeyboardButton("±15 דק׳", callback_data=CB_FLEX_15),
        InlineKeyboardButton("±30 דק׳", callback_data=CB_FLEX_30),
    ], [
        InlineKeyboardButton("אני גמיש מאוד", callback_data=CB_FLEX_ANY),
    ]]
    return InlineKeyboardMarkup(keyboard)


def _is_valid_ddmm(text: str) -> bool:
    # DD/MM where DD=01-31, MM=01-12 (basic validation)
    m = re.fullmatch(r"(0[1-9]|[12]\d|3[01])/(0[1-9]|1[0-2])", (text or "").strip())
    return m is not None


async def open_search_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if not _is_valid_ddmm(text):
        await update.message.reply_text(
            "כדי שאני אבין אותך הכי טוב שאפשר 🙂\n"
            "בבקשה כתוב תאריך בפורמט: 18/01"
        )
        return SEARCH_DATE

    context.user_data["search_date"] = text  # לדוגמה: "18/01"
    await update.message.reply_text("מעולה 😊 מאיפה אתה יוצא?")
    return SEARCH_FROM


async def open_search_day_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == CB_DAY_TODAY:
        context.user_data["search_day"] = "today"
        await query.message.reply_text("מעולה 😊 מאיפה אתה יוצא?", reply_markup=ReplyKeyboardRemove())
        return SEARCH_FROM

    if query.data == CB_DAY_TOMORROW:
        context.user_data["search_day"] = "tomorrow"
        await query.message.reply_text("מעולה 😊 מאיפה אתה יוצא?", reply_markup=ReplyKeyboardRemove())
        return SEARCH_FROM

    if query.data == CB_DAY_OTHER:
        context.user_data["search_day"] = "other"
        await query.message.reply_text(
            "סבבה 😊\nבבקשה כתוב תאריך בפורמט: DD/MM (לדוגמה 18/01)",
            reply_markup=ReplyKeyboardRemove()
        )
        return SEARCH_DATE
  

async def open_search_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # שומרים את נקודת המוצא שהמשתמש הקליד (למשל תל אביב)
    context.user_data["search_from"] = update.message.text
    
    print(f"[DEBUG] מוצא שנשמר: {update.message.text}")
    
    # בדיקה: האם היעד כבר נקבע מראש דרך מערכת ההמלצות החכמה?
    if "search_to" in context.user_data and context.user_data["search_to"]:
        already_to = context.user_data["search_to"]
        print(f"[DEBUG RECOMMENDATION] דילוג על שאלת יעד! המשתמש כבר אישר את: {already_to}")
        
        # מכיוון שהמוצא והיעד כבר ידועים, אנחנו מדלגים על השאלה ומפעילים מיד
        # את הפונקציה הבאה בתור (בדרך כלל בחירת שעה - open_search_to)
        # שימי לב: אנחנו ממש קוראים לפונקציה הבאה שלך ומעבירים לה את ה-update וה-context
        return await open_search_to(update, context)

    # אם היעד לא ידוע (המשתמש לחץ "לא" על ההמלצה) - שואלים כרגיל
    await update.message.reply_text("מעולה 😊 ולאן אתה נוסע?")
    return SEARCH_TO


async def open_search_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("רק תכתוב לאן אתה נוסע.")
        return SEARCH_TO

    context.user_data["search_to"] = text
    context.user_data["search_to_coords"] = await geocode_place(text)


    await update.message.reply_text(
        "ובאיזו שעה?\n"
        "כתוב בפורמט 18:30 (HH:MM)\n"
        "אם לא משנה — כתוב: לא משנה 😊"
    )
    return SEARCH_TIME

    context.user_data["search_to"] = text

    await update.message.reply_text(
        "מתי אתה מתכנן לנסוע?\n"
        "אפשר לכתוב: 18:30 / עכשיו / מחר בבוקר\n"
        "אם לא משנה, פשוט תכתוב: לא משנה 😊"
    )
    return SEARCH_WHEN

async def open_search_when(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("רק תכתוב מתי אתה מתכנן לנסוע.")
        return SEARCH_WHEN

    search_when = text
    ignore_when = (search_when == "לא משנה")

    telegram_id = update.effective_user.id
    user_data = get_user(telegram_id)
    viewer_role = user_data["role"]

    rides = list_open_for_role_and_route(
        viewer_role,
        context.user_data.get("search_from", ""),
        context.user_data.get("search_to", "")
    )

    search_from_coords = context.user_data.get("search_from_coords")

    if search_from_coords:
        filtered = []

        for r in rides:
            ride_from_coords = r.get("from_coords")
            if not ride_from_coords:
                continue

            try:
                d = distance_km(search_from_coords, tuple(ride_from_coords))
                print(f"[DISTANCE] ride_id={r.get('ride_id')} distance={d:.2f} km", flush=True)
            except Exception:
                continue

            if d <= MAX_PICKUP_DISTANCE_KM:
                filtered.append(r)

        rides = filtered

        print(f"[DEBUG] rides after distance filter: {len(rides)}", flush=True)
        for r in rides:
            print(f"[DEBUG] after distance ride_id={r.get('ride_id')} when={r.get('when')}", flush=True)

    if not ignore_when:
        rides = [
            r for r in rides
            if (r.get("when") or "").strip() == search_when
        ]

    print(f"[DEBUG] rides after time filter: {len(rides)}", flush=True)
    for r in rides:
        print(f"[DEBUG] after time ride_id={r.get('ride_id')} when={r.get('when')}", flush=True) 

    browse_ids = [r.get("ride_id") for r in sorted(rides, key=lambda x: x.get("ride_id", 0), reverse=True)]
    browse_ids = [rid for rid in browse_ids if isinstance(rid, int)]

    context.chat_data["browse_rides"] = rides  # שומרים בבטחה ב-chat_data!
    context.chat_data["browse_idx"] = 0

    # ניקוי נתוני חיפוש
    context.user_data.pop("search_from", None)
    context.user_data.pop("search_to", None)

    if not browse_ids:
        await update.effective_message.reply_text(
            "לא מצאתי כרגע טרמפים שמתאימים למסלול ולזמן הזה 😕\n"
            "אבל ממש שווה לנסות שוב בעוד כמה דקות",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    await _show_browse_ride(update, context, edit=False)
    return ConversationHandler.END

def _extract_hhmm(text: str) -> str | None:
    # מחפש שעה בפורמט HH:MM ומחזיר אותה (למשל "18:30") או None
    m = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", (text or "").strip())
    return m.group(0) if m else None


async def open_search_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if text == "לא משנה":
        context.user_data["search_time"] = None
    else:
        hhmm = _extract_hhmm(text)
        if not hhmm:
            await update.message.reply_text(
                "כדי שאני אבין אותך הכי טוב שאפשר 🙂\n"
                "בבקשה כתוב שעה בפורמט: 18:30"
            )
            return SEARCH_TIME
        context.user_data["search_time"] = hhmm

    await update.message.reply_text(
        "כמה אתה גמיש בשעה? 😊",
        reply_markup=time_flex_keyboard()
    )
    return SEARCH_FLEX


def _hhmm_to_minutes(hhmm: str) -> int | None:
    try:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


async def open_search_flex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

   # 1) שמירת הגמישות בדקות
    if data == CB_FLEX_15:
        context.user_data["search_flex_minutes"] = 15
        flex_text = "±15 דקות"
    elif data == CB_FLEX_30:
        context.user_data["search_flex_minutes"] = 30
        flex_text = "±30 דקות"
    elif data == CB_FLEX_ANY:
        context.user_data["search_flex_minutes"] = None
        flex_text = "גמיש מאוד"
    else:
        # זה קורה רק אם משהו השתבש - יוצאים מהשיחה
        return SEARCH_FLEX

    # --- מכאן והלאה הקוד רץ רק אם בחרת אחת מהאופציות למעלה ---
    
    user_name = update.effective_user.first_name 
    search_flex_minutes = context.user_data.get("search_flex_minutes", "??")

    # נבנה את הודעת הגמישות בצורה חכמה
    if flex_text == "גמיש מאוד":
        flex_display = "גמיש.ה מאוד"
    else:
        flex_display = f"גמיש.ה ב-{flex_text}"

    await query.message.reply_text(
        f"תודה {user_name}! הבנתי שאת.ה {flex_display}... בודק לך התאמות 🔍",
        parse_mode="Markdown"
)

    # 2) שליפת נתוני החיפוש
    telegram_id = query.from_user.id
    user_data = get_user(telegram_id)
    if not user_data or not user_data.get("role"):
        await query.message.reply_text(
            "צריך לבחור תפקיד קודם: /start",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    viewer_role = user_data["role"]
    search_from = context.user_data.get("search_from", "")
    search_to = context.user_data.get("search_to", "")
    search_time = context.user_data.get("search_time")
    flex_minutes = context.user_data.get("search_flex_minutes")
    ignore_when = (search_time is None)

    # שולפים את כל הנסיעות הפתוחות של התפקיד המבוקש ומציגים התאמה לפי מרחק גיאוגרפי אמיתי!
    rides = get_open_rides_by_role_from_mongo("passenger" if viewer_role == "driver" else "driver")

    # 4) סינון לפי מרחק אמיתי - גם מוצא וגם יעד (השדרוג המרכזי!)
    search_from_coords = context.user_data.get("search_from_coords")
    search_to_coords = context.user_data.get("search_to_coords")

    filtered_by_dist = []

    for r in rides:
        ride_from_c = r.get("from_coords")
        ride_to_c = r.get("to_coords")

        # אם יש קואורדינטות לשני הצדדים, נבצע חישוב מרחק כפול
        if ride_from_c and ride_to_c and search_from_coords and search_to_coords:
            d_from = distance_km(search_from_coords, tuple(ride_from_c))
            d_to = distance_km(search_to_coords, tuple(ride_to_c))
            
            print(f"[DIST CHECK] Ride {r.get('ride_id')}: From={d_from:.1f}km, To={d_to:.1f}km", flush=True)
            
            if d_from <= MAX_PICKUP_DISTANCE_KM and d_to <= MAX_PICKUP_DISTANCE_KM:
                filtered_by_dist.append(r)
        
        # גיבוי: אם חסר מידע גיאוגרפי, נסתמך על ההתאמה הטקסטואלית שכבר בוצעה ב-list_open_for_role_and_route
        elif not search_from_coords or not search_to_coords:
             filtered_by_dist.append(r)

    rides = filtered_by_dist

 
# 5) סינון לפי זמן
    if not ignore_when:
        search_minutes = _hhmm_to_minutes(search_time)
        time_filtered = []

        print(f"[DEBUG] מחפש זמן: {search_time} ({search_minutes} דקות)")

        for r in rides:
            # גיבוי מנצח: אם המשתמש גמיש מאוד - מאשרים את הטרמפ מיד בלי שום סינון שעות!
            if flex_minutes is None:
                time_filtered.append(r)
                continue

            ride_when = (r.get("when") or "").strip()
            ride_minutes = _hhmm_to_minutes(ride_when)
            
            if ride_minutes is None or search_minutes is None:
                # אם הזמן לא בפורמט HH:MM והמשתמש לא גמיש מאוד, אין לנו איך לחשב הפרש
                continue

            diff = abs(ride_minutes - search_minutes)
            if diff <= flex_minutes:
                time_filtered.append(r)

        rides = time_filtered

    # בדיקה סופית בטרמינל לפני הצגה
    print(f"[DEBUG] נמצאו {len(rides)} טרמפים סופיים להצגה")

    # בניית רשימת התוצאות לדפדוף
    
    # מיון לפי זמן היצירה ומאפשרים ל-ride_id להיות מחרוזת (string) ממונגו!
    browse_ids = [r.get("ride_id") for r in sorted(rides, key=lambda x: x.get("created_at", ""), reverse=True)]
    browse_ids = [rid for rid in browse_ids if rid is not None]
    
    context.user_data["browse_ids"] = browse_ids
    context.user_data["browse_idx"] = 0

    # אם הרשימה ריקה, שולחים הודעת אי התאמה ויוצאים מיד
    if not browse_ids:
        # ניקוי נתוני חיפוש למקרה של כישלון
        keys_to_clear = ["search_day", "search_date", "search_from", "search_to", "search_time", "search_flex_minutes", "search_from_coords", "search_to_coords"]
        for key in keys_to_clear:
            context.user_data.pop(key, None)
            
        await query.message.reply_text(
             f"מצטער {user_name}, לא מצאתי כרגע טרמפים שמתאימים בדיוק... 😕\nאולי כדאי לנסות שוב עם גמישות גדולה יותר?",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    # 1. ניקוי הזיכרון הישן
    keys_to_clear = ["search_day", "search_date", "search_from", "search_to", "search_time", "search_flex_minutes", "search_from_coords", "search_to_coords"]
    for key in keys_to_clear:
        context.user_data.pop(key, None)

    # 2. שולפים וממירים את הנתונים של הטרמפים לטקסט נקי (str)
    ride = rides[0]
    current_id = str(ride.get("_id"))
    
    next_id = None
    if len(rides) > 1:
        next_id = str(rides[1].get("_id"))

    print(f"[DEBUG FLEX] מציג טרמפ ראשון: {current_id}, מכין כפתור לטרמפ הבא: {next_id}")

    msg = (
        f"איזה כיף {user_name}! מצאתי טרמפ 👇\n\n"
        f"מוצא: {ride.get('from')}\n"
        f"יעד: {ride.get('to')}\n"
        f"מתי: {ride.get('when')}\n\n"
        "מה תרצה לעשות?"
    )
    
    # 3. שולחים את ההודעה עם המקלדת החכמה שמכילה את ה-ID הבא כטקסט
    await query.message.reply_text(msg, reply_markup=_browse_keyboard(current_id, next_id))
    return ConversationHandler.END


def _load_json_dict(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_json_dict(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def geocode_place(place_text: str) -> tuple[float, float] | None:
    """
    Returns (lat, lon) for a place string using Nominatim (OpenStreetMap).
    Uses a simple JSON cache to reduce repeated calls.
    """
    q = (place_text or "").strip()
    print(f"[GEOCODE START] q='{q}'", flush=True)

    if not q:
        return None

    # בדיקה בקאש
    cache = _load_json_dict(GEO_CACHE_FILE)
    if q in cache:
        try:
            lat = float(cache[q]["lat"])
            lon = float(cache[q]["lon"])
            print(f"[GEOCODE CACHE] '{q}' -> lat={lat}, lon={lon}", flush=True)
            return lat, lon
        except Exception as e:
            print(f"[GEOCODE CACHE ERROR] '{q}' -> {e}", flush=True)

    # קריאה ל־Nominatim
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": q, "format": "json", "limit": 1}
    headers = {"User-Agent": "TrempiBot/1.0 (edu project)"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        resp.raise_for_status()
        results = resp.json()

        if not results:
            print(f"[GEOCODE API] '{q}' -> no results", flush=True)
            return None

        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])

        print(f"[GEOCODE API] '{q}' -> lat={lat}, lon={lon}", flush=True)

        # שמירה בקאש
        cache[q] = {"lat": lat, "lon": lon}
        _save_json_dict(GEO_CACHE_FILE, cache)

        return lat, lon

    except Exception as e:
        print(f"[GEOCODE API ERROR] '{q}' -> {e}", flush=True)
        return None

    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": q, "format": "json", "limit": 1}
    headers = {"User-Agent": "TrempiBot/1.0 (edu project)"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None

        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])

        print(f"[GEOCODE] '{q}' -> lat={lat}, lon={lon}")


        cache[q] = {"lat": lat, "lon": lon}
        _save_json_dict(GEO_CACHE_FILE, cache)

        return lat, lon
    except Exception:
        return None

import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "TrempiBot/1.0 (contact: elish1919@gmail.com)"  

from math import radians, cos, sin, asin, sqrt

def distance_km(coord1: tuple, coord2: tuple) -> float:
    """
    מחשב מרחק בק״מ בין שתי נקודות (lat, lon)
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    # המרה לרדיאנים
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    R = 6371  # רדיוס כדור הארץ בק״מ
    return R * c


def geocode_place_osm(place: str) -> tuple[float, float] | None:
    q = (place or "").strip()
    if not q:
        return None

    # הגדרת גבולות לישראל (בערך) כדי למנוע תוצאות מחו"ל
    # viewbox format: <lon1>,<lat1>,<lon2>,<lat2>
    israel_viewbox = "34.0,29.0,36.0,33.5" 

    params = {
        "q": q,
        "format": "json",
        "limit": 1,
        "countrycodes": "il",  # מחייב תוצאות מישראל
        "viewbox": israel_viewbox,
        "bounded": 1 # נותן עדיפות גבוהה מאוד לגבולות שקבענו
    }

    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": NOMINATIM_USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                return (lat, lon)
    except Exception as e:
        print(f"[ERROR] Geocoding failed for {q}: {e}")
        return None
    return None

    if not data:
        return None

    try:
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        return (lat, lon)
    except Exception:
        return None

async def geocode_place(place: str) -> tuple[float, float] | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, geocode_place_osm, place)


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN is missing. Check your .env file.")

    app = ApplicationBuilder().token(TOKEN).build()

    # --- 1. הגדרת שיחות מרובות שלבים (Conversations) ---
    
    new_ride_conv = ConversationHandler(
        entry_points=[
            CommandHandler("new", new_ride_start),
            MessageHandler(filters.Regex(f"^{BTN_NEW}$"), new_ride_start),
        ],
        states={
            ASK_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_from)],
            ASK_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_to)],
            ASK_WHEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_when)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    registration_conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_registration_button, pattern=r"^start_registration$"),
        ],
        states={
            REG_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_age)],
            REG_GENDER: [
                CallbackQueryHandler(
                    reg_gender_button,
                    pattern=f"^({CB_GENDER_MALE}|{CB_GENDER_FEMALE}|{CB_GENDER_OTHER})$"
                )
            ],
            REG_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_address)],
            REG_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_phone)],
            REG_ROLE: [
                CallbackQueryHandler(
                    reg_role_button,
                    pattern=f"^({CB_ROLE_DRIVER}|{CB_ROLE_PASSENGER}|{CB_ROLE_BOTH})$"
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    open_search_conv = ConversationHandler(
        entry_points=[
            CommandHandler("open", open_search_start),
            MessageHandler(filters.Regex(f"^{BTN_OPEN}$"), open_search_start),
        ],
        states={
            # 1. שלב מערכת ההמלצות - כאן הבוט יחכה ללחיצה על כן או לא!
            SEARCH_RECOMMENDATION: [
                CallbackQueryHandler(handle_recommendation_yes, pattern="^rec_yes$"),
                CallbackQueryHandler(handle_recommendation_no, pattern="^rec_no$")
            ],
            
            # 2. שאר השלבים המקוריים שלך בסדר המדויק שלהם:
            SEARCH_DAY: [
                CallbackQueryHandler(
                    open_search_day_button,
                    pattern=f"^({CB_DAY_TODAY}|{CB_DAY_TOMORROW}|{CB_DAY_OTHER})$"
                )
            ],
            SEARCH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, open_search_date)],
            SEARCH_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, open_search_from)],
            SEARCH_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, open_search_to)],
            SEARCH_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, open_search_time)],
            SEARCH_FLEX: [
                CallbackQueryHandler(
                    open_search_flex,
                    pattern=f"^({CB_FLEX_15}|{CB_FLEX_30}|{CB_FLEX_ANY})$"
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # --- 2. רישום ה-Handlers בבוט (בסדר הנכון) ---
    
    # כפתורי דפדוף והצטרפות גלובליים (שמנו אותם הכי למעלה כדי שיגיבו תמיד!)
    app.add_handler(CallbackQueryHandler(browse_next, pattern="^next_"))
    app.add_handler(CallbackQueryHandler(browse_join, pattern=r"^browse_join:\d+$"))
    app.add_handler(CallbackQueryHandler(role_button, pattern=r"^role_"))

    # פקודות ישירות
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("my", my_cmd))
    
    # שיחות 
    app.add_handler(registration_conv)
    app.add_handler(new_ride_conv)
    app.add_handler(open_search_conv)

    # התפריט הראשי (חייב להיות אחרון!)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_router))

    print("Bot is running...")
    app.run_polling()

# הפעלת ה-main 
if __name__ == "__main__":
    main()