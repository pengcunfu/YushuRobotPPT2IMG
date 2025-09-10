import os

from api import app

os.makedirs("uploads", exist_ok=True)
os.makedirs("results", exist_ok=True)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8020)
