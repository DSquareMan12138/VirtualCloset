"""Run with: python -m streamlit run app.py"""
import json
import io
import logging
import math
import time
import uuid
import streamlit as st
from PIL import ImageOps
from virtual_closet import database as db
from virtual_closet.attributes import CATEGORIES
from virtual_closet.brands import BRANDS
from virtual_closet.images import read_image, image_hash, remove_background, display_image
from virtual_closet.metadata import automatic_name, clean_brand, reviewed_attributes
from virtual_closet.recommendation import OCCASIONS, recommend, signature

st.set_page_config(page_title="VirtualCloset", page_icon="👕", layout="wide")
st.markdown("""<style>
.block-container {max-width:1180px;padding-top:2rem;}
div[data-testid="stImage"] img {border-radius:12px;}
.item-name {overflow-wrap:anywhere;white-space:normal;}
</style>""", unsafe_allow_html=True)

@st.cache_resource(show_spinner="Preparing clothing recognition…")
def get_model():
    from virtual_closet.model import FashionModel
    return FashionModel()

def preview_bytes(raw, background, size=420, square=False):
    """Cache bounded, display-sized previews in this user's session."""
    cache = st.session_state.setdefault("_photo_previews", {})
    key = (image_hash(raw), background, size, square)
    if key in cache:
        return cache[key]
    photo = display_image(raw, background)
    if square:
        photo = ImageOps.pad(photo, (size, size), color=background)
    else:
        photo.thumbnail((size, size))
    buffer = io.BytesIO()
    photo.save(buffer, format="JPEG", quality=88)
    result = buffer.getvalue()
    if len(cache) >= 128:
        del cache[next(iter(cache))]
    cache[key] = result
    return result

def reset_session(user=None):
    st.session_state.clear()
    if user:
        st.session_state["user"] = user

def clear_selection():
    for key in list(st.session_state):
        if key.startswith("select_"):
            del st.session_state[key]
    st.session_state.pop("remove_confirmation", None)

def choose_category(value):
    st.session_state["closet_category"] = value
    clear_selection()

def mark_manual(prefix):
    st.session_state[prefix + "manual"] = True

def cancel_rename(item_id, name):
    st.session_state[f"rename_input_{item_id}"] = name

def review_values(entry):
    p = entry["prefix"]
    category = st.session_state.get(p + "category", entry["result"]["attributes"]["Category"])
    if category == "Other":
        category = st.session_state.get(p + "custom_category", "")
    attrs = reviewed_attributes(entry["result"]["attributes"], category)
    brand = st.session_state.get(p + "brand")
    if brand == "Other":
        brand = st.session_state.get(p + "custom_brand", "")
    return attrs, clean_brand(brand)

def sync_name(entry):
    p = entry["prefix"]
    if not st.session_state.get(p + "manual", False):
        attrs, brand = review_values(entry)
        st.session_state[p + "name"] = automatic_name(attrs, brand)

def save_review(uid):
    added = skipped = 0
    failures, remaining = [], []
    for entry in st.session_state.get("review", []):
        try:
            attrs, brand = review_values(entry)
            result = dict(entry["result"], attributes=attrs)
            ok = db.save_item(uid, entry["filename"], entry["digest"], entry["original"],
                              result, name=st.session_state.get(entry["prefix"] + "name"),
                              brand=brand, cutout_data=entry["cutout"], reviewed=True)
            added += ok
            skipped += not ok
        except Exception as exc:
            logging.exception("Saving reviewed item failed")
            failures.append(f'{entry["filename"]}: {exc}')
            remaining.append(entry)
    st.session_state["review"] = remaining
    st.session_state["failures"] = failures
    st.session_state["notice"] = f"Added {added} item(s). Skipped {skipped} duplicate(s)."
    st.session_state.pop("outfits", None)
    if not remaining:
        st.session_state["upload_version"] = st.session_state.get("upload_version", 0) + 1

