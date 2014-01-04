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

from google.appengine.ext import ndb
from google.appengine.api import memcache
import json
import copy
import sys
sys.path.insert(0, 'libs')
from bs4 import BeautifulSoup
from collections import OrderedDict
from google.appengine.api import mail
from time import gmtime, strftime, localtime

# Global variables
template_dir = os.path.join(os.path.dirname(__file__), 'html_template')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape = True)

# Databases
class Apps(ndb.Model):
    name = ndb.StringProperty(required = True)
    link = ndb.StringProperty(required = True)
    description = ndb.TextProperty(required = True)
    created_time = ndb.DateTimeProperty(auto_now_add = True)
    last_modified = ndb.DateTimeProperty(auto_now = True)

# class Class(ndb.Model):
#     subject = ndb.StringProperty(required = True)
#     catalog_num = ndb.StringProperty(required = True)
#     class_num = ndb.IntegerProperty(required = True)
#     comp_sec = ndb.StringProperty(required = True)
#     camp_loc = ndb.StringProperty(required = True)
#     assoc_class = ndb.IntegerProperty(required = False)
#     rel1 = ndb.IntegerProperty(required = False)
#     rel2 = ndb.IntegerProperty(required = False)
#     enrol_cap = ndb.IntegerProperty(required = False)
#     enrol_tot = ndb.IntegerProperty(required = False)
#     wait_cap = ndb.IntegerProperty(required = False)
#     wait_tot = ndb.IntegerProperty(required = False)
#     time_date = ndb.TextProperty(required = False)
#     bldg_room = ndb.StringProperty(required = False)
#     instructor = ndb.StringProperty(required = False)
#     note = ndb.TextProperty(required = False, repeated = True)

# class Course(ndb.Model):
#     subject = ndb.StringProperty(required = True)
#     catalog_num = ndb.StringProperty(required = True)
#     units = ndb.FloatProperty(required = True)
#     title = ndb.StringProperty(required = True)
#     note = ndb.StringProperty(required = False)
#     #classes = ndb.StructuredProperty(Class, repeated = True)
#     created_time = ndb.DateTimeProperty(auto_now_add = True)
#     last_modified = ndb.DateTimeProperty(auto_now = True)

class DB_Alert(ndb.Model):
    level = ndb.StringProperty(required = True)
    sess = ndb.StringProperty(required = True)
    subject = ndb.StringProperty(required = True)
    catalog_num = ndb.StringProperty(required = True)
    class_num = ndb.StringProperty(required = True)
    enrol_cap = ndb.IntegerProperty(required = True)
    enrol_tot = ndb.IntegerProperty(required = True)
    email = ndb.StringProperty(required = False, repeated = True)
    created_time = ndb.DateTimeProperty(auto_now_add = True)
    last_modified = ndb.DateTimeProperty(auto_now = True)

    queried_time = ndb.IntegerProperty(required = True)

# data structures
class CClass_TBI:
    col6 = None
    enrol_cap = None
    enrol_tot = None
    time_date = None
    bldg_room = None
    instructor = None
    col10 = None
    def __init__(self, col6 = None, enrol_cap = None, enrol_tot = None, time_date = None, bldg_room = None, instructor = None,
                       col10 = None):
        self.col6 = col6
        self.enrol_cap = enrol_cap
        self.enrol_tot = enrol_tot
        self.time_date = time_date
        self.bldg_room = bldg_room
        self.instructor = instructor
        self.col10 = col10

class CClass:
    def __init__(self, id = None, subject = None, catalog_num = None, class_num = None, comp_sec = None, camp_loc = None,
                       assoc_class = None, rel1 = None, rel2 = None, enrol_cap = None, enrol_tot = None,
                       wait_cap = None, wait_tot = None, time_date = None, bldg_room = None, 
                       instructor = None, note = []):
        self.id = id,
        self.subject = subject
        self.catalog_num = catalog_num
        self.class_num = class_num
        self.comp_sec = comp_sec
        self.camp_loc = camp_loc
        self.assoc_class = assoc_class
        self.rel1 = rel1
        self.rel2 = rel2
        self.enrol_cap = enrol_cap
        self.enrol_tot = enrol_tot
        self.wait_cap = wait_cap
        self.wait_tot = wait_tot
        self.time_date = time_date
        self.bldg_room = bldg_room
        self.instructor = instructor
        self.note = note

