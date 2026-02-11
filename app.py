from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, send_from_directory, session
from flask import send_from_directory
import requests
from dotenv import load_dotenv
import os

# Завантажуємо змінні середовища
load_dotenv()

# API ключі
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')
WEATHER_ENABLED = os.getenv('WEATHER_ENABLED', 'True') == 'True'

# Система досягнень
ACHIEVEMENTS = {
    'first_trip': {
        'name': 'Перша подорож',
        'description': 'Створіть свою першу поїздку',
        'icon': '🎉',
        'color': '#48bb78'
    },
    'trips_5': {
        'name': 'Мандрівник',
        'description': 'Створіть 5 поїздок',
        'icon': '🎒',
        'color': '#4299e1'
    },
    'trips_10': {
        'name': 'Досвідчений',
        'description': 'Створіть 10 поїздок',
        'icon': '✈️',
        'color': '#9f7aea'
    },
    'trips_25': {
        'name': 'Майстер подорожей',
        'description': 'Створіть 25 поїздок',
        'icon': '🌍',
        'color': '#ed8936'
    },
    'countries_5': {
        'name': 'Дослідник',
        'description': 'Відвідайте 5 країн',
        'icon': '🗺️',
        'color': '#38b2ac'
    },
    'countries_10': {
        'name': 'Глобус-троттер',
        'description': 'Відвідайте 10 країн',
        'icon': '🌎',
        'color': '#f56565'
    },
    'budget_master': {
        'name': 'Економний',
        'description': 'Завершіть поїздку в межах бюджету',
        'icon': '💰',
        'color': '#48bb78'
    },
    'planner': {
        'name': 'Планувальник',
        'description': 'Додайте 50+ активностей',
        'icon': '📋',
        'color': '#667eea'
    },
    'year_summary': {
        'name': 'Рік подорожей',
        'description': 'Подорожуйте протягом року',
        'icon': '🎊',
        'color': '#f687b3'
    }
}


def check_achievements(user_id):
    """Перевіряє та розблоковує досягнення"""
    from datetime import datetime, date

    user = User.query.get(user_id)
    trips = Trip.query.filter_by(user_id=user_id).all()

    new_achievements = []

    # Кількість поїздок
    trips_count = len(trips)

    achievements_to_check = [
        ('first_trip', 1),
        ('trips_5', 5),
        ('trips_10', 10),
        ('trips_25', 25)
    ]

    for achievement_key, required_count in achievements_to_check:
        if trips_count >= required_count:
            # Перевірка чи вже є це досягнення
            existing = UserAchievement.query.filter_by(
                user_id=user_id,
                achievement_type=achievement_key
            ).first()

            if not existing:
                new_achievement = UserAchievement(
                    user_id=user_id,
                    achievement_type=achievement_key
                )
                db.session.add(new_achievement)
                new_achievements.append(ACHIEVEMENTS[achievement_key])

    # Кількість країн
    destinations = set([trip.destination for trip in trips])
    countries_count = len(destinations)

    if countries_count >= 5:
        existing = UserAchievement.query.filter_by(user_id=user_id, achievement_type='countries_5').first()
        if not existing:
            new_achievement = UserAchievement(user_id=user_id, achievement_type='countries_5')
            db.session.add(new_achievement)
            new_achievements.append(ACHIEVEMENTS['countries_5'])

    if countries_count >= 10:
        existing = UserAchievement.query.filter_by(user_id=user_id, achievement_type='countries_10').first()
        if not existing:
            new_achievement = UserAchievement(user_id=user_id, achievement_type='countries_10')
            db.session.add(new_achievement)
            new_achievements.append(ACHIEVEMENTS['countries_10'])

    # Кількість активностей
    total_activities = Activity.query.join(Trip).filter(Trip.user_id == user_id).count()

    if total_activities >= 50:
        existing = UserAchievement.query.filter_by(user_id=user_id, achievement_type='planner').first()
        if not existing:
            new_achievement = UserAchievement(user_id=user_id, achievement_type='planner')
            db.session.add(new_achievement)
            new_achievements.append(ACHIEVEMENTS['planner'])

    db.session.commit()

    return new_achievements


def get_user_level(user_id):
    """Визначає рівень користувача"""
    trips_count = Trip.query.filter_by(user_id=user_id).count()

    if trips_count >= 25:
        return {'level': 'Легенда', 'icon': '👑', 'color': '#f6ad55', 'next': None}
    elif trips_count >= 10:
        return {'level': 'Майстер', 'icon': '🌟', 'color': '#9f7aea', 'next': 25}
    elif trips_count >= 5:
        return {'level': 'Досвідчений', 'icon': '✨', 'color': '#4299e1', 'next': 10}
    elif trips_count >= 1:
        return {'level': 'Мандрівник', 'icon': '🎒', 'color': '#48bb78', 'next': 5}
    else:
        return {'level': 'Новачок', 'icon': '🌱', 'color': '#a0aec0', 'next': 1}


def transliterate(text):
    """Транслітерація українського тексту для PDF"""
    if not text:
        return text

    translit_dict = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e', 'є': 'ie',
        'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'i', 'й': 'i', 'к': 'k', 'л': 'l',
        'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'iu', 'я': 'ia',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'H', 'Ґ': 'G', 'Д': 'D', 'Е': 'E', 'Є': 'Ie',
        'Ж': 'Zh', 'З': 'Z', 'И': 'Y', 'І': 'I', 'Ї': 'I', 'Й': 'I', 'К': 'K', 'Л': 'L',
        'М': 'M', 'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch', 'Ь': '', 'Ю': 'Iu', 'Я': 'Ia',
        '✈': '', '️': '', '📅': '', '🎒': '', '📝': '', '✓': 'V', '☐': '[ ]'
    }

    result = []
    for char in text:
        result.append(translit_dict.get(char, char))
    return ''.join(result)

# Курси валют (статичні для MVP, можна підключити API)
CURRENCY_RATES = {
    'UAH': 1.0,
    'USD': 42.5,
    'EUR': 50.0,
    'PLN': 10.5,
    'GBP': 52.0,
    'CHF': 48.0,
    'CZK': 1.8,
}

CURRENCY_SYMBOLS = {
    'UAH': '₴',
    'USD': '$',
    'EUR': '€',
    'PLN': 'zł',
    'GBP': '£',
    'CHF': '₣',
    'CZK': 'Kč',
}

def convert_to_uah(amount, from_currency):
    """Конвертує суму з вказаної валюти в гривні"""
    if from_currency not in CURRENCY_RATES:
        return amount
    return amount * CURRENCY_RATES[from_currency]

def convert_from_uah(amount, to_currency):
    """Конвертує суму з гривень у вказану валюту"""
    if to_currency not in CURRENCY_RATES:
        return amount
    return amount / CURRENCY_RATES[to_currency]

def format_currency(amount, currency):
    """Форматує суму з символом валюти"""
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    return f"{amount:.2f} {symbol}"
# Ініціалізація Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-travel-planner-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travel_planner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)

# Ініціалізація SQLAlchemy
db = SQLAlchemy(app)

# Ініціалізація Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.session_protection = "strong"


# Фільтр для відмінювання слів
def plural_filter(number, form1, form2, form5):
    n = abs(number)
    n %= 100
    if n >= 5 and n <= 20:
        return form5
    n %= 10
    if n == 1:
        return form1
    if n >= 2 and n <= 4:
        return form2
    return form5


app.jinja_env.filters['plural'] = plural_filter


# ============= МОДЕЛІ БАЗИ ДАНИХ =============

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    trips = db.relationship('Trip', backref='owner', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'


class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    destination = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    budget = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='UAH')
    created_at = db.Column(db.DateTime, default=datetime.now)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    activities = db.relationship('Activity', backref='trip', lazy=True, cascade='all, delete-orphan')
    packing_items = db.relationship('PackingItem', backref='trip', lazy=True, cascade='all, delete-orphan')
    accommodations = db.relationship('Accommodation', backref='trip', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Trip {self.title}>'


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    date = db.Column(db.DateTime, nullable=False)
    time = db.Column(db.String(10))
    location = db.Column(db.String(200))
    cost = db.Column(db.Float, default=0.0)
    category = db.Column(db.String(50), default='general')
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)

    def __repr__(self):
        return f'<Activity {self.title}>'


class PackingItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), default='general')
    quantity = db.Column(db.Integer, default=1)
    is_packed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)

    def __repr__(self):
        return f'<PackingItem {self.name}>'


class Accommodation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(300))
    check_in = db.Column(db.DateTime, nullable=False)
    check_out = db.Column(db.DateTime, nullable=False)
    price_per_night = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
    booking_reference = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    website = db.Column(db.String(200))
    notes = db.Column(db.Text)
    rating = db.Column(db.Float, default=0.0)
    amenities = db.Column(db.String(500))
    image_url = db.Column(db.String(500))
    booking_status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.now)

    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)

    def __repr__(self):
        return f'<Accommodation {self.name}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
# ============= МАРШРУТИ (ROUTES) =============

# Головна сторінка
@app.route('/')
def index():
    return render_template('index.html')


# Реєстрація
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Перевірка чи існує користувач
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email вже зареєстрований', 'danger')
            return redirect(url_for('register'))

        # Створення нового користувача
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256')
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Реєстрація успішна! Тепер ви можете увійти.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# Service Worker з правильними headers
@app.route('/sw.js')
def service_worker():
    response = send_from_directory('static', 'sw.js')
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

# Вхід
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            session.permanent = True  # ← Робить сесію постійною
            flash('Ви успішно увійшли!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Невірний email або пароль', 'danger')

    return render_template('login.html')


# Вихід
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Ви вийшли з системи', 'info')
    return redirect(url_for('index'))


