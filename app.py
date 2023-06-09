import os

from flask import Flask, render_template, request, flash, redirect, session, g
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError

from forms import UserAddForm, LoginForm, MessageForm, ProfileEditForm
from models import db, connect_db, User, Message, Likes

CURR_USER_KEY = "curr_user"

app = Flask(__name__)

# Get DB_URI from environ variable (useful for production/testing) or,
# if not set there, use development local db.
app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL', 'postgresql:///warbler'))

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = True
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "it's a secret")
toolbar = DebugToolbarExtension(app)

connect_db(app)


##############################################################################
# User signup/login/logout


@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])

    else:
        g.user = None


def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id


def do_logout():
    """Logout user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]





@app.route('/login', methods=["GET"])
def login_form():
    """Handle user login."""

    form = LoginForm()
    return render_template('users/login.html', form=form)



@app.route('/login', methods=["POST"])
def login():
    """Handle user login."""

    form = LoginForm()
    user = User.authenticate(form.username.data, form.password.data)

    if user:
        do_login(user)
        flash(f"Hello, {user.username}!", "success")
        return redirect("/")

    flash("Invalid credentials.", 'danger')






##############################################################################
# General user routes:

@app.route('/users')
def list_users():
    """Page with listing of users.

    Can take a 'q' param in querystring to search by that username.
    """

    search = request.args.get('q')

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template('users/index.html', users=users)


@app.route('/users/<int:user_id>')
def users_show(user_id):
    """Show user profile."""

    user = User.query.get_or_404(user_id)

    # snagging messages in order from the database;
    # user.messages won't be in order by default
    messages = (Message
                .query
                .filter(Message.user_id == user_id)
                .order_by(Message.timestamp.desc())
                .limit(100)
                .all())
    
    likes = Likes.query.filter(Likes.user_id == g.user.id).all()
    list_of_liked_message_ids = []
    for like in likes:
        list_of_liked_message_ids.append(like.message_id)
    num_likes = len(list_of_liked_message_ids)

    return render_template('users/show.html', user=user, messages=messages, num_likes=num_likes)


@app.route('/users/<int:user_id>/following')
def show_following(user_id):
    """Show list of people this user is following."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/following.html', user=user)


@app.route('/users/<int:user_id>/followers')
def users_followers(user_id):
    """Show list of followers of this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/followers.html', user=user)



@app.route('/users/<int:user_id>/likes')
def user_likes(user_id):
    """Show list of liked messages."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    likes = Likes.query.filter(Likes.user_id == g.user.id).all()
    list_of_liked_message_ids = []
    for like in likes:
        list_of_liked_message_ids.append(like.message_id)
   
    liked_messages = (Message
                    .query
                    .filter(Message.id.in_(list_of_liked_message_ids))
                    .order_by(Message.timestamp.desc())
                    .all())
    return render_template('users/likes.html', user=user, liked_messages=liked_messages)




@app.route('/users/follow/<int:follow_id>', methods=['POST'])
def add_follow(follow_id):
    """Add a follow for the currently-logged-in user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get_or_404(follow_id)
    g.user.following.append(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/stop-following/<int:follow_id>', methods=['POST'])
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get(follow_id)
    g.user.following.remove(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")





@app.route('/users/delete', methods=["POST"])
def delete_user():
    """Delete user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")
    curr_user = g.user
    messages_to_delete = (Message
                .query
                .filter(Message.user_id == curr_user.id)
                .all())
    for message in messages_to_delete:
        db.session.delete(message)

    db.session.commit()

    db.session.delete(curr_user)
    db.session.commit()

    do_logout()

    return redirect("/signup")


##############################################################################
# Messages routes:






@app.route('/messages/new', methods=["GET"])
def messages_add_form():
    """Add a message:

    Show form if GET. If valid, update message and redirect to user page.
    """

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = MessageForm()
    return render_template('messages/new.html', form=form)





@app.route('/messages/new', methods=["POST"])
def messages_add():
    """Add a message:

    Show form if GET. If valid, update message and redirect to user page.
    """

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = MessageForm()
    msg = Message(text=form.text.data)
    g.user.messages.append(msg)
    db.session.commit()

    return redirect(f"/users/{g.user.id}")

    









@app.route('/messages/<int:message_id>', methods=["GET"])
def messages_show(message_id):
    """Show a message."""

    msg = Message.query.get(message_id)
    return render_template('messages/show.html', message=msg)


