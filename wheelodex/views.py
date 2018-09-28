from flask import Blueprint, jsonify
from .db   import Wheel, db

web = Blueprint('web', __name__)

@web.route('/<wheel>.json')
def wheel_json(wheel):
    whl = db.session.query(Wheel).filter(Wheel.filename == wheel + '.whl')\
                    .first_or_404()
    return jsonify(whl.as_json())