# Особистий кабінет
# Dashboard з розширеною статистикою
@app.route('/dashboard')
@login_required
def dashboard():
    from datetime import datetime, date

    # Отримуємо параметри пошуку та фільтрації
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'date_desc')
    filter_status = request.args.get('status', 'all')

    # Базовий запит
    query = Trip.query.filter_by(user_id=current_user.id)

    # Пошук по назві або напрямку
    if search_query:
        # Конвертуємо в нижній регістр для порівняння
        all_user_trips = Trip.query.filter_by(user_id=current_user.id).all()
        search_lower = search_query.lower()

        filtered = []
        for trip in all_user_trips:
            if (search_lower in trip.title.lower() or
                    search_lower in trip.destination.lower()):
                filtered.append(trip)

        # Створюємо query з filtered trips
        if filtered:
            trip_ids = [t.id for t in filtered]
            query = Trip.query.filter(Trip.id.in_(trip_ids))
        else:
            # Якщо нічого не знайдено, повертаємо порожній результат
            query = Trip.query.filter(Trip.id == -1)
    else:
        query = Trip.query.filter_by(user_id=current_user.id)

    # Сортування
    if sort_by == 'date_desc':
        query = query.order_by(Trip.start_date.desc())
    elif sort_by == 'date_asc':
        query = query.order_by(Trip.start_date.asc())
    elif sort_by == 'budget_desc':
        query = query.order_by(Trip.budget.desc())
    elif sort_by == 'budget_asc':
        query = query.order_by(Trip.budget.asc())
    elif sort_by == 'title':
        query = query.order_by(Trip.title.asc())

    all_trips = query.all()

    # Фільтрація по статусу (майбутні/минулі)
    today = date.today()

    if filter_status == 'upcoming':
        trips = [t for t in all_trips if
                 (t.start_date.date() if isinstance(t.start_date, datetime) else t.start_date) >= today]
    elif filter_status == 'past':
        trips = [t for t in all_trips if
                 (t.end_date.date() if isinstance(t.end_date, datetime) else t.end_date) < today]
    else:
        trips = all_trips

    # Загальна статистика
    total_trips = len(trips)

    # Витрати
    total_spent = 0
    total_budget = 0
    for trip in trips:
        activities = Activity.query.filter_by(trip_id=trip.id).all()
        accommodations = Accommodation.query.filter_by(trip_id=trip.id).all()
        trip_spent = sum(a.cost for a in activities) + sum(acc.total_price for acc in accommodations)
        total_spent += trip_spent
        total_budget += trip.budget

    # Кількість днів подорожей
    total_days = 0
    for trip in trips:
        days = (trip.end_date - trip.start_date).days + 1
        total_days += days

    # Відвідані країни та міста
    destinations = [trip.destination for trip in trips]
    unique_destinations = len(set(destinations))

    # Активності
    all_activities = Activity.query.join(Trip).filter(Trip.user_id == current_user.id).all()
    total_activities = len(all_activities)
    completed_activities = len([a for a in all_activities if a.completed])

    # Готелі
    all_accommodations = Accommodation.query.join(Trip).filter(Trip.user_id == current_user.id).all()
    total_accommodations = len(all_accommodations)

    # Майбутні поїздки
    from datetime import datetime, date
    today = date.today()
    upcoming_trips = []
    past_trips = []
    for trip in trips:
        # Конвертуємо datetime в date якщо потрібно
        start = trip.start_date.date() if isinstance(trip.start_date, datetime) else trip.start_date
        end = trip.end_date.date() if isinstance(trip.end_date, datetime) else trip.end_date

        if start >= today:
            upcoming_trips.append(trip)
        elif end < today:
            past_trips.append(trip)

    # Топ-5 напрямків
    destination_count = {}
    for trip in trips:
        if trip.destination in destination_count:
            destination_count[trip.destination] += 1
        else:
            destination_count[trip.destination] = 1

    top_destinations = sorted(destination_count.items(), key=lambda x: x[1], reverse=True)[:5]

    # Витрати по місяцях (останні 6 місяців)
    monthly_expenses = {}
    for trip in trips:
        activities = Activity.query.filter_by(trip_id=trip.id).all()
        accommodations = Accommodation.query.filter_by(trip_id=trip.id).all()

        for activity in activities:
            month_key = activity.date.strftime('%Y-%m')
            if month_key in monthly_expenses:
                monthly_expenses[month_key] += activity.cost
            else:
                monthly_expenses[month_key] = activity.cost

        for acc in accommodations:
            month_key = acc.check_in.strftime('%Y-%m')
            if month_key in monthly_expenses:
                monthly_expenses[month_key] += acc.total_price
            else:
                monthly_expenses[month_key] = acc.total_price

    # Сортуємо по датах
    sorted_months = sorted(monthly_expenses.items())[-6:]

    # Форматуємо назви місяців
    month_names = {
        '01': 'Січ', '02': 'Лют', '03': 'Бер', '04': 'Кві',
        '05': 'Тра', '06': 'Чер', '07': 'Лип', '08': 'Сер',
        '09': 'Вер', '10': 'Жов', '11': 'Лис', '12': 'Гру'
    }

    monthly_data = []
    for month_key, amount in sorted_months:
        year, month = month_key.split('-')
        month_label = f"{month_names[month]} {year}"
        monthly_data.append({'month': month_label, 'amount': amount})

    return render_template('dashboard.html',
                           trips=trips,
                           total_trips=total_trips,
                           total_spent=total_spent,
                           total_budget=total_budget,
                           total_days=total_days,
                           unique_destinations=unique_destinations,
                           total_activities=total_activities,
                           completed_activities=completed_activities,
                           total_accommodations=total_accommodations,
                           upcoming_trips=upcoming_trips,
                           past_trips=past_trips,
                           top_destinations=top_destinations,
                           monthly_data=monthly_data,
                           today=today,
                           search_query=search_query,
                           sort_by=sort_by,
                           filter_status=filter_status)


# ==================== КАРТА СВІТУ ====================

@app.route('/world-map')
@login_required
def world_map():
    from datetime import date

    # Всі поїздки користувача
    trips = Trip.query.filter_by(user_id=current_user.id).all()

    # Отримуємо вручну відмічені країни з БД
    manual_countries = VisitedCountry.query.filter_by(user_id=current_user.id).all()

    # Спочатку створюємо словники для вручну відмічених
    manual_visited = {}
    manual_planned = {}

    for country in manual_countries:
        if country.status == 'visited':
            manual_visited[country.country_name] = True
        elif country.status == 'planned':
            manual_planned[country.country_name] = True

    visited = {}
    planned = {}

    today = date.today()

    # Обробляємо поїздки
    for trip in trips:
        destination_parts = trip.destination.split(',')
        country = destination_parts[-1].strip() if len(destination_parts) > 1 else trip.destination.strip()

        trip_end = trip.end_date.date() if hasattr(trip.end_date, 'date') else trip.end_date

        if trip_end < today:
            # Відвідано через поїздку
            if country not in visited:
                visited[country] = []
            visited[country].append({
                'title': trip.title,
                'date': trip.start_date.strftime('%d.%m.%Y')
            })
        else:
            # Заплановано через поїздку
            # НЕ додаємо якщо вручну вже відмічено як visited
            if country not in manual_visited and country not in planned:
                planned[country] = {
                    'country': country,
                    'date': trip.start_date.strftime('%d.%m.%Y')
                }

    # ТЕПЕР додаємо вручну відмічені країни
    for country_name in manual_visited:
        if country_name not in visited:
            visited[country_name] = []
        visited[country_name].insert(0, {
            'title': 'Відмічено вручну',
            'date': 'Без дати'
        })

    for country_name in manual_planned:
        # НЕ додаємо якщо вже є у visited (з поїздок або вручну)
        if country_name not in visited and country_name not in planned:
            planned[country_name] = {
                'country': country_name,
                'date': 'Не вказано'
            }

    # Форматуємо для шаблону
    visited_countries = [
        {
            'country': country,
            'trips': trips_list
        }
        for country, trips_list in visited.items()
    ]

    planned_countries = list(planned.values())

    # Статистика
    total_countries = 195
    coverage = (len(visited) / total_countries * 100) if visited else 0

    # ВАЖЛИВО: передаємо назви країн для JavaScript
    visited_country_names = list(visited.keys())
    planned_country_names = list(planned.keys())

    return render_template('world_map.html',
                           visited_countries=visited_countries,
                           planned_countries=planned_countries,
                           total_trips=len(trips),
                           coverage_percentage=round(coverage, 1),
                           visited_country_names=visited_country_names,
                           planned_country_names=planned_country_names)

# Мої поїздки (окрема сторінка)
@app.route('/my-trips')
@login_required
def my_trips():
    from datetime import datetime, date

    # Отримуємо параметри пошуку та фільтрації
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'date_desc')
    filter_status = request.args.get('status', 'all')

    # Отримуємо всі поїздки користувача
    all_user_trips = Trip.query.filter_by(user_id=current_user.id).all()

    # Пошук
    if search_query:
        search_lower = search_query.lower()
        all_user_trips = [
            trip for trip in all_user_trips
            if search_lower in trip.title.lower() or
               search_lower in trip.destination.lower()
        ]

    # Сортування
    if sort_by == 'date_desc':
        all_user_trips.sort(key=lambda x: x.start_date, reverse=True)
    elif sort_by == 'date_asc':
        all_user_trips.sort(key=lambda x: x.start_date)
    elif sort_by == 'budget_desc':
        all_user_trips.sort(key=lambda x: x.budget, reverse=True)
    elif sort_by == 'budget_asc':
        all_user_trips.sort(key=lambda x: x.budget)
    elif sort_by == 'title':
        all_user_trips.sort(key=lambda x: x.title.lower())

    # Фільтрація по статусу
    today = date.today()

    if filter_status == 'upcoming':
        trips = [t for t in all_user_trips if
                 (t.start_date.date() if isinstance(t.start_date, datetime) else t.start_date) >= today]
    elif filter_status == 'past':
        trips = [t for t in all_user_trips if
                 (t.end_date.date() if isinstance(t.end_date, datetime) else t.end_date) < today]
    else:
        trips = all_user_trips

    return render_template('my_trips.html',
                           trips=trips,
                           today=today,
                           search_query=search_query,
                           sort_by=sort_by,
                           filter_status=filter_status)
# Календар подорожей
@app.route('/calendar')
@login_required
def trip_calendar():
    from datetime import datetime, date, timedelta
    import calendar as cal

    # Отримуємо поточний місяць та рік
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))

    # Отримуємо всі поїздки користувача
    trips = Trip.query.filter_by(user_id=current_user.id).all()

    # Створюємо календар
    month_calendar = cal.monthcalendar(year, month)
    month_name = cal.month_name[month]

    # Знаходимо поїздки для кожного дня місяця
    trips_by_date = {}
    for trip in trips:
        start = trip.start_date.date() if isinstance(trip.start_date, datetime) else trip.start_date
        end = trip.end_date.date() if isinstance(trip.end_date, datetime) else trip.end_date

        # Додаємо поїздку до всіх днів між start та end
        current_date = start
        while current_date <= end:
            if current_date.year == year and current_date.month == month:
                date_key = current_date.day
                if date_key not in trips_by_date:
                    trips_by_date[date_key] = []
                trips_by_date[date_key].append(trip)
            current_date += timedelta(days=1)

    # Навігація по місяцях
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    # Поточна дата
    today = date.today()

    # Статистика місяця
    month_trips = [t for t in trips if
                   (t.start_date.date() if isinstance(t.start_date, datetime) else t.start_date).year == year and
                   (t.start_date.date() if isinstance(t.start_date, datetime) else t.start_date).month == month]

    return render_template('calendar.html',
                           year=year,
                           month=month,
                           month_name=month_name,
                           month_calendar=month_calendar,
                           trips_by_date=trips_by_date,
                           prev_month=prev_month,
                           prev_year=prev_year,
                           next_month=next_month,
                           next_year=next_year,
                           today=today,
                           month_trips=month_trips,
                           all_trips=trips)


