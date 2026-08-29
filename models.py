from datetime import datetime

from extensions import db

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from flask_login import UserMixin


# ============================================================
# USER
# ============================================================

class User(
    UserMixin,
    db.Model
):

    __tablename__ = 'users'


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )


    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )


    password_hash = db.Column(
        db.String(255),
        nullable=False
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    language = db.Column(
        db.String(10),
        default='es'
    )


    # ========================================================
    # RELACIONES
    # ========================================================

    expenses = db.relationship(
        'Expense',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan'
    )


    budgets = db.relationship(
        'Budget',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan'
    )


    goals = db.relationship(
        'FinancialGoal',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan'
    )


    insights = db.relationship(
        'FinancialInsight',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan'
    )


    market_posts = db.relationship(
        'MarketPost',
        backref='author',
        lazy=True,
        cascade='all, delete-orphan'
    )


    # ========================================================
    # PASSWORD
    # ========================================================

    def set_password(
        self,
        password
    ):

        self.password_hash = generate_password_hash(

            password,

            method='pbkdf2:sha256'

        )


    def check_password(
        self,
        password
    ):

        return check_password_hash(

            self.password_hash,

            password

        )


    # ========================================================
    # FLASK LOGIN
    # ========================================================

    def get_id(
        self
    ):

        return str(
            self.id
        )


    # ========================================================
    # REPRESENTACIÓN
    # ========================================================

    def __repr__(
        self
    ):

        return f"<User {self.username}>"


# ============================================================
# EXPENSE
# ============================================================

class Expense(
    db.Model
):

    __tablename__ = 'expenses'


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'users.id'
        ),
        nullable=False
    )


    amount = db.Column(
        db.Float,
        nullable=False
    )


    currency = db.Column(
        db.String(8),
        default='GTQ'
    )


    description = db.Column(
        db.String(512)
    )


    merchant = db.Column(
        db.String(255)
    )


    category = db.Column(
        db.String(80)
    )


    payment_method = db.Column(
        db.String(80)
    )


    payment_status = db.Column(
        db.String(80)
    )


    expense_date = db.Column(
        db.Date
    )


    receipt_image_url = db.Column(
        db.String(255)
    )


    ai_generated = db.Column(
        db.Boolean,
        default=False
    )


    ai_confidence = db.Column(
        db.Float
    )


    transaction_type = db.Column(
        db.String(16),
        default='expense',
        nullable=False
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    updated_at = db.Column(
        db.DateTime,
        onupdate=datetime.utcnow
    )


    def __repr__(
        self
    ):

        return (
            f"<Expense "
            f"{self.amount} "
            f"{self.currency} "
            f"- {self.category}>"
        )


# ============================================================
# BUDGET
# ============================================================

class Budget(
    db.Model
):

    __tablename__ = 'budgets'


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'users.id'
        ),
        nullable=False
    )


    category = db.Column(
        db.String(80),
        nullable=False
    )


    amount = db.Column(
        db.Float,
        nullable=False
    )


    month = db.Column(
        db.Integer,
        nullable=False
    )


    year = db.Column(
        db.Integer,
        nullable=False
    )


# ============================================================
# FINANCIAL GOAL
# ============================================================

class FinancialGoal(
    db.Model
):

    __tablename__ = 'financial_goals'


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'users.id'
        ),
        nullable=False
    )


    name = db.Column(
        db.String(255),
        nullable=False
    )


    target_amount = db.Column(
        db.Float,
        nullable=False
    )


    current_amount = db.Column(
        db.Float,
        default=0.0
    )


    target_date = db.Column(
        db.Date
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# ============================================================
# FINANCIAL INSIGHT
# ============================================================

class FinancialInsight(
    db.Model
):

    __tablename__ = 'financial_insights'


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'users.id'
        ),
        nullable=False
    )


    insight_type = db.Column(
        db.String(80)
    )


    title = db.Column(
        db.String(255)
    )


    description = db.Column(
        db.Text
    )


    severity = db.Column(
        db.String(20)
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    is_read = db.Column(
        db.Boolean,
        default=False
    )


    def __repr__(
        self
    ):

        return (
            f"<Insight "
            f"{self.title} "
            f"({self.severity})>"
        )


# ============================================================
# MARKET POST
# ============================================================

class MarketPost(
    db.Model
):

    __tablename__ = 'marketnexo_posts'


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'users.id'
        ),
        nullable=False
    )


    product = db.Column(
        db.String(255),
        nullable=False
    )


    description = db.Column(
        db.Text,
        nullable=False
    )


    email = db.Column(
        db.String(120),
        nullable=False
    )


    phone = db.Column(
        db.String(40)
    )


    whatsapp = db.Column(
        db.String(40)
    )


    social_media = db.Column(
        db.String(255)
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )


    def __repr__(
        self
    ):

        return (
            f"<MarketPost "
            f"{self.product}>"
        )
