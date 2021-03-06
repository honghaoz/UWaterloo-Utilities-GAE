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

# Importations
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
from google.appengine.api import users

import datetime
import requests

# Global variables for jinja environment
template_dir = os.path.join(os.path.dirname(__file__), 'html_template')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape = True)

# Databases
# Database - Apps
#   used for store applications created for UW utilities
#   UW Utilities is meant for different apps in one place.
class Apps(ndb.Model):
    # name is the name of the app
    # link is the url link for this app
    # description is used to introduce this app, for what this app is used for
    name = ndb.StringProperty(required = True)
    link = ndb.StringProperty(required = True)
    description = ndb.TextProperty(required = True)
    created_time = ndb.DateTimeProperty(auto_now_add = True)
    last_modified = ndb.DateTimeProperty(auto_now = True)

# Deleted Class
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

# Database Term_Dic
#   This Database is used for store global dictionary: term_dic, 
#   which is store values and description of the term, 
#   for example: term_dic["1141"] == "Winter 2014"
class Term_Dic(ndb.Model):
    term_dic = ndb.JsonProperty(required = True)

# Database DB_Alert
#   This Database is main database, used for store class information of alerts
#   This Database is updated when uw-cen/Alert/run runs
#   When run once, this database is added with a new item just add 1 to queried_time and new informations
class DB_Alert(ndb.Model):
    # level is either 'under' or 'grad'
    level = ndb.StringProperty(required = True)
    # sess is '1141' - Winter 2014
    sess = ndb.StringProperty(required = True)
    # subject is 'ECE' ...
    subject = ndb.StringProperty(required = True)
    # catalog_num is 653 for exmaple
    catalog_num = ndb.StringProperty(required = True)
    # class_num
    class_num = ndb.StringProperty(required = True)
    enrol_cap = ndb.IntegerProperty(required = True)
    enrol_tot = ndb.IntegerProperty(required = True)
    # email is a list of email addresses, for example: ['abc@qq.com', '123@123.com']
    email = ndb.StringProperty(required = False, repeated = True)
    created_time = ndb.DateTimeProperty(auto_now_add = True)
    last_modified = ndb.DateTimeProperty(auto_now = True)

    # quried_time is the number of queried time, for exmaple, when ECE 653 4404 is updated for
    # the 4th time, then this property is 4
    queried_time = ndb.IntegerProperty(required = True)

    # user_email is a dic, like this formate: {'user name' : [['123@abc.com', 3], ['abc@123.com', 0]...}
    # user name (google email) is the key, value is list of list : [email_address, email_sent_times]
    user_email = ndb.JsonProperty(required = True)


# Database
#   used for setting google account black list, when user is set in black list,
#   then this user cannot use this app
class Email_BlackList(ndb.Model):
    email_black = ndb.StringProperty(required = True)
    redirect_link = ndb.TextProperty(required = True)

# Database
#   used for storing feedback informations
#   name email and feedback content
class FeedBack(ndb.Model):
    name = ndb.StringProperty(required = True)
    email = ndb.StringProperty(required = True)
    feedback = ndb.TextProperty(required = True)

# Global Data structures

# CClass_TBI is cluster of information stored in the note list of CClass
# includes:
#   Reserved(colspan = 6), 
#       with enrol_cap and enrol_tot
#   time_date, bldg_room, instructor
#   Held with(colspan = 10)

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

# CClass class is used to stroing class informations
# includes:
#   id, used for put and get, like operations of database
#   subject, catalog_num, ...
#   note is a list of CClass_TBI, two kinds: Reserved(colspan = 6), Held with(colspan = 10)
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

# List_Dic_CClass is a dict stroing CClass
# used for storing different users' query data
# for example, for this app only have one instance, if two different users query at the same time
# their query results will affect with each other. 
# use dict to separate different users' query
List_Dic_CClass = {} 
#Dic_CClass = OrderedDict()

# get_by_id, put and clear, used for storing query result of CClass to List_Dic_CClass, 
# need query_id (query sequence)
def Dic_CClass_get_by_id(query_id ,id):
    global List_Dic_CClass
    D_CClass = List_Dic_CClass[query_id]
    if id in D_CClass:
        return D_CClass[id]
    else:
        return None
def Dic_CClass_put(query_id, id, CClass_instance):
    global List_Dic_CClass
    if query_id in List_Dic_CClass:
        D_CClass =  List_Dic_CClass[query_id]
    else:
        D_CClass = OrderedDict()
        List_Dic_CClass[query_id] = D_CClass
    D_CClass[id] = CClass_instance
    
def Dic_CClass_clear(query_id):
    global List_Dic_CClass
    try:
        List_Dic_CClass[query_id].clear()
    except:
        pass

# class CCourse
# used for stroing queried course information, the classes is a list of CClass
class CCourse:
    def __init__(self, subject = None, catalog_num = None, units = None, title = None, note = None):
        self.subject = subject
        self.catalog_num = catalog_num
        self.units = units
        self.title = title
        self.note = note
        self.classes = []
        self.created_time = time.localtime()


List_Dic_CCourse = {} # used for storing different users' query data
#Dic_CCourse = OrderedDict()
def Dic_CCourse_get_by_id(query_id, id):
    global List_Dic_CCourse
    D_CCourse = List_Dic_CCourse[query_id]
    if id in D_CCourse:
        return D_CCourse[id]
    else:
        return None
def Dic_CCourse_put(query_id, id, CCourse_instance):
    global List_Dic_CCourse
    if query_id in List_Dic_CCourse:
        D_CCourse =  List_Dic_CCourse[query_id]
    else:
        D_CCourse = OrderedDict()
        List_Dic_CCourse[query_id] = D_CCourse
    D_CCourse[id] = CCourse_instance

def Dic_CCourse_clear(query_id):
    global List_Dic_CCourse
    try:
        List_Dic_CCourse[query_id].clear()
    except:
        pass

