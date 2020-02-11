"""The actual API calls"""

import os
import logging
from os import path
import feedparser
from flask import request, jsonify, abort
from werkzeug.utils import secure_filename

from crispy_webapi import app
from crispy_webapi.helpers import create_session, get_session, prepare, scan
from crispy_webapi.error_handlers import BadRequest


@app.route('/api/v1.0/version', methods=['GET'])
def get_version():
    import subprocess
    from crispy_webapi.version import __version__ as api_version
    from crispy_models.version import __version__ as cylib_version
    ret = {
        'webapi': api_version,
        'lib': cylib_version,
        'gitrev': subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip(),
    }

    return jsonify(ret)


@app.route('/api/v1.0/seqs/id', methods=['POST'])
def post_sequence_id():
    if not request.json or 'asID' not in request.json:
        raise BadRequest('no antiSMASH ID specified')

    session = create_session(from_id=request.json['asID'])
    session_id = session._session_id

    prepare(session)
    data = dict(uri='/api/v1.0/genome', id=str(session_id))
    return jsonify(data)



@app.route('/api/v1.0/seqs/file', methods=['POST'])
def post_sequence_file():
    if not request.files or 'gbk' not in request.files:
        raise BadRequest('No file provided')

    upload = request.files['gbk']
    if upload is None:
        raise BadRequest('No file found in provided field')

    filename = secure_filename(upload.filename)
    session = create_session(from_file=filename)
    session_id = session._session_id

    save_dir = path.join(app.config['UPLOAD_PATH'], '{}'.format(session_id))
    if not path.exists(save_dir):
        os.mkdir(save_dir)
    upload.save(path.join(save_dir, filename))

    prepare(session)
    data = dict(uri='/api/v1.0/genome', id=str(session_id))
    return jsonify(data)


@app.route('/api/v1.0/genome/<int:session_id>', methods=['GET'])
def get_genome(session_id):
    session = get_session(session_id)
    ret = {
        'state': session.state,
        'genome': session.genome,
        'last_updated': session.last_changed,
    }
    if session.state == 'error':
        ret['error'] = session.error

    return jsonify(ret)


@app.route('/api/v1.0/genome/<int:session_id>/<new_state>', methods=['PUT'])
def reset_session_status(session_id, new_state):
    session = get_session(session_id)

    if session.derived:
        abort(403)

    # Only allow changing state to the identical state, apart from allowing to
    # go back to 'loaded' from 'done'
    if new_state == session.state:
        pass
    elif session.state == 'done' and new_state == 'loaded':
        session.state = new_state
        session.region = {}
    else:
        abort(403)

    ret = {
        'state': session.state
    }

    return jsonify(ret)


