"""Helper functions for the webapi"""

import os
import redis
from flask import g, abort
from crispy_models.models import Session, Queue

def create_session(from_id=None, from_file=None):
    """Create a new Session object"""
    session = Session(_get_db(), from_id=from_id, from_file=from_file)
    #TODO: Add session to queue
    return session


def get_session(session_id):
    try:
        session = Session(_get_db(), session_id=session_id)
        #FIXME: Use proper session handling
        return session
    except ValueError:
        abort(404)


def prepare(session):
    """Prepare a session for running CRISPy"""
    queue = Queue(_get_db(), 'prepare')
    queue.submit(session)


def scan(session):
    """Scan a genome for PAMs"""
    queue = Queue(_get_db(), 'scan')
    queue.submit(session)


def _get_db():
    redis_store = getattr(g, '_database', None)
    if redis_store is None:
        redis_store = redis.from_url(os.getenv('CRISPY_REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
        setattr(g, '_database', redis_store)
    return redis_store

