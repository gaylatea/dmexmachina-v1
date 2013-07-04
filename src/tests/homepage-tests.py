# -*- coding: utf-8 -*-
"""Unit tests for the frontpage DM Ex Machina pages.


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
from dmxm import webclient
from unittest import TestCase
from pymongo import Connection
from hashlib import sha256
from datetime import datetime


##
class DMXMAppUnitTests(TestCase):

    def setUp(self):
        webclient.DATABASE = 'dmxm-tests'

        # Setup a sample user to login.
        # TODO: Bcrypt hashing for passwords?
        self.db = Connection()[webclient.DATABASE]
        self.db.players.insert({'_id': 'test@dmexmachina.com',
            'password': sha256('testpassword').hexdigest(),
            'games': ['testsession'], 'admin': True}, safe=True)


        # Insert sample game data for testing.
        self.db.campaigns.insert({'name': 'Test Session',
            'started': datetime.utcnow(), '_id': 'testsession',
            'dms': ['test@dmexmachina.com']}, safe=True)

        self.db.campaigns.insert({'name': 'Test Session 2',
            'started': datetime.utcnow(), '_id': 'testsession2'}, safe=True)

        self.chapter = self.db.chapters.insert({'name': 'ENCOUNTER IX',
            'game': 'testsession', 'started': datetime.utcnow(),
            'players': ['test@dmexmachina.com']}, safe=True)

        self.db.posts.insert({'chapter': self.chapter,
            'posted': datetime.utcnow(),
            'source': 'chapter', 'body': 'This is a test post.'})

        self.db.posts.insert({'chapter': self.chapter,
            'posted': datetime.utcnow(),
            'source': 'text@dmexmachina.com', 'body': 'Hello there.'})

        self.db.chapters.insert({'name': 'ENCOUNTER X', 'game': 'testsession',
            'started': datetime.utcnow(),
            'players': ['nonexistentplayer@dmexmachina.com']}, safe=True)

        self.app = webclient.APP.test_client()

    def tearDown(self):
        """Destroy data in the database."""
        self.db.players.remove()
        self.db.campaigns.remove()
        self.db.chapters.remove()
        self.db.chats.remove()

    def test_homepage_login_form(self):
        """Anonymous users should see a login screen."""
        rv = self.app.get('/')
        self.assertIn('Player ID', rv.data)
        self.assertNotIn('Sign Out', rv.data)

    def test_homepage_login(self):
        """Test that the actual login facility works."""
        self.login()

    def test_homepage_login_incorrect(self):
        """Incorrect passwords should send the user back to login."""
        rv = self.app.post('/signin', data={
            'pid': 'test@dmexmachina.com',
            'password': 'WRONGWRONGWRONG'
        }, follow_redirects=True)

        self.assertNotIn('Sign Out', rv.data)
        self.assertIn('Incorrect username or password', rv.data)

    def test_homepage_logged_in_sessions(self):
        """Logged-in users should see a list of active games.

        Note that this will only show games/chapters that they are
        currently inserted into.

        """
        rv = self.login()
        
        # Session details.
        self.assertIn('Test Session', rv.data)
        self.assertIn(datetime.utcnow().strftime('%b %Y'), rv.data)
        self.assertIn('ENCOUNTER IX', rv.data)
        self.assertNotIn('ENCOUNTER X', rv.data)

    def test_gamepage_sessions(self):
        """The game page should show the full list of sessions."""
        self.login()

        rv = self.app.get('/games/testsession')
        
        # Session details.
        self.assertIn('Test Session', rv.data)
        self.assertIn(datetime.utcnow().strftime('%b %Y'), rv.data)
        self.assertIn('ENCOUNTER IX', rv.data)
        self.assertNotIn('ENCOUNTER X', rv.data)

    def test_gamepage_not_logged_in(self):
        """You must be logged in in order to view games."""
        rv = self.app.get('/games/testsession', follow_redirects=True)
        self.assertNotIn('Sign Out', rv.data)

    def test_gamepage_no_player_access(self):
        """Players can be denied access to a whole game."""
        self.login()

        rv = self.app.get('/games/testsession2', follow_redirects=True)
        
        # Session details.
        self.assertNotIn('/games/testsession2', rv.data)

    def test_chapterpage_exists(self):
        """A chapter should exist and be navigatable to."""
        rv = self.login()

        rv = self.app.get('/games/testsession/chapter/%s' % self.chapter)
        self.assertIn('test post', rv.data)
        self.assertIn('Hello there', rv.data)

    def test_chapterpage_nologin(self):
        """You must be logged in to view a chapter."""
        rv = self.app.get('/games/testsession/chapter/%s' % self.chapter,
            follow_redirects=True)
        
        self.assertNotIn('Sign Out', rv.data)

    def test_chapterpage_post(self):
        """Add a post to a chapter."""
        self.login()

        rv = self.app.post('/games/testsession/chapter/%s/post' % self.chapter,
            data={'post-text': 'Hello there.'}, follow_redirects=True)

        self.assertIn('Hello there.', rv.data)

    def test_chapterpage_locked(self):
        """Locking a chapter should disallow players from posting."""
        self.login()

        rv = self.app.get('/games/testsession/chapter/%s' % self.chapter)
        self.assertIn('<form', rv.data)

        # Lock the chapter for this test.
        self.db.chapters.update({'_id': self.chapter},
            {'$set': {'locked': True}})

        rv = self.app.get('/games/testsession/chapter/%s' % self.chapter)
        self.assertNotIn('testsession/post', rv.data)

    def test_chapterpost_markdown(self):
        """Posts in chapters should support Markdown syntax."""
        self.login()

        rv = self.app.post('/games/testsession/chapter/%s/post' % self.chapter,
            data={'post-text': '**Hello there.**'}, follow_redirects=True)

        self.assertIn('<strong>Hello there.</strong>', rv.data)

    def test_chapterpage_chaptertext_highlights(self):
        """Text posted by the DM of the game should be highlighted."""
        self.login()

        rv = self.app.post('/games/testsession/chapter/%s/post' % self.chapter,
            data={'post-text': '**Hello there.**'}, follow_redirects=True)

        self.assertIn('dm-post', rv.data)

    def test_chapterpage_dieroll(self):
        """Chapter posts must now support integral dice rolls."""
        self.login()

        rv = self.app.post('/games/testsession/chapter/%s/post' % self.chapter,
            data={'post-text': 'Basic Attack on Vlad, 1d20+4 vs AC, 6'},
            follow_redirects=True)

        self.assertNotIn('1d20+4', rv.data)

    def test_logout(self):
        """Users should be able to logout."""
        self.login()

        rv = self.app.get('/signout', follow_redirects=True)
        self.assertIn('Login', rv.data)

    
    def test_chat_exists(self):
        """Game and chapter pages should have a chatbox for users."""
        self.login()

        uri = '/games/testsession/chapter/%s' % self.chapter
        rv = self.app.get(uri)
        self.assertIn('post-chat', rv.data)

    def test_chat_post_nojs(self):
        """Users should be able to post chat messages.

        Simulates without Javascript; will redirect to the page they
        were originally at.
            
        """
        self.login()

        rv = self.app.post('/games/testsession/chat',
            data={'post-text': 'Rawr a test message'}, follow_redirects=True)

        rv = self.app.get('/games/testsession/chapter/%s' % self.chapter)
        
        self.assertIn('Rawr a test message', rv.data)
        self.assertIn('Test Session', rv.data)

    def test_chat_post_markdown(self):
        """Chat posts should support markdown as well."""
        self.login()

        rv = self.app.post('/games/testsession/chat',
            data={'post-text': '**RAWR**'}, follow_redirects=True)
        
        rv = self.app.get('/games/testsession/chapter/%s' % self.chapter)
        self.assertIn('<strong>RAWR</strong>', rv.data)


    def login(self):
        """Performs a login as our test user."""
        rv = self.app.post('/signin', data={
            'pid': 'test@dmexmachina.com',
            'password': 'testpassword'
        }, follow_redirects=True)

        self.assertIn('Sign Out', rv.data)
        return rv
