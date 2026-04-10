import aiosqlite

DB = "bot.db"


async def init_db():
    async with aiosqlite.connect(DB) as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            photo TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            rating REAL DEFAULT 0,
            votes INTEGER DEFAULT 0,
            has_profile INTEGER DEFAULT 0
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            from_id INTEGER,
            to_id INTEGER,
            score INTEGER,
            PRIMARY KEY (from_id, to_id)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            user_id INTEGER PRIMARY KEY,
            partner_id INTEGER
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS incoming (
            user_id INTEGER,
            from_id INTEGER
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS pending_messages (
            sender_id INTEGER,
            receiver_id INTEGER,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (sender_id, receiver_id)
        )
        """)

        await db.commit()


# ---------------- USERS ----------------
async def add_user(user_id, username):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        await db.commit()


async def user_has_profile(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT has_profile FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        return row and row[0] == 1


async def set_bio(user_id, bio):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET bio=?, has_profile=1 WHERE user_id=?",
            (bio, user_id)
        )
        await db.commit()


async def set_photo(user_id, photo):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET photo=? WHERE user_id=?",
            (photo, user_id)
        )
        await db.commit()


async def get_full_user(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT username, photo, bio
            FROM users
            WHERE user_id=?
        """, (user_id,))
        return await cur.fetchone()


async def get_user_stats(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT rating, votes, bio
            FROM users
            WHERE user_id=?
        """, (user_id,))
        return await cur.fetchone() or (0, 0, "")


# ---------------- RANDOM ----------------
async def get_random_user(exclude_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT user_id FROM users
            WHERE user_id != ?
            AND has_profile = 1
            ORDER BY RANDOM()
            LIMIT 1
        """, (exclude_id,))
        row = await cur.fetchone()
        return row[0] if row else None


# ---------------- RATINGS ----------------
async def save_rating(from_id, to_id, score):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            INSERT OR REPLACE INTO ratings VALUES (?, ?, ?)
        """, (from_id, to_id, score))
        await db.commit()


async def get_rating(from_id, to_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT score FROM ratings
            WHERE from_id=? AND to_id=?
        """, (from_id, to_id))
        row = await cur.fetchone()
        return row[0] if row else 0


async def update_rating(to_id, score):
    async with aiosqlite.connect(DB) as db:

        cur = await db.execute(
            "SELECT rating, votes FROM users WHERE user_id=?",
            (to_id,)
        )
        row = await cur.fetchone()

        if not row:
            return

        rating, votes = row
        new_rating = (rating * votes + score) / (votes + 1)

        await db.execute("""
            UPDATE users
            SET rating=?, votes=votes+1
            WHERE user_id=?
        """, (new_rating, to_id))

        await db.commit()


# ---------------- INCOMING ----------------
async def save_incoming_rating(to_id, from_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO incoming VALUES (?, ?)
        """, (to_id, from_id))
        await db.commit()


async def get_last_rater(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT from_id
            FROM incoming
            WHERE user_id=?
            ORDER BY rowid DESC
            LIMIT 1
        """, (user_id,))
        row = await cur.fetchone()
        return row[0] if row else None


# ---------------- PENDING MSG ----------------
async def inc_pending_messages(sender_id, receiver_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO pending_messages (sender_id, receiver_id, count)
        VALUES (?, ?, 1)
        ON CONFLICT(sender_id, receiver_id)
        DO UPDATE SET count = count + 1
        """, (sender_id, receiver_id))
        await db.commit()


async def get_pending_count(sender_id, receiver_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT count FROM pending_messages
            WHERE sender_id=? AND receiver_id=?
        """, (sender_id, receiver_id))
        row = await cur.fetchone()
        return row[0] if row else 0


async def clear_pending(sender_id, receiver_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        DELETE FROM pending_messages
        WHERE sender_id=? AND receiver_id=?
        """, (sender_id, receiver_id))
        await db.commit()


# ---------------- CHAT ----------------
async def set_chat(u1, u2):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR REPLACE INTO chats VALUES (?, ?)", (u1, u2))
        await db.execute("INSERT OR REPLACE INTO chats VALUES (?, ?)", (u2, u1))
        await db.commit()


async def get_partner(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT partner_id FROM chats WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def exit_chat(user_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM chats WHERE user_id=?", (user_id,))
        await db.commit()