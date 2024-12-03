#Deriving the latest base image
FROM python:latest


#Labels as key value pair
LABEL Maintainer="Ryan Parsons"


# Any working directory can be chosen as per choice like '/' or '/home' etc
# i have chosen /usr/app/src
WORKDIR /

#to COPY the remote file at working directory in container
COPY import_events.py ./
# Now the structure looks like this '/import_events.py'

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt

COPY . .

#CMD instruction should be used to run the software
#contained by your image, along with any arguments.

CMD [ "python", "import_events.py"]