# ==================== API ІНТЕГРАЦІЇ ====================

# API для зміни порядку активностей
@app.route('/api/reorder-activities', methods=['POST'])
@login_required
def reorder_activities():
    data = request.get_json()
    trip_id = data.get('trip_id')
    activity_ids = data.get('activity_ids', [])

    trip = Trip.query.get_or_404(trip_id)
    if trip.user_id != current_user.id:
        return {'success': False, 'error': 'Access denied'}, 403

    # Оновлюємо порядок (можна зберегти в поле order якщо воно є)
    for index, activity_id in enumerate(activity_ids):
        activity = Activity.query.get(activity_id)
        if activity and activity.trip_id == int(trip_id):
            # Якщо є поле order - оновіть його
            # activity.order = index
            pass

    db.session.commit()

    return {'success': True}

def get_weather(city, country_code=''):
    """Отримує погоду для міста"""
    if not WEATHER_ENABLED or not OPENWEATHER_API_KEY:
        return None

    try:
        # Формуємо запит
        location = f"{city},{country_code}" if country_code else city
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': location,
            'appid': OPENWEATHER_API_KEY,
            'units': 'metric',
            'lang': 'uk'
        }

        response = requests.get(url, params=params, timeout=5)

        if response.status_code == 200:
            data = response.json()

            return {
                'temp': round(data['main']['temp']),
                'feels_like': round(data['main']['feels_like']),
                'description': data['weather'][0]['description'],
                'icon': data['weather'][0]['icon'],
                'humidity': data['main']['humidity'],
                'wind_speed': round(data['wind']['speed'] * 3.6, 1),  # м/с в км/год
                'pressure': data['main']['pressure']
            }

        return None

    except Exception as e:
        print(f"Помилка отримання погоди: {e}")
        return None


def get_weather_forecast(city, country_code='', days=5):
    """Отримує прогноз погоди на кілька днів"""
    if not WEATHER_ENABLED or not OPENWEATHER_API_KEY:
        return None

    try:
        location = f"{city},{country_code}" if country_code else city
        url = f"http://api.openweathermap.org/data/2.5/forecast"
        params = {
            'q': location,
            'appid': OPENWEATHER_API_KEY,
            'units': 'metric',
            'lang': 'uk'
        }

        response = requests.get(url, params=params, timeout=5)

        if response.status_code == 200:
            data = response.json()

            # Групуємо по днях (беремо полуденні показники)
            daily_forecast = []
            current_date = None

            for item in data['list']:
                dt = datetime.fromtimestamp(item['dt'])
                date_str = dt.strftime('%Y-%m-%d')

                # Беремо один запис на день (близько 12:00)
                if date_str != current_date and dt.hour >= 11 and dt.hour <= 14:
                    current_date = date_str
                    daily_forecast.append({
                        'date': dt,
                        'temp': round(item['main']['temp']),
                        'temp_min': round(item['main']['temp_min']),
                        'temp_max': round(item['main']['temp_max']),
                        'description': item['weather'][0]['description'],
                        'icon': item['weather'][0]['icon']
                    })

                    if len(daily_forecast) >= days:
                        break

            return daily_forecast

        return None

    except Exception as e:
        print(f"Помилка отримання прогнозу: {e}")
        return None


def get_live_exchange_rates():
    """Отримує актуальні курси валют з ПриватБанку"""
    try:
        url = "https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=5"
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()

            rates = {'UAH': 1.0}

            for item in data:
                if item['ccy'] in ['USD', 'EUR']:
                    # Беремо курс продажу
                    rates[item['ccy']] = float(item['sale'])

            # Додаємо інші валюти через USD
            if 'USD' in rates:
                rates['PLN'] = rates['USD'] / 4.0  # Приблизно
                rates['GBP'] = rates['USD'] * 1.27
                rates['CHF'] = rates['USD'] * 1.1
                rates['CZK'] = rates['USD'] / 23

            return rates

        return None

    except Exception as e:
        print(f"Помилка отримання курсів: {e}")
        return None


def parse_city_country(destination):
    """Парсить місто та країну з рядка напрямку"""
    # Очікуємо формат: "Київ, Україна" або просто "Париж"
    parts = [p.strip() for p in destination.split(',')]

    if len(parts) >= 2:
        return parts[0], parts[1]  # місто, країна
    else:
        return parts[0], ''  # тільки місто


# ==================== ГЛОБАЛЬНИЙ ПОШУК ====================

@app.route('/search')
@login_required
def global_search():
    query = request.args.get('q', '').strip()

    if not query:
        return render_template('search_results.html',
                               query='',
                               trips=[],
                               activities=[],
                               notes=[],
                               accommodations=[])

    # Пошук в нижньому регістрі
    search_term = f"%{query.lower()}%"

    # Пошук поїздок
    trips = Trip.query.filter(
        Trip.user_id == current_user.id
    ).filter(
        db.or_(
            Trip.title.ilike(search_term),
            Trip.destination.ilike(search_term)
        )
    ).all()

    # Пошук активностей
    activities = Activity.query.join(Trip).filter(
        Trip.user_id == current_user.id
    ).filter(
        db.or_(
            Activity.title.ilike(search_term),
            Activity.description.ilike(search_term),
            Activity.location.ilike(search_term)
        )
    ).all()

    # Пошук нотаток
    notes = TripNote.query.join(Trip).filter(
        Trip.user_id == current_user.id
    ).filter(
        db.or_(
            TripNote.title.ilike(search_term),
            TripNote.content.ilike(search_term)
        )
    ).all()

    # Пошук готелів
    accommodations = Accommodation.query.join(Trip).filter(
        Trip.user_id == current_user.id
    ).filter(
        db.or_(
            Accommodation.name.ilike(search_term),
            Accommodation.address.ilike(search_term)
        )
    ).all()

    return render_template('search_results.html',
                           query=query,
                           trips=trips,
                           activities=activities,
                           notes=notes,
                           accommodations=accommodations)


# Швидкий пошук (API для autocomplete)
@app.route('/api/quick-search')
@login_required
def quick_search():
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return {'results': []}

    search_term = f"%{query.lower()}%"
    results = []

    # Пошук поїздок (топ 3)
    trips = Trip.query.filter(
        Trip.user_id == current_user.id
    ).filter(
        db.or_(
            Trip.title.ilike(search_term),
            Trip.destination.ilike(search_term)
        )
    ).limit(3).all()

    for trip in trips:
        results.append({
            'type': 'trip',
            'id': trip.id,
            'title': trip.title,
            'subtitle': trip.destination,
            'url': url_for('view_trip', trip_id=trip.id),
            'icon': '🗺️'
        })

    # Пошук активностей (топ 3)
    activities = Activity.query.join(Trip).filter(
        Trip.user_id == current_user.id
    ).filter(
        Activity.title.ilike(search_term)
    ).limit(3).all()

    for activity in activities:
        results.append({
            'type': 'activity',
            'id': activity.id,
            'title': activity.title,
            'subtitle': f"{activity.trip.title} • {activity.date.strftime('%d.%m.%Y')}",
            'url': url_for('view_trip', trip_id=activity.trip_id),
            'icon': '📍'
        })

    # Пошук нотаток (топ 3)
    notes = TripNote.query.join(Trip).filter(
        Trip.user_id == current_user.id
    ).filter(
        db.or_(
            TripNote.title.ilike(search_term),
            TripNote.content.ilike(search_term)
        )
    ).limit(3).all()

    for note in notes:
        results.append({
            'type': 'note',
            'id': note.id,
            'title': note.title,
            'subtitle': note.trip.title,
            'url': url_for('trip_notes', trip_id=note.trip_id),
            'icon': '📝'
        })

    return {'results': results[:9]}  # Максимум 9 результатів


# Рекомендації на основі історії
@app.route('/recommendations')
@login_required
def recommendations():
    # Аналізуємо історію подорожей
    trips = Trip.query.filter_by(user_id=current_user.id).all()

    # Найчастіші напрямки
    destinations = {}
    for trip in trips:
        dest = trip.destination
        destinations[dest] = destinations.get(dest, 0) + 1

    top_destinations = sorted(destinations.items(), key=lambda x: x[1], reverse=True)[:5]

    # Середній бюджет
    if trips:
        avg_budget = sum(t.budget * CURRENCY_RATES.get(t.currency, 1) for t in trips) / len(trips)
    else:
        avg_budget = 0

    # Середня тривалість
    if trips:
        avg_duration = sum((t.end_date - t.start_date).days + 1 for t in trips) / len(trips)
    else:
        avg_duration = 0

    # Популярні категорії активностей
    activities = Activity.query.join(Trip).filter(Trip.user_id == current_user.id).all()

    categories = {}
    for activity in activities:
        cat = activity.category
        categories[cat] = categories.get(cat, 0) + 1

    top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]

    # Рекомендації напрямків (прості - можна підключити реальний API)
    recommendations_list = [
        {'city': 'Львів', 'country': 'Україна', 'reason': 'Популярно серед користувачів', 'budget': 5000},
        {'city': 'Краків', 'country': 'Польща', 'reason': 'Близько до України', 'budget': 8000},
        {'city': 'Будапешт', 'country': 'Угорщина', 'reason': 'Культурна столиця', 'budget': 10000},
        {'city': 'Стамбул', 'country': 'Туреччина', 'reason': 'Екзотика та історія', 'budget': 12000},
        {'city': 'Прага', 'country': 'Чехія', 'reason': 'Архітектурна краса', 'budget': 15000},
    ]

    return render_template('recommendations.html',
                           top_destinations=top_destinations,
                           avg_budget=avg_budget,
                           avg_duration=avg_duration,
                           top_categories=top_categories,
                           recommendations=recommendations_list)

# Конвертер валют
@app.route('/converter')
@login_required
def currency_converter():
    # Спробуємо отримати живі курси
    live_rates = get_live_exchange_rates()

    # Якщо не вийшло, використовуємо статичні
    rates = live_rates if live_rates else CURRENCY_RATES

    return render_template('currency_converter.html',
                           currencies=rates.keys(),
                           currency_rates=rates,
                           currency_symbols=CURRENCY_SYMBOLS,
                           live_rates=live_rates is not None)


