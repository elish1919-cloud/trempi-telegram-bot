# Trempi 🚗 — Community Rideshare Telegram Bot

A Telegram bot that connects **drivers** offering rides with **passengers** looking for rides,
using smart matching based on **route**, **geographic distance** (Haversine calculation), and a **flexible time window**.

---

## 1. Project Description and Purpose

**Trempi** is a Hebrew-language Telegram bot designed to make ride-sharing within a community easier.
A user registers once (age, gender, address, phone, and preferred role), and can then:

- **As a driver** — post a ride (where from, where to, and when).
- **As a passenger** — search open rides, browse matches, and join the ride that fits.

The bot performs **automatic matching** between passenger and driver based on:
- **Route** (origin and destination point).
- **Geographic proximity** — a ride is considered a match only if the driver's origin and destination are within
  `MAX_PICKUP_DISTANCE_KM = 5` km of the passenger's origin and destination (distance calculated with the Haversine formula).
- **Flexible time window** — the passenger chooses how flexible they are on time (±15 min / ±30 min / "very flexible").

In addition, the bot includes a **personal recommendation engine** based on MongoDB, which suggests the passenger's
last searched destination and the most popular destination, to shorten the search process.

---

## 2. Key Features

| Feature | Description |
|-------|-------|
| **Guided registration** | Multi-step conversation: age → gender → address → phone → preferred role (driver / passenger / both), with validation (age 16–120, phone 9–10 digits). |
| **Personal profile** | View details (`My Profile`) with an option to edit. |
| **Post a ride (driver)** | A from → to → when conversation, including automatic geocoding of the origin and destination points. |
| **Search for a ride (passenger)** | Guided conversation: day → date → origin → destination → time → flexibility. |
| **Recommendation engine** | Suggests the user's last searched destination (`get_last_searched_destination`) and the most popular destination (`get_most_popular_destination`). |
| **Geographic filtering** | Matching by real distance in km using the Haversine formula (`distance_km`). |
| **Flexible time window (FLEX)** | Filters rides by the allowed minute difference between the search time and the ride time. |
| **Browsing matches** | "Show me another ride" / "I want to join" buttons above the match list. |
| **Joining a ride** | The passenger joins with a button tap and receives confirmation that the driver will get in touch. |
| **My requests** | Displays the user's recent rides. |
| **Geocoding + Cache** | Converts a place name to coordinates via Nominatim (OpenStreetMap), with a local cache (`geocache.json`) to reduce network calls. |
| **Cloud storage** | Rides are stored in MongoDB Atlas; user details are stored in a local `users.json` file. |

---

## 3. Installation and Setup Instructions