# class Alert is the class type of DB_Alerts, 
# if class Alert is empty, the app will copy data from DB_Alert to Alert.
# all of the alerts operations will use Alert's information
class Alert:
    max_send_time = 6
    def __init__(self, level = None, sess = None, subject = None, catalog_num = None,
                       class_num = None, enrol_cap = None, enrol_tot = None,
                       email = [], user_email = {}):
        self.level = level
        self.sess = sess
        self.subject = subject
        self.catalog_num = catalog_num
        self.class_num = class_num
        self.enrol_cap = enrol_cap
        self.enrol_tot = enrol_tot
        self.email = email

        # user_email is a dic, like this formate: {'user name' : [['123@abc.com', 3], ['abc@123.com', 0]...}
        # user name (google email) is the key, value is list of list : [email_address, email_sent_times]
        self.user_email = user_email

    # check if spots are available
    def isAvailable(self):
        if self.enrol_tot < self.enrol_cap:
            return True
        else:
            return False
    # when isAvailable == True, we will send notification emails to users
    def sendEmail(self):
        sender_address = "UWaterloo Course Notifier<uw.course.notifier@gmail.com>"
        email_subject = "UW-Courese Notifier: %(subject)s %(catalog_num)s %(class_num)s is available!" % {"subject" : self.subject, "catalog_num" : self.catalog_num, "class_num" : self.class_num}
        body = '''
            UWaterloo Course Notifier:
            %(subject)s %(catalog_num)s 
            Class Number: %(class_num)s is now available!
            Current Enrolment:  %(enrol_tot)s / %(enrol_cap)s (total / capacity)

            Go QUEST and add it Now!

            For not sending too many email notifications,
            You will receive %(send_time)s more email notifications, if you want to receive more, add this email address again.
            ----------------------
            UWaterloo Course Notifier
            by Honghao Zhang
        '''
               # Last query time: %(time)s
               # "time" : str(strftime("%Y-%m-%d %H:%M:%S", localtime()))

        # send email to users, email addresses is retrived from the list of email address (email)
        for email in self.email:
            logging.info(email)
            send_time = self.get_send_time(email)
            if send_time == None:
                logging.error("send_time Failed")
            else:
                send_time += 1
            logging.info(send_time)
            if send_time <= self.max_send_time:
                newbody = body % {"subject" : self.subject, 
                                  "catalog_num" : self.catalog_num, 
                                  "class_num" : self.class_num, 
                                  "enrol_tot" : self.enrol_tot, 
                                  "enrol_cap" : self.enrol_cap,
                                  'send_time' : 5 - send_time}
                mail.send_mail(sender_address, email, email_subject, newbody)
                logging.info("Send %(subject)s %(catalog_num)s : %(class_num)s (%(enrol_tot)s / %(enrol_cap)s) [%(email)s] Successfully! Send_time: %(send_time)s Time: %(time)s" % {"subject" : self.subject, "catalog_num" : self.catalog_num, "class_num" : self.class_num, "enrol_tot" : self.enrol_tot, "enrol_cap" : self.enrol_cap, "email" : email, "send_time" : send_time, "time" : str(strftime("%Y-%m-%d %H:%M:%S", gmtime()))})
            else:
                logging.info("Stop sending %(subject)s %(catalog_num)s : %(class_num)s (%(enrol_tot)s / %(enrol_cap)s) [%(email)s]! Tried_Send_time: %(send_time)s Time: %(time)s" % {"subject" : self.subject, "catalog_num" : self.catalog_num, "class_num" : self.class_num, "enrol_tot" : self.enrol_tot, "enrol_cap" : self.enrol_cap, "email" : email, "send_time" : send_time, "time" : str(strftime("%Y-%m-%d %H:%M:%S", gmtime()))})
                continue


        # add send times for each email address item
        # add for Alert
        for user, email_list in self.user_email.items():
            for email_sendtimes in email_list:
                email_sendtimes[1] += 1
        # add for DB_Alert
        alreadyExistDB_Alert = DB_Alert.query(DB_Alert.subject == self.subject, 
                                              DB_Alert.catalog_num == self.catalog_num,
                                              DB_Alert.class_num == self.class_num).order(-DB_Alert.queried_time).get()
        for user, email_list in alreadyExistDB_Alert.user_email.items():
            for email_sendtimes in email_list:
                email_sendtimes[1] += 1
        alreadyExistDB_Alert.put()

    def get_send_time(self, email_addr):
        for user, email_list in self.user_email.items():
            for email in email_list:
                logging.info(email)
                #logging.info(email_addr)
                if email[0] == email_addr:
                    return email[1]
        return None


# get_by_id and put for class Alert
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

    def set_secure_cookie(self, name, val, path):
        cookie_val = self.make_secure_val(val)
        # set expires data is 1 hour later
        expires_date = datetime.datetime.now() + datetime.timedelta(minutes = 20)
        expires = expires_date.strftime('%a, %d %b %Y %H:%M:%S GMT')
        self.response.headers.add_header('Set-Cookie', '%s=%s; Path=%s; expires=%s' % (name, cookie_val, path, expires))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        if cookie_val == None:
            return None
        else:
            return self.check_secure_val(cookie_val)

    ## login means set the cookie
    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()), "/")

    ## logout means clear the cookie
    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    # google user
    # process_user_area used for setting user_area, which is used in html template
    # return user's email address or 'public'
    user_area = ""
    def process_user_area(self):
        user = users.get_current_user()
        if user:
            self.user_area = ('''<div class="sub-login-area">
                                    <div class="user">
                                        <a href="https://www.google.com/settings/personalinfo?ref=home" class="logout-link" target="_blank">
                                        %s
                                        </a>
                                    </div>
                                    <div class="user-signout">(<a href="%s" class="logout-link">Sign out</a>)</div>
                                    <br>
                                    <div class="user">
                                        <a href="/uw-cen/user=%s" class="manage">
                                        Manage your Alerts
                                        </a>
                                    </div>
                                    <div class="user">
                                        <a href="/uw-cen/user=public" class="manage">
                                        Check Public Alerts
                                        </a>
                                    </div>
                                    <br>
                                    <div class="user">
                                        <a href="/uw-cen/feedback" class="manage">
                                        Give me a feedback
                                        </a>
                                    </div>
                                </div>''' %
                             (user.email(), users.create_logout_url(self.request.url), user.email()))
            return user.email()
        else:
            self.user_area = ('''<a href="%s" class="login-link"></a>
                                 <div class="sub-login-area">
                                 <div class="user">
                                    <div style="font-size: 11px;"><i>Log in to manage your alerts!</i></div>
                                 </div>
                                    <div class="user">
                                    <br>
                                    <a href="/uw-cen/user=public" class="manage">
                                        Check Public Alerts
                                    </a>
                                    </div>
                                 <br>
                                    <div class="user">
                                        <a href="/uw-cen/feedback" class="manage">
                                        Give me a feedback
                                        </a>
                                    </div>
                                 </div>''' %
                             users.create_login_url(self.request.url))
            return "public"
    def get_user_email(self):
        user = users.get_current_user()
        if user:
            return "<%s>" % user.email()
        else:
            return "<Not Login>"
    def is_in_black_list(self):
        current_email = self.get_user_email()[1:-1]
        logging.info(current_email)
        if not current_email == "<Not Login>":
            theBlack = Email_BlackList.query(Email_BlackList.email_black == current_email).get()
            if theBlack:
                self.redirect('https://www.google.ca/webhp?q=shabby')
                return True
            else:
                return False
        else:
            return False