# Створення поїздки
@app.route('/trip/new', methods=['GET', 'POST'])
@login_required
def new_trip():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        destination = request.form.get('destination', '').strip()
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        budget_str = request.form.get('budget', '0')
        currency = request.form.get('currency', 'UAH')

        # Серверна валідація
        if not title or not destination:
            flash('Назва та напрямок є обов\'язковими полями', 'danger')
            return render_template('trip.html')

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

            # Перевірка логічності дат
            if end_date < start_date:
                flash('Дата закінчення не може бути раніше дати початку', 'danger')
                return render_template('trip.html')

            budget = float(budget_str)
            if budget < 0:
                flash('Бюджет не може бути від\'ємним', 'danger')
                return render_template('trip.html')

        except ValueError:
            flash('Невірний формат дати або бюджету', 'danger')
            return render_template('trip.html')

        new_trip = Trip(
            title=title,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            currency=currency,
            user_id=current_user.id
        )

        db.session.add(new_trip)
        db.session.commit()

        db.session.add(new_trip)
        db.session.commit()

        # Перевірка досягнень
        new_badges = check_achievements(current_user.id)

        flash('Поїздку створено!', 'success')

        # Повідомлення про нові досягнення
        for badge in new_badges:
            flash(f"🏆 Нове досягнення: {badge['icon']} {badge['name']}!", 'info')

        return redirect(url_for('dashboard'))

        flash('Поїздку створено!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('new_trip.html',
                           currencies=CURRENCY_RATES.keys(),
                           currency_symbols=CURRENCY_SYMBOLS)

    return render_template('trip.html')


# Сторінка досягнень
@app.route('/achievements')
@login_required
def achievements_page():
    from datetime import datetime, date

    # Отримуємо всі досягнення користувача
    user_achievements = UserAchievement.query.filter_by(user_id=current_user.id).all()
    unlocked_types = [a.achievement_type for a in user_achievements]

    # Розділяємо на розблоковані та заблоковані
    unlocked = []
    locked = []

    for key, achievement in ACHIEVEMENTS.items():
        achievement_data = {
            'key': key,
            'name': achievement['name'],
            'description': achievement['description'],
            'icon': achievement['icon'],
            'color': achievement['color']
        }

        if key in unlocked_types:
            # Знаходимо дату розблокування
            user_ach = next((a for a in user_achievements if a.achievement_type == key), None)
            if user_ach:
                achievement_data['unlocked_at'] = user_ach.unlocked_at
            unlocked.append(achievement_data)
        else:
            locked.append(achievement_data)

    # Рівень користувача
    user_level = get_user_level(current_user.id)
    trips_count = Trip.query.filter_by(user_id=current_user.id).count()

    # Прогрес до наступного рівня
    if user_level['next']:
        progress = (trips_count / user_level['next']) * 100
    else:
        progress = 100

    # Статистика року
    current_year = datetime.now().year
    year_trips = Trip.query.filter_by(user_id=current_user.id).filter(
        db.func.strftime('%Y', Trip.start_date) == str(current_year)
    ).all()

    year_stats = {
        'trips': len(year_trips),
        'countries': len(set([t.destination for t in year_trips])),
        'total_days': sum([(t.end_date - t.start_date).days + 1 for t in year_trips])
    }

    return render_template('achievements.html',
                           unlocked=unlocked,
                           locked=locked,
                           user_level=user_level,
                           trips_count=trips_count,
                           progress=progress,
                           year_stats=year_stats,
                           current_year=current_year,
                           total_achievements=len(ACHIEVEMENTS))


@app.route('/trip/<int:trip_id>')
@login_required
def view_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    # Групуємо активності по днях
    from collections import defaultdict
    activities_by_day = defaultdict(list)

    for activity in trip.activities:
        activity_date = activity.date.date() if hasattr(activity.date, 'date') else activity.date
        activities_by_day[activity_date].append(activity)

    # Сортуємо дати
    activities_by_day = dict(sorted(activities_by_day.items()))

    # Отримуємо погоду
    city, country = parse_city_country(trip.destination)
    weather = get_weather(city, country)
    weather_forecast = get_weather_forecast(city, country, days=7)

    return render_template('trip_view.html',
                           trip=trip,
                           activities_by_day=activities_by_day,
                           currency_rates=CURRENCY_RATES,
                           currency_symbols=CURRENCY_SYMBOLS,
                           weather=weather,
                           weather_forecast=weather_forecast)

# Зберегти поїздку як шаблон
@app.route('/trip/<int:trip_id>/save-as-template', methods=['GET', 'POST'])
@login_required
def save_as_template(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        import json

        template_name = request.form.get('template_name')
        description = request.form.get('description')
        is_public = request.form.get('is_public') == 'on'

        # Збираємо активності
        activities_data = []
        for activity in trip.activities:
            activities_data.append({
                'title': activity.title,
                'category': activity.category,
                'location': activity.location if hasattr(activity, 'location') else '',
                'time': activity.time if hasattr(activity, 'time') else '',
                'cost': activity.cost if hasattr(activity, 'cost') else 0
            })

        # Збираємо packing list
        packing_data = []
        packing_items = PackingItem.query.filter_by(trip_id=trip.id).all()
        for item in packing_items:
            packing_data.append({
                'name': item.name,
                'category': item.category,
                'quantity': item.quantity
            })

        # Створюємо шаблон
        duration = (trip.end_date - trip.start_date).days + 1

        template = TripTemplate(
            name=template_name,
            description=description,
            destination_type=trip.destination,
            duration_days=duration,
            budget_estimate=trip.budget,
            currency=trip.currency,
            is_public=is_public,
            user_id=current_user.id,
            activities_template=json.dumps(activities_data, ensure_ascii=False),
            packing_template=json.dumps(packing_data, ensure_ascii=False)
        )

        db.session.add(template)
        db.session.commit()

        flash(f'Шаблон "{template_name}" збережено!', 'success')
        return redirect(url_for('templates_list'))

    return render_template('save_as_template.html', trip=trip)


# Список шаблонів
@app.route('/templates')
@login_required
def templates_list():
    # Мої шаблони
    my_templates = TripTemplate.query.filter_by(user_id=current_user.id).order_by(TripTemplate.created_at.desc()).all()

    # Публічні шаблони інших користувачів
    public_templates = TripTemplate.query.filter_by(is_public=True).filter(
        TripTemplate.user_id != current_user.id).limit(10).all()

    return render_template('templates_list.html',
                           my_templates=my_templates,
                           public_templates=public_templates)


# Створити поїздку з шаблону
@app.route('/templates/<int:template_id>/use', methods=['GET', 'POST'])
@login_required
def use_template(template_id):
    template = TripTemplate.query.get_or_404(template_id)

    # Перевірка доступу
    if not template.is_public and template.user_id != current_user.id:
        flash('У вас немає доступу до цього шаблону', 'danger')
        return redirect(url_for('templates_list'))

    if request.method == 'POST':
        import json
        from datetime import timedelta

        title = request.form.get('title')
        destination = request.form.get('destination')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        budget = float(request.form.get('budget'))

        # Створюємо нову поїздку
        end_date = start_date + timedelta(days=template.duration_days - 1)

        new_trip = Trip(
            title=title,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            currency=template.currency,
            user_id=current_user.id
        )

        db.session.add(new_trip)
        db.session.flush()  # Отримуємо ID нової поїздки

        # Додаємо активності з шаблону
        if template.activities_template:
            activities_data = json.loads(template.activities_template)
            current_date = start_date

            for act_data in activities_data:
                activity = Activity(
                    title=act_data['title'],
                    date=current_date,
                    time=act_data.get('time'),
                    location=act_data.get('location'),
                    category=act_data['category'],
                    cost=act_data.get('cost', 0),
                    notes=act_data.get('notes'),
                    trip_id=new_trip.id
                )
                db.session.add(activity)

                # Розподіляємо активності по днях
                if len(activities_data) > template.duration_days:
                    # Якщо активностей більше ніж днів, розподіляємо рівномірно
                    pass
                else:
                    current_date += timedelta(days=1)
                    if current_date > end_date:
                        current_date = start_date

        # Додаємо packing list з шаблону
        if template.packing_template:
            packing_data = json.loads(template.packing_template)

            for pack_data in packing_data:
                packing_item = PackingItem(
                    name=pack_data['name'],
                    category=pack_data['category'],
                    quantity=pack_data.get('quantity', 1),
                    trip_id=new_trip.id
                )
                db.session.add(packing_item)

        db.session.commit()

        flash(f'Поїздку "{title}" створено з шаблону!', 'success')
        return redirect(url_for('view_trip', trip_id=new_trip.id))

    return render_template('use_template.html',
                           template=template,
                           currency_symbols=CURRENCY_SYMBOLS)


# Нотатки для поїздки
class TripNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))  # Загальне, Важливе, Контакти, Посилання
    is_pinned = db.Column(db.Boolean, default=False)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    trip = db.relationship('Trip', backref='notes_list')

    def __repr__(self):
        return f'<TripNote {self.title}>'