Dic_CClass = OrderedDict()
def Dic_CClass_get_by_id(id):
    global Dic_CClass
    if id in Dic_CClass:
        return Dic_CClass[id]
    else:
        return None
def Dic_CClass_put(id, CClass_instance):
    global Dic_CClass
    Dic_CClass[id] = CClass_instance

class CCourse:
    def __init__(self, subject = None, catalog_num = None, units = None, title = None, note = None):
        self.subject = subject
        self.catalog_num = catalog_num
        self.units = units
        self.title = title
        self.note = note
        self.classes = []
        self.created_time = time.localtime()

Dic_CCourse = OrderedDict()
def Dic_CCourse_get_by_id(id):
    global Dic_CCourse
    if id in Dic_CCourse:
        return Dic_CCourse[id]
    else:
        return None
def Dic_CCourse_put(id, CCourse_instance):
    global Dic_CCourse
    Dic_CCourse[id] = CCourse_instance

class Alert:
    def __init__(self, level = None, sess = None, subject = None, catalog_num = None,
                       class_num = None, enrol_cap = None, enrol_tot = None,
                       email = []):
        self.level = level
        self.sess = sess
        self.subject = subject
        self.catalog_num = catalog_num
        self.class_num = class_num
        self.enrol_cap = enrol_cap
        self.enrol_tot = enrol_tot
        self.email = email

    def isAvailable(self):
        if self.enrol_tot < self.enrol_cap:
            return True
        else:
            return False
    def sendEmail(self):
        sender_address = "UW Course Enrolment Notifier<uw.course.enrolment.notifier@gmail.com>"
        subject = "UW-CEN: %(subject)s %(catalog_num)s %(class_num)s is available!" % {"subject" : self.subject, "catalog_num" : self.catalog_num, "class_num" : self.class_num}
        body = '''
            UW Course Enrolment Notifier:
            %(subject)s %(catalog_num)s 
            Class Number: %(class_num)s is now available!

            Go QUEST and add it Now!

            ----------------------
            UW Course Enrolment Notifier
            by Honghao Zhang
        ''' % {"subject" : self.subject, "catalog_num" : self.catalog_num, "class_num" : self.class_num}
        for email in self.email:
            mail.send_mail(sender_address, email, subject, body)

Dic_Alert = OrderedDict()
def Dic_Alert_get_by_id(id):
    global Dic_Alert
    if id in Dic_Alert:
        return Dic_Alert[id]
    else:
        return None
