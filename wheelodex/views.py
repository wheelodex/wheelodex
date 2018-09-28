from flask import Blueprint, jsonify, render_template
from .db   import Wheel, db

web = Blueprint('web', __name__)

from .     import macros  # noqa

@web.route('/wheels.html')
def wheel_list():
    wheels = db.session.query(Wheel).filter(Wheel.data.has()).all()
    return render_template('wheel_list.html', wheels=wheels)

@web.route('/<wheel>.json')
def wheel_json(wheel):
    whl = db.session.query(Wheel).filter(Wheel.filename == wheel + '.whl')\
                    .first_or_404()
    return jsonify(whl.as_json())

@web.route('/<wheel>.html')
def wheel_html(wheel):
    whl = db.session.query(Wheel).filter(Wheel.filename == wheel + '.whl')\
                    .first_or_404()
    return render_template('wheel_data.html', whl=whl)
