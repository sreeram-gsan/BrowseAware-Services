from flask import Flask,session,request,jsonify
from pymongo import MongoClient
from datetime import datetime
from flask_login import LoginManager,login_user, logout_user, login_required
import logging
import configparser

from common.user import User
from common.loginform import LoginForm
from common.database import Database


app = Flask(__name__)
#loding configurations
config = configparser.ConfigParser()
config.read('./config.ini')
service_config = config['SERVICE']
logging_config = config['LOGGING']
database_config = config['DATABASE']
other_config = config['OTHER']
nudge_config = config['NUDGING']

#login manager
app.secret_key = other_config['SECRET_KEY']
login_manager = LoginManager()
login_manager.init_app(app)

#Category map
CATEGORY_MAP = {
    'search' : ['google.com'],
    'social' : ['twitter','facebook','instagram','linkedin'],
    'work' : ['gmail.com','zimbra','oracle','opower','opera','symphony','elsevier','ieee','overleaf','sharelatex','teams','sciencedirect']
}

#methods
def enqueue_url(url,category,url_queue,category_queue,url_cache,username):    
    logging.info ("Enter enqueue_url")
    logging.debug("URL_QUEUE: ")
    logging.debug(url_queue)
    
    if (len(list(url_queue)) >= 50):
        del url_queue[0]
        del category_queue[0]
        
    url_queue.append(url)
    category_queue.append(category)    

    Database.update("url_cache",{'username': username}, {'$set': {'url_queue': url_queue}})
    Database.update("url_cache",{'username': username}, {'$set': {'categ_queue': category_queue}})
    
def get_category(url,url_queue,category_queue):
    logging.info ("Enter get_category")

    for i in range(0,len(list(url_queue))):        
        if (url_queue[i] == url):
            return category_queue[i]
    return "Not Present"

def record_user_feedback(feedback):
    logging.info("Enter record_user_feedback")

    try:
        un = session['username']
    except KeyError:        
        un = None

    if (un!=None):

        now = datetime.datetime.now()
        current_date = str(now.year)+"-"+str(now.month)+"-"+str(now.day);
        current_time = str(now.hour)+"-"+str(now.minute)+"-"+str(now.second);

        try:
            data = {
                    "id" : session['username_session'],
                    "status":feedback,
                    "date": current_date,
                    "time": current_time
            }
        except KeyError:
            data = {
                    "id" : 'Unknown',
                    "status":"Diverted",
                    "date": current_date,
                    "time": current_time
            }
                
        Database.insert("fedback_from_extension",data)  
        return "User feedback has been recorded"
    else:        
        return "User has not logged in"
    
def record_nudge_feedback(nudge_feedback):

    try:
        un = session['username']
    except KeyError:
        un = None

    if (un != None):
        user_current_session = Database.find_one("cache",{'username' : str(un)})['session']        
        data = {}
        data['username'] = un
        data['session'] = user_current_session
        data['feedback'] = nudge_feedback        
        Database.insert("nudge_feedback_cache",data)        
        return "User feedback has been recorded"

    else:
        return "User has not logged in"

def reset_nudge_status(username,session):

    last_below_threshold_json = Database.find_one("nudge_status",{'username':username , 'session' : session },{'last_below_threshold':1,'below_threshold':1,"_id":0})
        
    if (last_below_threshold_json != None):
        last_below_threshold = last_below_threshold_json['last_below_threshold'] + last_below_threshold_json['below_threshold']
    else:
        last_below_threshold = 0

    Database.update("nudge_status",
        { 'username' : username, 'session' : session },
        { 
            "$set": 
            { 
                'below_threshold' : 0,
                'last_below_threshold':last_below_threshold
            },
            "$inc":
            {
                'nudges_pushed' : 1
            }
        }
        )

#Endpoints

@app.route('/extension/health', methods=['GET'])
def health():
    logging.info("Enter status")
    return service_config['NAME'] + " is up!"

@app.route('/extension/loginstatus')
def loginstatus():
    try:
        return "Logged In As  " + session['username']
    except KeyError:
        return "Please Login"


@app.route('/extension/login', methods=['POST'])
def login():
    logging.info("Enter login")
    form = LoginForm()
    if request.method == 'POST':
        user = Database.find_one(
            'users', {"_id": request.form['username'].replace(" ", "").lower()})
        if user and User.validate_login(user['password'], request.form['password'].lower()):
            user_obj = User(user['_id'])
            login_user(user_obj)
            response = jsonify(message="success")
            response.set_cookie('username', user_obj.get_id())
            session['username'] = user_obj.get_id()
            session.permanent = True
            logging.debug("Login successful")
            return response

        logging.debug("username or password is incorrect")
        return "username or password is incorrect"


@login_required
@app.route('/extension/logout', methods=['GET'])
def logout():
    logging.info("Enter logout")
    logout_user()
    return jsonify(message="success")


@login_required
@app.route('/extension/sessionNumber',methods=['GET'])
def session_number():
    logging.info("Enter session_number")    
    try:
        return str(Database.find_one("cache",{"username" : session['username']},{"session":1,"_id":0})['session'])
    except KeyError:        
        return "Please Login"

