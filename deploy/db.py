from datetime import datetime
from sqlalchemy import create_engine, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String
from sqlalchemy.orm import sessionmaker


def get_engine(path):
    engine = create_engine('sqlite:////%s' % path, echo=True)
    session = sessionmaker(bind=engine)
    return (engine, session)


Base = declarative_base()


class DbContainer(Base):
    __tablename__ = 'images'

    container_id = Column(String, primary_key=True)
    image = Column(String)
    config = Column(String)
    created = Column(DateTime)

    def __init__(self,*args,**kwargs):
        self.created = datetime.now()
        super().__init__(*args,**kwargs)

    def __repr__(self):
        return "<Container(id'%s', image='%s' created=%r)>" % (
            self.container_id, self.image, self.created)