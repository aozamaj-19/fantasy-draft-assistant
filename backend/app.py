from dotenv import load_dotenv

load_dotenv()

from flask import Flask
from flask_cors import CORS

from routes.auth import auth_bp
from routes.draft import draft_bp
from routes.leagues import leagues_bp
from routes.mock_draft import mock_draft_bp
from routes.players import players_bp
from routes.recommendations import recommendations_bp

app = Flask(__name__)
CORS(app, origins=["https://fantasy-draft-assistant2.netlify.app", "*"])

app.register_blueprint(auth_bp)
app.register_blueprint(leagues_bp)
app.register_blueprint(draft_bp)
app.register_blueprint(players_bp)
app.register_blueprint(recommendations_bp)
app.register_blueprint(mock_draft_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)
