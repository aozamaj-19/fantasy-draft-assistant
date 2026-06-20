from dotenv import load_dotenv

load_dotenv()

from flask import Flask

from routes.auth import auth_bp
from routes.draft import draft_bp
from routes.leagues import leagues_bp
from routes.mock_draft import mock_draft_bp
from routes.players import players_bp
from routes.recommendations import recommendations_bp

app = Flask(__name__)

@app.after_request
def after_request(response):
    response.headers.set('Access-Control-Allow-Origin', '*')
    response.headers.set('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.set('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

app.register_blueprint(auth_bp)
app.register_blueprint(leagues_bp)
app.register_blueprint(draft_bp)
app.register_blueprint(players_bp)
app.register_blueprint(recommendations_bp)
app.register_blueprint(mock_draft_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)