@app.route('/trip/<int:trip_id>/export/pdf')
@login_required
def export_trip_pdf(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    elements = []

    # Шрифт
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    font_path = os.path.join(os.path.dirname(__file__), 'static', 'fonts')

    try:
        pdfmetrics.registerFont(TTFont('DejaVu', os.path.join(font_path, 'DejaVuSans.ttf')))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', os.path.join(font_path, 'DejaVuSans-Bold.ttf')))
        font_name = 'DejaVu'
        font_bold = 'DejaVu-Bold'
    except:
        font_name = 'Helvetica'
        font_bold = 'Helvetica-Bold'

    # Стилі
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=32,
        fontName=font_bold,
        textColor=colors.HexColor('#667eea'),
        spaceAfter=10,
        alignment=TA_CENTER,
        leading=38
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=16,
        fontName=font_name,
        textColor=colors.HexColor('#718096'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=20,
        fontName=font_bold,
        textColor=colors.white,
        spaceAfter=15,
        spaceBefore=25,
        backColor=colors.HexColor('#667eea'),
        borderPadding=10,
        borderRadius=5
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
        leading=14
    )

    # ========== ОБКЛАДИНКА ==========

    icon_style = ParagraphStyle(
        'Icon',
        parent=styles['Normal'],
        fontSize=60,
        alignment=TA_CENTER,
        spaceAfter=20
    )
    elements.append(Paragraph("✈", icon_style))
    elements.append(Paragraph(trip.title, title_style))

    subtitle_text = f"{trip.destination}"
    elements.append(Paragraph(subtitle_text, subtitle_style))

    line = Table([['']], colWidths=[18 * cm])
    line.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 3, colors.HexColor('#667eea')),
    ]))
    elements.append(line)
    elements.append(Spacer(1, 0.5 * cm))

    # ========== ІНФОРМАЦІЙНА КАРТКА ==========

    trip_duration = (trip.end_date - trip.start_date).days + 1

    info_card_data = [
        [
            Paragraph('<b>ДАТИ</b>', normal_style),
            Paragraph(f'{trip.start_date.strftime("%d.%m.%Y")} - {trip.end_date.strftime("%d.%m.%Y")}', normal_style)
        ],
        [
            Paragraph('<b>ТРИВАЛІСТЬ</b>', normal_style),
            Paragraph(f'{trip_duration} днів', normal_style)
        ],
        [
            Paragraph('<b>БЮДЖЕТ</b>', normal_style),
            Paragraph(f'{trip.budget:.2f} {CURRENCY_SYMBOLS.get(trip.currency, trip.currency)}', normal_style)
        ],
    ]

    info_card = Table(info_card_data, colWidths=[5 * cm, 13 * cm])
    info_card.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#edf2f7')),
        ('BACKGROUND', (1, 0), (1, -1), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2d3748')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1.5, colors.HexColor('#cbd5e0')),
    ]))

    elements.append(info_card)
    elements.append(Spacer(1, 1 * cm))

    # ========== МІСТА ПОЇЗДКИ ==========

    destinations = TripDestination.query.filter_by(trip_id=trip_id).order_by(TripDestination.order).all()

    if destinations:
        elements.append(Paragraph("МІСТА ПОЇЗДКИ", heading_style))
        elements.append(Spacer(1, 0.3 * cm))

        dest_data = []
        for i, dest in enumerate(destinations, 1):
            dest_data.append([
                Paragraph(f'<b>{i}</b>', normal_style),
                Paragraph(f'<b>{dest.city}</b>', normal_style),
                Paragraph(dest.country, normal_style),
                Paragraph(
                    f'{dest.arrival_date.strftime("%d.%m") if dest.arrival_date else "—"} - {dest.departure_date.strftime("%d.%m") if dest.departure_date else "—"}',
                    normal_style)
            ])

        dest_table = Table(dest_data, colWidths=[1.5 * cm, 7 * cm, 5 * cm, 4.5 * cm])
        dest_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (1, 0), (-1, -1), [colors.white, colors.HexColor('#f7fafc')])
        ]))

        elements.append(dest_table)
        elements.append(Spacer(1, 0.5 * cm))

    # ========== ТРАНСПОРТ ==========

    transports = Transport.query.filter_by(trip_id=trip_id).order_by(Transport.departure_date).all()

    if transports:
        elements.append(Paragraph(" ТРАНСПОРТ ТА МАРШРУТИ", heading_style))
        elements.append(Spacer(1, 0.3 * cm))

        transport_icons = {
            'plane': '',
            'train': '',
            'bus': '',
            'car': '',
            'ferry': ''
        }

        for transport in transports:
            icon = transport_icons.get(transport.type, '•')

            transport_data = [[
                Paragraph(f'<b>{icon} {transport.from_location} → {transport.to_location}</b>', normal_style),
                Paragraph(f'{transport.cost:.0f} грн' if transport.cost > 0 else '—', normal_style)
            ]]

            transport_info = f'{transport.departure_date.strftime("%d.%m.%Y %H:%M")}'
            if transport.arrival_date:
                transport_info += f' → {transport.arrival_date.strftime("%d.%m.%Y %H:%M")}'
            if transport.carrier:
                transport_info += f' • {transport.carrier}'

            transport_data.append([
                Paragraph(f'<i>{transport_info}</i>', ParagraphStyle('Small', parent=normal_style, fontSize=9,
                                                                     textColor=colors.HexColor('#718096'))),
                ''
            ])

            transport_table = Table(transport_data, colWidths=[15 * cm, 3 * cm])
            transport_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7fafc')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0'))
            ]))

            elements.append(transport_table)
            elements.append(Spacer(1, 0.3 * cm))

    # ========== МАРШРУТ ПОДОРОЖІ ==========

    from collections import defaultdict
    activities_by_day = defaultdict(list)

    for activity in trip.activities:
        activity_date = activity.date.date() if hasattr(activity.date, 'date') else activity.date
        activities_by_day[activity_date].append(activity)

    if activities_by_day:
        elements.append(PageBreak())
        elements.append(Paragraph(" ПЛАН ПОДОРОЖІ", heading_style))
        elements.append(Spacer(1, 0.3 * cm))

        trip_start = trip.start_date.date() if hasattr(trip.start_date, 'date') else trip.start_date

        for day_date in sorted(activities_by_day.keys()):
            day_activities = activities_by_day[day_date]
            day_num = (day_date - trip_start).days + 1

            day_heading = ParagraphStyle(
                'DayHeading',
                parent=normal_style,
                fontSize=14,
                fontName=font_bold,
                textColor=colors.HexColor('#2d3748'),
                spaceAfter=10,
                spaceBefore=15,
                leftIndent=10,
                backColor=colors.HexColor('#edf2f7'),
                borderPadding=8
            )

            day_title = f"День {day_num} • {day_date.strftime('%d %B %Y')}"
            elements.append(Paragraph(day_title, day_heading))
            elements.append(Spacer(1, 0.2 * cm))

            activities_data = []

            for activity in day_activities:
                time_cell = Paragraph(
                    f'<b>{activity.time or "—"}</b>',
                    normal_style
                )

                title_cell = Paragraph(
                    f'<b>{activity.title}</b>',
                    normal_style
                )

                location_cell = Paragraph(
                    f' {activity.location}' if activity.location else '—',
                    ParagraphStyle('Location', parent=normal_style, textColor=colors.HexColor('#718096'))
                )

                cost_cell = Paragraph(
                    f'<b>{activity.cost:.0f} грн</b>' if activity.cost else '—',
                    ParagraphStyle('Cost', parent=normal_style, textColor=colors.HexColor('#48bb78'))
                )

                activities_data.append([time_cell, title_cell, location_cell, cost_cell])

            if activities_data:
                activities_table = Table(activities_data, colWidths=[2 * cm, 8 * cm, 5 * cm, 3 * cm])
                activities_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('FONTNAME', (0, 0), (-1, -1), font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                    ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f7fafc')])
                ]))

                elements.append(activities_table)
                elements.append(Spacer(1, 0.4 * cm))

    # ========== PACKING LIST ==========

    packing_items = PackingItem.query.filter_by(trip_id=trip.id).all()

    if packing_items:
        elements.append(PageBreak())
        elements.append(Paragraph("СПИСОК РЕЧЕЙ", heading_style))
        elements.append(Spacer(1, 0.3 * cm))

        items_by_category = defaultdict(list)

        category_names = {
            'clothes': ' Одяг',
            'toiletries': ' Засоби особистої гігієни',
            'electronics': ' Електроніка',
            'documents': ' Документи',
            'other': ' Інше'
        }

        for item in packing_items:
            cat_name = category_names.get(item.category, item.category)
            items_by_category[cat_name].append(item)

        for category in sorted(items_by_category.keys()):
            items = items_by_category[category]

            cat_heading = ParagraphStyle(
                'CategoryHeading',
                parent=normal_style,
                fontSize=12,
                fontName=font_bold,
                textColor=colors.HexColor('#4a5568'),
                spaceAfter=8,
                spaceBefore=12
            )
            elements.append(Paragraph(category, cat_heading))

            packing_data = []

            for item in items:
                checkbox = '☑' if item.is_packed else '☐'
                item_style = ParagraphStyle(
                    'ItemStyle',
                    parent=normal_style,
                    textColor=colors.HexColor('#a0aec0') if item.is_packed else colors.HexColor('#2d3748')
                )

                packing_data.append([
                    Paragraph(checkbox, normal_style),
                    Paragraph(item.name, item_style),
                    Paragraph(f'x{item.quantity}', item_style)
                ])

            packing_table = Table(packing_data, colWidths=[1 * cm, 15 * cm, 2 * cm])
            packing_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, -1), font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white)
            ]))

            elements.append(packing_table)
            elements.append(Spacer(1, 0.2 * cm))

    # ========== ФУТЕР ==========

    elements.append(Spacer(1, 1.5 * cm))
    elements.append(line)
    elements.append(Spacer(1, 0.3 * cm))

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=9,
        textColor=colors.HexColor('#a0aec0'),
        alignment=TA_CENTER
    )

    footer_text = f"Створено в Travel Planner • {datetime.now().strftime('%d.%m.%Y')} • Гарних подорожей! ✈"
    elements.append(Paragraph(footer_text, footer_style))

    # Генеруємо PDF
    doc.build(elements)

    buffer.seek(0)
    filename = f"trip_{trip.title.replace(' ', '_')}_{trip.start_date.strftime('%Y%m%d')}.pdf"

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

# Чекліст для поїздки (віза, страховка тощо)
class TripChecklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))  # Документи, Бронювання, Підготовка, Інше
    is_completed = db.Column(db.Boolean, default=False)
    due_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    trip = db.relationship('Trip', backref='checklist_items')

    def __repr__(self):
        return f'<TripChecklist {self.item}>'


# Транспорт
class Transport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # plane, train, bus, car, ferry
    from_location = db.Column(db.String(200), nullable=False)
    to_location = db.Column(db.String(200), nullable=False)
    departure_date = db.Column(db.DateTime, nullable=False)
    arrival_date = db.Column(db.DateTime, nullable=True)
    carrier = db.Column(db.String(200))  # Авіакомпанія, автобусна компанія
    ticket_number = db.Column(db.String(100))
    seat_number = db.Column(db.String(20))
    cost = db.Column(db.Float, default=0)
    booking_reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

    trip = db.relationship('Trip', backref='transports')


# Напрямки (міста) в поїздці
class TripDestination(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    city = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(200), nullable=False)
    arrival_date = db.Column(db.Date, nullable=True)
    departure_date = db.Column(db.Date, nullable=True)
    order = db.Column(db.Integer, default=0)  # Порядок відвідування
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

    trip = db.relationship('Trip', backref='destinations')

    def __repr__(self):
        return f'<TripDestination {self.city}, {self.country}>'


# Відвідані країни
class VisitedCountry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    country_name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # visited, planned
    visit_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

    user = db.relationship('User', backref='visited_countries')

    def __repr__(self):
        return f'<VisitedCountry {self.country_name} - {self.status}>'

# Досягнення користувача
class UserAchievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    achievement_type = db.Column(db.String(50), nullable=False)  # badge_first_trip, badge_5_trips тощо
    unlocked_at = db.Column(db.DateTime, default=datetime.now)

    user = db.relationship('User', backref='achievements')

    def __repr__(self):
        return f'<Achievement {self.achievement_type}>'


