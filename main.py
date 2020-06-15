import os
from flask import Flask, flash, jsonify, redirect, render_template, request, session, app, url_for, flash
from bs4 import BeautifulSoup
import requests
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import InputRequired, Email, Length
from datetime import datetime
from flask import g

app = Flask(__name__)
app.config['SECRET_KEY'] = 'THISISASOCIETY'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLAlCHEMY_TRACK_MODIFICATIONS'] =False
Bootstrap(app)
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

current_match = None

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(15), unique=True)
    email = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(80))
    wishlist = db.relationship('Item', backref='buyer', lazy=True)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    store = db.Column(db.Text, nullable=False)
    link = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=80)])
    remember = BooleanField('Remember me')

class RegisterForm(FlaskForm):
    email = StringField('email', validators=[InputRequired(), Email(message="Invalid Email"), Length(max=100)])
    username = StringField('username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])

def itemDict(item):
    dict = {
        "image_link": item.find('div', class_='pic').find('img')['data-src'],
        "name": item.find('strong').text,
        "shop_name": item.find('div', class_='offer').find('img')['alt'],
        "price": item.find('div', class_='offer').find('a', class_='price').text,
        "link": item.find('div', class_='offer').find('a', class_='price')['href']
    }
    return dict

current_match =  None

@app.route('/', methods=["GET", "POST"])
@app.route('/index')
@login_required
def index():
    if request.method =="GET":
        return render_template('home.html', name = current_user.username)
    else:
        name = list(request.form.get("name"))
        # match counter to check if words match
        matches = 0
        counter = 0

        # replace spaces with hyphens for url link
        for letter in name:
            if letter == ' ':
                name[counter] = '-'
            counter += 1
        name = ''.join(name)

        source = requests.get(f'https://www.getprice.com.au/buy-best-{name}.htm').text

        name = name.split('-')

        name_length = len(name)
        #compiles source into lxml file
        soup = BeautifulSoup(source, 'lxml')

        # list of items in HTML
        items_source = soup.findAll('div', class_='list-item-compare li-product')

        # list for item dicts to be stored in
        items = []

        # creates an item dictionary for each item and stores it in items = []
        for item in items_source:
            items.append(itemDict(item))

        for item in items:
            # buffer to store item name from items
            item_buffer = list(set(item['name'].split(' ')))
            print(f'buffer --> {item_buffer}/n')
            matches = 0
            # iterates over every word in item_buffer
            for i in item_buffer:
                # iterates over every word in name
                for j in name:
                    if (i.lower() == j.lower()):
                        matches += 1
            if matches == name_length:
                global current_match
                current_match = item
                print(current_match)
                return render_template('lowest.html', item=item)
        return render_template('notfound.html')

@app.route('/about', methods=['GET', 'POST'])
@login_required
def about():
    items = []
    global current_match
    user = User.query.get(current_user.get_id())
    if request.method == 'POST':
        new_item = current_match
        item = Item(name=new_item['name'], store=new_item['shop_name'], link=new_item['link'], user_id=current_user.get_id())
        user_id = current_user.get_id()
        item_name = new_item['name']
        checkItem = db.engine.execute(f'SELECT * FROM item WHERE user_id=:user_id AND name=:item_name;', user_id=user_id, item_name=item_name)
        if len(checkItem.fetchall()) == 0:
            db.session.add(item)
            db.session.commit()
        items = user.wishlist
        return render_template('about.html', items=items, quantity=len(items))
    else:
        return render_template('about.html', items=items, quantity=len(items))

@app.route('/wishlist', methods=['POST', 'GET'])
@login_required
def wishlist():
    global current_match
    user = User.query.get(current_user.get_id())
    if request.method == 'POST':
        item_name = request.form.get("delete")
        print(item_name)
        user_id = current_user.get_id()
        # if item_name not None:
        db.engine.execute(f'DELETE FROM item WHERE user_id=:user_id AND name=:item_name;', user_id=user_id, item_name=item_name)
        items = user.wishlist
        return render_template('about.html', items=items, quantity=len(items))
    else:
        items = user.wishlist
        return render_template('about.html', items=items, quantity=len(items))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegisterForm()

    if form.validate_on_submit():
        new_user = User(username=form.username.data, email=form.email.data, password=generate_password_hash(form.password.data, method='sha256'))
        db.session.add(new_user)
        db.session.commit()

        form = LoginForm()
        message = "You have successfully signed up!"
        return render_template('login.html', form=form, message=message)

    return render_template('signup.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    user = User.query.filter_by(username=form.username.data).first()
    if user:
        if check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            return redirect(url_for('index'))

        form = LoginForm()
        message = "Incorrect password or username!"
        return render_template('login.html', form=form, message=message)

    if form.validate_on_submit():
        return '<h1>' + form.username.data + ' ' + form.password.data + '</h1>'

    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