# Handlers
class HomePage(ECEHandle):
    def get(self):
        if not self.is_in_black_list():
            # self.process_user_area()
            apps = ndb.gql("SELECT * FROM Apps ORDER BY created_time ASC")
            self.render('homepage.html', apps = apps)
# add app for UW Utilities
class AddApp(ECEHandle):
    referer = ""
    def render_page(self):
        #self.process_user_area()
        self.render('add-apps-form.html', referer = self.referer)
    def post(self):
        name = self.request.get('name')
        link = self.request.get('link')
        description = self.request.get('description')

        Apps(id = name, 
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

# add emails to black list
class AddBlack(ECEHandle):
    referer = ""
    def render_page(self):
        #self.process_user_area()
        self.render('add-black-form.html', referer = self.referer)
    def post(self):
        email_black = self.request.get('email_black')
        redirect_link = self.request.get("redirect_link")
        Email_BlackList(id = email_black, email_black = str(email_black), redirect_link = str(redirect_link)).put()
        self.redirect(str(self.referer))
    def get(self):
        # initialize referer, keep the origin referer
        if not self.request.referer == self.request.url:
            self.referer = self.request.referer
        else: 
            self.referer = self.referer
        self.render_page()

# global variables, used for communication between handlers
level_id = "" # under grad
level = ""  # Undergraduate  graduate
sess_id = None  # 1141
sess = ""   # Winter 2014
subject = ""    # ECE
query_url = "http://www.adm.uwaterloo.ca/cgi-bin/cgiwrap/infocour/salook.pl"

# email address validation
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

# alert switch, True in default
Alert_runing_switch = True

# global functions can be called in jinja2 templates
# produce true if the note of a class has col10 != None
def noteHasCol10(note):
    for item in note:
        if not item.col10 == None:
            return True
    return False
jinja_env.globals.update(noteHasCol10=noteHasCol10)

# Handler for UWaterloo Course Notifier
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

    #used for redirect to origin url
    referer = ""

    # used for separating different uses' query data
    def get_query_id_from_cookie(self):
        query_id = self.read_secure_cookie("query_id")
        if query_id == None:
            query_id = len(List_Dic_CCourse)
            self.set_secure_cookie("query_id", str(query_id) ,"/uw-cen")
        else:
            query_id = int(query_id)
        return query_id

    # render different pages
    def render_front_page(self, sess_values = "", term_dic = "", subject_values = ""):
        self.process_user_area()
        self.render('/course-enrol/cen-front.html', sess_values = sess_values, term_dic = term_dic, subject_values = subject_values, user_area = self.user_area)

    def render_error_page(self, errors = []):
        self.process_user_area()
        self.render('/course-enrol/cen-error.html', errors = errors, user_area = self.user_area)

    def render_result_course_page(self, Dic_CCourse):
        self.process_user_area()

        global level
        level = level
        global sess
        sess = sess
        global subject
        subject = subject
        self.render('/course-enrol/cen-result-course.html', level = level,
                                                            sess = sess,
                                                            subject = subject,
                                                            Dic_CCourse = Dic_CCourse,
                                                            user_area = self.user_area)
    def render_result_class_page(self, course):
        self.process_user_area()

        global level
        level = level
        global sess
        sess = sess
        global subject
        subject = subject
        self.render('/course-enrol/cen-result-class.html', course = course,
                                                           level = level,
                                                           sess = sess,
                                                           subject = subject,
                                                           user_area = self.user_area)

    def render_alert_page(self, theClass, course, email, tips = "", error = ""):
        user_email = self.process_user_area()

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
                                                    email = email,
                                                    tips = tips,
                                                    error = error,
                                                    user_email = user_email,
                                                    user_area = self.user_area)
    def render_alert_showdict_page(self, dic_alert):
        self.process_user_area()
        self.render('/course-enrol/cen-alert-dict.html', dic_alert = dic_alert, Alert_runing_switch = Alert_runing_switch, user_area = self.user_area)

    def render_user_manage_page(self, user_email, 
                                dic_alert, 
                                sure_to_delete = 0, 
                                email_to_be_deleted = "", 
                                subject_to_be_deleted = "",
                                catalog_num_to_be_deleted = "",
                                class_num_to_be_deleted = ""):
        current_user = self.process_user_area()
        login_link = users.create_login_url(self.request.url)
        isUser_email_exist = False
        for id, alert in dic_alert.items():
            if user_email in alert.user_email:
                isUser_email_exist = True
                break
            else:
                continue
        if user_email == "public":
            self.render('/course-enrol/cen-user-manage-public.html', user_email = user_email, 
                                                              isUser_email_exist = isUser_email_exist, 
                                                              dic_alert = dic_alert, 
                                                              user_area = self.user_area, 
                                                              login_link = login_link, 
                                                              current_user = current_user, 
                                                              term_dic = self.term_dic, 
                                                              sure_to_delete = sure_to_delete,
                                                              email_to_be_deleted = email_to_be_deleted,
                                                              subject_to_be_deleted = subject_to_be_deleted,
                                                              catalog_num_to_be_deleted = catalog_num_to_be_deleted,
                                                              class_num_to_be_deleted = class_num_to_be_deleted)
        else:
            self.render('/course-enrol/cen-user-manage.html', user_email = user_email, 
                                                              isUser_email_exist = isUser_email_exist, 
                                                              dic_alert = dic_alert, 
                                                              user_area = self.user_area, 
                                                              login_link = login_link, 
                                                              current_user = current_user, 
                                                              term_dic = self.term_dic, 
                                                              sure_to_delete = sure_to_delete,
                                                              email_to_be_deleted = email_to_be_deleted,
                                                              subject_to_be_deleted = subject_to_be_deleted,
                                                              catalog_num_to_be_deleted = catalog_num_to_be_deleted,
                                                              class_num_to_be_deleted = class_num_to_be_deleted)

    def render_feedback_page(self, name = "", name_error = "", email = "", email_error = "", feedback = "", feedback_error = "", referer = ""):
        user_email = self.process_user_area()
        self.render('/course-enrol/cen-feedback.html', name = name, name_error = name_error, email = user_email if (email == "" and not user_email == 'public') else email, email_error = email_error, feedback = feedback, feedback_error = feedback_error, referer = referer, user_email = user_email, user_area = self.user_area)
    def render_feedback_thanks_page(self, referer_url):
        self.render('/course-enrol/cen-feedback-thanks.html' , referer_url = referer_url, user_area = self.user_area)
    def get(self):
       if not self.is_in_black_list():
            # used for separate different users query result
            List_Dic_CCourse[time.time()] = None # used for add 1 to length of List_Dic_CCourse
            query_id = self.get_query_id_from_cookie()
            logging.info(self.get_user_email() + " Query sequence: " + str(query_id))
            scheduleURL = "http://www.adm.uwaterloo.ca/infocour/CIR/SA/%s.html"
            graduateSampleURL = scheduleURL % "grad"
            if self.readQueryFrontPage(graduateSampleURL):
                self.render_front_page(self.sess_values, self.term_dic, self.subject_values)
            else:
                self.render_error_page(errors = ["Sorry...", "Query Page is not available,", "Please try again later!", "Thanks!"])

    def post(self):
        # used for separate different users query result
        query_id = self.get_query_id_from_cookie()
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

        global level
        if self.level == 'grad':
            level = 'Graduate'
        elif self.level == 'under':
            level = 'Undergraduate'
        global sess
        # bug: because new instance always initial, it will clear term_dic
        # so, use database to initial self.term_dic if it is empty
        try:
            sess = str(self.term_dic[self.sess])
        except:
            self.term_dic = Term_Dic.get_by_id(1).term_dic;
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
        queryResult = self.readQueryResult(query_url, query_obj, query_id)
        if queryResult == True:
            global List_Dic_CCourse
            self.render_result_course_page(List_Dic_CCourse[query_id])
        elif queryResult == 'NO RESULT':
            pass
        else:
            self.render_error_page(errors = ["Sorry...", "Query Response Time Out!", "Please try again later..."])

    # read query list from the courese schedule front page
    # lis the options for querying
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
            new_Term_Dict = Term_Dic(id = 1, term_dic = {})
            new_Term_Dict.put()
            for term in term_list:
                term_id, term_descp = term.split("=")
                self.term_dic[term_id] = term_descp
                new_Term_Dict.term_dic[term_id] = term_descp
            new_Term_Dict.put()

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

    def readQueryResult(self, query_url, query_obj, query_id):
        try:
            query_result = urllib2.urlopen(query_url, query_obj).read()
        except urllib2.URLError:
            return 'URL ERROR'
        if query_result:
            Dic_CCourse_clear(query_id)
            Dic_CClass_clear(query_id)
            soup = BeautifulSoup(query_result)
            table = soup.table
            if table:
                if self.readCourses(table, query_id):
                    return True
                else:
                    return 'TABLE ERROR'
            else:
                self.render_error_page(errors = ["Sorry...", "Sorry, but your query has no matches."])
                return 'NO RESULT'
        else:
            return False

    def readCourses(self, table, query_id):
        subject = None
        catalog_num = 'NULL'
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
            elif len(list(tr.children)) == 7 and str(tr.get_text().strip().split()[0]) == str(self.subject):
                # #clear old data
                # subject = None
                # catalog_num = 'NULL'
                # units = None
                # title = None
                # # set new data
                # try:
                #     subject = str(tr.contents[0].string.strip())
                # except:
                #     subject = None
                # try:
                #     catalog_num = str(tr.contents[2].string.strip())
                #     if catalog_num == "":
                #         catalog_num = 'NULL'
                # except:
                #     catalog_num = 'NULL'
                # try:
                #     units = float(tr.contents[3].string.strip())
                # except:
                #     units = None
                # try:
                #     title = str(tr.contents[5].string.strip())
                # except:
                #     title = None

                #if catalog num == "", no need to read this entry!
                row += 6
                continue
            elif len(list(tr.children)) == 8 and str(tr.get_text().strip().split()[0]) == str(self.subject):
                #clear old data
                subject = None
                catalog_num = 'NULL'
                units = None
                title = None
                # set new data
                try:
                    subject = str(tr.contents[0].string.strip())
                except:
                    subject = None
                try:
                    catalog_num = str(tr.contents[2].string.strip())
                    if catalog_num == "":
                        catalog_num = 'NULL'
                except:
                    catalog_num = 'NULL'
                try:
                    units = float(tr.contents[4].string.strip())
                except:
                    units = None
                try:
                    title = str(tr.contents[6].string.strip())
                except:
                    title = None
                row += 1
                continue
            elif len(list(tr.children)) == 1 and (not tr.get_text().strip() == u'') and tr.get_text().strip().split()[0] == u'Notes:':
                note = None
                try:
                    note = str(tr.get_text().strip())
                except:
                    note = None
                row += 1
                continue
            elif len(list(tr.children)) == 2 and (not tr.table == None):
                if note:
                    Dic_CCourse_put(query_id, subject + "-" + str(catalog_num), CCourse(subject, catalog_num, units, title, note))
                else:
                    Dic_CCourse_put(query_id, subject + "-" + str(catalog_num), CCourse(subject, catalog_num, units, title))
                if self.readClasses(tr.table, subject + "-" + str(catalog_num), subject, catalog_num, query_id):
                    row += 1
                    continue
                else:
                    return False
            else:
                row += 1
                continue
        return True

    def readClasses(self, table, id, subject, catalog_num, query_id):
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
                    c = Dic_CClass_get_by_id(query_id, id + "-" + str(class_num))
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
                Dic_CClass_put(query_id, id + "-" + str(class_num), newCClass)
                Dic_CCourse_get_by_id(query_id, id).classes.append(newCClass)
                row += 1
            # need revise
            elif len(list(tr.children)) < 9 and (not tr.i == None):
                c = Dic_CClass_get_by_id(query_id, id + "-" + str(class_num))
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

