"""JSONified error handlers"""
from flask import make_response, jsonify
from crispy_webapi import app

class BadRequest(Exception):
    pass

@app.errorhandler(400)
def bad_req(error):
    return make_response(jsonify({'error': 'Bad request'}), 400)


# Like above, but with extra information to display to the client
@app.errorhandler(BadRequest)
def bad_req(error):
    return make_response(jsonify({'error': 'Bad request', 'message': str(error)}), 400)


@app.errorhandler(403)
def not_found(error):
    return make_response(jsonify({'error': 'Forbidden'}), 403)


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


@app.errorhandler(405)
def method_not_allowed(error):
    return make_response(jsonify({'error': 'Method not allowed'}), 405)


@app.errorhandler(500)
def internal_server_error(error):
    return make_response(jsonify({'error': 'Internal server error'}), 500)