@app.route('/messages/<int:message_id>/delete', methods=["POST"])
def messages_destroy(message_id):
    """Delete a message."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    msg = Message.query.get(message_id)
    db.session.delete(msg)
    db.session.commit()

    return redirect(f"/users/{g.user.id}")


##############################################################################
# Homepage and error pages


@app.route('/')
def homepage():
    """Show homepage:

    - anon users: no messages
    - logged in: 100 most recent messages of followed_users
    """
   
    list_of_following_ids = []
    if g.user:
         
        for user in g.user.following:
            list_of_following_ids.append(user.id)

        messages = (Message
                    .query
                    .filter(Message.user_id.in_(list_of_following_ids))
                    .order_by(Message.timestamp.desc())
                    .limit(100)
                    .all())
       

        likes = Likes.query.filter(Likes.user_id == g.user.id).all()
        list_of_liked_message_ids = []
        for like in likes:
            list_of_liked_message_ids.append(like.message_id)
        num_likes = len(list_of_liked_message_ids)
        return render_template('home.html', messages=messages, likes_ids=list_of_liked_message_ids, num_likes=num_likes)

    else:
        return render_template('home-anon.html')


##############################################################################
# Turn off all caching in Flask
#   (useful for dev; in production, this kind of stuff is typically
#   handled elsewhere)
#
# https://stackoverflow.com/questions/34066804/disabling-caching-in-flask

@app.after_request
def add_header(req):
    """Add non-caching headers on every request."""

    req.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req.headers["Pragma"] = "no-cache"
    req.headers["Expires"] = "0"
    req.headers['Cache-Control'] = 'public, max-age=0'
    return req













@app.route('/logout', methods=['GET'])
def logout():
    """Handle logout of user."""
    
    user = User.query.get_or_404(session[CURR_USER_KEY])
    do_logout()
    flash(f"Goodbye, {user.username}!", "info")
    return redirect('/login')





















@app.route('/signup', methods=["GET"])
def signup_form():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """

    form = UserAddForm()
    return render_template('users/signup.html', form=form)
    












@app.route('/signup', methods=["POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """

    form = UserAddForm()
    try:
        user = User.signup(
            username=form.username.data,
            password=form.password.data,
            email=form.email.data,
            image_url=form.image_url.data or User.image_url.default.arg,
        )
        db.session.commit()

    except IntegrityError:
        flash("Username already taken", 'danger')
        return render_template('users/signup.html', form=form)

    do_login(user)

    return redirect("/")




























@app.route('/users/profile', methods=["GET"])
def update_profile_Form():
    """Update profile for current user."""
    user = User.query.get_or_404(session[CURR_USER_KEY])
    form = ProfileEditForm(obj=user)
    return render_template('users/edit.html', form=form, user=user)
    # IMPLEMENT THIS


@app.route('/users/profile', methods=["POST"])
def update_profile():
    """Update profile for current user."""
    user = User.query.get_or_404(session[CURR_USER_KEY])
    old_user_name = user.username
    form = ProfileEditForm(obj=user)
    confirmed_user = User.authenticate(old_user_name, form.password.data)
    if confirmed_user:
        
        confirmed_user.username = form.username.data
        confirmed_user.email = form.email.data
        confirmed_user.image_url = form.image_url.data
        confirmed_user.header_image_url = form.header_image_url.data
        confirmed_user.location = form.location.data
        confirmed_user.bio = form.bio.data
        db.session.commit()
        
        return redirect(f"/users/{confirmed_user.id}")
    else:
        flash("Wrong password !!", 'danger')
        return redirect("/")
    



@app.route('/users/add_like/<int:message_id>', methods=["POST"])
def add_like(message_id):
    likes = Likes.query.all()
    list_of_liked_message_ids = []
    for like in likes:
        list_of_liked_message_ids.append(like.message_id)
    if message_id in list_of_liked_message_ids:
        unlike = Likes.query.filter(Likes.message_id == message_id).first()
        db.session.delete(unlike)
        db.session.commit()
        return redirect(f"/users/{g.user.id}/likes")
    else:
        user = User.query.get_or_404(session[CURR_USER_KEY])
        new_like = Likes(user_id=user.id, message_id=message_id)
        db.session.add(new_like)
        db.session.commit()
        return redirect("/")

    