@app.route('/api/v1.0/genome/<int:session_id>', methods=['POST'])
def start_scan(session_id):
    if not request.json:
        logging.info("no json")
        raise BadRequest("no JSON data")

    if not 'from' in request.json or not 'to' in request.json:
        logging.info("no coordinates")
        raise BadRequest("missing coordinates")

    if request.json['from'] > request.json['to'] or request.json['from'] < 0:
        logging.info("bad coordinates")
        raise BadRequest("invalid coordinates")

    if not 'best_size' in request.json:
        request.json['best_size'] = 7

    if not 0 < request.json['best_size'] < 20:
        logging.info("bad CRISPR BEST size")
        raise BadRequest("Invalid CRISPR BEST edit window size")

    if not 'best_offset' in request.json:
        request.json['best_offset'] = 13

    if not 0 <= request.json['best_offset'] < 20:
        logging.info("bad CRISPR BEST offset")
        raise BadRequest("Invalid CRISPR BEST edit window offset")

    if request.json['best_size'] + request.json['best_offset'] > 20:
        logging.info("CRISPR BEST offset and window size too large")
        raise BadRequest("CRISPR BEST offset and window size too large")

    session = get_session(session_id)

    if request.json['to'] > int(session.genome['length']):
        logging.info("to coordinate too big: to: {!r}, length: {!r}".format(request.json['to'], session.genome['length']))
        raise BadRequest("coordinates out of range 0 - {!r}".format(session.genome['length']))

    if not session.region:
        logging.info(request.json)
        session.from_coord = request.json['from']
        session.to_coord = request.json['to']
        session.best_size = request.json['best_size']
        session.best_offset = request.json['best_offset']
        if 'full_size' in request.json:
            full_size = int(request.json['full_size'])
            if full_size > 50:
                full_size = 50
            session.full_size = full_size
        session.state = 'scanning'
        scan(session)
    else:
        relative_start = request.json['from']
        relative_end = request.json['to']

        if session.from_coord + relative_end > session.to_coord:
            logging.info('new subreq to coord too large')
            raise BadRequest('new subreq to coord too large')

        new_session = create_session(from_file=session.filename)
        new_session.derived = True
        region = session.region

        if 'name' in request.json:
            region['name'] = request.json['name']
        else:
            region['name'] = ''

        new_orfs = []
        for orf in region['orfs']:
            if orf['start'] < relative_start or orf['end'] > relative_end:
                continue
            orf['start'] -= relative_start
            orf['end'] -= relative_start
            new_orfs.append(orf)
        region['orfs'] = new_orfs

        new_grnas = {}
        for _id, grna in region['grnas'].iteritems():
            if grna['start'] < relative_start or grna['end'] > relative_end:
                continue
            grna['start'] -= relative_start
            grna['end'] -= relative_start
            new_grnas[_id] = grna
        region['grnas'] = new_grnas

        new_session.from_coord = session.from_coord + relative_start
        new_session.to_coord = session.from_coord + relative_end
        new_session.region = region
        new_session.state = 'done'
        session_id = new_session._session_id
        new_session.best_size = request.json['best_size']
        new_session.best_offset = request.json['best_offset']

    data = dict(uri='/api/v1.0/crispr', id=str(session_id))
    return jsonify(data)


@app.route('/api/v1.0/crispr/<int:session_id>', methods=['GET'])
def get_criprs(session_id):
    session = get_session(session_id)
    region = session.region

    region['state'] = session.state
    region['from'] = session.from_coord
    region['to'] = session.to_coord
    region['last_updated'] = session.last_changed
    region['derived'] = session.derived
    region['best_size'] = session.best_size
    region['best_offset'] = session.best_offset
    if session.state == 'error':
        region['error'] = session.error

    return jsonify(region)


@app.route('/api/v1.0/crispr/<int:session_id>', methods=['POST'])
def get_crispr_csv(session_id):
    if not request.json or 'ids' not in request.json:
        raise BadRequest('Invalid ID field')

    session = get_session(session_id)
    region = session.region

    grnas_for_csv = []
    for crispy_id in request.json['ids']:
        if not crispy_id in region['grnas']:
            continue
        grnas_for_csv.append(region['grnas'][crispy_id])

    save_dir = path.join(app.config['UPLOAD_PATH'], '{:039d}'.format(session_id))
    if not path.exists(save_dir):
        os.mkdir(save_dir)
    csv_file = path.join(save_dir, 'output.csv')
    with open(csv_file, 'w') as fh:
        fh.write('ID,Start,End,Strand,ORF,Sequence,PAM,C to T mutations,A to G mutations,0bp mismatches,1bp mismatches,2bp mismatches\n')
        for grna in grnas_for_csv:
            ctot = '"{}"'.format(",".join(grna.get('changed_aas', {}).get('CtoT', [])))
            atog = '"{}"'.format(",".join(grna.get('changed_aas', {}).get('AtoG', [])))
            fh.write('{id},{start},{end},{strand},{orf},{sequence},{pam},{ctot},{atog},{0bpmm},{1bpmm},{2bpmm}\n'.format(ctot=ctot, atog=atog, **grna))

    return jsonify(dict(id=str(session_id), uri="/download/{:039d}/output.csv".format(session_id)))


@app.route('/api/v1.0/news', methods=['GET'])
def get_news():
    """Get a JSON version of the ATOM news feed"""

    feed = feedparser.parse("https://news.secondarymetabolites.org/feeds/tag-crispy.atom.xml")
    entries = []
    json_feed = dict(title=feed.feed.title, entries=entries)

    for entry in feed.entries[:5]:
        json_entry = {
            'title': entry.title,
            'link': entry.link,
            'published': entry.published,
            'summary': entry.summary,
        }
        entries.append(json_entry)

    return jsonify(json_feed)
