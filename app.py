from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

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
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travel_planner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


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
            login_user(user)
            flash('Успішний вхід!', 'success')
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

# Конвертер валют
@app.route('/converter')
@login_required
def currency_converter():
    return render_template('currency_converter.html',
                          currencies=CURRENCY_RATES.keys(),
                          currency_rates=CURRENCY_RATES,
                          currency_symbols=CURRENCY_SYMBOLS)
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

        flash('Поїздку створено!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('new_trip.html',
                           currencies=CURRENCY_RATES.keys(),
                           currency_symbols=CURRENCY_SYMBOLS)

    return render_template('trip.html')


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

    return render_template('trip_view.html',
                           trip=trip,
                           activities_by_day=activities_by_day,
                           currency_rates=CURRENCY_RATES,
                           currency_symbols=CURRENCY_SYMBOLS)


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