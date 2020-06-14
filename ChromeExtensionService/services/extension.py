from flask import Flask,session
from pymongo import MongoClient
from datetime import datetime
import logging
import configparser

app = Flask(__name__)

#loding configuration
config = configparser.ConfigParser()
config.read('./config.ini')
service_config = config['SERVICE']
logging_config = config['LOGGING']
database_config = config['DATABASE']
other_config = config['OTHER']

#database
mongoclient = MongoClient(database_config['ADDRESS'],int(database_config['PORT']))
database = mongoclient.database_config['DB_NAME']
NUDGE_STATUS = database.nudge_status
CACHE = database.cache
HISTORY = database.history
EXTENSION_FEEDBACK = database.feedback_from_extension
NUDGE_FEEDBACK = database.nudge_feedback_cache
NUDGE_STATUS = db.nudge_status

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
    logging.debig(url_queue)

    if (len(list(url_queue)) >= 50):
        del url_queue[0]
        del categ_queue[0]
        
    url_queue.append(url)
    categ_queue.append(category)    

    url_cache.update({'username': username},
    {'$set': {
                'url_queue': url_queue
            }
    }, upsert=False)

    url_cache.update({'username': username},
    {'$set': {
                'categ_queue': category_queue
            }
    }, upsert=False)


def get_category(url,url_queue,category_queue):
    logging.info ("Enter get_category")

    for i in range(0,len(list(url_queue))):        
        if (url_queue[i] == url):
            return category_queue[i]
    return "Not Present"

def record_user_feedback(feedback):
    logging.info("Enter record_user_feedback")

    try:
        un = session['username_session']
    except KeyError:        
        un = None

    if (un!=None):

        now = datetime.datetime.now()
        this_date = str(now.year)+"-"+str(now.month)+"-"+str(now.day);
        this_time = str(now.hour)+"-"+str(now.minute)+"-"+str(now.second);

        try:
            data = {
                    "id" : session['username_session'],
                    "status":feedback,
                    "date": this_date,
                    "time": this_time
            }
        except KeyError:
            data = {
                    "id" : 'Unknown',
                    "status":"Diverted",
                    "date": this_date,
                    "time": this_time
            }
        
        EXTENSION_FEEDBACK.insert(data)        
        return "User feedback has been recorded"
    else:        
        return "User has not logged in"
    
def record_nudge_feedback(nudge_feedback):

    try:
        un = session['username_session']
    except KeyError:
        un = None

    if (un != None):

        user_current_session = CACHE.find_one({'username' : str(un)})['session']
        data = {}
        data['username'] = un
        data['session'] = user_current_session
        data['feedback'] = nudge_feedback        
        NUDGE_FEEDBACK.insert(data)        
        return "User feedback has been recorded"

    else:
        return "User has not logged in"

def reset_nudge_status(username,session):

    last_below_threshold_json = NUDGE_STATUS.find_one({'username':username , 'session' : session },{'last_below_threshold':1,'below_threshold':1,"_id":0})
        
    if (last_below_threshold_json != None):
        last_below_threshold = last_below_threshold_json['last_below_threshold'] + last_below_threshold_json['below_threshold']
    else:
        last_below_threshold = 0

    NUDGE_STATUS.update(
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
def status():
    logging.info("Enter status")
    return service_config['NAME'] + " is up!"


@app.route('/extension/sessionNumber',methods=['GET'])
def session_number():
    logging.info("Enter session_number")    
    try:
        return str(CACHE.find_one({"username" : session['username_session']},{"session":1,"_id":0})['session'])
    except KeyError:        
        return "Not Logged In"

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
        url_cache_data = db.url_cache.find_one({"username" : un })
        url_queue = url_cache_data['url_queue']
        category_queue = url_cache_data['categ_queue']

        #4. fetching session,month,day,hour,minute of a user
        temp = []
        url_cache = CACHE.find_one({"username": un})        
        temp.append(int(url_cache['session']))
        temp.append(int(url_cache['month']))
        temp.append(int(url_cache['day']))
        temp.append(int(url_cache['hour']))
        temp.append(int(url_cache['minute']))

        #5. Starting a new session if expired
        last_active_datetime = url_cache['last_active_datetime']
        session_duration = (datetime.now()-last_active_datetime).total_seconds() / 60.0 
        if (session_duration >= SESSION_TIMEOUT_AT):
            db.cache.update({'username': un},
            {'$set': {
                        'session': temp[0] + 1,
                        'session_start_time' : datetime.now()
                    }
            }, upsert=False)

            temp[0] += 1

        logging.debug("Value of temp: ")
        logging.debug(temp)
        
        #6. Updating the Server cache with the current date and time
        db.cache.update({'username': un},
        {'$set': {
                    'month': now.month,
                    'day': now.day,
                    'hour': now.hour,
                    'minute': now.minute,
                    'last_active_datetime':datetime.now()
                }
        }, upsert=False)

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
                    "date": this_date,
                    "time": this_time,
                    "session": temp_cache[0],
                    "category": category
            }
        except KeyError:
            post = {"id" : 'Unknown',
                    "url": url,
                    "date": this_date,
                    "time": this_time,
                    "session": temp_cache[0],
                    "category":category
            }

        HISTORY.insert(post)
        logging.debug("URL Category: " + category)        
        logging.debug("success")
        return "Success"
    else:        
        logging.debug("User has not logged in")        

    return "Success"


@app.route("/extension/feedback/<user_feedback>")
def feedback(user_feedback):
    return record_user_feedback(request.view_args['user_feedback'])
    
@app.route("/extension/nudgeFeedback/<nudge_feedback>")
def feedback(user_feedback):
    return record_nudge_feedback(request.view_args['nudge_feedback'])

#Nudging part of the extension
@app.route('/extension/get_nudge_status')
def get_nudge_status():

    try:
        un = session['username_session']
        if (un != None):      
            user_cache = CACHE.find_one({"session": { "$gt": 0 },"username":str(session['username_session'])})        
            session_start_time = user_cache["session_start_time"]
            session_duration = (datetime.now() - session_start_time).total_seconds() / 60.0 #Session duration in minutes
            logging.debug("Session Duration: " + str(session_duration))

            if ( session_duration >= MINIMUM_TIME_TO_NUDGE):
                current_session = user_cache["session"]
                nudge_status_result = NUDGE_STATUS.find_one({ "username" : str(session['username_session']),"session":current_session})        

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

if __name__ == '__main__':    
    app.run('0.0.0.0',5000,debug = True)