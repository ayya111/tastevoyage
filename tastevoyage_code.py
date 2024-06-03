import streamlit as st
import pandas as pd
import bcrypt
from github import Github
import io
from PIL import Image, UnidentifiedImageError
import requests
from io import BytesIO
import matplotlib.pyplot as plt
import json

# Constants for file paths and GitHub
DATA_FILE_MAIN = "Getränke.csv"
BENUTZER_DATEN_PFAD = 'users.csv'
GITHUB_REPO = st.secrets["github"]["repo"]
GITHUB_OWNER = st.secrets["github"]["owner"]
GITHUB_TOKEN = st.secrets["github"]["token"]

# GitHub Initialization using secrets
gh = Github(GITHUB_TOKEN)
repo = gh.get_repo(f"{GITHUB_OWNER}/{GITHUB_REPO}")

# Set global style
st.markdown("""
    <style>
    body {
        font-family: 'Cascadia Mono', monospace;
        background-color: #f5f5f5;
    }
    .sidebar .sidebar-content {
        background-color: #FAD6A5;
    }
    </style>
    """, unsafe_allow_html=True)

def sidebar_button():
    st.sidebar.markdown("""
    <style>
    .css-1y4p8pa {
        display: flex;
        justify-content: center;
        align-items: center;
    }
    .css-1y4p8pa > button {
        font-size: 20px;
        padding: 10px 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    if st.sidebar.button("☰ Dashboard"):
        st.session_state['menu_open'] = not st.session_state.get('menu_open', False)
        st.experimental_rerun()

def read_github_file(file_path):
    try:
        file_content = repo.get_contents(file_path)
        df = pd.read_csv(io.StringIO(file_content.decoded_content.decode()))
        return df
    except Exception as e:
        st.error(f"Error reading file from GitHub: {e}")
        return pd.DataFrame()

def write_github_file(file_path, df, commit_message="update file"):
    try:
        file_content = repo.get_contents(file_path)
        repo.update_file(file_content.path, commit_message, df.to_csv(index=False), file_content.sha)
    except Exception as e:
        try:
            repo.create_file(file_path, commit_message, df.to_csv(index=False))
        except Exception as e:
            st.error(f"Error writing file to GitHub: {e}")

def delete_image_from_github(image_url):
    try:
        image_filename = image_url.split('/')[-1]
        file_content = repo.get_contents(f"images/{image_filename}")
        repo.delete_file(f"images/{image_filename}", "Delete image", file_content.sha)
    except Exception as e:
        st.error(f"Error deleting image from GitHub: {e}")

# Load or initialize the user data
benutzer_df = read_github_file(BENUTZER_DATEN_PFAD)
if benutzer_df.empty:
    benutzer_df = pd.DataFrame(columns=['username', 'password', 'Category', 'favorits', 'edits', 'statistik', 'added_beverages'])
benutzer_df = benutzer_df.fillna({'favorits': '{}', 'edits': '{}', 'statistik': '{}', 'added_beverages': '{}'})

# Load the main data file
df = read_github_file(DATA_FILE_MAIN)
if df.empty:
    df = pd.DataFrame(columns=['Name', 'Image URL', 'Description', 'Category'])

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf8'), bcrypt.gensalt()).decode('utf8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf8'), hashed.encode('utf8'))

def verify_login(username, password, benutzer_df):
    user_info = benutzer_df[benutzer_df['username'] == username]
    if not user_info.empty and check_password(password, user_info.iloc[0]['password']):
        return True
    return False

def register_user(username, password, benutzer_df):
    if username not in benutzer_df['username'].values:
        hashed_password = hash_password(password)
        new_user_data = {'username': username, 'password': hashed_password, 'Category': '', 'favorits': '{}', 'edits': '{}', 'statistik': '{}', 'added_beverages': '{}'}
        benutzer_df = pd.concat([benutzer_df, pd.DataFrame([new_user_data])], ignore_index=True)
        write_github_file(BENUTZER_DATEN_PFAD, benutzer_df, "Register new user")
        return True
    return False

def save_user_data(username, benutzer_df):
    user_info = benutzer_df[benutzer_df['username'] == username].iloc[0]
    favorits = json.dumps(st.session_state.get('favorits', {}))
    edits = json.dumps(st.session_state.get('edits', {}))
    statistik = json.dumps(st.session_state.get('statistik', {}))
    added_beverages = json.dumps(st.session_state.get('added_beverages', {}))
    
    benutzer_df.loc[benutzer_df['username'] == username, 'favorits'] = favorits
    benutzer_df.loc[benutzer_df['username'] == username, 'edits'] = edits
    benutzer_df.loc[benutzer_df['username'] == username, 'statistik'] = statistik
    benutzer_df.loc[benutzer_df['username'] == username, 'added_beverages'] = added_beverages
    write_github_file(BENUTZER_DATEN_PFAD, benutzer_df)

def load_user_data(username, benutzer_df):
    user_info = benutzer_df[benutzer_df['username'] == username].iloc[0]
    st.session_state['favorits'] = json.loads(user_info['favorits'] if pd.notna(user_info['favorits']) else '{}')
    st.session_state['edits'] = json.loads(user_info['edits'] if pd.notna(user_info['edits']) else '{}')
    st.session_state['statistik'] = json.loads(user_info['statistik'] if pd.notna(user_info['statistik']) else '{}')
    st.session_state['added_beverages'] = json.loads(user_info['added_beverages'] if pd.notna(user_info['added_beverages']) else '{}')

def save_or_update(df, path=DATA_FILE_MAIN):
    write_github_file(path, df)

def save_image_to_github(image, name):
    if image is not None:
        image_filename = f"{name}_{image.name}"
        content = image.read()
        repo.create_file(f"images/{image_filename}", f"Upload {image_filename}", content)
        return f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main/images/{image_filename}"
    return ""

def main_app():
    sidebar_button()
    if 'menu_choice' not in st.session_state:
        st.session_state['menu_choice'] = 'Start'

    category_filter = st.sidebar.selectbox("Kategorie wählen", ["Alle"] + sorted(list(df['Category'].unique()), key=lambda x: (x == 'Other', x)))
    search_query = st.sidebar.text_input("Suche")
    
    choice = st.sidebar.radio("Menü:", ["Start", "Hauptmenü", "Favoriten", "Getränk hinzufügen", "Statistiken"], key='menu_choice')

    filtered_df = df.copy()
    if category_filter != "Alle":
        filtered_df = filtered_df[filtered_df['Category'] == category_filter]
    
    if search_query:
        filtered_df = filtered_df[filtered_df['Name'].str.contains(search_query, case=False)]

    user_favoriten = st.session_state.get('favorits', {})
    user_edits = st.session_state.get('edits', {})
    user_added_beverages = st.session_state.get('added_beverages', {})

    # Filter user added beverages for search query
    if search_query:
        user_added_beverages = {k: v for k, v in user_added_beverages.items() if search_query.lower() in v['Name'].lower()}

    if choice == "Start":
        start_page()
    elif choice == "Hauptmenü":
        main_menu(filtered_df, user_favoriten, user_edits, user_added_beverages)
    elif choice == "Favoriten":
        favorites_page(user_favoriten, user_edits)
    elif choice == "Getränk hinzufügen":
        add_beverage_form(user_added_beverages)
    elif choice == "Statistiken":
        statistics_page(df, user_added_beverages)

def start_page():
    st.title(f"Willkommen {st.session_state['username']} bei TasteVoyage!")
    st.markdown("""
        ### TasteVoyage
        TasteVoyage ist die ultimative App für alle Getränke-Enthusiasten. Entdecke eine vielfältige Auswahl an Getränken, bewerte sie und erstelle eine persönliche Liste deiner Favoriten. Unsere App bietet detaillierte Informationen zu jedem Getränk, das du selbst erstellen kannst. Darüber hinaus ermöglicht sie das Hochladen neuer Getränke und präsentiert statistische Auswertungen basierend auf deinen Bewertungen.

        #### Hauptfunktionen:
        - 🗂 Hauptmenü: Durchstöbere eine umfassende Liste von Getränken, von denen einige bereits vorgegeben sind, um dir den Einstieg zu erleichtern.
        - ⭐  Favoriten: Verwalte und greife einfach auf deine Lieblingsgetränke zu, ohne das Hauptmenü durchsuchen zu müssen.
        - ➕ Getränk hinzufügen: Füge neue Getränke zur Datenbank hinzu, einschließlich Bildern, um die visuelle Attraktivität und Wiedererkennung jedes Getränks zu erhöhen.
        - 📊 Statistiken: Sieh dir detaillierte statistische Auswertungen der Getränkebewertungen an, kategorisiert und in Balkendiagrammen dargestellt, die die am besten bewerteten Getränke in jeder Kategorie hervorheben.
        - 🔒 Benutzerspezifische Daten: Alle Daten werden auf GitHub gespeichert, wodurch jeder Benutzer eine personalisierte Erfahrung mit sicherem Zugriff auf seine Informationen beim Einloggen hat.

        ##### Tauche ein in die Welt der Getränke und beginne noch heute deine Geschmacksreise mit TasteVoyage! 🌍
    """)

def main_menu(filtered_df, user_favoriten, user_edits, user_added_beverages):
    st.title("🗂 Hauptmenü")
    st.markdown("Durchstöbere die umfassende Liste der verfügbaren Getränke.")
    combined_df = pd.concat([filtered_df, pd.DataFrame(user_added_beverages).T])
    if not combined_df.empty:
        for i in range(0, len(combined_df), 2):
            cols = st.columns(2)
            for idx in range(2):
                if i + idx < len(combined_df):
                    with cols[idx]:
                        show_item(combined_df.iloc[i + idx], i + idx, combined_df, user_favoriten=user_favoriten, user_edits=user_edits, user_added_beverages=user_added_beverages, show_favorite_action=True)

def favorites_page(user_favoriten, user_edits):
    st.title("Favoriten ⭐ ")
    st.markdown("Verwalte und greife einfach auf deine Lieblingsgetränke zu.")
    if user_favoriten:
        favoriten_df = pd.DataFrame(user_favoriten).T
        for i in range(0, len(favoriten_df), 2):
            cols = st.columns(2)
            for idx in range(2):
                if i + idx < len(favoriten_df):
                    with cols[idx]:
                        show_item(favoriten_df.iloc[i + idx], i + idx, favoriten_df, user_edits=user_edits, show_favorite_action=False)

def show_item(item, index, df, user_favoriten=None, user_edits=None, user_added_beverages=None, show_favorite_action=True):
    st.markdown(f"###  {item['Name']}")
    try:
        if 'Image URL' in item and item['Image URL']:
            response = requests.get(item['Image URL'])
            try:
                img = Image.open(BytesIO(response.content))
                img = resize_image(img)
                st.image(img, caption=item['Name'])
            except UnidentifiedImageError:
                st.write("Bild konnte nicht identifiziert oder geladen werden")
        else:
            st.write("Kein Bild verfügbar")
    except FileNotFoundError:
        st.write("Bild nicht gefunden")
    if 'Description' in item:
        st.write(f"Beschreibung: {item['Description']}")
    else:
        st.write("Beschreibung: Keine Beschreibung verfügbar")
    
    if user_favoriten and item['Name'] in user_favoriten:
        st.markdown(f"<span style='color:green;'>Dieses Getränk ist in deinen Favoriten</span>", unsafe_allow_html=True)
    
    rating_key = f"rating_{item['Name']}"
    current_rating = user_edits.get(item['Name'], None)
    if current_rating:
        st.markdown(f"Deine Bewertung: {'⭐' * current_rating} ({current_rating}/5)", unsafe_allow_html=True)
    
    options = ["Aktion wählen", "Produkt bewerten"]
    if show_favorite_action:
        options.append("Zu Favoriten hinzufügen")
    if show_favorite_action and user_favoriten and item['Name'] in user_favoriten:
        options.append("Aus Favoriten entfernen")
    if user_added_beverages and item['Name'] in user_added_beverages:
        options.append("Dieses Getränk löschen")

    option = st.selectbox("Optionen:", options, key=f"options_{index}")
    if option == "Produkt bewerten":
        new_rating = st.slider("Bewertung von 1 bis 5", 1, 5, key=rating_key, value=current_rating if current_rating else 1)
        if st.button("Bewertung speichern", key=f"save_{index}"):
            user_edits[item['Name']] = new_rating
            save_user_data(st.session_state['username'], benutzer_df)
            st.success("Bewertung erfolgreich aktualisiert!")
            st.experimental_rerun()
    elif option == "Aus Favoriten entfernen" and user_favoriten:
        del user_favoriten[item['Name']]
        st.success(f"{item['Name']} aus den Favoriten entfernt!")
        st.experimental_rerun()
    elif option == "Zu Favoriten hinzufügen" and user_favoriten is not None:
        if item['Name'] not in user_favoriten:
            user_favoriten[item['Name']] = item.to_dict()
            st.success(f"{item['Name']} zu Favoriten hinzugefügt!")
            st.experimental_rerun()
        else:
            st.warning(f"{item['Name']} ist bereits in den Favoriten!")
    elif option == "Dieses Getränk löschen" and user_added_beverages and item['Name'] in user_added_beverages:
        # Remove from added beverages
        image_url = user_added_beverages[item['Name']].get('Image URL', '')
        del user_added_beverages[item['Name']]
        # Update session state
        st.session_state['added_beverages'] = user_added_beverages
        # Remove from favorites if present
        if item['Name'] in user_favoriten:
            del user_favoriten[item['Name']]
        # Remove from edits if present
        if item['Name'] in user_edits:
            del user_edits[item['Name']]
        # Save updated user data
        save_user_data(st.session_state['username'], benutzer_df)
        # Delete image from GitHub
        if image_url:
            delete_image_from_github(image_url)
        st.success(f"{item['Name']} erfolgreich gelöscht!")
        st.experimental_rerun()

def statistics_page(df, user_added_beverages):
    st.title("Statistische Auswertungsergebnisse")
    if df.empty and not user_added_beverages:
        st.write("Keine Daten verfügbar für die Statistik.")
        return

    combined_df = pd.concat([df, pd.DataFrame(user_added_beverages).T])
    if combined_df.empty:
        st.write("Keine Daten verfügbar für die Statistik.")
        return
    
    categories = sorted(combined_df['Category'].unique(), key=lambda x: (x == 'Other', x))
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

    category_avg_ratings = {}

    col1, col2 = st.columns(2)

    for i, category in enumerate(categories):
        category_df = combined_df[combined_df['Category'] == category]
        if category_df.empty:
            continue
        
        # Calculate average rating from user_edits
        avg_rating = {}
        for item in category_df['Name']:
            if item in st.session_state['edits']:
                avg_rating[item] = st.session_state['edits'][item]
        
        if avg_rating:
            avg_rating_series = pd.Series(avg_rating).sort_values()
            category_avg_ratings[category] = avg_rating_series.mean()
            color = colors[i % len(colors)]
            
            fig, ax = plt.subplots(figsize=(6, 4))
            avg_rating_series.plot(kind='barh', ax=ax, color=color)
            ax.set_xlabel('Durchschnittliche Bewertung', fontsize=10)
            ax.set_ylabel('Getränkename', fontsize=10)
            ax.set_title(f'{category}', fontsize=14, color=color, fontweight='bold')
            ax.tick_params(axis='x', labelsize=8)
            ax.tick_params(axis='y', labelsize=8)

            if i % 2 == 0:
                col1.pyplot(fig)
                col1.markdown(f"Fazit: Bestbewertet: {avg_rating_series.idxmax()} ({avg_rating_series.max()}/5)")
                col1.markdown("<hr style='border:1px solid #ddd;' />", unsafe_allow_html=True)
            else:
                col2.pyplot(fig)
                col2.markdown(f"Fazit: Bestbewertet: {avg_rating_series.idxmax()} ({avg_rating_series.max()}/5)")
                col2.markdown("<hr style='border:1px solid #ddd;' />", unsafe_allow_html=True)

    if category_avg_ratings:
        best_category = max(category_avg_ratings, key=category_avg_ratings.get)
        st.write(f"Bestbewertete Kategorie: {best_category} mit einer durchschnittlichen Bewertung von {category_avg_ratings[best_category]:.2f}")
    else:
        st.write("Keine Bewertungen verfügbar, um die beste Kategorie zu bestimmen.")

def add_beverage_form(user_added_beverages):
    st.title("➕ Neues Getränk hinzufügen")
    with st.form(key='new_beverage_form'):
        name = st.text_input("Name des Getränks")
        description = st.text_area("Beschreibung")
        category = st.selectbox("Kategorie", ["Soft Drink", "Saft", "Wasser", "Alkoholisch", "Energy Drink", "Tee", "Kaffee", "Andere"])
        image = st.file_uploader("Bild hochladen", type=['jpg', 'png'])
        submit_button = st.form_submit_button("Getränk speichern")
        if submit_button:
            image_url = save_image_to_github(image, name)
            new_beverage = {'Name': name, 'Description': description, 'Image URL': image_url, 'Category': category}
            user_added_beverages[name] = new_beverage
            st.session_state['added_beverages'] = user_added_beverages
            save_user_data(st.session_state['username'], benutzer_df)
            st.success("Getränk erfolgreich hinzugefügt!")
            st.experimental_rerun()

def resize_image(image, max_width=300, max_height=300):
    width, height = image.size
    aspect_ratio = width / height
    if width > max_width or height > max_height:
        if aspect_ratio > 1:
            new_width = min(max_width, width)
            new_height = int(new_width / aspect_ratio)
        else:
            new_height = min(max_height, height)
            new_width = int(new_height * aspect_ratio)
        return image.resize((new_width, new_height))
    return image

def login_page(benutzer_df):
    st.title("🔑 Anmeldung")
    with st.form(key='login_form'):
        username = st.text_input("Benutzername")
        password = st.text_input("Passwort", type="password")
        if st.form_submit_button("Anmelden"):
            if verify_login(username, password, benutzer_df):
                st.session_state['authentication'] = True
                st.session_state['username'] = username
                load_user_data(username, benutzer_df)
                st.success("Anmeldung erfolgreich!")
                st.experimental_rerun()
            else:
                st.error("Ungültiger Benutzername oder Passwort")

def register_page(benutzer_df):
    st.title("➕ Registrierung")
    with st.form(key='register_form'):
        username = st.text_input("Neuer Benutzername")
        password = st.text_input("Neues Passwort", type="password")
        if st.form_submit_button("Registrieren"):
            if register_user(username, password, benutzer_df):
                st.success("Registrierung erfolgreich! Du kannst dich jetzt anmelden.")
            else:
                st.error("Benutzername bereits vergeben. Bitte wähle einen anderen.")

def main():
    benutzer_df = read_github_file(BENUTZER_DATEN_PFAD)
    if benutzer_df.empty:
        benutzer_df = pd.DataFrame(columns=['username', 'password', 'Category', 'favorits', 'edits', 'statistik', 'added_beverages'])

    if 'authentication' not in st.session_state:
        st.session_state['authentication'] = False

    if not st.session_state['authentication']:
        options = st.sidebar.selectbox("Seite wählen", ["Anmelden", "Registrieren"])
        if options == "Anmelden":
            login_page(benutzer_df)
        elif options == "Registrieren":
            register_page(benutzer_df)
    else:
        with st.sidebar:
            if st.button("Abmelden"):
                save_user_data(st.session_state['username'], benutzer_df)
                st.session_state['authentication'] = False
                st.experimental_rerun()
        main_app()

if __name__ == "__main__":
    main()
