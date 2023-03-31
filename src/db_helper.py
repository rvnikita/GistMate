import os
import configparser
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.orm import Session

config = configparser.SafeConfigParser(os.environ)
config_path = os.path.dirname(__file__) + '/../config/' #we need this trick to get path to config folder
config.read(config_path + 'settings.ini')


Base = declarative_base()

#connect to postgresql
engine = create_engine(f"postgresql://{config['DB']['USER']}:{config['DB']['PASSWORD']}@{config['DB']['HOST']}:{config['DB']['PORT']}/{config['DB']['NAME']}")

session = Session(engine)