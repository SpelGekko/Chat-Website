from waitress import serve
import main as main
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

serve(main.app, host='0.0.0.0', port=8080)