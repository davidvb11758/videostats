from flask import Flask, render_template
from database import VideoStatsDB
from api.routes import api

app = Flask(__name__)
app.register_blueprint(api)

# Initialize database on startup
db = VideoStatsDB()
db.initialize_database()
db.connect()
db.create_collection_tables()
db.close()

# Root route - serve the main page
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # Bind to 0.0.0.0 to accept connections from any IP
    # Use port 5000 (or your preferred port)
    app.run(host='0.0.0.0', port=5000, debug=True)