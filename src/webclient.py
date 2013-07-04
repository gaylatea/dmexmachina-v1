#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Main webclient routes for DM Ex Machina.


This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <http://unlicense.org/>

"""
##
from flask import Flask, flash, g, render_template, request, redirect, session
from pymongo import Connection, DESCENDING, ASCENDING
from bson.objectid import ObjectId
from hashlib import sha256
from datetime import datetime
from flaskext.markdown import Markdown
from flask.ext.assets import Environment, Bundle
from functools import wraps
from dmxm import dice
import re
import pytz


##
APP = Flask(__name__)
Markdown(APP)
assets = Environment(APP)
DATABASE = 'dmxm'
APP.secret_key = '\xf6w\x9c.\xe6;>{\x931\x0cp\xa7g\xc6\x15'


##
js = Bundle('jquery.js', 'main.js',
    filters='jsmin', output='packed.js')

assets.register('js_all', js)

css = Bundle('reset.css', 'style.css', filters='cssmin', output='packed.css')
assets.register('css_all', css)


##
@APP.context_processor
def inject_user_info():
    """Insert user info into all templates."""
    if 'pid' in session:
        g.user = g.db.players.find_one({'_id': session['pid']})
        return {'user': g.user}
    else:
        return {}


@APP.before_request
def request_database():
    """Each page request gets a connection to MongoDB."""
    g.db = Connection()[DATABASE]


@APP.context_processor
def inject_localtime_processing():
    """Give templates a function to convert to Pacific time."""
    def format_as_localtime(dt):
        dt = dt.replace(tzinfo=pytz.utc)
        pacific_tz = pytz.timezone('America/Los_Angeles')
        return dt.astimezone(pacific_tz)
    return {'localtime': format_as_localtime}


##
def requiresLogin(func):
    """Redirects users to the login if they are not authenticated."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if 'pid' not in session:
            return redirect('/')
        else:
            return func(*args, **kwargs)
    return decorated_function


##
@APP.route('/')
def homepage():
    """Either a login screen, or a list of campaigns running.

    Will only show games that the current player has access to, with
    updates on OOC chat, chapter text, and new chapters available.

    """
    if 'pid' not in session:
        return render_template('login.html')
    else:
        # Lookup sessions that this player is a part of.
        sessions = []
        user = g.db.players.find_one({'_id': session['pid']})
        for sid in user['games']:
            s = g.db.campaigns.find_one({'_id': sid})

            # Lookup the chapter list that this character is in.
            chapters = g.db.chapters.find({'game': sid,
                'players': {'$in': [session['pid']]}}
                ).sort('started', ASCENDING)

            s['chapters'] = chapters

            sessions.append(s)

        return render_template('sessions.html', sessions=sessions)


@APP.route('/games/<gamename>')
@requiresLogin
def game_chapters(gamename):
    """Show all chapters in a particular game that we have access to."""
    user = g.db.players.find_one({'_id': session['pid']})
    if gamename not in user['games']:
        return redirect('/')

    # Get the chapters that this character has access to.
    s = g.db.campaigns.find_one({'_id': gamename})

    s['chapters'] = g.db.chapters.find({'game': gamename,
                'players': {'$in': [session['pid']]}},
    ).sort('started', ASCENDING)

    sessions = [s]

    return render_template('sessions.html', sessions=sessions, game=gamename)


@APP.route('/games/<gamename>/chat', methods=['POST'])
@requiresLogin
def game_post_message(gamename):
    """Post a chat message to the channel for this game."""
    g.db.chats.insert({'game': gamename, 'body': request.form['post-text'],
        'source': session['pid'], 'posted': datetime.utcnow()})

    game = '/games/%s' % gamename
    ret = request.headers['Referer'] if 'Referer' in request.headers else game
    ret = '%s#bottom' % ret

    return redirect(ret)


@APP.route('/games/<gamename>/chapter/<chapter>')
@requiresLogin
def game_chapter(gamename, chapter):
    """Show the posting interface for player posts.

    This is the real meat and potatoes of the site.

    """
    current_chapter = g.db.chapters.find_one({'_id': ObjectId(chapter)})
    posts = g.db.posts.find({'chapter': ObjectId(chapter)}).sort('posted',
        ASCENDING)

    # Current game for the link back.
    current_game = g.db.campaigns.find_one({'_id': gamename})

    # Retrieve chat messages for this game.
    chats = g.db.chats.find({'game': gamename}).sort('posted', DESCENDING)

    cs = []
    for each in chats:
        cs.append(each)

    cs.reverse()

    # Is the current user the DM?
    is_dm = (session['pid'] in current_game['dms'])

    return render_template('chapter.html', posts=posts,
        chapter=current_chapter, chats=cs, game=gamename,
        current_game=current_game, is_dm=is_dm)


@APP.route('/games/<gamename>/chapter/<chapter>/post', methods=['POST'])
@requiresLogin
def game_chapter_post(gamename, chapter):
    """Post a reply to a chapter."""

    chapter = ObjectId(chapter)
    current_chapter = g.db.chapters.find_one({'_id': chapter})
    if not current_chapter:
        return redirect('/')

    # Determine if this was posted by one of the DMs.
    campaign = g.db.campaigns.find_one({'_id': gamename}, fields=['dms'])
    src = 'dm' if session['pid'] in campaign['dms'] else session['pid']

    # Compute inline die rolls.
    body = dice.process(request.form['post-text'])

    postdata = {'chapter': chapter, 'body': body, 'posted': datetime.utcnow(),
        'source': src}

    if 'players' in request.form:
        postdata['players'] = request.form.getlist('players')

    g.db.posts.insert(postdata)

    return redirect('/games/%s/chapter/%s#bottom' % (gamename, chapter))


@APP.route('/signin', methods=['POST'])
def signin():
    """Log a user into the system."""
    username = request.form['pid']
    password = sha256(request.form['password']).hexdigest()
    user = g.db.players.find_one({'_id': username, 'password': password})
    if user:
        session['pid'] = username
        return redirect('/')
    else:
        # Smarter error handling than just a generic 401 error.
        flash('Incorrect username or password', 'error')
        return redirect('/')


@APP.route('/signout')
def signout():
    """Log a user out of the system."""
    del session['pid']
    return redirect('/')


##
if __name__ == '__main__':
    # Don't run this on a production server. Holy god.
    APP.run(host='0.0.0.0', port=5000, debug=True)