@login_required
@app.route("/extension/push_url",methods=['POST'])
def push_url():
    logging.info("Enter push_url")   
    try:
        un = session['username_session']
    except KeyError:        
        un = None
        logging.debug("User hasn't logged in")

    if (request.method == 'POST' and un!=None):

        #1. Get Incoming URL
        url = request.form['url']        
        logging.debug("URL TO PUSH: ")
        logging.debug(url)
        
        #2. Excluding a certain input URLs
        urls_to_exclude = other_config['URLS_TO_EXCLUDE']
        for i in urls_to_exclude:            
            if url in i:
                logging.debug("Incoming URL is excluded")
                return 'success'
                
        now = datetime.now()
        current_date = str(now.year)+"-"+str(now.month)+"-"+str(now.day);
        current_time = str(now.hour)+"-"+str(now.minute)+"-"+str(now.second);

        #3. Fetching the category of the incoming URL if present in the cache
        url_cache_data = Database.find_one("url_cache",{"username" : un })
        url_queue = url_cache_data['url_queue']
        category_queue = url_cache_data['categ_queue']

        #4. fetching session,month,day,hour,minute of a user
        temp = []
        url_cache = Database.find("cache",{"username": un})        
        temp.append(int(url_cache['session']))
        temp.append(int(url_cache['month']))
        temp.append(int(url_cache['day']))
        temp.append(int(url_cache['hour']))
        temp.append(int(url_cache['minute']))

        #5. Starting a new session if expired
        last_active_datetime = url_cache['last_active_datetime']
        session_duration = (datetime.now()-last_active_datetime).total_seconds() / 60.0 
        if (session_duration >= other_config['SESSION_TIMEOUT_AT']):
            Database.update("cache",{'username': un},
            {'$set': {
                        'session': temp[0] + 1,
                        'session_start_time' : datetime.now()
                    }
            })

            temp[0] += 1

        logging.debug("Value of temp: ")
        logging.debug(temp)
        
        #6. Updating the Server cache with the current date and time
        Database.update("cache",{'username': un},
        {'$set': {
                    'month': now.month,
                    'day': now.day,
                    'hour': now.hour,
                    'minute': now.minute,
                    'last_active_datetime':datetime.now()
                }
        })

        category = 'Error'
        for key in len(CATEGORY_MAP):
            for i in CATEGORY_MAP[key]:
                if (i in url):
                    category = key


        if (get_category(url,url_queue,category_queue) == "Not Present"):
            category = get_category(url)
            enqueue_url(url,category,url_queue,category_queue,url_cache,un)

        try:
            post = {"id" : session['username_session'],
                    "url": url,
                    "date": current_date,
                    "time": current_time,
                    "session": temp[0],
                    "category": category
            }
        except KeyError:
            post = {"id" : 'Unknown',
                    "url": url,
                    "date": current_date,
                    "time": current_time,
                    "session": temp[0],
                    "category":category
            }

        Database.insert("history",post)
        logging.debug("URL Category: " + category)        
        logging.debug("success")
        return "Success"
    else:        
        logging.debug("User has not logged in")        

    return "Success"


@login_required
@app.route("/extension/feedback/<user_feedback>")
def user_feedback(user_feedback):
    logging.info("Enter user_feedback")   
    return record_user_feedback(request.view_args['user_feedback'])
    
@login_required
@app.route("/extension/nudgeFeedback/<nudge_feedback>")
def nudge_feedback(user_feedback):
    logging.info("Enter nudge_feedback")   
    return record_nudge_feedback(request.view_args['nudge_feedback'])

#Nudging part of the extension
@login_required
@app.route('/extension/get_nudge_status')
def get_nudge_status():
    logging.info("Enter get_nudge_status")   
    try:
        un = session['username_session']
        if (un != None):      
            user_cache = Database.find_one("cache",{"session": { "$gt": 0 },"username":str(session['username_session'])})        
            session_start_time = user_cache["session_start_time"]
            session_duration = (datetime.now() - session_start_time).total_seconds() / 60.0 #Session duration in minutes
            logging.debug("Session Duration: " + str(session_duration))

            if ( session_duration >= nudge_config['MINIMUM_TIME_TO_NUDGE']):
                current_session = user_cache["session"]
                nudge_status_result = Database.find_one("nudge_status",{ "username" : str(session['username_session']),"session":current_session})        

                if (nudge_status_result != None and nudge_status_result["below_threshold"] > 0):
                    reset_nudge_status(un,current_session)
                    return str(nudge_status_result["below_threshold"])
                else:
                    return "The Users doesn't have a nudge status"
            else:
                logging.debug("Session time is less than MINIMUM_TIME_TO_NUDGE")
                return "Session time is less than MINIMUM_TIME_TO_NUDGE"

        else:
            return "User has not logged in"
    
    except KeyError:
        un = None
        logging.debug("Key Error in get_nudge_status")
        return "Key Error in get_nudge_status"

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

if __name__ == '__main__':    
    logging.basicConfig(filename="extension.log",level=logging.DEBUG,filemode="w")
    logging.info("Service " + service_config['NAME'] + " start")
    Database.initialize()
    app.run('0.0.0.0',5000,debug = True)