class cenJson(CourseEnrolmentNotifier):
    def get(self):
        jsonDic = {}

        try:
            content = urllib2.urlopen("http://www.adm.uwaterloo.ca/infocour/CIR/SA/grad.html").read()
        except urllib2.URLError:
            logging.error("json error")
        if content:
            soup = BeautifulSoup(content)

            # sess
            sess = soup.find_all("select", {"name" : "sess"})
            sess = BeautifulSoup(str(sess[0]))
            # sess_selected = <option selected="" value="1141">1141 <option value="1145">1145 </option></option>
            sess_selected = BeautifulSoup(str(sess.find_all(selected=True)))
            sess_selected = sess_selected.option['value']
            jsonDic['current_term'] = sess_selected
            self.write(json.dumps(jsonDic))

# the class page for one course
class CEN_class_page(CourseEnrolmentNotifier):
    def get(self, course_id):
        # used for separate different users query result
        query_id = self.get_query_id_from_cookie()
        try:
            subject, catalog_num = course_id.split('-')
            theCourse = Dic_CCourse_get_by_id(query_id, subject + '-' + catalog_num)
            self.render_result_class_page(theCourse)
        except:
            self.error(404)
            self.render_error_page(errors = ["Sorry...", "404 NOT FOUND, this page is not found!"])

