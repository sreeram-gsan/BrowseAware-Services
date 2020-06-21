from pymongo import MongoClient
import configparser

config = configparser.ConfigParser()
config.read('./config.ini')
database_config = config['DATABASE']

mongoclient = MongoClient(database_config['ADDRESS'],int(database_config['PORT']))
database = mongoclient.database_config['DB_NAME']
NUDGE_STATUS = database.nudge_status
CACHE = database.cache
HISTORY = database.history
EXTENSION_FEEDBACK = database.feedback_from_extension
NUDGE_FEEDBACK = database.nudge_feedback_cache
NUDGE_STATUS = database.nudge_status
USERS = database.users