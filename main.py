#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# importations
import webapp2
import re
import os
import time
import jinja2

import logging
import hmac
import random
import string
import hashlib

import urllib
import urllib2
from xml.dom import minidom

from google.appengine.ext import db
from google.appengine.api import memcache
import json
import copy
import sys
sys.path.insert(0, 'libs')
from bs4 import BeautifulSoup

# Global variables
template_dir = os.path.join(os.path.dirname(__file__), 'html_template')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape = True)

# Databases
class Apps(db.Model):
    name = db.StringProperty(required = True)
    link = db.StringProperty(required = True)
    description = db.TextProperty(required = True)
    created_time = db.DateTimeProperty(auto_now = True)

# Basic Handler
class ECEHandle(webapp2.RequestHandler):
    # rewrite the write, more neat
    def write(self, *a, **kw):
        self.response.write(*a, **kw)
    # render helper function, use jinja2 to get template
    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)
    # render page using jinja2
    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header('Set-Cookie', '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        if cookie_val == None:
            return None
        else:
            return check_secure_val(cookie_val)

    ## login means set the cookie
    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    ## logout means clear the cookie
    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

# Handlers
class HomePage(ECEHandle):
    def get(self):
        apps = db.GqlQuery("SELECT * FROM Apps")
        self.render('homepage.html', apps = apps)
class AddApp(ECEHandle):
    referer = ""
    def render_page(self):
        self.render('add-apps-form.html', referer = self.referer)
    def post(self):
        name = self.request.get('name')
        link = self.request.get('link')
        description = self.request.get('description')

        Apps(key_name = name, 
             name = name, 
             link = link,
             description = description).put()
        self.redirect(str(self.referer))
    def get(self):
        # initialize referer, keep the origin referer
        if not self.request.referer == self.request.url:
            self.referer = self.request.referer
        else: 
            self.referer = self.referer
        self.render_page()


class CourseEnrolmentNotifier(ECEHandle):
    level = ""
    sess = ""
    subject = ""
    cournum = ""
    term_dic = {}
    sess_values = []
    subject_values = []
    def readQueryFrontPage(self, url):
        try:
            content = urllib2.urlopen(url).read()
        except URLError:
            return
        if content:
            self.term_dic.clear()
            del self.sess_values[:]
            del self.subject_values[:]
            soup = BeautifulSoup(content)
            # get the term description
            # termDescp should like u'1135=Spring 2013, 1139=Fall 2013, 1141=Winter 2014, 1145=Spring 2014'
            termDescp = soup.input.get_text()
            first_parentheses = termDescp.find("(", 3)
            next_paentheses = termDescp.find(")", first_parentheses + 1)
            termDescp = termDescp[first_parentheses + 1:next_paentheses]

            # assign term_dic
            # term_dic should like this:
            # {u'1135': u'Spring 2013', u'1139': u'Fall 2013',u'1141': u'Winter 2014', u'1145': u'Spring 2014'}
            term_list = termDescp.split(", ")
            for term in term_list:
                term_id, term_descp = term.split("=")
                self.term_dic[term_id] = term_descp

            # sess
            sess = soup.find_all("select", {"name" : "sess"})
            sess = BeautifulSoup(str(sess[0]))
            # sess_selected = <option selected="" value="1141">1141 <option value="1145">1145 </option></option>
            sess_selected = BeautifulSoup(str(sess.find_all(selected=True)))
            sess_selected = sess_selected.option['value'] # sess_selected =  u'1141'
            # sess_values:
            # [[u'1135', False],
            #  [u'1139', False],
            #  [u'1141', True],
            #  [u'1145', False]]
            for se in sess.strings:
                se = se[:se.find('\n')]
                if se == u'':
                    continue
                elif se == sess_selected:
                    self.sess_values.append([se, True])
                else:
                    self.sess_values.append([se, False])
            # subject
            subject = soup.find_all("select", {"name" : "subject"})
            subject = BeautifulSoup(str(subject[0]))
            for su in subject.strings:
                su = su[:su.find('\n')]
                if su == u'':
                    continue
                else:
                    self.subject_values.append(su)
            return True
        else:
            return False

    def render_page(self, sess_values = "", term_dic = "", subject_values = ""):
        self.render('/course-enrol/cen-front.html', sess_values = sess_values, term_dic = term_dic, subject_values = subject_values)
    def get(self):
        scheduleURL = "http://www.adm.uwaterloo.ca/infocour/CIR/SA/%s.html"
        graduateSampleURL = scheduleURL % "grad"
        if self.readQueryFrontPage(graduateSampleURL):
            self.render_page(self.sess_values, self.term_dic, self.subject_values)

    def readQueryResult(self, query_url, query_obj):
        try:
            query_result = urllib2.urlopen(query_url, query_obj).read()
        except URLError:
            return
        if query_result:
            soup = BeautifulSoup(query_result)
            self.write(soup.prettify())
            return True
        else:
            return False
    def post(self):
        query_url = "http://www.adm.uwaterloo.ca/cgi-bin/cgiwrap/infocour/salook.pl"
        # produce query_object
        self.level = self.request.get('level')
        self.sess = self.request.get('sess')
        self.subject = self.request.get('subject')
        self.cournum = self.request.get('cournum')
        query_dic = {}
        query_dic['level'] = self.level
        query_dic['sess'] = self.sess
        query_dic['subject'] = self.subject
        query_dic['cournum'] = self.cournum
        query_obj = urllib.urlencode(query_dic)
        # read query result
        if self.readQueryResult(query_url, query_obj):
            pass

control = True
count = 0        
class Test(ECEHandle):
    # def get(self):
    #     global control
    #     global count
    #     while control:
    #         count += 1
    #         time.sleep(0.5)
    #     self.write(count)
    def get(self):
        # global control
        # control = False
        time = 10
        while time > 0:
            result = urllib2.urlopen('http://localhost:10080/course-reminder')
            time -= 1
        self.write(count)


app = webapp2.WSGIApplication([
    ('/?', HomePage),
    ('/add-app', AddApp),
    ('/uw-cen', CourseEnrolmentNotifier),
    ('/test', Test)
], debug=True)
