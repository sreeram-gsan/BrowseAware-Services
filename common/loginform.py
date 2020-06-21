from wtforms.validators import DataRequired
from wtforms import StringField, PasswordField

class LoginForm():
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])