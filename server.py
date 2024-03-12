# to run in windows using waitress
# run "pip install waitress" then "python server.py" in terminal

from waitress import serve
from bom.wsgi import application

if __name__ == "__main__":
    serve(application, port="8000")
