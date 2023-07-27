from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import secrets
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import os

dotenv_path = Path('.\\templates')
print(dotenv_path)
load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
# app.config["SECRET_KEY"] = secrets.token_hex()
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# f you want function or variable accessible in all templates (globally).
# You can add them during flask application initialization to app.jinja_env.globals dict, 
# like:app.jinja_env.globals['func'] = f
# Source: https://stackoverflow.com/questions/44206613/how-to-import-and-call-a-python-function-in-a-jinja-template
app.jinja_env.globals["curr_time"] = datetime.now().year # add current date to jinja environment global variables - use in the footer

# Configuring authentication
login_manager = LoginManager()
login_manager.init_app(app)

gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False, base_url=None)

##CONFIGURE TABLES

################# Bidirectional relationships #####################
# Need to add relationship variable to both parent and child class
# relationship first argument = class name, back_populates - name of variable in other class using the relationship method 
# Add foreign key to the child using the tablename.id
################# Single direction relationship - One to many #####
# Only parent has relationship bariable to child

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    
    # Relationship BlogPost and User
    # Create foreign key: "users" refers to tablename of User class 
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Create relationship to User object, "posts" refers to posts property within class
    author = relationship("User", back_populates="posts")
    
    # Relationship BlogPost and Comments - parent
    blog_comments = relationship("Comment", back_populates="blog_post")

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key = True)
    email = db.Column(db.String(100), unique = True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    
    # Replationship BlogPost and User - parent
    posts = relationship("BlogPost", back_populates="author") # refer to author attribute in BlogPost class
    
    # Relationship User and Comment tables - parent
    comments = relationship("Comment", back_populates="comment_author")
    
class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False) # use text instead of String - more characters storable
    
    # Relationship between User and Comment tables - child
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    
    # Relationship between BlogPost and Comment - child
    blog_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    blog_post = relationship("BlogPost", back_populates="blog_comments")
    
    
@app.errorhandler(403)
def admin_only(function):
    @wraps(function)
    def wrapper_function(*args, **kwargs):
        if current_user.id ==1:
            return function(*args, **kwargs)
        else:
            return abort(403)
            
    return wrapper_function

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    registration = RegisterForm()
    if registration.validate_on_submit():
        new_user = User()
        new_user.email = registration.email.data
        new_user.password = generate_password_hash(registration.password.data, method='pbkdf2:sha256', salt_length=8)
        new_user.name = registration.name.data
        if User.query.filter_by(email=new_user.email).first(): # must use .first() else won't give None if email not in database
            # Check whether email already exists in the database
            flash("Email already exists, please login with that email")
            return redirect(url_for("login"))
        else:
            db.session.add(new_user)
            db.session.commit()        
            login_user(new_user)
            return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=registration)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=request.form.get("email")).first()
        if not user: 
                flash("Email does not exist, please try again")
                return redirect(url_for("login"))
            
        else:
            given_password = request.form.get("password")
            
            if check_password_hash(user.password, given_password):
                login_user(user)
                return redirect(url_for("get_all_posts"))
            
            else:
                # return message if password wrong
                flash("Incorrect password, try again")
            return redirect(url_for("login"))
    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods = ["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    print(requested_post.img_url)
    form = CommentForm()
    if form.validate_on_submit():
        new_comment = Comment()
        new_comment.text = form.body.data
        new_comment.blog_post = requested_post
        new_comment.comment_author = current_user
        if current_user.is_authenticated:
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            flash("You must log in to comment")
            return redirect(url_for("login"))
    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author= current_user, # must be class now as defined using the relationship method between the 2 tables
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        
        return redirect(url_for("get_all_posts"))
    
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
