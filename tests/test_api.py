import pytest
import json
from flask import url_for, g
from crispy_models.models import Session

from crispy_webapi.helpers import create_session, get_session


@pytest.fixture
def app(monkeypatch):
    """Flask app with fake redis wrapper"""
    from crispy_webapi import app as flask_app
    import redis
    from mockredis import mock_redis_client
    mock_redis_client.from_url = lambda x: mock_redis_client()
    monkeypatch.setattr(redis, 'Redis', mock_redis_client)
    return flask_app


def test_post_sequence_id(client):
    response = client.post(url_for('post_sequence_id'), data='{"asID": 1234}', content_type='application/json')
    assert response.status_code == 200
    assert 'uri' in response.json


def test_post_sequence_id_no_id(client):
    response = client.post(url_for('post_sequence_id'), data='{"fake": 1234}', content_type='application/json')
    assert response.status_code == 400


def test_get_sequence_id(client):
    response = client.get(url_for('post_sequence_id'))
    assert response.status_code == 405


def test_post_sequence_file(client, config, tmpdir):
    from io import BytesIO
    config['UPLOAD_PATH'] = str(tmpdir)
    data = {
        'gbk': (BytesIO(b'this is a fake gbk file'), 'fake.gbk')
    }
    response = client.post(url_for('post_sequence_file'), data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    assert 'uri' in response.json


def test_post_sequence_file_errors(client):
    data = {
        'fake': 1234
    }
    response = client.post(url_for('post_sequence_file'), data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert response.json['message'] == 'No file provided'


def test_get_genome(client):
    first = client.post(url_for('post_sequence_id'), data='{"asID": 1234}', content_type='application/json').json
    url = '/'.join([first['uri'], str(first['id'])])
    response = client.get(url)
    assert response.status_code == 200
    assert response.json['state'] == 'pending'
    session = Session(g._database, session_id=int(first['id']))
    assert session.state == 'pending'
    session.state = 'error'
    session.error = 'aborted by test'
    response = client.get(url)
    assert response.status_code == 200
    assert response.json['state'] == 'error'
    assert response.json['error'] == 'aborted by test'


def test_get_genome_invalid_session(client):
    assert client.get(url_for('get_genome', session_id=23456)).status_code == 404


def test_start_scan_invalid(client):
    # Ask for a fake session_id to initialize the client context
    url = url_for('start_scan', session_id=12345)
    data = {
        'from': 1234,
        'to': 2345,
    }
    response = client.post(url, data=data, content_type='application/json')
    assert response.status_code == 400


def test_start_scan(client):
    first = client.post(url_for('post_sequence_id'), data='{"asID": 1234}', content_type='application/json').json
    url = '/'.join([first['uri'], str(first['id'])])
    response = client.get(url)
    assert response.status_code == 200
    assert response.json['state'] == 'pending'

    session = Session(g._database, session_id=int(first['id']))
    assert session.state == 'pending'
    session.genome = {
        "clusters": [
            {
                "description": "fake cluster",
                "start": 1234,
                "end": 2345,
                "name": "Cluster 1",
                "type": "Fake"
            }
        ],
        "description": "F. ake full genome, complete sequence",
        "id": "FAKE12345",
        "length": 3456,
        "organism": "Fakecillus ake subps. bogus"
    }

    url = url_for('start_scan', session_id=session._session_id)

    data = json.dumps({'from': 1234, 'to': 2345, 'best_size': 7, 'best_offset': 13})
    response = client.post(url, data=data, content_type='application/json')
    assert response.status_code == 200
    assert session.state == 'scanning'


def test_get_crispr_csv(client, app, tmpdir):
    TEST_ID = 42

    # Create a session object to hijack
    session_template = create_session(from_id='asID')
    g._database.rename(session_template._session_key, 'crispy:session:{:039d}'.format(TEST_ID))
    session = get_session(TEST_ID)

    session.state = 'done'
    session.genome = {
        "clusters": [
            {
                "description": "fake cluster",
                "start": 1234,
                "end": 2345,
                "name": "Cluster 1",
                "type": "Fake"
            }
        ],
        "description": "F. ake full genome, complete sequence",
        "id": "FAKE12345",
        "length": 3456,
        "organism": "Fakecillus ake subps. bogus"
    }

    session.region = {
        'grnas': {
            'FAKE1': {
                '0bpmm': 0,
                '1bpmm': 2,
                '2bpmm': 4,
                '3bpmm': 8,
                'start': 1240,
                'end': 1263,
                'id': 'FAKE1',
                'orf': 'FAK1',
                'pam': 'AGG',
                'sequence': 'AAAAAAAATTTTTTTTCCCC',
                'strand': 1,
                'changed_aas': {
                    'CtoT': ['A1*', 'B2C'],
                    'AtoG': ['D3*'],
                },
            },
            'FAKE2': {
                '0bpmm': 0,
                '1bpmm': 1,
                '2bpmm': 2,
                '3bpmm': 4,
                'start': 2320,
                'end': 2343,
                'id': 'FAKE2',
                'orf': 'FAK1',
                'pam': 'TGG',
                'sequence': 'TTTTTTTTAAAAAAAACCCC',
                'strand': -1,
            },
        },
        'name': 'Cluster 1',
    }

    app.config['UPLOAD_PATH'] = str(tmpdir)

    url = url_for('get_crispr_csv', session_id=session._session_id)
    data = json.dumps({'ids': ['FAKE1']})
    res = client.post(url, data=data, content_type='application/json')

    # Check if correct URI is returned
    assert res.status_code == 200
    assert res.json['uri'] == '/download/{:039d}/output.csv'.format(TEST_ID)

    # Check if output file is correct
    result_dir = tmpdir.join('{:039d}'.format(TEST_ID))
    assert result_dir.check(dir=1)

    result_file = result_dir.join('output.csv')
    assert result_file.check(file=1)
    assert result_file.read() == '''\
ID,Start,End,Strand,ORF,Sequence,PAM,C to T mutations,A to G mutations,0bp mismatches,1bp mismatches,2bp mismatches
FAKE1,1240,1263,1,FAK1,AAAAAAAATTTTTTTTCCCC,AGG,"A1*,B2C","D3*",0,2,4
'''