# ==================== API ДЛЯ КАРТИ ====================

# Отримати статус країни
@app.route('/api/country-status/<country_name>')
@login_required
def get_country_status(country_name):
    country = VisitedCountry.query.filter_by(
        user_id=current_user.id,
        country_name=country_name
    ).first()

    if country:
        return {
            'status': country.status,
            'visit_date': country.visit_date.strftime('%Y-%m-%d') if country.visit_date else None,
            'notes': country.notes
        }
    else:
        return {'status': 'not_visited'}


# Встановити статус країни
@app.route('/api/country-status', methods=['POST'])
@login_required
def set_country_status():
    try:
        data = request.get_json()

        if not data:
            return {'success': False, 'error': 'No data provided'}, 400

        country_name = data.get('country_name')
        status = data.get('status')

        if not country_name or not status:
            return {'success': False, 'error': 'Missing country_name or status'}, 400

        # Шукаємо чи є вже запис
        country = VisitedCountry.query.filter_by(
            user_id=current_user.id,
            country_name=country_name
        ).first()

        if status == 'not_visited':
            # Видаляємо запис якщо скидаємо статус
            if country:
                db.session.delete(country)
                db.session.commit()
            return {'success': True, 'status': 'not_visited'}

        # Обробляємо дату
        visit_date = None
        if data.get('visit_date'):
            try:
                visit_date = datetime.strptime(data.get('visit_date'), '%Y-%m-%d').date()
            except:
                pass

        # Створюємо або оновлюємо
        if country:
            country.status = status
            country.visit_date = visit_date
            country.notes = data.get('notes', '')
        else:
            country = VisitedCountry(
                user_id=current_user.id,
                country_name=country_name,
                status=status,
                visit_date=visit_date,
                notes=data.get('notes', '')
            )
            db.session.add(country)

        db.session.commit()

        return {'success': True, 'status': status}

    except Exception as e:
        db.session.rollback()
        print(f"Error in set_country_status: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}, 500

# ==================== НАПРЯМКИ (МІСТА) ====================

# Додати місто до поїздки
@app.route('/trip/<int:trip_id>/destination/add', methods=['POST'])
@login_required
def add_destination(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        return {'success': False, 'error': 'Access denied'}, 403

    data = request.get_json()

    # Визначаємо порядок (останнє + 1)
    last_destination = TripDestination.query.filter_by(trip_id=trip_id).order_by(TripDestination.order.desc()).first()
    order = (last_destination.order + 1) if last_destination else 0

    new_destination = TripDestination(
        trip_id=trip_id,
        city=data.get('city'),
        country=data.get('country'),
        arrival_date=datetime.strptime(data.get('arrival_date'), '%Y-%m-%d').date() if data.get(
            'arrival_date') else None,
        departure_date=datetime.strptime(data.get('departure_date'), '%Y-%m-%d').date() if data.get(
            'departure_date') else None,
        order=order,
        notes=data.get('notes', '')
    )

    db.session.add(new_destination)
    db.session.commit()

    return {
        'success': True,
        'destination': {
            'id': new_destination.id,
            'city': new_destination.city,
            'country': new_destination.country,
            'arrival_date': new_destination.arrival_date.strftime('%d.%m.%Y') if new_destination.arrival_date else None,
            'departure_date': new_destination.departure_date.strftime(
                '%d.%m.%Y') if new_destination.departure_date else None,
            'order': new_destination.order
        }
    }


# Редагувати місто
@app.route('/trip/<int:trip_id>/destination/<int:destination_id>/edit', methods=['POST'])
@login_required
def edit_destination(trip_id, destination_id):
    destination = TripDestination.query.get_or_404(destination_id)

    if destination.trip.user_id != current_user.id:
        return {'success': False, 'error': 'Access denied'}, 403

    data = request.get_json()

    destination.city = data.get('city')
    destination.country = data.get('country')
    destination.arrival_date = datetime.strptime(data.get('arrival_date'), '%Y-%m-%d').date() if data.get(
        'arrival_date') else None
    destination.departure_date = datetime.strptime(data.get('departure_date'), '%Y-%m-%d').date() if data.get(
        'departure_date') else None
    destination.notes = data.get('notes', '')

    db.session.commit()

    return {'success': True}


# Видалити місто
@app.route('/trip/<int:trip_id>/destination/<int:destination_id>/delete', methods=['POST'])
@login_required
def delete_destination(trip_id, destination_id):
    destination = TripDestination.query.get_or_404(destination_id)

    if destination.trip.user_id != current_user.id:
        return {'success': False, 'error': 'Access denied'}, 403

    db.session.delete(destination)
    db.session.commit()

    return {'success': True}


# Змінити порядок міст
@app.route('/trip/<int:trip_id>/destinations/reorder', methods=['POST'])
@login_required
def reorder_destinations(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        return {'success': False, 'error': 'Access denied'}, 403

    data = request.get_json()
    destination_ids = data.get('destination_ids', [])

    for index, destination_id in enumerate(destination_ids):
        destination = TripDestination.query.get(destination_id)
        if destination and destination.trip_id == trip_id:
            destination.order = index

    db.session.commit()

    return {'success': True}

# ==================== ТРАНСПОРТ ====================

# Список транспорту
@app.route('/trip/<int:trip_id>/transport')
@login_required
def transport_list(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    transports = Transport.query.filter_by(trip_id=trip_id).order_by(Transport.departure_date).all()

    return render_template('transport_list.html',
                           trip=trip,
                           transports=transports)


# Додати транспорт
@app.route('/trip/<int:trip_id>/transport/new', methods=['GET', 'POST'])
@login_required
def new_transport(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        new_transport = Transport(
            trip_id=trip_id,
            type=request.form.get('type'),
            from_location=request.form.get('from_location'),
            to_location=request.form.get('to_location'),
            departure_date=datetime.strptime(request.form.get('departure_date'), '%Y-%m-%dT%H:%M'),
            arrival_date=datetime.strptime(request.form.get('arrival_date'), '%Y-%m-%dT%H:%M') if request.form.get(
                'arrival_date') else None,
            carrier=request.form.get('carrier'),
            ticket_number=request.form.get('ticket_number'),
            seat_number=request.form.get('seat_number'),
            cost=float(request.form.get('cost', 0)),
            booking_reference=request.form.get('booking_reference'),
            notes=request.form.get('notes')
        )

        db.session.add(new_transport)
        db.session.commit()

        flash('Транспорт додано!', 'success')
        return redirect(url_for('transport_list', trip_id=trip_id))

    return render_template('transport_form.html', trip=trip)


# Редагувати транспорт
@app.route('/trip/<int:trip_id>/transport/<int:transport_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_transport(trip_id, transport_id):
    transport = Transport.query.get_or_404(transport_id)

    if transport.trip.user_id != current_user.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        transport.type = request.form.get('type')
        transport.from_location = request.form.get('from_location')
        transport.to_location = request.form.get('to_location')
        transport.departure_date = datetime.strptime(request.form.get('departure_date'), '%Y-%m-%dT%H:%M')
        transport.arrival_date = datetime.strptime(request.form.get('arrival_date'),
                                                   '%Y-%m-%dT%H:%M') if request.form.get('arrival_date') else None
        transport.carrier = request.form.get('carrier')
        transport.ticket_number = request.form.get('ticket_number')
        transport.seat_number = request.form.get('seat_number')
        transport.cost = float(request.form.get('cost', 0))
        transport.booking_reference = request.form.get('booking_reference')
        transport.notes = request.form.get('notes')

        db.session.commit()

        flash('Транспорт оновлено!', 'success')
        return redirect(url_for('transport_list', trip_id=trip_id))

    return render_template('transport_form.html', trip=transport.trip, transport=transport)


# Видалити транспорт
@app.route('/trip/<int:trip_id>/transport/<int:transport_id>/delete', methods=['POST'])
@login_required
def delete_transport(trip_id, transport_id):
    transport = Transport.query.get_or_404(transport_id)

    if transport.trip.user_id != current_user.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(transport)
    db.session.commit()

    flash('Транспорт видалено', 'success')
    return redirect(url_for('transport_list', trip_id=trip_id))
# Видалити шаблон
@app.route('/templates/<int:template_id>/delete', methods=['POST'])
@login_required
def delete_template(template_id):
    template = TripTemplate.query.get_or_404(template_id)

    if template.user_id != current_user.id:
        flash('У вас немає доступу до цього шаблону', 'danger')
        return redirect(url_for('templates_list'))

    db.session.delete(template)
    db.session.commit()

    flash('Шаблон видалено', 'info')
    return redirect(url_for('templates_list'))

# Редагування поїздки
@app.route('/trip/<int:trip_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    # Перевірка доступу
    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        destination = request.form.get('destination', '').strip()
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        budget_str = request.form.get('budget', '0')

        # Валідація
        if not title or not destination:
            flash('Назва та напрямок є обов\'язковими', 'danger')
            return render_template('trip_edit.html', trip=trip)

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

            if end_date < start_date:
                flash('Дата закінчення не може бути раніше дати початку', 'danger')
                return render_template('trip_edit.html', trip=trip)

            budget = float(budget_str)
            if budget < 0:
                flash('Бюджет не може бути від\'ємним', 'danger')
                return render_template('trip_edit.html', trip=trip)

            # Оновлення даних
            trip.title = title
            trip.destination = destination
            trip.start_date = start_date
            trip.end_date = end_date
            trip.budget = budget

            db.session.commit()
            flash('Поїздку оновлено!', 'success')
            return redirect(url_for('view_trip', trip_id=trip.id))

        except ValueError:
            flash('Невірний формат дати або бюджету', 'danger')
            return render_template('trip_edit.html', trip=trip)

    return render_template('trip_edit.html', trip=trip)


# ==================== НОТАТКИ ====================

# Сторінка з нотатками та чеклістом
@app.route('/trip/<int:trip_id>/notes')
@login_required
def trip_notes(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    notes = TripNote.query.filter_by(trip_id=trip_id).order_by(TripNote.is_pinned.desc(),
                                                               TripNote.created_at.desc()).all()
    checklist_items = TripChecklist.query.filter_by(trip_id=trip_id).order_by(TripChecklist.is_completed,
                                                                              TripChecklist.due_date).all()

    # Групуємо чекліст по категоріях
    from collections import defaultdict
    checklist_by_category = defaultdict(list)
    for item in checklist_items:
        checklist_by_category[item.category or 'Інше'].append(item)

    # Статистика чекліста
    total_items = len(checklist_items)
    completed_items = len([item for item in checklist_items if item.is_completed])
    completion_percentage = (completed_items / total_items * 100) if total_items > 0 else 0

    return render_template('trip_notes.html',
                           trip=trip,
                           notes=notes,
                           checklist_by_category=dict(checklist_by_category),
                           total_items=total_items,
                           completed_items=completed_items,
                           completion_percentage=completion_percentage)


# Перемикач виконання пункту чекліста
@app.route('/trip/<int:trip_id>/checklist/<int:item_id>/toggle', methods=['POST'])
@login_required
def toggle_checklist_item(trip_id, item_id):
    item = TripChecklist.query.get_or_404(item_id)

    if item.trip.user_id != current_user.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    item.is_completed = not item.is_completed
    db.session.commit()

    return redirect(url_for('trip_notes', trip_id=trip_id))
# Додати нотатку
@app.route('/trip/<int:trip_id>/notes/add', methods=['POST'])
@login_required
def add_note(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    title = request.form.get('title')
    content = request.form.get('content')
    category = request.form.get('category', 'Загальне')
    is_pinned = request.form.get('is_pinned') == 'on'

    note = TripNote(
        title=title,
        content=content,
        category=category,
        is_pinned=is_pinned,
        trip_id=trip_id
    )

    db.session.add(note)
    db.session.commit()

    flash('Нотатку додано!', 'success')
    return redirect(url_for('trip_notes', trip_id=trip_id))


# Редагувати нотатку
@app.route('/trip/<int:trip_id>/notes/<int:note_id>/edit', methods=['POST'])
@login_required
def edit_note(trip_id, note_id):
    note = TripNote.query.get_or_404(note_id)

    if note.trip.user_id != current_user.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    note.title = request.form.get('title')
    note.content = request.form.get('content')
    note.category = request.form.get('category')
    note.is_pinned = request.form.get('is_pinned') == 'on'
    note.updated_at = datetime.now()

    db.session.commit()

    flash('Нотатку оновлено!', 'success')
    return redirect(url_for('trip_notes', trip_id=trip_id))


# Видалити нотатку
@app.route('/trip/<int:trip_id>/notes/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(trip_id, note_id):
    note = TripNote.query.get_or_404(note_id)

    if note.trip.user_id != current_user.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(note)
    db.session.commit()

    flash('Нотатку видалено', 'info')
    return redirect(url_for('trip_notes', trip_id=trip_id))


# ==================== ЧЕКЛІСТ ====================

# Додати пункт чекліста
@app.route('/trip/<int:trip_id>/checklist/add', methods=['POST'])
@login_required
def add_checklist_item(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    item = request.form.get('item')
    category = request.form.get('category', 'Інше')
    due_date_str = request.form.get('due_date')
    notes = request.form.get('notes')

    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None

    checklist_item = TripChecklist(
        item=item,
        category=category,
        due_date=due_date,
        notes=notes,
        trip_id=trip_id
    )

    db.session.add(checklist_item)
    db.session.commit()

    flash('Пункт додано до чекліста!', 'success')
    return redirect(url_for('trip_notes', trip_id=trip_id))



# Видалити пункт чекліста
@app.route('/trip/<int:trip_id>/checklist/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_checklist_item(trip_id, item_id):
    item = TripChecklist.query.get_or_404(item_id)

    if item.trip.user_id != current_user.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(item)
    db.session.commit()

    flash('Пункт видалено', 'info')
    return redirect(url_for('trip_notes', trip_id=trip_id))

# Видалення поїздки
@app.route('/trip/<int:trip_id>/delete', methods=['POST'])
@login_required
def delete_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    # Перевірка доступу
    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(trip)
    db.session.commit()

    flash('Поїздку видалено', 'info')
    return redirect(url_for('dashboard'))


# Додавання активності
@app.route('/trip/<int:trip_id>/activity/new', methods=['GET', 'POST'])
@login_required
def new_activity(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        date_str = request.form.get('date')
        time = request.form.get('time', '').strip()
        location = request.form.get('location', '').strip()
        cost_str = request.form.get('cost', '0')
        category = request.form.get('category', 'general')

        if not title or not date_str:
            flash('Назва та дата є обов\'язковими', 'danger')
            return render_template('activity_form.html', trip=trip)

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')

            # Перевірка, чи дата в межах поїздки
            if date.date() < trip.start_date.date() or date.date() > trip.end_date.date():
                flash('Дата активності повинна бути в межах дат поїздки', 'danger')
                return render_template('activity_form.html', trip=trip)

            cost = float(cost_str)

            new_activity = Activity(
                title=title,
                description=description,
                date=date,
                time=time,
                location=location,
                cost=cost,
                category=category,
                trip_id=trip.id
            )

            db.session.add(new_activity)
            db.session.commit()

            flash('Активність додано!', 'success')
            return redirect(url_for('view_trip', trip_id=trip.id))

        except ValueError:
            flash('Невірний формат даних', 'danger')
            return render_template('activity_form.html', trip=trip)

    return render_template('activity_form.html', trip=trip)


# Редагування активності
@app.route('/trip/<int:trip_id>/activity/<int:activity_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_activity(trip_id, activity_id):
    trip = Trip.query.get_or_404(trip_id)
    activity = Activity.query.get_or_404(activity_id)

    if trip.user_id != current_user.id or activity.trip_id != trip.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        date_str = request.form.get('date')
        time = request.form.get('time', '').strip()
        location = request.form.get('location', '').strip()
        cost_str = request.form.get('cost', '0')
        category = request.form.get('category', 'general')

        if not title or not date_str:
            flash('Назва та дата є обов\'язковими', 'danger')
            return render_template('activity_form.html', trip=trip, activity=activity)

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')

            if date.date() < trip.start_date.date() or date.date() > trip.end_date.date():
                flash('Дата активності повинна бути в межах дат поїздки', 'danger')
                return render_template('activity_form.html', trip=trip, activity=activity)

            cost = float(cost_str)

            activity.title = title
            activity.description = description
            activity.date = date
            activity.time = time
            activity.location = location
            activity.cost = cost
            activity.category = category

            db.session.commit()

            flash('Активність оновлено!', 'success')
            return redirect(url_for('view_trip', trip_id=trip.id))

        except ValueError:
            flash('Невірний формат даних', 'danger')
            return render_template('activity_form.html', trip=trip, activity=activity)

    return render_template('activity_form.html', trip=trip, activity=activity)


# Видалення активності
@app.route('/trip/<int:trip_id>/activity/<int:activity_id>/delete', methods=['POST'])
@login_required
def delete_activity(trip_id, activity_id):
    trip = Trip.query.get_or_404(trip_id)
    activity = Activity.query.get_or_404(activity_id)

    if trip.user_id != current_user.id or activity.trip_id != trip.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(activity)
    db.session.commit()

    flash('Активність видалено', 'info')
    return redirect(url_for('view_trip', trip_id=trip.id))


# Позначити активність як виконану
@app.route('/trip/<int:trip_id>/activity/<int:activity_id>/toggle', methods=['POST'])
@login_required
def toggle_activity(trip_id, activity_id):
    trip = Trip.query.get_or_404(trip_id)
    activity = Activity.query.get_or_404(activity_id)

    if trip.user_id != current_user.id or activity.trip_id != trip.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    activity.completed = not activity.completed
    db.session.commit()

    return redirect(url_for('view_trip', trip_id=trip.id))


# Статистика поїздки
@app.route('/trip/<int:trip_id>/statistics')
@login_required
def trip_statistics(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    # Витрати з активностей
    activities = Activity.query.filter_by(trip_id=trip.id).all()
    total_activities_cost = sum(activity.cost for activity in activities)

    # Витрати на готелі
    accommodations = Accommodation.query.filter_by(trip_id=trip.id).all()
    total_accommodation_cost = sum(acc.total_price for acc in accommodations)

    # Загальні витрати
    total_spent = total_activities_cost + total_accommodation_cost
    remaining_budget = trip.budget - total_spent
    budget_percentage = (total_spent / trip.budget * 100) if trip.budget > 0 else 0

    # Витрати по категоріях активностей
    category_costs = {}
    for activity in activities:
        if activity.category in category_costs:
            category_costs[activity.category] += activity.cost
        else:
            category_costs[activity.category] = activity.cost

    # Додаємо готелі як окрему категорію
    if total_accommodation_cost > 0:
        category_costs['accommodation_hotels'] = total_accommodation_cost

    # Відсоток виконаних активностей
    completed_activities = len([a for a in activities if a.completed])
    completion_rate = (completed_activities / len(activities) * 100) if activities else 0

    # Назви категорій українською
    category_names = {
        'transport': '🚗 Транспорт',
        'food': '🍽️ Їжа',
        'activity': '🎡 Розваги',
        'accommodation': '🏨 Додаткове проживання',
        'shopping': '🛍️ Покупки',
        'general': '🎯 Загальне',
        'accommodation_hotels': '🏨 Готелі'
    }

    # Підготовка даних для діаграми
    category_data = []
    for category, cost in category_costs.items():
        percentage = (cost / total_spent * 100) if total_spent > 0 else 0
        category_data.append({
            'name': category_names.get(category, category),
            'cost': cost,
            'percentage': percentage
        })

    # Сортуємо за вартістю
    category_data.sort(key=lambda x: x['cost'], reverse=True)

    # Детальний список витрат (активності + готелі)
    expense_list = []

    # Додаємо активності
    for activity in activities:
        expense_list.append({
            'type': 'activity',
            'date': activity.date,
            'title': activity.title,
            'category': category_names.get(activity.category, activity.category),
            'cost': activity.cost
        })

    # Додаємо готелі
    for acc in accommodations:
        nights = (acc.check_out - acc.check_in).days
        expense_list.append({
            'type': 'accommodation',
            'date': acc.check_in,
            'title': f"{acc.name} ({nights} ночей)",
            'category': '🏨 Готелі',
            'cost': acc.total_price
        })

    # Сортуємо за датою
    expense_list.sort(key=lambda x: x['date'])

    return render_template('trip_statistics.html',
                           trip=trip,
                           total_spent=total_spent,
                           total_activities_cost=total_activities_cost,
                           total_accommodation_cost=total_accommodation_cost,
                           remaining_budget=remaining_budget,
                           budget_percentage=budget_percentage,
                           category_data=category_data,
                           completion_rate=completion_rate,
                           expense_list=expense_list,
                           activities_count=len(activities),
                           completed_count=completed_activities,
                           accommodations_count=len(accommodations))



# Packing List - перегляд
@app.route('/trip/<int:trip_id>/packing')
@login_required
def packing_list(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    # Групуємо речі по категоріях
    items_by_category = {
        'clothes': [],
        'toiletries': [],
        'electronics': [],
        'documents': [],
        'other': []
    }

    for item in trip.packing_items:
        if item.category in items_by_category:
            items_by_category[item.category].append(item)

    # Статистика
    total_items = len(trip.packing_items)
    packed_items = len([item for item in trip.packing_items if item.is_packed])
    packing_progress = (packed_items / total_items * 100) if total_items > 0 else 0

    return render_template('packing_list.html',
                           trip=trip,
                           items_by_category=items_by_category,
                           total_items=total_items,
                           packed_items=packed_items,
                           packing_progress=packing_progress)


# Додавання речі
@app.route('/trip/<int:trip_id>/packing/add', methods=['POST'])
@login_required
def add_packing_item(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    name = request.form.get('name', '').strip()
    category = request.form.get('category', 'other')
    quantity = int(request.form.get('quantity', 1))

    if not name:
        flash('Введіть назву речі', 'danger')
        return redirect(url_for('packing_list', trip_id=trip.id))

    new_item = PackingItem(
        name=name,
        category=category,
        quantity=quantity,
        trip_id=trip.id
    )

    db.session.add(new_item)
    db.session.commit()

    flash('Річ додано до списку!', 'success')
    return redirect(url_for('packing_list', trip_id=trip.id))


# Позначити як зібрану
@app.route('/trip/<int:trip_id>/packing/<int:item_id>/toggle', methods=['POST'])
@login_required
def toggle_packing_item(trip_id, item_id):
    trip = Trip.query.get_or_404(trip_id)
    item = PackingItem.query.get_or_404(item_id)

    if trip.user_id != current_user.id or item.trip_id != trip.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    item.is_packed = not item.is_packed
    db.session.commit()

    return redirect(url_for('packing_list', trip_id=trip.id))


# Видалення речі
@app.route('/trip/<int:trip_id>/packing/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_packing_item(trip_id, item_id):
    trip = Trip.query.get_or_404(trip_id)
    item = PackingItem.query.get_or_404(item_id)

    if trip.user_id != current_user.id or item.trip_id != trip.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(item)
    db.session.commit()

    flash('Річ видалено зі списку', 'info')
    return redirect(url_for('packing_list', trip_id=trip.id))


# Очистити список зібраних речей
@app.route('/trip/<int:trip_id>/packing/clear-packed', methods=['POST'])
@login_required
def clear_packed_items(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    PackingItem.query.filter_by(trip_id=trip.id, is_packed=True).delete()
    db.session.commit()

    flash('Зібрані речі видалено зі списку', 'info')
    return redirect(url_for('packing_list', trip_id=trip.id))


# Модель шаблону поїздки
class TripTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    destination_type = db.Column(db.String(100))  # Пляж, Гори, Місто тощо
    duration_days = db.Column(db.Integer)
    budget_estimate = db.Column(db.Float)
    currency = db.Column(db.String(3), default='UAH')
    is_public = db.Column(db.Boolean, default=False)  # Публічний шаблон чи особистий
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    source_trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=True)  # З якої поїздки створено
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Зберігаємо дані як JSON
    activities_template = db.Column(db.Text)  # JSON список активностей
    packing_template = db.Column(db.Text)  # JSON списку речей

    user = db.relationship('User', backref='templates')

# Список готелів
@app.route('/trip/<int:trip_id>/accommodations')
@login_required
def accommodations_list(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    accommodations = Accommodation.query.filter_by(trip_id=trip.id).order_by(Accommodation.check_in).all()

    # Статистика
    total_cost = sum(acc.total_price for acc in accommodations)
    total_nights = sum((acc.check_out - acc.check_in).days for acc in accommodations)

    return render_template('accommodations_list.html',
                           trip=trip,
                           accommodations=accommodations,
                           total_cost=total_cost,
                           total_nights=total_nights)


# Додавання готелю
@app.route('/trip/<int:trip_id>/accommodations/add', methods=['GET', 'POST'])
@login_required
def add_accommodation(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        check_in_str = request.form.get('check_in')
        check_out_str = request.form.get('check_out')
        price_per_night = float(request.form.get('price_per_night', 0))
        booking_reference = request.form.get('booking_reference', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        website = request.form.get('website', '').strip()
        notes = request.form.get('notes', '').strip()
        rating = float(request.form.get('rating', 0))
        amenities = request.form.get('amenities', '').strip()
        image_url = request.form.get('image_url', '').strip()
        booking_status = request.form.get('booking_status', 'pending')

        if not name or not check_in_str or not check_out_str:
            flash('Назва та дати є обов\'язковими', 'danger')
            return render_template('accommodation_form.html', trip=trip)

        try:
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d')
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d')

            if check_out <= check_in:
                flash('Дата виїзду має бути пізніше дати заїзду', 'danger')
                return render_template('accommodation_form.html', trip=trip)

            # Обчислюємо загальну вартість
            nights = (check_out - check_in).days
            total_price = price_per_night * nights

            new_accommodation = Accommodation(
                name=name,
                address=address,
                check_in=check_in,
                check_out=check_out,
                price_per_night=price_per_night,
                total_price=total_price,
                booking_reference=booking_reference,
                phone=phone,
                email=email,
                website=website,
                notes=notes,
                rating=rating,
                amenities=amenities,
                image_url=image_url,
                booking_status=booking_status,
                trip_id=trip.id
            )

            db.session.add(new_accommodation)
            db.session.commit()

            flash('Готель додано!', 'success')
            return redirect(url_for('accommodations_list', trip_id=trip.id))

        except ValueError:
            flash('Невірний формат даних', 'danger')
            return render_template('accommodation_form.html', trip=trip)

    return render_template('accommodation_form.html', trip=trip)


# Редагування готелю
@app.route('/trip/<int:trip_id>/accommodations/<int:acc_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_accommodation(trip_id, acc_id):
    trip = Trip.query.get_or_404(trip_id)
    accommodation = Accommodation.query.get_or_404(acc_id)

    if trip.user_id != current_user.id or accommodation.trip_id != trip.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        accommodation.name = request.form.get('name', '').strip()
        accommodation.address = request.form.get('address', '').strip()
        check_in_str = request.form.get('check_in')
        check_out_str = request.form.get('check_out')
        accommodation.price_per_night = float(request.form.get('price_per_night', 0))
        accommodation.booking_reference = request.form.get('booking_reference', '').strip()
        accommodation.phone = request.form.get('phone', '').strip()
        accommodation.email = request.form.get('email', '').strip()
        accommodation.website = request.form.get('website', '').strip()
        accommodation.notes = request.form.get('notes', '').strip()
        accommodation.rating = float(request.form.get('rating', 0))
        accommodation.amenities = request.form.get('amenities', '').strip()
        accommodation.image_url = request.form.get('image_url', '').strip()
        accommodation.booking_status = request.form.get('booking_status', 'pending')

        try:
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d')
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d')

            if check_out <= check_in:
                flash('Дата виїзду має бути пізніше дати заїзду', 'danger')
                return render_template('accommodation_form.html', trip=trip, accommodation=accommodation)

            accommodation.check_in = check_in
            accommodation.check_out = check_out

            # Перерахунок загальної вартості
            nights = (check_out - check_in).days
            accommodation.total_price = accommodation.price_per_night * nights

            db.session.commit()

            flash('Готель оновлено!', 'success')
            return redirect(url_for('accommodations_list', trip_id=trip.id))

        except ValueError:
            flash('Невірний формат даних', 'danger')
            return render_template('accommodation_form.html', trip=trip, accommodation=accommodation)

    return render_template('accommodation_form.html', trip=trip, accommodation=accommodation)


# Видалення готелю
@app.route('/trip/<int:trip_id>/accommodations/<int:acc_id>/delete', methods=['POST'])
@login_required
def delete_accommodation(trip_id, acc_id):
    trip = Trip.query.get_or_404(trip_id)
    accommodation = Accommodation.query.get_or_404(acc_id)

    if trip.user_id != current_user.id or accommodation.trip_id != trip.id:
        flash('У вас немає доступу', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(accommodation)
    db.session.commit()

    flash('Готель видалено', 'info')
    return redirect(url_for('accommodations_list', trip_id=trip.id))


# Пошук готелів (заготовка для API)
@app.route('/trip/<int:trip_id>/accommodations/search')
@login_required
def search_accommodations(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != current_user.id:
        flash('У вас немає доступу до цієї поїздки', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('accommodations_search.html', trip=trip)


# Профіль користувача
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()

        if not username or not email:
            flash('Ім\'я та email є обов\'язковими', 'danger')
            return render_template('user_profile.html')

        # Перевірка унікальності email (якщо змінився)
        if email != current_user.email:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Цей email вже використовується', 'danger')
                return render_template('user_profile.html')

        # Перевірка унікальності username (якщо змінився)
        if username != current_user.username:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Це ім\'я користувача вже зайняте', 'danger')
                return render_template('user_profile.html')

        # Оновлення даних
        current_user.username = username
        current_user.email = email

        # Зміна паролю (якщо вказано)
        new_password = request.form.get('new_password', '').strip()
        if new_password:
            current_password = request.form.get('current_password', '').strip()

            if not check_password_hash(current_user.password, current_password):
                flash('Невірний поточний пароль', 'danger')
                return render_template('user_profile.html')

            current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')

        db.session.commit()
        flash('Профіль оновлено!', 'success')
        return redirect(url_for('user_profile'))

    # Статистика користувача
    total_trips = Trip.query.filter_by(user_id=current_user.id).count()
    total_activities = Activity.query.join(Trip).filter(Trip.user_id == current_user.id).count()
    total_spent = db.session.query(db.func.sum(Activity.cost)).join(Trip).filter(
        Trip.user_id == current_user.id).scalar() or 0

    # Останні поїздки
    recent_trips = Trip.query.filter_by(user_id=current_user.id).order_by(Trip.created_at.desc()).limit(5).all()

    return render_template('user_profile.html',
                           total_trips=total_trips,
                           total_activities=total_activities,
                           total_spent=total_spent,
                           recent_trips=recent_trips)


# Видалення акаунту
@app.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    user_id = current_user.id

    # Видаляємо користувача (всі пов'язані дані видаляться автоматично через cascade)
    User.query.filter_by(id=user_id).delete()
    db.session.commit()

    logout_user()
    flash('Ваш акаунт було видалено', 'info')
    return redirect(url_for('index'))

# ============= ЗАПУСК ДОДАТКУ =============

if __name__ == '__main__':
    # Створення всіх таблиць в базі даних
    with app.app_context():
        db.create_all()
        print("База даних створена успішно!")

    # Запуск сервера
    app.run(debug=True, host='0.0.0.0', port=5001)