### Prerequisites
- Python 3.10 or higher (the code uses `type | None` syntax).
- A Telegram bot token from [@BotFather](https://t.me/BotFather).
- Access to a MongoDB database (Atlas or local).

### Step 1 — Create a virtual environment

```bash
# Create the environment
python -m venv venv

# Activate on Windows (PowerShell)
venv\Scripts\Activate.ps1

# Activate on Linux / macOS
source venv/bin/activate
```

### Step 2 — Install dependencies

The dependencies are listed in `requirements.txt` with pinned versions:

```text
python-telegram-bot==22.5
pymongo==4.17.0
certifi==2025.11.12
requests==2.32.5
python-dotenv==1.2.1
```

Install:

```bash
pip install -r requirements.txt
```

### Step 3 — Configure environment variables
Create a `.env` file in the project root (see section 4).

### Step 4 — Run the bot

```bash
python bot.py
```

On success, the terminal will show `Bot is running...` and the bot will start working via polling.
From here you can open the bot in Telegram and send `/start`.

---

## 4. Environment Variable Management (.env)

The code loads the `.env` file via `python-dotenv` (`load_dotenv()` in `bot.py`).

| Key | Required? | Description |
|------|-------|-------|
| `BOT_TOKEN` | ✅ Yes | The Telegram bot token. Loaded in `bot.py` (`os.getenv("BOT_TOKEN")`). If missing — the bot raises a `BOT_TOKEN is missing` error and does not start. |
| `MONGO_URI` | ✅ Yes | The MongoDB Atlas connection string (including username and password). Loaded in `database.py` (`os.getenv("MONGO_URI")`). If missing — a `MONGO_URI is missing` error is raised and the bot does not start. |

Example `.env` file:

```env
BOT_TOKEN=123456789:ABCdefGhIJKlmnOPQRstuVWxyz
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?appName=Cluster0
```

> **Security note:** The `.env` file contains secrets (the bot token and the DB password), so it must never be
> committed to Git. Make sure it is listed in `.gitignore`.

---

## 5. Security Notes

- **Storing database credentials:** The MongoDB connection string (`MONGO_URI`, including username
  and password) and the bot token (`BOT_TOKEN`) are stored only in the local `.env` file, and are never committed
  to Git. The `.env` file is listed in `.gitignore` and is therefore not included in the project's Git history.
- **Previously exposed secrets:** To the extent that any credentials were previously exposed in the Git history
  (for example, in old commits before `.env` was added to `.gitignore`), they have been **rotated** — i.e.,
  replaced with new values — and the old exposed values **are no longer valid** and do not grant access to the system.
- **Recommendation for developers:** When cloning the project, create a new local `.env` file (per the example
  in section 4) and never add it to Git. If a secret is accidentally committed, rotate it immediately even if
  the commit is later removed, since Git history may still retain it.
- **Removed unused and personal-data files:** `rides.json` was unused dead code — no code in `bot.py` or
  `database.py` ever read or wrote it — and it contained real address data from testing, so it has been deleted
  from the repository entirely. `users.json`, which contains personal test data (name, phone number, age, gender,
  and address) collected while testing the bot, has been removed from Git tracking and added to `.gitignore`
  going forward: it still exists locally on disk for the bot to read/write at runtime, but new commits will no
  longer include it. Note that this does not erase copies of that data already present in earlier Git history/commits.

---

## 6. Folder Structure

```
Trempi/
├── bot.py            # The heart of the bot: all handlers, ConversationHandler conversations,
│                     #   registration/search/posting logic, geocoding and the Haversine formula
├── database.py       # MongoDB Atlas access layer: save/fetch/update rides + the recommendation engine
├── users.json        # Local storage of registered users' details (created/updated automatically) —
│                     #   contains real personal data, not tracked in Git (see Security Notes)
├── geocache.json     # Local cache of geocoding results (created automatically at runtime), not tracked in Git
├── test_mongo.py     # Test data (fake_rides) for injecting into the DB during TEST_MODE
├── test_geo.py       # Tests/experiments around the geocoding functions
├── requirements.txt  # List of dependencies with pinned versions
├── requirements-dev.txt  # Test-only dependencies (pytest, pytest-asyncio)
├── .env              # Environment variables (BOT_TOKEN, MONGO_URI) — not included in Git
├── venv/             # Virtual environment
└── README.md
```

> Note: `rides.json` (a legacy pre-MongoDB rides file, unused by any code) has been deleted from the
> repository entirely — see Security Notes above.

**Division of responsibility between files:**
- `bot.py` — all Telegram communication, conversation state management, validations, geographic calculation
  (Haversine), and time-window filtering.
- `database.py` — all operations against MongoDB (the `rides` collection), including the recommendation queries.

---

## 7. Usage Examples — A Typical Conversation

### 👤 Driver Flow — Posting a Ride

1. The driver sends `/start`. If not yet registered, the bot shows a **"Start Registration"** button and guides
   them through questions about age, gender, address, phone, and preferred role.
2. After registration, the main menu appears (button keyboard):

   ```
   [ Create a Ride ]   [ What's Available Now ]
   [ My Requests ]   [ Help ]
   [ My Profile ]
   ```
3. The driver taps **"Create a Ride"**, and the bot asks, one after another:

   > 🤖 **Where are you leaving from?**
   > 👤 Tel Aviv
   >
   > 🤖 **Where are you going?**
   > 👤 Bar-Ilan University
   >
   > 🤖 **When is it? You can write, for example: now / 18:30 / tomorrow morning**
   > 👤 07:00

4. The bot geocodes both points, saves the ride to MongoDB (status `open`), and replies:

   > 🤖 Got it.
   > Request number: 665f...
   > Origin: Tel Aviv
   > Destination: Bar-Ilan University
   > When: 07:00
   >
   > 🤖 Great. The request has been saved and the system is looking for a match for you.

### 🎒 Passenger Flow — Finding and Joining a Ride

1. The passenger taps **"What's Available Now"** (or sends `/open`).
2. If they have search history, the bot shows personalized recommendations:

   > 🤖 Hi Tamar, where are you headed this time? 🚗
   > `[ 🕒 My last ride — Bar-Ilan University ]`
   > `[ ⭐ Your most popular ride — Bar-Ilan University ]`
   > `[ 🔍 Take me to another destination ]`

3. The bot guides them through the search steps:

   > 🤖 **Which day is the ride?**  `[ Today ]  [ Tomorrow ]  [ Another date ]`
   >
   > 🤖 **Great 😊 Where are you leaving from?**
   > 👤 Tel Aviv
   >
   > 🤖 **And where are you going?** (skipped if the destination was already chosen from a recommendation)
   > 👤 Bar-Ilan University
   >
   > 🤖 **And what time?** (format 18:30, or "doesn't matter")
   > 👤 07:00
   >
   > 🤖 **How flexible are you on time? 😊**  `[ ±15 min ]  [ ±30 min ]  [ I'm very flexible ]`

4. The bot performs geographic filtering + time-window filtering, and shows the first match:

   > 🤖 How exciting, Tamar! I found a ride 👇
   > 🚗 Origin: Tel Aviv
   > 📍 Destination: Bar-Ilan University
   > ⏰ When: 07:00
   >
   > What would you like to do?
   > `[ Perfect, I want to join ]`
   > `[ Show me another ride ]`

5. Tapping **"I want to join"** closes the match, and the passenger receives:

   > 🤖 Wonderful, your request has been sent! 🚗✨
   > The driver has been notified that you want to join, and will contact you soon to coordinate the ride. Have a great trip!

---

## 8. End-to-End Flow Explanation (Technical Event Flow)

From the moment `/start` is sent until the match between driver and passenger is created:

### A. Registration — `registration_conv`
1. `/start` triggers the `start()` handler in `bot.py`. The function calls `register_or_update_user()`,
   which writes/updates the record in `users.json`.
2. If the user is not registered — the `start_registration` button is shown, which triggers a `ConversationHandler`
   that moves through the states `REG_AGE → REG_GENDER → REG_ADDRESS → REG_PHONE → REG_ROLE`.
3. At the end, `reg_role_button()` calls `update_user_fields()` and sets `is_registered = True` in `users.json`.

### B. Posting a Ride (Driver) — `new_ride_conv`
1. The "Create a Ride" button triggers `new_ride_start()` and the `ASK_FROM → ASK_TO → ASK_WHEN` conversation.
2. In `ask_when()`:
   - `geocode_place()` is called (delegates to `geocode_place_osm()` via an executor) for both the origin and
     destination → coordinates `(lat, lon)` are obtained from Nominatim (with caching in `geocache.json`).
   - A `ride` dict is built with `from_coords` / `to_coords` / `when` / `status="open"`.
   - `add_ride()` in `bot.py` calls `save_ride_to_mongo()` in `database.py` → the ride is saved
     to the `rides` collection in MongoDB, and the `_id` is returned as `ride_id`.

### C. Searching and Matching (Passenger) — `open_search_conv`
1. The "What's Available Now" button / `/open` triggers `open_search_start()`:
   - Calls `get_last_searched_destination()` and `get_most_popular_destination()` (in `database.py`)
     to build the recommendations screen (state `SEARCH_RECOMMENDATION`).
2. The conversation continues through the states: `SEARCH_DAY → (SEARCH_DATE) → SEARCH_FROM → SEARCH_TO → SEARCH_TIME → SEARCH_FLEX`.
   - `open_search_to()` geocodes the destination (`search_to_coords`).
3. **The matching point — `open_search_flex()`** (state `SEARCH_FLEX`):
   - Fetches from MongoDB all open rides of the opposite role (`get_open_rides_by_role_from_mongo()`):
     a passenger searching → gets `driver` rides, and vice versa.
   - If origin/destination coordinates are missing — fills them in real time via `geocode_place()`.
   - **Geographic filtering (Haversine):** For each ride, `distance_km(search_from_coords, ride_from_coords)`
     and `distance_km(search_to_coords, ride_to_coords)` are computed. The ride is kept only if **both** distances
     are less than or equal to `MAX_PICKUP_DISTANCE_KM` (5 km). The `distance_km()` function implements the
     Haversine formula (`bot.py`). If there are no coordinates at all — there is a smart fallback to text-based
     filtering by city name.
   - **Time window filtering (FLEX):** If a time was chosen, each time is converted to minutes with
     `_hhmm_to_minutes()`, and `diff = abs(ride_minutes - search_minutes)` is computed. The ride passes the filter
     only if `diff <= flex_minutes` (15 / 30). With "very flexible" (`flex_minutes = None`), the time filter is skipped.
   - The results are sorted and stored in `context.chat_data["browse_rides"]`, and the first match is shown with
     the `_browse_keyboard(current_id, next_id)` keyboard.

### D. Browsing and Joining (Closing the Match)
1. The **"Show me another ride"** button (`callback_data="next_..."`) is handled by `browse_next()`, which fetches
   the next ride from MongoDB / memory and displays it.
2. The **"I want to join"** button (`callback_data="join_..."`) is handled by `handle_join_ride()`, which sends
   the passenger confirmation that the join was received and that the driver will make contact — this is the final
   matching point between passenger and driver.

### Condensed Flow Diagram

```
/start ─► start() ─► register_or_update_user() ─► users.json
   └─(not registered)─► registration_conv (REG_AGE…REG_ROLE) ─► update_user_fields()

[Driver] "Create a Ride" ─► new_ride_conv (ASK_FROM→ASK_TO→ASK_WHEN)
        └─► geocode_place() ─► add_ride() ─► save_ride_to_mongo() ─► MongoDB(rides, status=open)

[Passenger] "What's Available Now" ─► open_search_conv
        ├─ SEARCH_RECOMMENDATION (get_last_searched_destination / get_most_popular_destination)
        ├─ SEARCH_DAY→FROM→TO→TIME
        └─ SEARCH_FLEX ─► open_search_flex():
              ├─ get_open_rides_by_role_from_mongo(target_role)   [database.py]
              ├─ distance_km()  ≤ 5 km   ← Haversine filtering       [bot.py]
              ├─ abs(ride−search) ≤ flex_minutes  ← FLEX window     [bot.py]
              └─ _show / _browse_keyboard(join_, next_)
                    └─ "I want to join" ─► handle_join_ride() ─► ✅ Match
```

---

## 9. Testing

The project includes an automated `pytest` test suite covering the bot's core logic
(geographic filtering, flexible time window, input validation, role management, and duplicate-join prevention)
without needing a real connection to MongoDB or Telegram — all network and database calls are replaced
with mocks using `unittest.mock`.

> **Note:** `test_geo.py` and `test_mongo.py` are old manual scripts (not part of the
> pytest suite) — `test_mongo.py` in particular injects demo data directly into the real MongoDB
> when run, so `conftest.py` explicitly excludes them from test collection (`collect_ignore`) so
> that `pytest` doesn't accidentally run them.

### Running the Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

For verbose output (each test's name + result):

```bash
pytest -v
```

### Test Structure and Mocking

| File | What It Covers |
|------|----------|
| `conftest.py` | Shared infrastructure: dummy environment variables for `BOT_TOKEN`/`MONGO_URI` (so importing `bot.py`/`database.py` doesn't require a real `.env`), builders for mock `Update`/`CallbackQuery`/`Message` objects (`unittest.mock.MagicMock`/`AsyncMock`), and a lightweight `FakeContext` instead of `ContextTypes.DEFAULT_TYPE`. Also sets `collect_ignore` for `test_geo.py`/`test_mongo.py`. |
| `test_validation.py` | Date/time validation: `_extract_hhmm()` (e.g. `"18:30"` is valid, `"tomorrow morning"`/`"now"` contain no time, `"25:00"`/`"12:60"` invalid hour/minute), `_hhmm_to_minutes()`, and `_is_valid_ddmm()` (`DD/MM` format). |
| `test_matching.py` | `distance_km()` (Haversine formula) with real-world coordinates (Tel Aviv / Bar-Ilan / Modiin Illit); distance filtering and FLEX filtering via `open_search_flex()` with `get_open_rides_by_role_from_mongo`/`get_user` mocked; a "no match" scenario (distance too large, time outside the window, or both). |
| `test_ride_actions.py` | Canceling an active conversation (`cancel()`), switching role driver↔passenger (`set_user_role()`/`get_user()`/`role_button()` with a temporary `users.json` for testing), and preventing duplicate joins on the same ride (`handle_join_ride()` with `find_ride()`/`update_ride()` mocked). |

**Mocking principles:**
- No test opens a real connection to MongoDB — `get_open_rides_by_role_from_mongo`, `find_ride`, and `update_ride`
  are replaced via `monkeypatch.setattr` with in-memory mock functions/classes.
- No test writes to the real `users.json` — tests that touch the users file use the `isolated_users_file` fixture,
  which points `bot.USERS_FILE` at a temporary file (`tmp_path`).
- Calls to Telegram (`reply_text`, `edit_message_text`, `answer`) are replaced with `AsyncMock` so the exact
  messages sent can be checked, without opening a real connection to the bot.

### A Bug Found and Fixed While Writing the Tests

While writing tests for "duplicate-join prevention," it was discovered that the real handler wired to the
"I want to join" button (`handle_join_ride()`) referenced variables that were never defined (`ride_id`,
`fallback_message`), so every real tap on the button would crash with a `NameError` — and it also never
actually checked whether the ride had already been taken before replying with success. The correct logic
(status check and atomic update) already existed in the `browse_join()` function, which was never actually
wired up. The fix connects that same logic into `handle_join_ride()`, and it is now covered by `test_ride_actions.py`.

---

## 10. Edge Case Handling

The bot is expected to degrade gracefully — reply with a clear message — rather than crash or silently drop
the user's message when it hits bad input or a flaky dependency. `test_edge_cases.py` covers the following
scenarios:

| Scenario | How the system responds | Covered by |
|----------|--------------------------|------------|
| **Unrecognized/invalid city name** | `geocode_place()` already returns `None` instead of raising when Nominatim finds no match for a place name. Ride creation still completes (the ride is saved without coordinates), and ride search still proceeds (falls back to text-based city-name matching in `open_search_flex()`, or just stores `None` coordinates in `open_search_to()`). No crash, no dead end. | `TestUnrecognizedCityName` |
| **Invalid time format** (e.g. gibberish instead of `18:30`) | `open_search_time()` validates the input with `_extract_hhmm()` and, if it doesn't look like a time, replies asking for the `HH:MM` format again and stays in the same conversation state (`SEARCH_TIME`) instead of crashing or advancing with bad data. | `TestInvalidTimeFormat` |
| **No matching rides found** (distance and/or time window) | `open_search_flex()` replies with a friendly "no rides match right now" message and cleanly ends the conversation (`ConversationHandler.END`) instead of raising an error or leaving the user without a reply. | `TestNoMatchingRidesExplicit` (see also the more detailed `test_matching.py::TestNoMatchScenario`) |
| **External service failure** (geocoding API or MongoDB call raising an exception, e.g. a timeout or a DB outage) | **Originally a real bug:** `ask_when()` (ride creation), `open_search_flex()` (ride search/matching), and `open_search_to()` (search destination step) had no error handling around their `geocode_place()` / MongoDB calls — an exception there would propagate out of the handler uncaught, and the user would simply get no reply at all. Fixed by wrapping those calls in `try/except`: `ask_when()` and `open_search_flex()` now reply with a short Hebrew "temporary glitch, try again" message and end the conversation; `open_search_to()` treats a geocoding exception the same as "place not found" (falls back to `None` coordinates) since the rest of the search flow already handles that case. | `TestExternalServiceFailure` |

**Why this mattered:** before the fix, a MongoDB blip or a Nominatim timeout during ride creation or ride search
would silently kill the conversation from the user's point of view — no error, no retry prompt, just nothing.
`TestExternalServiceFailure` was verified to actually fail against the pre-fix code (confirmed by temporarily
reverting the fix and re-running the suite), so it is a real regression guard, not a test written to match
already-correct behavior.