# the page for setting alerts when click "set an alert" on the class page
class CEN_alert(CourseEnrolmentNotifier):
    theCourse = None
    theClass = None
    def get(self, class_id):
        # used for separate different users query result
        query_id = self.get_query_id_from_cookie()
        try:
            subject, catalog_num, class_num = class_id.split('-')
            self.theCourse = Dic_CCourse_get_by_id(query_id, subject + '-' + catalog_num)
            self.theClass = Dic_CClass_get_by_id(query_id, subject + '-' + catalog_num + '-' + class_num)
            user = users.get_current_user()
            if user:
                self.render_alert_page(self.theClass, self.theCourse, user.email(), "*Login is recommonded, <br>otherwise, alert information will be visible to others and cannot manage your alerts!", "")
            else:
                self.render_alert_page(self.theClass, self.theCourse, "", "*Login is recommonded, <br>otherwise, alert information will be visible to others and cannot manage your alerts!", "")
        except:
            self.error(404)
            self.render_error_page(errors = ["Sorry...", "404 NOT FOUND, this page is not found!"])

    def post(self, class_id):
        # used for separate different users query result
        query_id = self.get_query_id_from_cookie()

        subject, catalog_num, class_num = class_id.split('-')
        self.theCourse = Dic_CCourse_get_by_id(query_id, subject + '-' + catalog_num)
        self.theClass = Dic_CClass_get_by_id(query_id, subject + '-' + catalog_num + '-' + class_num)

        email = self.request.get('email')
        logging.info("POST: Email: %s" % email)
        if not isValidEmailAddress(email):
            self.render_alert_page(self.theClass, self.theCourse, email, "*Login is recommonded, <br>otherwise, alert information will be visible to others and cannot manage your alerts!", "Email address is invalid!")
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
            # if Dic_Alert is empty, means new instance is running, copy db to dic_alert
            if not Dic_Alert:
                self.copy_db2dict()
            user_name = 'public'
            user = users.get_current_user()
            if user:
                user_name = user.email()
            queryResult = self.readQueryResult_Alert(query_url, query_obj, level_id, sess_id, subject, catalog_num, class_num, email, user_name)
            if queryResult == "EMAIL_EXISIT":
                self.render_alert_page(self.theClass, self.theCourse, email, "*Login is recommonded, <br>otherwise, alert information will be visible to others and cannot manage your alerts!", "This Email address is already set for this class")
            elif queryResult == True:
                sender_address = "UWaterloo Course Notifier <uw.course.notifier@gmail.com>"
                mail_subject = "Alert:%(subject)s %(catalog_num)s %(class_num)s is set successfully! UW-Course Notifier" % {"subject" : subject, "catalog_num" : catalog_num, "class_num" : class_num}
                mail_body = '''
                    UWaterloo Course Notifier:

                    Alert Information:
                    %(subject)s %(catalog_num)s 
                    Class Number: %(class_num)s

                    When spot is open, you will receive an email notification!
                    For not sending too many email notifications,
                    You will receive 5 email notifications.
                    ----------------------
                    UWaterloo Course Notifier
                    by Honghao Zhang
                ''' % {"subject" : subject, "catalog_num" : catalog_num, "class_num" : class_num}
                mail.send_mail(sender_address, email, mail_subject, mail_body)

                logging.info("Add %(subject)s %(catalog_num)s : %(class_num)s [%(email)s] Successfully! Time: %(time)s" % {"subject" : subject, "catalog_num" : catalog_num, "class_num" : class_num, "email" : email, "time" : str(strftime("%Y-%m-%d %H:%M:%S", gmtime()))})
                self.redirect('/uw-cen/user=%s' % user_name)
            elif queryResult == 'NO RESULT':
                pass
            else:
                self.render_error_page(errors = ["Sorry...", "Query Response Time Out!", "Please try again later..."])

    def readQueryResult_Alert(self, query_url, query_obj, level_id, sess_id, subject, catalog_num, class_num, email, user_name):
        try:
            query_result = urllib2.urlopen(query_url, query_obj).read()
        except urllib2.URLError:
            return 'URL ERROR'
        if query_result:
            soup = BeautifulSoup(query_result)
            table = soup.table
            if table:
                readCourse_result = self.readCourses_Alert(table, level_id, sess_id, subject, catalog_num, class_num, email, user_name)
                if readCourse_result == "EMAIL_EXISIT":
                    return "EMAIL_EXISIT"
                elif readCourse_result == True:
                    return True
                else:
                    return 'TABLE ERROR'
            else:
                return 'NO RESULT'
        else:
            return False

    def readCourses_Alert(self, table, level_id, sess_id, subject, catalog_num, class_num, email, user_name):
        lenOfChildren = len(list(table.children))
        row = 0
        while row < lenOfChildren:
            tr = table.contents[row]
            if tr == u'\n':
                row += 1
                continue
            elif len(list(tr.children)) == 2 and (not tr.table == None):
                logging.info("Run read class")
                readClass_result = self.readClasses_Alert(tr.table, subject + "-" + str(catalog_num), level_id, sess_id, subject, catalog_num, class_num, email, user_name)
                logging.info("End read class")
                if readClass_result == "EMAIL_EXISIT":
                    return "EMAIL_EXISIT"
                elif readClass_result == True:
                    # Fix!!!
                    return True
                    row += 1
                    continue
                else:
                    return False
            else:
                row += 1
                continue
        return True

    def readClasses_Alert(self, table, id, level_id, sess_id, subject, catalog_num, class_num, email, user_name):
        enrol_cap = None
        enrol_tot = None
        lenOfChildren = len(list(table.children))
        row = 0
        while row < lenOfChildren:
            tr = table.contents[row]
            if tr == u'\n':
                row += 1
                continue
            logging.info("len: %d", len(list(tr.children)))
            logging.info("Class number: %d", int(class_num))
            logging.info("Compared: %s\n", tr.contents[0].string.strip())
            # Match class number, only run once
            if 9 < len(list(tr.children)) <= 13 and int(class_num) == int(tr.contents[0].string.strip()):
                logging.info("Enter!!!!")
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

                # logging.info("add new Alert to Dic_Alert!!!!")

                # add new Alert to Dic_Alert
                alreadyExistAlert = Dic_Alert_get_by_id(id + "-" + str(class_num))
                # if there is no any alert
                if alreadyExistAlert == None:
                    newAlert = Alert(level_id, 
                                 sess_id, 
                                 subject, 
                                 catalog_num, 
                                 class_num,
                                 enrol_cap, 
                                 enrol_tot,
                                 [email],
                                 {user_name : [[email, 0]]})
                    Dic_Alert_put(id + "-" + str(class_num), newAlert)
                else:
                    # email to be added is not added before
                    if not email in alreadyExistAlert.email:
                        alreadyExistAlert.enrol_cap = enrol_cap
                        alreadyExistAlert.enrol_tot = enrol_tot
                        alreadyExistAlert.email.append(email)
                        if user_name in alreadyExistAlert.user_email:
                            old_user_email = alreadyExistAlert.user_email[user_name]
                            old_user_email.append([email, 0])
                        else:
                            alreadyExistAlert.user_email[user_name] = [[email, 0]]
                    else:
                        # email to be added is added before, reset the send_time
                        alreadyExistAlert.enrol_cap = enrol_cap
                        alreadyExistAlert.enrol_tot = enrol_tot
                        if user_name in alreadyExistAlert.user_email:
                            old_user_email = alreadyExistAlert.user_email[user_name]
                            for each_email in old_user_email:
                                if each_email[0] == email:
                                    each_email[1] = 0
                                    break
                        else:
                            logging.error("email exist, but user not exist??")
                        #return "EMAIL_EXISIT"
                        #break

                # logging.info("add new DB_Alert to Database!!!!")

                # add new DB_Alert to Database
                alreadyExistDB_Alert = DB_Alert.query(DB_Alert.subject == subject, 
                                                      DB_Alert.catalog_num == catalog_num,
                                                      DB_Alert.class_num == class_num).order(-DB_Alert.queried_time).get()
                if alreadyExistDB_Alert == None:
                    queried_time = 1
                    #id = id + "-" + str(class_num)  + "-" + str(queried_time),
                    DB_Alert(id = id + "-" + str(class_num),
                             level = level_id,
                             sess = sess_id,
                             subject = subject,
                             catalog_num = catalog_num,
                             class_num = class_num,
                             enrol_cap = enrol_cap,
                             enrol_tot = enrol_tot,
                             email = [email],
                             user_email = {user_name : [[email, 0]]},
                             queried_time = queried_time).put()
                else:
                    # new_email = copy.copy(alreadyExistDB_Alert.email)
                    # if not email in new_email:
                    #     new_email.append(email)
                    #     new_queried_time = alreadyExistDB_Alert.queried_time# + 1
                    #     new_user_email = copy.copy(alreadyExistDB_Alert.user_email) #{u'zhh358': [[u'1@1.com', 0]]}
                    #     if user_name in new_user_email:
                    #         # user already exist
                    #         # get the old email list of this user
                    #         new_user_email_list = new_user_email[user_name]
                    #         # make the new email list
                    #         new_user_email_list.append([email, 0])
                    #         # change the dict, let the value of this user is new email list
                    #         new_user_email[user_name] = new_user_email_list
                    #     else:
                    #         # user dosen't exist
                    #         # simply add new key to dict
                    #         new_user_email[user_name] = [[email, 0]]

                    #     DB_Alert(id = id + "-" + str(class_num) + "-" + str(new_queried_time),
                    #              level = level_id,
                    #              sess = sess_id,
                    #              subject = subject,
                    #              catalog_num = catalog_num,
                    #              class_num = class_num,
                    #              enrol_cap = enrol_cap,
                    #              enrol_tot = enrol_tot,
                    #              email = new_email,
                    #              # let new dict to user_email
                    #              user_email = new_user_email,
                    #              queried_time = new_queried_time).put()
                    # else:
                    #     return "EMAIL_EXISIT"
                    #     break

                    #new_email = copy.copy(alreadyExistDB_Alert.email)
                    if not email in alreadyExistDB_Alert.email:
                        alreadyExistDB_Alert.enrol_cap = enrol_cap
                        alreadyExistDB_Alert.enrol_tot = enrol_tot
                        alreadyExistDB_Alert.email.append(email)
                        alreadyExistDB_Alert.queried_time + 1
                        #new_user_email = copy.copy(alreadyExistDB_Alert.user_email) #{u'zhh358': [[u'1@1.com', 0]]}
                        if user_name in alreadyExistDB_Alert.user_email:
                            # user already exist
                            # get the old email list of this user
                            #new_user_email_list = new_user_email[user_name]
                            alreadyExistDB_Alert.user_email[user_name].append([email, 0])
                            # make the new email list
                            #new_user_email_list.append([email, 0])
                            # change the dict, let the value of this user is new email list
                            #new_user_email[user_name] = new_user_email_list
                        else:
                            # user dosen't exist
                            # simply add new key to dict
                            alreadyExistDB_Alert.user_email[user_name] = [[email, 0]]
                        alreadyExistDB_Alert.put()

                        # DB_Alert(id = id + "-" + str(class_num) + "-" + str(new_queried_time),
                        #          level = level_id,
                        #          sess = sess_id,
                        #          subject = subject,
                        #          catalog_num = catalog_num,
                        #          class_num = class_num,
                        #          enrol_cap = enrol_cap,
                        #          enrol_tot = enrol_tot,
                        #          email = new_email,
                        #          # let new dict to user_email
                        #          user_email = new_user_email,
                        #          queried_time = new_queried_time).put()
                    else:
                        alreadyExistDB_Alert.enrol_cap = enrol_cap
                        alreadyExistDB_Alert.enrol_tot = enrol_tot
                        if user_name in alreadyExistDB_Alert.user_email:
                            old_user_email = alreadyExistDB_Alert.user_email[user_name]
                            for each_email in old_user_email:
                                if each_email[0] == email:
                                    each_email[1] = 0
                                    break
                        else:
                            logging.error("email exist, but user not exist??")
                        alreadyExistDB_Alert.put()
                        # return "EMAIL_EXISIT"
                        # break
                logging.info("Return!!!!")
                return True
                logging.info("Break!!!!")
                break
            else:
                row += 1
                continue
        return True
    def copy_db2dict(self):
        Dic_Alert.clear()
        ListOfDB_Alert = DB_Alert.query().order(DB_Alert.subject, DB_Alert.catalog_num, DB_Alert.class_num, -DB_Alert.queried_time)
        if not ListOfDB_Alert == None:
            logging.info("copy!!!")
            for alert in ListOfDB_Alert:
                alert_id = alert.key.id() #ECE-628-4400-5
                searchId = ""
                if alert_id.count("-") == 3:
                    searchId = alert_id[:alert_id.rfind("-")] #ECE-628-4400
                else:
                    searchId = alert_id
                logging.info(searchId)
                if Dic_Alert_get_by_id(searchId) == None:
                    newAlert = Alert(alert.level, 
                                     alert.sess, 
                                     alert.subject, 
                                     alert.catalog_num, 
                                     alert.class_num,
                                     alert.enrol_cap, 
                                     alert.enrol_tot,
                                     alert.email,
                                     alert.user_email)
                    Dic_Alert_put(searchId, newAlert)
                else:
                    continue
        else:
            logging.info("shabi bu copy!!!")