def analyze_files(uid, files):
    batch, failures, seen = [], [], set()
    skipped = 0
    progress = st.progress(0)
    for index, file in enumerate(files):
        try:
            raw = file.getvalue()
            digest = image_hash(raw)
            if digest in seen or db.exists(uid, digest):
                skipped += 1
                continue
            seen.add(digest)
            # Required order: segmentation first, then recognition on a white composite.
            cutout = remove_background(raw)
            result = get_model().analyze(read_image(cutout))
            batch.append({"prefix": "review_" + uuid.uuid4().hex + "_",
                          "filename": file.name, "digest": digest, "original": raw,
                          "cutout": cutout, "result": result})
        except Exception as exc:
            logging.exception("Analyzing upload failed")
            failures.append(f"{file.name}: {exc}")
        finally:
            progress.progress((index + 1) / len(files))
    progress.empty()
    st.session_state["review"] = batch
    st.session_state["failures"] = failures
    if skipped:
        st.session_state["notice"] = f"Skipped {skipped} duplicate image(s)."
    st.rerun()

try:
    if not st.session_state.get("_database_ready"):
        db.initialize()
        st.session_state["_database_ready"] = True
except Exception as exc:
    st.error(f'Could not open your closet database: {exc}')
    st.stop()

if 'user' not in st.session_state:
    st.caption('YOUR WARDROBE, SIMPLIFIED')
    st.title('A little less “what do I wear?”')
    st.write('Keep your clothes in one place. Find an outfit for your day.')
    login_tab, signup_tab = st.tabs(['Log in','Create account'])
    with login_tab:
        with st.form('login'):
            username = st.text_input('Username')
            password = st.text_input('Password',type='password')
            submitted = st.form_submit_button('Log in',type='primary')
        if submitted:
            remaining = st.session_state.get('locked_until',0)-time.time()
            if remaining > 0:
                st.error(f'Too many attempts. Try again in {int(remaining)+1} seconds.')
            else:
                user = db.login(username,password)
                if user:
                    reset_session(user)
                    st.rerun()
                else:
                    attempts = st.session_state.get('login_attempts',0)+1
                    st.session_state['login_attempts'] = attempts
                    if attempts >= 5:
                        st.session_state['locked_until'] = time.time()+30
                        st.session_state['login_attempts'] = 0
                    st.error('Incorrect username or password.')
    with signup_tab:
        st.caption('Use 3–32 letters, numbers or underscores for your username; 10–128 characters for your password.')
        with st.form('signup'):
            username = st.text_input('Choose a username')
            password = st.text_input('Choose a password',type='password')
            confirmation = st.text_input('Repeat password',type='password')
            submitted = st.form_submit_button('Create my closet',type='primary')
        if submitted:
            if password != confirmation:
                st.error('Passwords do not match.')
            else:
                try:
                    user = db.register(username,password)
                    reset_session(user)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    logging.exception('Registration failed')
                    st.error('Account creation failed. Check the terminal for details.')
    st.caption('Local demonstration · Accounts are stored on this computer. Refreshing the page may require signing in again.')
    st.stop()


user = st.session_state["user"]
uid = user["id"]
with st.sidebar:
    st.title("VirtualCloset")
    st.write(f'Signed in as {user["username"]}')
    stored_color = db.get_background(uid)
    background = st.color_picker("Photo background", stored_color, key="theme_color")
    if background != stored_color:
        db.set_background(uid, background)
    if st.button("Log out"):
        reset_session()
        st.rerun()

st.title("VirtualCloset")
items = db.list_items(uid)
st.caption(f"{len(items)} pieces in your closet")
with st.container(key="notifications"):
    if "notice" in st.session_state:
        st.success(st.session_state.pop("notice"))
    for failure in st.session_state.get("failures", []):
        st.error(failure)
# Stable key and render position preserve the selected browser tab.
# Switching tabs is client-side: no database reads or image rendering reruns.
today, closet, upload = st.tabs(
    ["Today's outfit", "My closet", "Add clothes"],
    key="main_tabs",
    on_change="ignore",
)

