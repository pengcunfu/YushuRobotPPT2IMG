from api import socketio, app

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=8020, allow_unsafe_werkzeug=True)