# used for run scheduled query
class CEN_alert_run(CEN_alert):
    def get(self):
        global Alert_runing_switch
        if Alert_runing_switch:
            if not Dic_Alert:
                self.copy_db2dict()
            self.refreshDB()
            for id, alert in Dic_Alert.items():
                if alert.isAvailable():
                    logging.info(alert.subject + alert.catalog_num + ":"+ alert.class_num + " is available!!! Time: %s" % str(strftime("%Y-%m-%d %H:%M:%S", gmtime())))
                    alert.sendEmail()
                else:
                    logging.info(alert.subject + alert.catalog_num + ":"+ alert.class_num + " is not available... Time: %s" % str(strftime("%Y-%m-%d %H:%M:%S", gmtime())))

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
                logging.info("Refresh %(subject)s %(catalog_num)s : %(class_num)s Successfully! Time: %(time)s" % {"subject" : alert.subject, "catalog_num" : alert.catalog_num, "class_num" : alert.class_num, "time" : str(strftime("%Y-%m-%d %H:%M:%S", gmtime()))})
            else:
                logging.info("Refresh %(subject)s %(catalog_num)s : %(class_num)s Failed! Time: %(time)s" % {"subject" : alert.subject, "catalog_num" : alert.catalog_num, "class_num" : alert.class_num, "time" : str(strftime("%Y-%m-%d %H:%M:%S", gmtime()))})
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
                    return True
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

                #logging.info("id " + id + "-" + str(alert.class_num))
                alreadyExistAlert.enrol_cap = enrol_cap
                alreadyExistAlert.enrol_tot = enrol_tot

                # refresh DB_Alert
                alreadyExistDB_Alert = DB_Alert.query(DB_Alert.subject == alert.subject, 
                                                      DB_Alert.catalog_num == alert.catalog_num,
                                                      DB_Alert.class_num == alert.class_num).order(-DB_Alert.queried_time).get()
                if not alreadyExistDB_Alert == None:
                    alreadyExistDB_Alert.queried_time += 1
                    alreadyExistDB_Alert.enrol_cap = enrol_cap
                    alreadyExistDB_Alert.enrol_tot = enrol_tot
                    alreadyExistDB_Alert.put()
                    # new_queried_time = alreadyExistDB_Alert.queried_time + 1
                    # DB_Alert(id = id + "-" + str(alert.class_num) + "-" + str(new_queried_time),
                    #                  level = alreadyExistDB_Alert.level,
                    #                  sess = alreadyExistDB_Alert.sess,
                    #                  subject = alreadyExistDB_Alert.subject,
                    #                  catalog_num = alreadyExistDB_Alert.catalog_num,
                    #                  class_num = alreadyExistDB_Alert.class_num,
                    #                  enrol_cap = enrol_cap,
                    #                  enrol_tot = enrol_tot,
                    #                  email = copy.copy(alreadyExistDB_Alert.email),
                    #                  user_email = copy.copy(alreadyExistDB_Alert.user_email),
                    #                  queried_time = new_queried_time).put()
                else:
                    logging.error("Query Failed!!!!")
                    return False
                return True
                break
            else:
                row += 1
                continue
        return True

