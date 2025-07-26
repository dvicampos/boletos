from flask import Flask
from models import db

def init_db(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://usuario:password@localhost/credi_db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
