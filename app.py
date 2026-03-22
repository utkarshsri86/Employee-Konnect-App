import streamlit as st
import sqlite3
import hashlib
import os
from datetime import datetime

# ============================================================
#  DB CONNECTION
# ============================================================
@st.cache_resource
def get_connection():
    conn = sqlite3.connect(
        "database.db",
        check_same_thread=False,
        timeout=10,
        isolation_level=None
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

conn = get_connection()
c = conn.cursor()

# ============================================================
#  DB TABLES SETUP
# ============================================================
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT    NOT NULL,
    company TEXT    NOT NULL,
    role    TEXT    NOT NULL,
    skills  TEXT    NOT NULL
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS accounts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT "user"
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS connections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user   TEXT    NOT NULL,
    to_user     TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT "pending",
    created_at  TEXT    NOT NULL,
    UNIQUE(from_user, to_user)
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user   TEXT    NOT NULL,
    to_user     TEXT    NOT NULL,
    message     TEXT    NOT NULL,
    is_read     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL
)
''')

# Seed default admin
ADMIN_HASH = hashlib.sha256("admin123".encode()).hexdigest()
c.execute("SELECT id FROM accounts WHERE username='admin'")
if not c.fetchone():
    c.execute(
        "INSERT INTO accounts (username, password_hash, role) VALUES (?, ?, ?)",
        ("admin", ADMIN_HASH, "admin")
    )

# ============================================================
#  HELPERS
# ============================================================
def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_initials(name):
    parts = name.strip().split()
    return "".join(p[0].upper() for p in parts[:2])

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def skill_badges(skills_str):
    badges = ""
    for s in skills_str.split(","):
        s = s.strip()
        if s:
            badges += (
                f"<span style='background:#EBF5FB;color:#2E86C1;"
                f"padding:3px 10px;border-radius:12px;margin:3px;"
                f"display:inline-block;font-size:12px;'>{s}</span>"
            )
    return badges

def profile_card(row, show_full=True):
    initials = get_initials(row[1])
    skills_html = skill_badges(row[4]) if show_full else ""
    company_html = f"<p style='margin:4px 0;'><b>🏢 Company:</b> {row[2]}</p>" if show_full else ""
    hidden = "" if show_full else "<p style='color:#aaa;font-size:13px;margin:4px 0;'>🔒 Company & Skills hidden</p>"
    return f"""
    <div style="border:1px solid #e0e0e0;border-radius:14px;
                padding:18px;margin:8px 0;background:#fff;
                box-shadow:1px 2px 8px rgba(0,0,0,0.07);">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
            <div style="width:44px;height:44px;border-radius:50%;
                        background:#2E86C1;color:white;
                        display:flex;align-items:center;justify-content:center;
                        font-weight:bold;font-size:15px;flex-shrink:0;">{initials}</div>
            <div>
                <b style="font-size:15px;">{row[1]}</b><br>
                <span style="color:#666;font-size:13px;">💼 {row[3]}</span>
            </div>
        </div>
        {company_html}
        {f'<div style="margin-top:8px;">{skills_html}</div>' if skills_html else ""}
        {hidden}
    </div>
    """

def get_conn_status(from_user, to_user):
    c.execute("SELECT status FROM connections WHERE from_user=? AND to_user=?",
              (from_user, to_user))
    row = c.fetchone()
    if row: return row[0]
    c.execute("SELECT status FROM connections WHERE from_user=? AND to_user=?",
              (to_user, from_user))
    row = c.fetchone()
    return row[0] if row else None

def get_unread_count(username):
    c.execute("SELECT COUNT(*) FROM messages WHERE to_user=? AND is_read=0", (username,))
    return c.fetchone()[0]

def get_pending_requests(username):
    c.execute("SELECT from_user FROM connections WHERE to_user=? AND status='pending'",
              (username,))
    return c.fetchall()

# ============================================================
#  SESSION STATE
# ============================================================
for key, default in [("role", None), ("username", None),
                     ("edit_id", None), ("chat_with", None)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ============================================================
#  LOGIN / REGISTER
# ============================================================
if st.session_state.role is None:
    st.markdown("""
    <h1 style='text-align:center;color:#2E86C1;margin-bottom:0;'>🚀 Employee Connect</h1>
    <p style='text-align:center;color:#888;margin-top:4px;'>Connect with the right people</p>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])

    with tab1:
        st.markdown("### Login to your account")
        username_in = st.text_input("Username", key="login_user")
        password_in = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login", use_container_width=True):
            if not username_in.strip() or not password_in.strip():
                st.error("Please enter username and password.")
            else:
                clean_user = username_in.strip()
                c.execute("SELECT role FROM accounts WHERE username=? AND password_hash=?",
                          (clean_user, hash_password(password_in)))
                result = c.fetchone()
                if result:
                    st.session_state.role = result[0]
                    st.session_state.username = clean_user
                    st.success(f"✅ Logged in as **{result[0]}**")
                    st.rerun()
                else:
                    c.execute("SELECT id FROM accounts WHERE username=?", (clean_user,))
                    if c.fetchone():
                        st.error("❌ Wrong password.")
                    else:
                        st.error(f"❌ No account found for '{clean_user}'. Please register first.")

        with st.expander("🔧 Debug — Check registered accounts"):
            c.execute("SELECT username, role FROM accounts")
            for acc in c.fetchall():
                st.write(f"👤 `{acc[0]}` — `{acc[1]}`")
            st.caption(f"DB: `{os.path.abspath('database.db')}`")

    with tab2:
        st.markdown("### Create a new account")
        new_user = st.text_input("Choose Username", key="reg_user")
        new_pw   = st.text_input("Choose Password", type="password", key="reg_pw")
        new_pw2  = st.text_input("Confirm Password", type="password", key="reg_pw2")
        if st.button("Register", use_container_width=True):
            if not new_user.strip() or not new_pw.strip() or not new_pw2.strip():
                st.error("All fields are required.")
            elif new_pw != new_pw2:
                st.error("Passwords do not match.")
            elif len(new_pw) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                try:
                    c.execute(
                        "INSERT INTO accounts (username, password_hash, role) VALUES (?, ?, ?)",
                        (new_user.strip(), hash_password(new_pw), "user")
                    )
                    st.success(f"✅ Account **'{new_user.strip()}'** created! Go to Login tab.")
                except sqlite3.IntegrityError:
                    st.error(f"Username '{new_user.strip()}' already taken.")
                except Exception as ex:
                    st.error(f"❌ Error: {ex}")
    st.stop()

# ============================================================
#  SIDEBAR
# ============================================================
unread    = get_unread_count(st.session_state.username)
pending_r = get_pending_requests(st.session_state.username)

with st.sidebar:
    st.markdown(f"""
    <div style="padding:10px 0;">
        <b style="font-size:15px;">👋 {st.session_state.username}</b><br>
        <span style="color:#888;font-size:13px;">Role: {st.session_state.role}</span>
    </div>
    """, unsafe_allow_html=True)

    if unread > 0:
        st.info(f"💬 **{unread} unread message{'s' if unread>1 else ''}**")
    if pending_r:
        st.warning(f"🔔 **{len(pending_r)} connection request{'s' if len(pending_r)>1 else ''}**")

    st.divider()
    menu_options = ["👥 View Profiles", "➕ Add Profile", "🔍 Search",
                    "💬 Messages", "🤝 My Connections"]
    if st.session_state.role == "admin":
        menu_options.append("⚙️ Admin Panel")
    choice = st.selectbox("Navigate", menu_options)
    st.divider()

    if st.button("🚪 Logout", use_container_width=True):
        for key in ["role", "username", "edit_id", "chat_with"]:
            st.session_state[key] = None
        st.rerun()

# ============================================================
#  HEADER
# ============================================================
st.markdown("""
<h1 style='text-align:center;color:#2E86C1;'>🚀 Employee Connect App</h1>
""", unsafe_allow_html=True)

# ============================================================
#  ADD PROFILE
# ============================================================
if choice == "➕ Add Profile":
    st.subheader("➕ Add Employee Profile")
    with st.form("add_profile_form", clear_on_submit=True):
        name       = st.text_input("Full Name")
        company    = st.text_input("Company")
        role_input = st.text_input("Role / Designation")
        skills     = st.text_input("Skills (comma separated)",
                                   placeholder="e.g. Python, SQL, Streamlit")
        submitted  = st.form_submit_button("💾 Save Profile", use_container_width=True)
    if submitted:
        errors = []
        if not name.strip():       errors.append("Name is required.")
        if not company.strip():    errors.append("Company is required.")
        if not role_input.strip(): errors.append("Role is required.")
        if not skills.strip():     errors.append("Skills are required.")
        if errors:
            for e in errors: st.error(f"❌ {e}")
        else:
            c.execute("INSERT INTO users (name, company, role, skills) VALUES (?, ?, ?, ?)",
                      (name.strip(), company.strip(), role_input.strip(), skills.strip()))
            st.success("✅ Profile saved successfully!")

# ============================================================
#  VIEW PROFILES
# ============================================================
elif choice == "👥 View Profiles":
    st.subheader("👨‍💼 Employee Directory")

    PAGE_SIZE = 6
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    total_pages = max(1, -(-total // PAGE_SIZE))

    cl, cr = st.columns([3, 1])
    with cr:
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
    with cl:
        st.caption(f"Page {page} of {total_pages}  •  {total} profiles")

    offset = (page - 1) * PAGE_SIZE
    c.execute("SELECT * FROM users LIMIT ? OFFSET ?", (PAGE_SIZE, offset))
    data = c.fetchall()
    me = st.session_state.username
    is_admin = st.session_state.role == "admin"

    if data:
        cols = st.columns(2)
        for i, row in enumerate(data):
            with cols[i % 2]:
                st.markdown(profile_card(row, show_full=is_admin), unsafe_allow_html=True)
                is_self = row[1].lower() == me.lower()

                if not is_self:
                    status = get_conn_status(me, row[1])
                    b1, b2 = st.columns(2)
                    with b1:
                        if status is None:
                            if st.button("🤝 Connect", key=f"conn_{row[0]}",
                                         use_container_width=True):
                                try:
                                    c.execute(
                                        "INSERT INTO connections (from_user,to_user,status,created_at) VALUES(?,?,'pending',?)",
                                        (me, row[1], now()))
                                    st.success(f"Request sent to {row[1]}!")
                                    st.rerun()
                                except sqlite3.IntegrityError:
                                    st.warning("Already sent.")
                        elif status == "pending":
                            st.button("⏳ Pending",  key=f"conn_{row[0]}", disabled=True, use_container_width=True)
                        elif status == "accepted":
                            st.button("✅ Connected", key=f"conn_{row[0]}", disabled=True, use_container_width=True)
                        else:
                            st.button("❌ Declined",  key=f"conn_{row[0]}", disabled=True, use_container_width=True)
                    with b2:
                        if st.button("💬 Message", key=f"msg_{row[0]}", use_container_width=True):
                            st.session_state.chat_with = row[1]
                            st.rerun()

                if is_admin:
                    d1, d2 = st.columns(2)
                    with d1:
                        if st.button("✏️ Edit", key=f"edit_{row[0]}"):
                            st.session_state.edit_id = row[0]
                    with d2:
                        if st.button("🗑️ Delete", key=f"del_{row[0]}"):
                            c.execute("DELETE FROM users WHERE id=?", (row[0],))
                            st.success(f"Deleted {row[1]}")
                            st.rerun()

        if st.session_state.edit_id:
            st.divider()
            st.subheader("✏️ Edit Profile")
            c.execute("SELECT * FROM users WHERE id=?", (st.session_state.edit_id,))
            er = c.fetchone()
            if er:
                with st.form("edit_form"):
                    e_name    = st.text_input("Name",    value=er[1])
                    e_company = st.text_input("Company", value=er[2])
                    e_role    = st.text_input("Role",    value=er[3])
                    e_skills  = st.text_input("Skills",  value=er[4])
                    c1, c2 = st.columns(2)
                    save_edit   = c1.form_submit_button("💾 Save", use_container_width=True)
                    cancel_edit = c2.form_submit_button("✖️ Cancel", use_container_width=True)
                if save_edit:
                    errors = []
                    if not e_name.strip():    errors.append("Name required.")
                    if not e_company.strip(): errors.append("Company required.")
                    if not e_role.strip():    errors.append("Role required.")
                    if not e_skills.strip():  errors.append("Skills required.")
                    if errors:
                        for e in errors: st.error(f"❌ {e}")
                    else:
                        c.execute(
                            "UPDATE users SET name=?,company=?,role=?,skills=? WHERE id=?",
                            (e_name.strip(), e_company.strip(),
                             e_role.strip(), e_skills.strip(), st.session_state.edit_id))
                        st.session_state.edit_id = None
                        st.success("✅ Updated!")
                        st.rerun()
                if cancel_edit:
                    st.session_state.edit_id = None
                    st.rerun()
    else:
        st.info("No profiles found.")

    # Quick message compose popup
    if st.session_state.chat_with:
        st.divider()
        target = st.session_state.chat_with
        st.subheader(f"💬 Message to {target}")
        with st.form("quick_msg_form", clear_on_submit=True):
            msg_text = st.text_area("Your message", placeholder=f"Write to {target}...", height=100)
            s1, s2 = st.columns(2)
            send   = s1.form_submit_button("📤 Send",   use_container_width=True)
            cancel = s2.form_submit_button("✖️ Cancel", use_container_width=True)
        if send:
            if not msg_text.strip():
                st.error("Message cannot be empty.")
            else:
                c.execute(
                    "INSERT INTO messages (from_user,to_user,message,is_read,created_at) VALUES(?,?,?,0,?)",
                    (me, target, msg_text.strip(), now()))
                st.session_state.chat_with = None
                st.success(f"✅ Message sent to {target}!")
                st.rerun()
        if cancel:
            st.session_state.chat_with = None
            st.rerun()

    # Recommendations
    st.divider()
    st.subheader("🤖 Recommended Connections")
    c.execute("SELECT * FROM users")
    all_data = c.fetchall()
    if all_data:
        sel_name = st.selectbox("Find connections for", [r[1] for r in all_data])
        sel_user = next((r for r in all_data if r[1] == sel_name), None)
        if sel_user:
            recs = [u for u in all_data if u != sel_user and (
                u[2] == sel_user[2] or u[3] == sel_user[3] or
                any(sk.strip().lower() in [x.strip().lower() for x in u[4].split(",")]
                    for sk in sel_user[4].split(","))
            )]
            if recs:
                rc1, rc2 = st.columns(2)
                for i, r in enumerate(recs):
                    with [rc1, rc2][i % 2]:
                        st.markdown(profile_card(r, show_full=is_admin), unsafe_allow_html=True)
            else:
                st.info("No recommendations found yet.")
    else:
        st.info("Add profiles to see recommendations.")

# ============================================================
#  MESSAGES PAGE
# ============================================================
elif choice == "💬 Messages":
    me = st.session_state.username
    st.subheader("💬 Messages")

    c.execute("""SELECT DISTINCT
                   CASE WHEN from_user=? THEN to_user ELSE from_user END as other
                 FROM messages WHERE from_user=? OR to_user=?
                 ORDER BY other""", (me, me, me))
    conversations = [r[0] for r in c.fetchall()]

    c.execute("SELECT username FROM accounts WHERE username != ?", (me,))
    all_users = [r[0] for r in c.fetchall()]

    left_col, right_col = st.columns([1, 2])

    with left_col:
        st.markdown("**Conversations**")
        new_convo = st.selectbox("＋ Start new chat", ["-- Select --"] + all_users,
                                  key="new_convo")
        if new_convo != "-- Select --":
            if new_convo not in conversations:
                conversations.insert(0, new_convo)
            st.session_state.chat_with = new_convo

        st.markdown("---")
        for person in conversations:
            c.execute("SELECT COUNT(*) FROM messages WHERE from_user=? AND to_user=? AND is_read=0",
                      (person, me))
            unread_from = c.fetchone()[0]
            label = f"🔴 {person} ({unread_from})" if unread_from > 0 else f"💬 {person}"
            if st.button(label, key=f"conv_{person}", use_container_width=True):
                st.session_state.chat_with = person
                st.rerun()

    with right_col:
        chat_with = st.session_state.chat_with
        if chat_with:
            st.markdown(f"**Chat with {chat_with}**")
            st.markdown("---")

            # Mark as read
            c.execute("UPDATE messages SET is_read=1 WHERE from_user=? AND to_user=? AND is_read=0",
                      (chat_with, me))

            # Load history
            c.execute("""SELECT from_user, message, created_at FROM messages
                         WHERE (from_user=? AND to_user=?) OR (from_user=? AND to_user=?)
                         ORDER BY created_at ASC""", (me, chat_with, chat_with, me))
            msgs = c.fetchall()

            chat_html = "<div style='height:380px;overflow-y:auto;padding:10px;background:#f9f9f9;border-radius:12px;border:1px solid #eee;'>"
            if msgs:
                for sender, text, ts in msgs:
                    is_me = sender == me
                    bg    = "#2E86C1" if is_me else "#f0f0f0"
                    fg    = "white"   if is_me else "#333"
                    align = "flex-end" if is_me else "flex-start"
                    label = "You" if is_me else sender
                    chat_html += f"""
                    <div style='display:flex;justify-content:{align};margin:8px 0;'>
                        <div style='max-width:75%;'>
                            <div style='font-size:11px;color:#999;margin-bottom:2px;
                                        text-align:{"right" if is_me else "left"};'>
                                {label} • {ts[11:16]}
                            </div>
                            <div style='background:{bg};color:{fg};padding:10px 14px;
                                        border-radius:16px;font-size:14px;line-height:1.5;
                                        border-bottom-{"right" if is_me else "left"}-radius:4px;'>
                                {text}
                            </div>
                        </div>
                    </div>"""
            else:
                chat_html += "<p style='text-align:center;color:#aaa;margin-top:60px;'>No messages yet. Say hello! 👋</p>"
            chat_html += "</div>"
            st.markdown(chat_html, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("send_msg_form", clear_on_submit=True):
                msg_input = st.text_input("Type a message...", label_visibility="collapsed",
                                          placeholder=f"Message {chat_with}...")
                if st.form_submit_button("📤 Send", use_container_width=True):
                    if msg_input.strip():
                        c.execute(
                            "INSERT INTO messages (from_user,to_user,message,is_read,created_at) VALUES(?,?,?,0,?)",
                            (me, chat_with, msg_input.strip(), now()))
                        st.rerun()
        else:
            st.markdown("""
            <div style='text-align:center;padding:80px 20px;color:#aaa;'>
                <div style='font-size:48px;'>💬</div>
                <p style='font-size:16px;margin-top:16px;'>Select a conversation or start a new one</p>
            </div>""", unsafe_allow_html=True)

# ============================================================
#  MY CONNECTIONS PAGE
# ============================================================
elif choice == "🤝 My Connections":
    me = st.session_state.username
    st.subheader("🤝 My Connections")

    tab_pending, tab_accepted, tab_sent = st.tabs([
        "🔔 Requests Received", "✅ Connected", "📤 Sent Requests"
    ])

    with tab_pending:
        c.execute("SELECT from_user, created_at FROM connections WHERE to_user=? AND status='pending'",
                  (me,))
        pending = c.fetchall()
        if pending:
            st.caption(f"{len(pending)} pending request(s)")
            for from_user, created_at in pending:
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.markdown(f"**👤 {from_user}**  \n*{created_at[:10]}*")
                with col2:
                    if st.button("✅ Accept", key=f"acc_{from_user}", use_container_width=True):
                        c.execute("UPDATE connections SET status='accepted' WHERE from_user=? AND to_user=?",
                                  (from_user, me))
                        st.success(f"Connected with {from_user}!")
                        st.rerun()
                with col3:
                    if st.button("❌ Decline", key=f"dec_{from_user}", use_container_width=True):
                        c.execute("UPDATE connections SET status='rejected' WHERE from_user=? AND to_user=?",
                                  (from_user, me))
                        st.info(f"Declined {from_user}.")
                        st.rerun()
                st.markdown("---")
        else:
            st.info("No pending requests.")

    with tab_accepted:
        c.execute("""SELECT CASE WHEN from_user=? THEN to_user ELSE from_user END as friend,
                            created_at
                     FROM connections
                     WHERE (from_user=? OR to_user=?) AND status='accepted'""",
                  (me, me, me))
        accepted = c.fetchall()
        if accepted:
            st.caption(f"{len(accepted)} connection(s)")
            cols = st.columns(2)
            for i, (friend, created_at) in enumerate(accepted):
                with cols[i % 2]:
                    st.markdown(f"""
                    <div style="border:1px solid #e0e0e0;border-radius:12px;
                                padding:14px;margin:6px 0;background:#fff;">
                        <b>👤 {friend}</b><br>
                        <span style="color:#aaa;font-size:12px;">Connected since {created_at[:10]}</span>
                    </div>""", unsafe_allow_html=True)
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("💬 Message", key=f"msgconn_{friend}", use_container_width=True):
                            st.session_state.chat_with = friend
                            st.rerun()
                    with b2:
                        if st.button("🔗 Remove", key=f"rem_{friend}", use_container_width=True):
                            c.execute("""DELETE FROM connections
                                         WHERE (from_user=? AND to_user=?)
                                            OR (from_user=? AND to_user=?)""",
                                      (me, friend, friend, me))
                            st.success(f"Removed {friend}.")
                            st.rerun()
        else:
            st.info("No connections yet. Go to View Profiles and connect!")

    with tab_sent:
        c.execute("SELECT to_user, status, created_at FROM connections WHERE from_user=?", (me,))
        sent = c.fetchall()
        if sent:
            for to_user, status, created_at in sent:
                badge = {"pending": "⏳ Pending", "accepted": "✅ Accepted",
                         "rejected": "❌ Declined"}.get(status, status)
                col1, col2 = st.columns([3, 1])
                col1.markdown(f"**👤 {to_user}**  \n*Sent: {created_at[:10]}*")
                col2.markdown(badge)
                if status in ("rejected", "accepted"):
                    if st.button("🗑️ Remove", key=f"remsent_{to_user}"):
                        c.execute("DELETE FROM connections WHERE from_user=? AND to_user=?",
                                  (me, to_user))
                        st.rerun()
                st.markdown("---")
        else:
            st.info("No sent requests yet.")

# ============================================================
#  SEARCH
# ============================================================
elif choice == "🔍 Search":
    me = st.session_state.username
    is_admin = st.session_state.role == "admin"
    st.subheader("🔍 Search Employees")
    search = st.text_input("Search by name / skill / company / role",
                           placeholder="e.g. Python, Data Analyst, Google")
    if search.strip():
        term = f"%{search.strip()}%"
        c.execute("SELECT * FROM users WHERE name LIKE ? OR company LIKE ? OR role LIKE ? OR skills LIKE ?",
                  (term, term, term, term))
        results = c.fetchall()
        st.caption(f"{len(results)} result(s) found")
        if results:
            r1, r2 = st.columns(2)
            for i, row in enumerate(results):
                with [r1, r2][i % 2]:
                    st.markdown(profile_card(row, show_full=is_admin), unsafe_allow_html=True)
                    if row[1].lower() != me.lower():
                        status = get_conn_status(me, row[1])
                        b1, b2 = st.columns(2)
                        with b1:
                            if status is None:
                                if st.button("🤝 Connect", key=f"srconn_{row[0]}", use_container_width=True):
                                    try:
                                        c.execute(
                                            "INSERT INTO connections (from_user,to_user,status,created_at) VALUES(?,?,'pending',?)",
                                            (me, row[1], now()))
                                        st.success("Request sent!")
                                        st.rerun()
                                    except sqlite3.IntegrityError:
                                        st.warning("Already sent.")
                            elif status == "pending":
                                st.button("⏳ Pending",  key=f"srconn_{row[0]}", disabled=True, use_container_width=True)
                            elif status == "accepted":
                                st.button("✅ Connected", key=f"srconn_{row[0]}", disabled=True, use_container_width=True)
                            else:
                                st.button("❌ Declined",  key=f"srconn_{row[0]}", disabled=True, use_container_width=True)
                        with b2:
                            if st.button("💬 Message", key=f"srmsg_{row[0]}", use_container_width=True):
                                st.session_state.chat_with = row[1]
                                st.rerun()
        else:
            st.warning("No results found.")
    else:
        st.info("Type something above to search.")

# ============================================================
#  ADMIN PANEL
# ============================================================
elif choice == "⚙️ Admin Panel" and st.session_state.role == "admin":
    st.subheader("⚙️ Admin Panel")

    c.execute("SELECT COUNT(*) FROM users")
    tp = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM accounts")
    ta = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM accounts WHERE role='admin'")
    tadm = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM connections WHERE status='accepted'")
    tc = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM messages")
    tm = c.fetchone()[0]

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("👥 Profiles",    tp)
    m2.metric("🔐 Accounts",    ta)
    m3.metric("🛡️ Admins",      tadm)
    m4.metric("🤝 Connections", tc)
    m5.metric("💬 Messages",    tm)

    st.divider()
    st.markdown("### 🔐 All Accounts")
    c.execute("SELECT id, username, role FROM accounts")
    for acc in c.fetchall():
        a1, a2, a3 = st.columns([3, 2, 1])
        a1.write(f"👤 **{acc[1]}**")
        a2.write(f"Role: `{acc[2]}`")
        if acc[1] != st.session_state.username:
            if a3.button("🗑️", key=f"delacc_{acc[0]}"):
                c.execute("DELETE FROM accounts WHERE id=?", (acc[0],))
                st.success(f"Deleted '{acc[1]}'.")
                st.rerun()
        else:
            a3.write("*(you)*")

    st.divider()
    st.markdown("### 🛡️ Promote User to Admin")
    c.execute("SELECT username FROM accounts WHERE role='user'")
    reg_users = [r[0] for r in c.fetchall()]
    if reg_users:
        promote_name = st.selectbox("Select user", reg_users)
        if st.button("⬆️ Promote to Admin"):
            c.execute("UPDATE accounts SET role='admin' WHERE username=?", (promote_name,))
            st.success(f"✅ {promote_name} is now an admin!")
            st.rerun()
    else:
        st.info("No regular users to promote.")
