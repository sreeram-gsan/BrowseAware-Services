import pymongo

class Database(object):    
    URI = "mongodb://127.0.0.1:27017"
    DATABASE = None

    @staticmethod
    def initialize():
        client = pymongo.MongoClient(Database.URI)
        Database.DATABASE = client['washi']

    @staticmethod
    def insert(collection,data):        
        Database.DATABASE[collection].insert(data)

    @staticmethod
    def find(collection,data):
        return Database.DATABASE[collection].find(data)

    @staticmethod
    def find_one(collection,data):        
        return Database.DATABASE[collection].find_one(data)
    
    @staticmethod
    def update(collection,filter_condition,data):
        return Database.DATABASE[collection].update(filter_condition,data)