with upload:
    st.subheader("Add clothes")
    files = st.file_uploader("Choose photos", type=["jpg", "jpeg", "png", "webp"],
                             accept_multiple_files=True,
                             key=f'upload_{st.session_state.get("upload_version", 0)}')
    st.caption("One garment per photo. Up to 20 MB and 24 megapixels per image.")
    review = st.session_state.get("review", [])
    if st.button("Analyze photos", disabled=not files or bool(review), type="primary"):
        analyze_files(uid, files)
    if review:
        st.caption("Review the cutouts and details. Nothing is added until you choose Add to closet.")
        st.button("Add to closet", key="add_top", type="primary", on_click=save_review, args=(uid,))
        for entry in review:
            p = entry["prefix"]
            attrs, brand = review_values(entry)
            if p + "name" not in st.session_state:
                st.session_state[p + "name"] = automatic_name(attrs, brand)
            left, right = st.columns([1, 2])
            with left:
                st.image(preview_bytes(entry["cutout"], background), width="stretch")
            with right:
                st.text_input("Name", key=p + "name", on_change=mark_manual, args=(p,))
                st.selectbox("Brand", ["Other"] + BRANDS, index=None,
                             placeholder="Select brand (optional)", key=p + "brand",
                             on_change=sync_name, args=(entry,))
                if st.session_state.get(p + "brand") == "Other":
                    st.text_input("Enter brand", key=p + "custom_brand",
                                  on_change=sync_name, args=(entry,))
                options = ["Other"] + sorted(CATEGORIES, key=str.casefold)
                predicted = entry["result"]["attributes"]["Category"]
                st.selectbox("Category", options,
                             index=options.index(predicted) if predicted in options else 0,
                             key=p + "category", on_change=sync_name, args=(entry,))
                if st.session_state.get(p + "category") == "Other":
                    st.text_input("Enter category", key=p + "custom_category",
                                  on_change=sync_name, args=(entry,))
            st.divider()
        st.button("Add to closet", key="add_bottom", type="primary", on_click=save_review, args=(uid,))
        if st.button("Discard this review"):
            st.session_state["review"] = []
            st.rerun()

with closet:
    st.subheader("My closet")
    attrs_by_id = {i["id"]: json.loads(i["attributes_json"]) for i in items}
    categories = {a.get("Category") or "Uncategorized" for a in attrs_by_id.values()}
    # None is the All filter, so a custom category named "All" still works.
    options = [None] + sorted(categories - {"Uncategorized"}, key=str.casefold)
    if "Uncategorized" in categories:
        options.append("Uncategorized")
    current = st.session_state.get("closet_category")
    if current not in options:
        current = None
        choose_category(None)
    # Flex rows wrap once and split evenly; buttons retain the native callbacks.
    split = math.ceil(len(options) / 2) if len(options) > 6 else len(options)
    for row in (options[:split], options[split:]):
        if row:
            cols = st.columns(len(row))
            for col, category in zip(cols, row):
                col.button("All" if category is None else category,
                           key="category_" + ("__all__" if category is None else category),
                           type="primary" if category == current else "secondary",
                           on_click=choose_category, args=(category,), width="stretch")
    visible = [i for i in items if current is None or
               (attrs_by_id[i["id"]].get("Category") or "Uncategorized") == current]
    a, b = st.columns(2)
    if a.button("Select all in this category", disabled=not visible):
        for item in visible:
            st.session_state[f'select_{item["id"]}'] = True
        st.session_state.pop("remove_confirmation", None)
    if b.button("Clear selection"):
        clear_selection()
    selected = [i["id"] for i in visible if st.session_state.get(f'select_{i["id"]}', False)]
    if st.button(f"Remove selected ({len(selected)})", disabled=not selected):
        st.session_state["remove_confirmation"] = tuple(selected)
    confirm = st.session_state.get("remove_confirmation")
    if confirm is not None:
        if tuple(selected) != confirm:
            st.session_state.pop("remove_confirmation", None)
        else:
            st.warning(f"Remove {len(confirm)} selected item(s) permanently?")
            yes, no = st.columns(2)
            if yes.button("Confirm removal", type="primary"):
                count = db.delete_items(uid, confirm)
                clear_selection()
                st.session_state.pop("outfits", None)
                st.session_state["notice"] = f"Removed {count} item(s)."
                st.rerun()
            if no.button("Cancel removal"):
                st.session_state.pop("remove_confirmation", None)
                st.rerun()
    missing = [i for i in items if not i.get("cutout_data")]
    if missing:
        st.info(f"{len(missing)} existing photo(s) still have their original backgrounds.")
        if st.button("Remove backgrounds from existing clothes"):
            failures = []
            with st.spinner("Removing backgrounds…"):
                for item in missing:
                    try:
                        db.set_cutout(uid, item["id"], remove_background(item["image_data"]))
                    except Exception as exc:
                        failures.append(f'{item["display_name"]}: {exc}')
            st.session_state["failures"] = failures
            st.rerun()
    if not visible:
        st.info("No clothes in this category yet.")
    for start in range(0, len(visible), 4):
        for col, item in zip(st.columns(4), visible[start:start+4]):
            with col:
                st.image(preview_bytes(item.get("cutout_data") or item["image_data"], background),
                         width="stretch")
                st.text(item["display_name"])
                st.caption(item.get("brand") or "Unknown / No brand")
                st.checkbox("Select", key=f'select_{item["id"]}')
                with st.expander("Rename"):
                    with st.form(f'rename_{item["id"]}'):
                        name = st.text_input("New name", value=item["display_name"], key=f'rename_input_{item["id"]}')
                        save = st.form_submit_button("Save")
                        cancel = st.form_submit_button("Cancel", on_click=cancel_rename,
                                                       args=(item["id"], item["display_name"]))
                    if save:
                        try:
                            db.rename_item(uid, item["id"], name)
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                    if cancel:
                        st.rerun()