class CEN_alert_manage(CEN_alert):
    def get(self, email):
        self.render_user_manage_page(user_email = email, dic_alert = Dic_Alert, sure_to_delete = 0)

class CEN_alert_manage_delete(CEN_alert):
    def get(self, current_user, class_id, email_to_be_deleted, sure_to_delete):
        subject, catalog_num, class_num = class_id.split('-')
        if sure_to_delete == "0":
            self.render_user_manage_page(user_email = current_user, 
                                         dic_alert = Dic_Alert, 
                                         sure_to_delete = "1",
                                         email_to_be_deleted = email_to_be_deleted,
                                         subject_to_be_deleted = subject,
                                         catalog_num_to_be_deleted = catalog_num,
                                         class_num_to_be_deleted = class_num)
        elif sure_to_delete == "1":
            # delete email in Dic_Alert
            alert = Dic_Alert_get_by_id(str(subject) + "-" + str(catalog_num) + "-" + str(class_num))
            # alert.email.remove(email_to_be_deleted)
            # for email_sendtimes in alert.user_email[current_user]:
            #     if current_user == email_sendtimes[0]:
            #         alert.user_email[current_user].remove(email_sendtimes)
            #         if alert.user_email[current_user] == []:
            #             del alert.user_email[current_user]

            # delete email in DB_Alert
            alreadyExistDB_Alert = DB_Alert.query(DB_Alert.subject == alert.subject, 
                                                  DB_Alert.catalog_num == alert.catalog_num,
                                                  DB_Alert.class_num == alert.class_num).order(-DB_Alert.queried_time).get()
            alreadyExistDB_Alert.email.remove(email_to_be_deleted)
            for email_sendtimes in alreadyExistDB_Alert.user_email[current_user]:
                if current_user == email_sendtimes[0]:
                    alreadyExistDB_Alert.user_email[current_user].remove(email_sendtimes)
                    if alreadyExistDB_Alert.user_email[current_user] == []:
                        del alreadyExistDB_Alert.user_email[current_user]
            alreadyExistDB_Alert.put()
            self.copy_db2dict()
            self.redirect("/uw-cen/user=%s" % current_user)

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

