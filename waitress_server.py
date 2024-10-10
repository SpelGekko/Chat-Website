from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
import main as main
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

server = pywsgi.WSGIServer(('0.0.0.0', 80), main.app, handler_class=WebSocketHandler)
server.serve_forever()