def Dic_Alert_put(id, Alert_instance):
    global Dic_Alert
    Dic_Alert[id] = Alert_instance

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

    ## used for make hash string in cookies
    SECRET = "I am a SECRET"
    def hash_str(self,s):
        return hmac.new(self.SECRET, s).hexdigest()

    def make_secure_val(self, s):
        return "%s|%s" % (s, self.hash_str(s))

    def check_secure_val(self, h):
        val = h.split('|')[0]
        if h == self.make_secure_val(val):
            return val

    def set_secure_cookie(self, name, val):
        cookie_val = self.make_secure_val(val)
        self.response.headers.add_header('Set-Cookie', '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        if cookie_val == None:
            return None
        else:
            return self.check_secure_val(cookie_val)

    ## login means set the cookie
    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    ## logout means clear the cookie
    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

# Handlers
class HomePage(ECEHandle):
    def get(self):
        apps = ndb.gql("SELECT * FROM Apps")
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

# global variables, used for communication between handlers
level_id = ""
level = ""
sess_id = None
sess = ""
subject = ""
query_url = "http://www.adm.uwaterloo.ca/cgi-bin/cgiwrap/infocour/salook.pl"

qtext = '[^\\x0d\\x22\\x5c\\x80-\\xff]'
dtext = '[^\\x0d\\x5b-\\x5d\\x80-\\xff]'
atom = '[^\\x00-\\x20\\x22\\x28\\x29\\x2c\\x2e\\x3a-\\x3c\\x3e\\x40\\x5b-\\x5d\\x7f-\\xff]+'
quoted_pair = '\\x5c[\\x00-\\x7f]'
domain_literal = "\\x5b(?:%s|%s)*\\x5d" % (dtext, quoted_pair)
quoted_string = "\\x22(?:%s|%s)*\\x22" % (qtext, quoted_pair)
domain_ref = atom
sub_domain = "(?:%s|%s)" % (domain_ref, domain_literal)
word = "(?:%s|%s)" % (atom, quoted_string)
domain = "%s(?:\\x2e%s)*" % (sub_domain, sub_domain)
local_part = "%s(?:\\x2e%s)*" % (word, word)
addr_spec = "%s\\x40%s" % (local_part, domain)
email_address = re.compile('\A%s\Z' % addr_spec)

def isValidEmailAddress(email):
    if email_address.match(email):
        return True
    else:
        return False

Alert_runing_switch = False

# global functions can be called in jinja2 templates
# produce true if the note of a class has col10 != None
def noteHasCol10(note):
    for item in note:
        if not item.col10 == None:
            return True
    return False
jinja_env.globals.update(noteHasCol10=noteHasCol10)

class CourseEnrolmentNotifier(ECEHandle):
    # data used for post get data
    level = ""
    sess = ""
    subject = ""
    cournum = ""
    # data used for read query page
    term_dic = {}
    sess_values = []
    subject_values = []

    def render_front_page(self, sess_values = "", term_dic = "", subject_values = ""):
        self.render('/course-enrol/cen-front.html', sess_values = sess_values, term_dic = term_dic, subject_values = subject_values)

    def render_error_page(self, errors = []):
        self.render('/course-enrol/cen-error.html', errors = errors)

    def render_result_course_page(self, Dic_CCourse):
        global level
        level = level
        global sess
        sess = sess
        global subject
        subject = subject
        self.render('/course-enrol/cen-result-course.html', level = level,
                                                            sess = sess,
                                                            subject = subject,
                                                            Dic_CCourse = Dic_CCourse)
    def render_result_class_page(self, course):
        global level
        level = level
        global sess
        sess = sess
        global subject
        subject = subject
        self.render('/course-enrol/cen-result-class.html', course = course,
                                                           level = level,
                                                           sess = sess,
                                                           subject = subject)

    def render_alert_page(self, theClass, course, error = ""):
        global level
        level = level
        global sess
        sess = sess
        global subject
        subject = subject
        self.render('/course-enrol/cen-alert.html', course = course,
                                                    theClass = theClass,
                                                    level = level,
                                                    sess = sess,
                                                    subject = subject,
                                                    error = error)
    def render_alert_showdict_page(self, dic_alert):
        self.render('/course-enrol/cen-alert-dict.html', dic_alert = dic_alert, Alert_runing_switch = Alert_runing_switch)

    def get(self):
        scheduleURL = "http://www.adm.uwaterloo.ca/infocour/CIR/SA/%s.html"
        graduateSampleURL = scheduleURL % "grad"
        if self.readQueryFrontPage(graduateSampleURL):
            self.render_front_page(self.sess_values, self.term_dic, self.subject_values)
        else:
            self.render_error_page(errors = ["Sorry...", "Query Page is not available,", "Please try again later!", "Thanks!"])

    def post(self):
        global query_url
        # produce query_object
        self.level = self.request.get('level')
        self.sess = self.request.get('sess')
        self.subject = self.request.get('subject')
        self.cournum = self.request.get('cournum')

        global level_id
        level_id = self.request.get('level')
        global sess_id
        sess_id = self.request.get('sess')

        if self.level == 'grad':
            global level
            level = 'Graduate'
        elif self.level == 'under':
            global level
            level = 'Undergraduate'
        global sess
        sess = str(self.term_dic[self.sess])
        global subject
        subject = str(self.subject)
        
        query_dic = {}
        query_dic['level'] = self.level
        query_dic['sess'] = self.sess
        query_dic['subject'] = self.subject
        query_dic['cournum'] = self.cournum
        query_obj = urllib.urlencode(query_dic)
        # read query result
        queryResult = self.readQueryResult(query_url, query_obj)
        if queryResult == True:
            self.render_result_course_page(Dic_CCourse)
        elif queryResult == 'NO RESULT':
            pass
        else:
            self.render_error_page(errors = ["Sorry...", "Query Response Time Out!", "Please try again later..."])

    def readQueryFrontPage(self, url):
        try:
            content = urllib2.urlopen(url).read()
        except urllib2.URLError:
            return False
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

    def readClasses(self, table, id, subject, catalog_num):
        class_num = None
        comp_sec = None
        camp_loc = None
        assoc_class = None
        rel1 = None
        rel2 = None
        enrol_cap = 0
        enrol_tot = 0
        wait_cap = 0
        wait_tot = 0
        time_date = None
        bldg_room = None
        instructor = None
        lenOfChildren = len(list(table.children))
        row = 0
        while row < lenOfChildren:
            # escape end line
            tr = table.contents[row]
            if tr == u'\n':
                row += 1
                continue
            elif len(list(tr.children)) == 27 and str(tr.get_text().strip().split()[0]) == 'Class':
                row += 1
                continue
            elif 9 < len(list(tr.children)) <= 13:
                if tr.contents[0].get_text().strip() == u'':
                    c = Dic_CClass_get_by_id(id + "-" + str(class_num))
                    # extra lines of additional information for previous class
                    # include: colspan = 6 : Reserve
                    #          colspan = 10 : Held With
                    #          colspan = 10 : Topic
                    # Store these kinds of information in note of CClass, in form of list of CClass_TBI
                    col6 = None
                    enrol_cap = None
                    enrol_tot = None
                    time_date = None
                    bldg_room = None
                    instructor = None
                    col10 = None

                    if not tr.contents[10].get_text().strip() == u'':
                        time_date = str('\n'.join(s.strip() for s in tr.contents[10].strings))

                    try:
                        if not tr.contents[11].get_text().strip() == u'':
                            bldg_room = str(tr.contents[11].string.strip())
                    except:
                        pass

                    try:
                        if not tr.contents[12].get_text().strip() == u'':
                            instructor = str(tr.contents[12].string.strip())
                    except:
                        pass
                    c.note.append(CClass_TBI(col6, enrol_cap, enrol_tot, time_date, bldg_room, instructor, col10))
                    row += 1
                    continue
                class_num = None
                comp_sec = None
                camp_loc = None
                assoc_class = None
                rel1 = None
                rel2 = None
                enrol_cap = 0
                enrol_tot = 0
                wait_cap = 0
                wait_tot = 0
                time_date = None
                bldg_room = None
                instructor = None
                try:
                    class_num = int(tr.contents[0].string.strip())
                except:
                    class_num = None
                try:
                    comp_sec = str(tr.contents[1].string.strip())
                except:
                    comp_sec = None
                try:
                    camp_loc = str(tr.contents[2].string.strip())
                except:
                    camp_loc = None
                try:
                    assoc_class = int(tr.contents[3].string.strip())
                except:
                    assoc_class = None
                try:
                    rel1 = int(tr.contents[4].string.strip())
                except:
                    rel1 = None
                try:
                    rel2 = int(tr.contents[5].string.strip())
                except:
                    rel2 = None
                try:
                    enrol_cap = int(tr.contents[6].string.strip())
                except:
                    enrol_cap = None
                try:
                    enrol_tot = int(tr.contents[7].string.strip())
                except:
                    enrol_tot = None
                try:
                    wait_cap = int(tr.contents[8].string.strip())
                except:
                    wait_cap = None
                try:
                    wait_tot = int(tr.contents[9].string.strip())
                except:
                    wait_tot = None
                try:
                    if not tr.contents[10].br == None:
                        time_date = str('\n'.join(s.strip() for s in tr.contents[10].strings))
                    else:
                        time_date = str(tr.contents[10].string.strip())
                except:
                    time_date = None
                try:
                    bldg_room = str(tr.contents[11].string.strip())
                except:
                    bldg_room = None
                try:
                    instructor = str(tr.contents[12].string.strip())
                except:
                    instructor = None
                newCClass = CClass(id + "-" + str(class_num),
                                   subject,
                                   catalog_num,
                                   class_num,
                                   comp_sec,
                                   camp_loc,
                                   assoc_class,
                                   rel1,
                                   rel2,
                                   enrol_cap,
                                   enrol_tot,
                                   wait_cap,
                                   wait_tot,
                                   time_date,
                                   bldg_room,
                                   instructor,
                                   [])
                Dic_CClass_put(id + "-" + str(class_num), newCClass)
                Dic_CCourse_get_by_id(id).classes.append(newCClass)
                row += 1
            # need revise
            elif len(list(tr.children)) < 9 and (not tr.i == None):
                c = Dic_CClass_get_by_id(id + "-" + str(class_num))
                col6 = None
                enrol_cap = None
                enrol_tot = None
                time_date = None
                bldg_room = None
                instructor = None
                col10 = None
                # colspan = 6, reserve line
                if tr.td['colspan'] == u'6':
                    col6 = str(tr.contents[0].string.strip())
                    enrol_cap = int(tr.contents[1].string.strip())
                    enrol_tot = int(tr.contents[2].string.strip())
                    try:
                        time_date = str('\n'.join(s.strip() for s in tr.contents[5].strings))
                    except:
                        pass
                    try:
                        bldg_room = str(tr.contents[6].string.strip())
                    except:
                        pass
                    try:
                        instructor = str(tr.contents[7].string.strip())
                    except:
                        pass
                    c.note.append(CClass_TBI(col6, enrol_cap, enrol_tot, time_date, bldg_room, instructor, col10))
                # colspan = 10, Held With and Topic lines
                elif tr.td['colspan'] == u'10':
                    col10 = str(tr.contents[0].string.strip())
                    c.note.append(CClass_TBI(col6, enrol_cap, enrol_tot, time_date, bldg_room, instructor, col10))
                else:
                    logging.error("colspan ERROR colspan ERROR colspan ERROR colspan ERROR colspan ERROR ")
                row += 1
            else:
                row += 1
                continue
        return True

    def readCourses(self, table):
        subject = None
        catalog_num = None
        units = None
        title = None
        note = None
        lenOfChildren = len(list(table.children))
        row = 0
        while row < lenOfChildren:
            # escape end line
            tr = table.contents[row]
            if tr == u'\n':
                row += 1
                continue
            # course head row
            elif len(list(tr.children)) == 8 and str(tr.get_text().strip().split()[0]) == str(self.subject):
                #clear old data
                subject = None
                catalog_num = None
                units = None
                title = None
                # set new data
                try:
                    subject = str(tr.contents[0].string.strip())
                except:
                    subject = None
                try:
                    catalog_num = str(tr.contents[2].string.strip())
                except:
                    catalog_num = None
                try:
                    units = float(tr.contents[4].string.strip())
                except:
                    units = None
                try:
                    title = str(tr.contents[6].string.strip())
                except:
                    title = None
                row += 1
            elif len(list(tr.children)) == 1 and (not tr.get_text().strip() == u'') and tr.get_text().strip().split()[0] == u'Notes:':
                note = None
                try:
                    note = str(tr.get_text().strip())
                except:
                    note = None
                row += 1
            elif len(list(tr.children)) == 2 and (not tr.table == None):
                if note:
                    Dic_CCourse_put(subject + "-" + str(catalog_num), CCourse(subject, catalog_num, units, title, note))
                else:
                    Dic_CCourse_put(subject + "-" + str(catalog_num), CCourse(subject, catalog_num, units, title))
                if self.readClasses(tr.table, subject + "-" + str(catalog_num), subject, catalog_num):
                    row += 1
                    continue
                else:
                    return False
            else:
                row += 1
                continue
        return True

    def readQueryResult(self, query_url, query_obj):
        try:
            query_result = urllib2.urlopen(query_url, query_obj).read()
        except urllib2.URLError:
            return 'URL ERROR'
        if query_result:
            Dic_CCourse.clear()
            Dic_CClass.clear()
            soup = BeautifulSoup(query_result)
            table = soup.table
            if table:
                if self.readCourses(table):
                    return True
                else:
                    return 'TABLE ERROR'
            else:
                self.render_error_page(errors = ["Sorry...", "Sorry, but your query has no matches."])
                return 'NO RESULT'
        else:
            return False

class CEN_class_page(CourseEnrolmentNotifier):
    def get(self, course_id):
        try:
            subject, catalog_num = course_id.split('-')
            theCourse = Dic_CCourse_get_by_id(subject + '-' + catalog_num)
            self.render_result_class_page(theCourse)
        except:
            self.error(404)
            self.render_error_page(errors = ["Sorry...", "404 NOT FOUND, this page is not found!"])

class CEN_alert(CourseEnrolmentNotifier):
    theCourse = None
    theClass = None
    def get(self, class_id):
        try:
            subject, catalog_num, class_num = class_id.split('-')
            self.theCourse = Dic_CCourse_get_by_id(subject + '-' + catalog_num)
            self.theClass = Dic_CClass_get_by_id(subject + '-' + catalog_num + '-' + class_num)
            self.render_alert_page(self.theClass, self.theCourse, "")
        except:
            self.error(404)
            self.render_error_page(errors = ["Sorry...", "404 NOT FOUND, this page is not found!"])

    def post(self, class_id):
        subject, catalog_num, class_num = class_id.split('-')
        self.theCourse = Dic_CCourse_get_by_id(subject + '-' + catalog_num)
        self.theClass = Dic_CClass_get_by_id(subject + '-' + catalog_num + '-' + class_num)

        email = self.request.get('email')
        if not isValidEmailAddress(email):
            self.render_alert_page(self.theClass, self.theCourse, "Email address is invalid!")
        else:
            global query_url
            global level_id
            global sess_id
            query_dic = {}
            query_dic['level'] = level_id
            query_dic['sess'] = sess_id
            query_dic['subject'] = subject
            query_dic['cournum'] = catalog_num
            query_obj = urllib.urlencode(query_dic)
            # read query result
            queryResult = self.readQueryResult_Alert(query_url, query_obj, level_id, sess_id, subject, catalog_num, class_num, email)
            if queryResult == True:
                logging.info("Add %(subject)s %(catalog_num)s : %(class_num)s [%(email)s] Successfully! Time: %(time)s" % {"subject" : subject, "catalog_num" : catalog_num, "class_num" : class_num, "email" : email, "time" : str(strftime("%Y-%m-%d %H:%M:%S", gmtime()))})
                self.redirect('/uw-cen/alert/show-dict')
            elif queryResult == 'NO RESULT':
                pass
            else:
                self.render_error_page(errors = ["Sorry...", "Query Response Time Out!", "Please try again later..."])

    def readQueryResult_Alert(self, query_url, query_obj, level_id, sess_id, subject, catalog_num, class_num, email):
        try:
            query_result = urllib2.urlopen(query_url, query_obj).read()
        except urllib2.URLError:
            return 'URL ERROR'
        if query_result:
            soup = BeautifulSoup(query_result)
            table = soup.table
            if table:
                if self.readCourses_Alert(table, level_id, sess_id, subject, catalog_num, class_num, email):
                    return True
                else:
                    return 'TABLE ERROR'
            else:
                return 'NO RESULT'
        else:
            return False

    def readCourses_Alert(self, table, level_id, sess_id, subject, catalog_num, class_num, email):
        lenOfChildren = len(list(table.children))
        row = 0
        while row < lenOfChildren:
            tr = table.contents[row]
            if tr == u'\n':
                row += 1
                continue
            elif len(list(tr.children)) == 2 and (not tr.table == None):
                if self.readClasses_Alert(tr.table, subject + "-" + str(catalog_num), level_id, sess_id, subject, catalog_num, class_num, email):
                    row += 1
                    continue
                else:
                    return False
            else:
                row += 1
                continue
        return True

    def readClasses_Alert(self, table, id, level_id, sess_id, subject, catalog_num, class_num, email):
        enrol_cap = None
        enrol_tot = None
        lenOfChildren = len(list(table.children))
        row = 0
        while row < lenOfChildren:
            tr = table.contents[row]
            if tr == u'\n':
                row += 1
                continue
            if 9 < len(list(tr.children)) <= 13 and int(class_num) == int(tr.contents[0].string.strip()):
                enrol_cap = 0
                enrol_tot = 0
                try:
                    enrol_cap = int(tr.contents[6].string.strip())
                except:
                    enrol_cap = None
                try:
                    enrol_tot = int(tr.contents[7].string.strip())
                except:
                    enrol_tot = None

                # add new Alert to Dic_Alert
                alreadyExistAlert = Dic_Alert_get_by_id(id + "-" + str(class_num))
                if alreadyExistAlert == None:
                    newAlert = Alert(level_id, 
                                 sess_id, 
                                 subject, 
                                 catalog_num, 
                                 class_num,
                                 enrol_cap, 
                                 enrol_tot,
                                 [email])
                    Dic_Alert_put(id + "-" + str(class_num), newAlert)
                else:
                    if not email in alreadyExistAlert.email:
                        alreadyExistAlert.enrol_cap = enrol_cap
                        alreadyExistAlert.enrol_tot = enrol_tot
                        alreadyExistAlert.email.append(email)
                    else:
                        self.render_alert_page(self.theClass, self.theCourse, "This Email address is already set for this class")
                        break


                # add new DB_Alert to Database
                alreadyExistDB_Alert = DB_Alert.query(DB_Alert.subject == subject, 
                                                      DB_Alert.catalog_num == catalog_num,
                                                      DB_Alert.class_num == class_num).order(-DB_Alert.queried_time).get()
                if alreadyExistDB_Alert == None:
                    queried_time = 1
                    DB_Alert(id = id + "-" + str(class_num) + "-" + str(queried_time),
                             level = level_id,
                             sess = sess_id,
                             subject = subject,
                             catalog_num = catalog_num,
                             class_num = class_num,
                             enrol_cap = enrol_cap,
                             enrol_tot = enrol_tot,
                             email = [email],
                             queried_time = queried_time).put()
                else:
                    new_email = copy.copy(alreadyExistDB_Alert.email)
                    if not email in new_email:
                        new_email.append(email)
                        new_queried_time = alreadyExistDB_Alert.queried_time + 1

                        DB_Alert(id = id + "-" + str(class_num) + "-" + str(new_queried_time),
                                 level = level_id,
                                 sess = sess_id,
                                 subject = subject,
                                 catalog_num = catalog_num,
                                 class_num = class_num,
                                 enrol_cap = enrol_cap,
                                 enrol_tot = enrol_tot,
                                 email = new_email,
                                 queried_time = new_queried_time).put()
                    else:
                        self.render_alert_page(self.theClass, self.theCourse, "This Email address is already set for this class")
                        break
                break
            else:
                row += 1
                continue
        return True
    def copy_db2dict(self):
        Dic_Alert.clear()
        ListOfDB_Alert = DB_Alert.query().order(DB_Alert.subject, DB_Alert.catalog_num, DB_Alert.class_num, -DB_Alert.queried_time)
        for alert in ListOfDB_Alert:
            alert_id = alert.key.id()
            searchId = alert_id[:alert_id.rfind("-")]
            if Dic_Alert_get_by_id(searchId) == None:
                newAlert = Alert(alert.level, 
                                 alert.sess, 
                                 alert.subject, 
                                 alert.catalog_num, 
                                 alert.class_num,
                                 alert.enrol_cap, 
                                 alert.enrol_tot,
                                 alert.email)
                Dic_Alert_put(searchId, newAlert)
            else:
                continue

class CEN_alert_run(CEN_alert):
    def get(self):
        global Alert_runing_switch
        if Alert_runing_switch:
            self.copy_db2dict()
            self.refreshDB()
            for id, alert in Dic_Alert.items():
                if alert.isAvailable():
                    logging.info(alert.subject + alert.catalog_num + ":"+ alert.class_num + " is available! Time: %s" % str(strftime("%Y-%m-%d %H:%M:%S", gmtime())))
                    alert.sendEmail()
                else:
                    logging.info(alert.subject + alert.catalog_num + ":"+ alert.class_num + " is not available! Time: %s" % str(strftime("%Y-%m-%d %H:%M:%S", gmtime())))

    def refreshDB(self):
        global query_url
        for id, alert in Dic_Alert.items():
            query_dic = {}
            query_dic['level'] = alert.level
            query_dic['sess'] = alert.sess
            query_dic['subject'] = alert.subject
            query_dic['cournum'] = alert.catalog_num
            query_obj = urllib.urlencode(query_dic)
            # read query result
            queryResult = self.readQueryResult_Refresh(query_url, query_obj, alert)
            if queryResult == True:
                logging.info("Refresh %(subject)s %(catalog_num)s : %(class_num)s Successfully! Time: %(time)s" % {"subject" : subject, "catalog_num" : catalog_num, "class_num" : class_num, "time" : str(strftime("%Y-%m-%d %H:%M:%S", gmtime()))})
            else:
                logging.info("Refresh %(subject)s %(catalog_num)s : %(class_num)s Failed! Time: %(time)s" % {"subject" : subject, "catalog_num" : catalog_num, "class_num" : class_num, "time" : str(strftime("%Y-%m-%d %H:%M:%S", gmtime()))})
    def readQueryResult_Refresh(self, query_url, query_obj, alert):
        try:
            query_result = urllib2.urlopen(query_url, query_obj).read()
        except urllib2.URLError:
            return 'URL ERROR'
        if query_result:
            soup = BeautifulSoup(query_result)
            table = soup.table
            if table:
                if self.readCourses_Refresh(table, alert):
                    return True
                else:
                    return 'TABLE ERROR'
            else:
                return 'NO RESULT'
        else:
            return False
    def readCourses_Refresh(self, table, alert):
        lenOfChildren = len(list(table.children))
        row = 0
        while row < lenOfChildren:
            tr = table.contents[row]
            if tr == u'\n':
                row += 1
                continue
            elif len(list(tr.children)) == 2 and (not tr.table == None):
                if self.readClasses_Refresh(tr.table, alert.subject + "-" + str(alert.catalog_num), alert):
                    row += 1
                    continue
                else:
                    return False
            else:
                row += 1
                continue
        return True

    def readClasses_Refresh(self, table, id, alert):
        enrol_cap = None
        enrol_tot = None
        lenOfChildren = len(list(table.children))
        row = 0
        while row < lenOfChildren:
            tr = table.contents[row]
            if tr == u'\n':
                row += 1
                continue
            if 9 < len(list(tr.children)) <= 13 and int(alert.class_num) == int(tr.contents[0].string.strip()):
                enrol_cap = 0
                enrol_tot = 0
                try:
                    enrol_cap = int(tr.contents[6].string.strip())
                except:
                    enrol_cap = None
                try:
                    enrol_tot = int(tr.contents[7].string.strip())
                except:
                    enrol_tot = None
                # refresh Dict_Alert
                alreadyExistAlert = Dic_Alert_get_by_id(id + "-" + str(alert.class_num))
                alreadyExistAlert.enrol_cap = enrol_cap
                alreadyExistAlert.enrol_tot = enrol_tot

                # refresh DB_Alert
                alreadyExistDB_Alert = DB_Alert.query(DB_Alert.subject == alert.subject, 
                                                      DB_Alert.catalog_num == alert.catalog_num,
                                                      DB_Alert.class_num == alert.class_num).order(-DB_Alert.queried_time).get()
                new_queried_time = alreadyExistDB_Alert.queried_time + 1
                DB_Alert(id = id + "-" + str(alert.class_num) + "-" + str(new_queried_time),
                                 level = alreadyExistDB_Alert.level,
                                 sess = alreadyExistDB_Alert.sess,
                                 subject = alreadyExistDB_Alert.subject,
                                 catalog_num = alreadyExistDB_Alert.catalog_num,
                                 class_num = alreadyExistDB_Alert.class_num,
                                 enrol_cap = enrol_cap,
                                 enrol_tot = enrol_tot,
                                 email = copy.copy(alreadyExistDB_Alert.email),
                                 queried_time = new_queried_time).put()
                break
            else:
                row += 1
                continue
        return True

class CEN_alert_showditc(CEN_alert):
    def get(self):
        self.render_alert_showdict_page(Dic_Alert)

class CEN_alert_copy_db2dict(CEN_alert):
    def get(self):
        self.copy_db2dict()
        self.redirect('/uw-cen/alert/show-dict')

class CEN_alert_on(CEN_alert):
    def get(self):
        global Alert_runing_switch
        Alert_runing_switch = True
        self.redirect('/uw-cen/alert/show-dict')

class CEN_alert_off(CEN_alert):
    def get(self):
        global Alert_runing_switch
        Alert_runing_switch = False
        self.redirect('/uw-cen/alert/show-dict')


class FlushCourseClass(ECEHandle):
    def render_error_page(self, errors = []):
        self.render('/course-enrol/cen-error.html', errors = errors)
    def get(self):
        # ndb.delete_multi(Course.query().fetch(keys_only=True))
        # ndb.delete_multi(Class.query().fetch(keys_only=True))
        self.render_error_page(errors = ["Course & Class Database are flushed successfully!"])

# python regex???? to solve it!!!!!!

courseID = r'([A-Z]+\-[a-zA-Z0-9]+)'
classID = r'([A-Z]+\-[a-zA-Z0-9]+\-[0-9]+)'
app = webapp2.WSGIApplication([
    ('/?', HomePage),
    ('/add-app', AddApp),
    ('/uw-cen/?', CourseEnrolmentNotifier),
    ('/uw-cen/' + courseID, CEN_class_page),
    ('/uw-cen/' + classID, CEN_alert),
    ('/uw-cen/alert/run', CEN_alert_run),
    ('/uw-cen/alert/show-dict', CEN_alert_showditc),
    ('/uw-cen/alert/copy-db2dict', CEN_alert_copy_db2dict),
    ('/uw-cen/alert/on', CEN_alert_on),
    ('/uw-cen/alert/off', CEN_alert_off),
    ('/uw-cen/flush', FlushCourseClass)
], debug=True)