with today:
    st.subheader("Outfits for your day")
    occasion = st.selectbox("Occasion", list(OCCASIONS))
    mood = st.text_input("Mood or style (optional)", placeholder="Relaxed, minimalist, colorful…")
    layer = st.checkbox("Include a jacket or coat")
    context = (occasion, mood.strip(), layer, tuple(i["id"] for i in items))
    if st.session_state.get("outfit_context") != context:
        st.session_state["outfit_context"] = context
        st.session_state.pop("outfits", None)
        st.session_state["variant"] = 0
    left, right = st.columns(2)
    generate = left.button("Suggest outfits", type="primary", disabled=not items)
    refresh = right.button("Refresh", disabled=not items or not st.session_state.get("outfits"))
    if generate or refresh:
        try:
            with st.spinner("Finding combinations…"):
                model = get_model()
                for item in items:
                    if not item.get("embedding_json"):
                        cutout = item.get("cutout_data") or remove_background(item["image_data"])
                        result = model.analyze(read_image(cutout))
                        db.update_analysis(uid, item["id"], result)
                        if not item.get("cutout_data"):
                            db.set_cutout(uid, item["id"], cutout)
                items = db.list_items(uid)
                query = OCCASIONS[occasion] + (f", {mood.strip()}" if mood.strip() else "")
                scores = model.occasion_scores(items, query)
                previous = st.session_state.get("outfits", [])
                st.session_state["variant"] = st.session_state.get("variant", 0) + 1
                outfits, notes = recommend(items, scores, layer,
                    variant=st.session_state["variant"],
                    exclude=[signature(o) for o in previous])
                # Store IDs so renames, deletions and cutouts never leave stale cards.
                st.session_state["outfits"] = [[{"id": i["id"]} for i in o] for o in outfits]
                st.session_state["outfit_notes"] = notes
        except Exception as exc:
            logging.exception("Recommendation failed")
            st.error(f"Could not generate outfits: {exc}")
    if not items:
        st.info("Add clothes to get started.")
    for note in st.session_state.get("outfit_notes", []) if st.session_state.get("outfits") is not None else []:
        st.info(note)
    lookup = {i["id"]: i for i in items}
    outfits = st.session_state.get("outfits", [])
    if outfits:
        for n, outfit in enumerate(outfits, 1):
            with st.container(border=True):
                st.subheader(f"Outfit {n}")
                outfit_items = [lookup[ref["id"]] for ref in outfit if ref["id"] in lookup]
                columns = st.columns(max(4, len(outfit_items)))
                for col, item in zip(columns, outfit_items):
                    with col:
                        photo = preview_bytes(item.get("cutout_data") or item["image_data"],
                                              background, size=180, square=True)
                        st.image(photo, width=180)
                        st.text(item["display_name"])
                        st.caption(item.get("brand") or "Unknown / No brand")