class CEN_feedback(CEN_alert):
    def get(self):
        # initialize referer, keep the origin referer
        if not self.request.referer == self.request.url:
            self.referer = self.request.referer
        else: 
            self.referer = self.referer
        self.render_feedback_page(feedback = "Please give me some suggestions!", referer = self.referer)
    def post(self):
        pass
        name = self.request.get('name')
        email = self.request.get('email')
        feedback = self.request.get('feedback')
        referer_url = self.request.get('referer')

        name_error = ""
        email_error = ""
        feedback_error = ""

        if name == "":
            name_error = "Name cannot be empty"
        if not (email == "" or isValidEmailAddress(email)):
            email_error = "Email address is invalid!"
        if feedback == "":
            feedback_error = "Please leave at least one word..."

        if not (name_error == "" and email_error == "" and feedback_error == ""):
            self.render_feedback_page(name = name,
                                      name_error = name_error, 
                                      email = email,
                                      email_error = email_error, 
                                      feedback = feedback,
                                      feedback_error = feedback_error,
                                      referer = referer_url)
        else:
            FeedBack(name = name, email = email, feedback = feedback).put()
            self.render_feedback_thanks_page(referer_url)

class FlushCourseClass(ECEHandle):
    def render_error_page(self, errors = []):
        self.render('/course-enrol/cen-error.html', errors = errors)
    def get(self):
        # ndb.delete_multi(Course.query().fetch(keys_only=True))
        # ndb.delete_multi(Class.query().fetch(keys_only=True))
        ndb.delete_multi(DB_Alert.query().fetch(keys_only=True))
        self.render_error_page(errors = ["DB_Alert Database are flushed successfully!"])

# python regex???? to solve it!!!!!!

class cenCourseJson(CourseEnrolmentNotifier):
    def get(self, term, courseID, class_num, email):
        subject = courseID.split('-')[0]
        catalog_num = courseID.split('-')[1]
        #self.write(term + subject + catalog_num + class_num + email)
        if int(catalog_num[0]) < 6:
            level = 'under'
        else:
            level = 'grad'
        query_dic = {}
        query_dic['level'] = level
        query_dic['sess'] = term
        query_dic['subject'] = subject
        query_dic['cournum'] = catalog_num

        targetURL = "http://uw.honghaoz.com/uw-cen"

        expires_date = datetime.datetime.now() + datetime.timedelta(minutes = 20)
        expires = expires_date.strftime('%a, %d %b %Y %H:%M:%S GMT')
        cookies = dict(query_id=self.make_secure_val("136"), Path="/uw-cen", expire=expires)

        #simulate query 
        #GET front page
        requests.get(url = targetURL, cookies = cookies)
        #POST front page
        requests.post(url= targetURL, data= query_dic, cookies = cookies)
        #POST to alert page
        requests.post(url= targetURL + "/" + subject + "-" + catalog_num + "-" + class_num, data = {'email' : email}, cookies = cookies)
        response = {"response" : "successfully"}
        self.write(json.dumps(response));
        

courseID = r'([A-Z]+\-[a-zA-Z0-9]+)'
classID = r'([A-Z]+\-[a-zA-Z0-9]+\-[0-9]+)'
class_num = r'([0-9]+)'
EMAIL = r'([\w-]+@[\w-]+\.+[\w-]+)'

app = webapp2.WSGIApplication([
    ('/?', HomePage),
    ('/add-app', AddApp),
    ('/add-black', AddBlack),
    ('/uw-cen/?', CourseEnrolmentNotifier),
    ('/uw-cen.json', cenJson),
    ('/uw-cen/([0-9]{4})-%s-%s-%s.json' % (courseID, class_num, EMAIL), cenCourseJson),
    ('/uw-cen/' + courseID, CEN_class_page),
    ('/uw-cen/' + classID, CEN_alert),
    ('/uw-cen/feedback', CEN_feedback),

    ('/uw-cen/user=([a-z]{6})/%s/%s/([0-1])' % (classID, EMAIL), CEN_alert_manage_delete),
    ('/uw-cen/user=%s/%s/%s/([0-1])' % (EMAIL, classID, EMAIL), CEN_alert_manage_delete),
    ('/uw-cen/user=([a-z]{6})', CEN_alert_manage),
    ('/uw-cen/user=%s' % EMAIL, CEN_alert_manage),
    ('/uw-cen/alert/run', CEN_alert_run),
    ('/uw-cen/alert/show-dict', CEN_alert_showditc),
    ('/uw-cen/alert/copy-db2dict', CEN_alert_copy_db2dict),
    ('/uw-cen/alert/on', CEN_alert_on),
    ('/uw-cen/alert/off', CEN_alert_off),
    ('/uw-cen/flush', FlushCourseClass)
], debug=True)
